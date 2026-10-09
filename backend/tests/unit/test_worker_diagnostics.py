"""Evidence must survive symbol, process and planning-attempt boundaries."""
import pickle
from datetime import datetime, timezone
from types import SimpleNamespace as S

import pytest

from backend.engine import orchestrator as module
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.tests.unit.test_cascade_no_direction_flip import _bare_orchestrator


@pytest.fixture
def worker_call(monkeypatch):
    monkeypatch.setattr(module, '_WORKER_ORCHESTRATOR', None)
    monkeypatch.setattr(module, '_WORKER_CONFIG_ID', None)
    config = ScanConfig(profile=get_mode('stealth').profile)
    def run(symbol, run_id='first'):
        return module._parallel_process_symbol_worker((
            symbol, run_id, datetime.now(timezone.utc), None, config,
            None, None, get_mode('stealth'), .01, .001))
    return run


def test_worker_diagnostics_are_detached_and_reset_for_symbols_and_runs(worker_call, monkeypatch):
    calls = []
    def process(engine, symbol, run_id, *args, **kwargs):
        calls.append(engine)
        if symbol == 'BTC/USDT':
            engine.diagnostics['indicator_failures'].append({'timeframe': '5m', 'error': run_id})
        return None, {'symbol': symbol, 'reason_type': 'test_decline'}
    monkeypatch.setattr(module.Orchestrator, '_process_symbol', process)
    snapshots = []
    for run_id in ['first', 'second']:
        for symbol in ['BTC/USDT', 'ETH/USDT']:
            plan, rejection, diagnostics = worker_call(symbol, run_id)
            assert plan is None and rejection['symbol'] == symbol
            expected = [{'symbol': symbol, 'timeframe': '5m', 'error': run_id}] if symbol == 'BTC/USDT' else []
            assert diagnostics['indicator_failures'] == expected
            assert pickle.loads(pickle.dumps(diagnostics)) == diagnostics
            snapshots.append(diagnostics)
    assert all(engine is calls[0] for engine in calls)
    assert snapshots[0]['indicator_failures'][0]['error'] == 'first'
    calls[0].diagnostics['indicator_failures'].append({'error': 'later mutation'})
    assert snapshots[-1]['indicator_failures'] == []


def test_worker_error_keeps_partial_diagnostics(worker_call, monkeypatch):
    def fail(engine, *args, **kwargs):
        engine.diagnostics['smc_rejections'].append({'timeframe': '1h', 'error': 'partial failure'})
        raise ValueError('worker crashed after SMC')
    monkeypatch.setattr(module.Orchestrator, '_process_symbol', fail)
    plan, rejection, diagnostics = worker_call('ETH/USDT')
    assert plan is None and rejection['reason_type'] == 'errors'
    assert 'worker crashed after SMC' in rejection['reason']
    assert 'ValueError' in rejection['error_details']
    assert diagnostics['smc_rejections'] == [{'symbol': 'ETH/USDT', 'timeframe': '1h', 'error': 'partial failure'}]


def test_worker_startup_error_does_not_export_previous_symbol(worker_call, monkeypatch):
    module._WORKER_ORCHESTRATOR = S(diagnostics={'smc_rejections': [{'symbol': 'OLD'}]})
    monkeypatch.setattr(module.Orchestrator, '__init__', lambda *a, **k: (_ for _ in ()).throw(ValueError('startup failed')))
    plan, rejection, diagnostics = worker_call('ETH/USDT')
    assert plan is None and 'startup failed' in rejection['reason']
    assert all(not records for records in diagnostics.values())


def test_rejection_telemetry_false_result_remains_retryable():
    engine = object.__new__(module.Orchestrator)
    outcomes = iter([False, True])
    calls = []
    engine.telemetry = S(log_event=lambda event: (calls.append(event), next(outcomes))[1])
    rejection = {'symbol': 'BTC/USDT', 'reason_type': 'no_trade_plan', 'reason': 'entry declined', 'direction': 'SHORT',
                 'diagnostics': {'reason_code': 'entry_depth', 'detail': {'timeframe': '15m'}}}
    engine._emit_rejection_telemetry('run', rejection)
    assert not rejection.get('__telemeterized')
    engine._emit_rejection_telemetry('run', rejection)
    engine._emit_rejection_telemetry('run', rejection)
    assert rejection['__telemeterized'] is True and len(calls) == 2
    assert calls[0].data['diagnostics'] == calls[1].data['diagnostics']
    assert calls[1].data['diagnostics']['reason_code'] == 'entry_depth'
    assert calls[1].data['diagnostics']['direction'] == 'SHORT'


@pytest.mark.parametrize('accepted', [False, True])
def test_worker_diagnostics_heartbeat_excludes_feature_occurrences(accepted):
    from backend.engine import cycle_heartbeat
    engine = object.__new__(module.Orchestrator)
    engine.config = S(scan_interval_seconds=60.)
    engine.scanner_mode = S(name='stealth')
    engine.current_regime = None
    summary = {'run_id': 'heartbeat-evidence', 'total_rejected': int(not accepted),
               'by_reason': {'features': 2, 'errors': int(not accepted)}}
    engine.scan = lambda *args: ([S()] if accepted else [], summary)
    cycle_heartbeat.clear()
    try:
        plans, result = engine.scan_with_heartbeat(['BTC/USDT'])
        heartbeat = cycle_heartbeat.get_latest()
        assert result is summary and heartbeat is not None
        assert 'features' not in heartbeat['signals_per_stage']
        assert heartbeat['bottleneck_stage'] == (None if accepted else 'errors')
        assert len(plans) + sum(heartbeat['signals_per_stage'].values()) == 1
        assert summary['by_reason']['features'] == 2
    finally:
        cycle_heartbeat.clear()


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
def test_risk_reason_does_not_leak_after_sizing_failure_or_success(direction):
    engine = object.__new__(module.Orchestrator)
    engine.config = S(max_risk_pct=1.)
    plan = S(symbol='BTC/USDT', direction=direction, entry_zone=S(near_entry=100.), stop_loss=S(level=99.))
    engine.position_sizer = S(calculate_fixed_fractional=lambda **k: S(notional_value=10., risk_amount=1.))
    engine.risk_manager = S(validate_new_trade=lambda **k: S(passed=False, reason='previous limit', limits_hit=[]))
    assert engine._validate_risk(plan) is False
    engine.position_sizer.calculate_fixed_fractional = lambda **k: (_ for _ in ()).throw(ValueError('invalid sizing input'))
    assert engine._validate_risk(plan) is False
    assert engine._last_risk_failure == 'Position sizing failed: invalid sizing input'
    engine.position_sizer.calculate_fixed_fractional = lambda **k: S(notional_value=10., risk_amount=1.)
    engine.risk_manager.validate_new_trade = lambda **k: S(passed=True)
    assert engine._validate_risk(plan) is True
    assert engine._last_risk_failure is None


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('final_pass', [False, True])
def test_cascade_attempt_reasons_are_isolated(direction, final_pass):
    engine = _bare_orchestrator()
    context = S(symbol='BTC/USDT', macro_context=None, smc_snapshot=None,
                metadata={'chosen_direction': direction, 'plan_failure_reason': 'stale'})
    seen = []
    winner = S(direction=direction, confidence_score=80., trade_type='scalp', metadata={})
    def generate(ctx, price, **kwargs):
        seen.append(dict(ctx.metadata))
        if len(seen) == 1:
            ctx.metadata['plan_failure_reason'] = 'first scale decline'
            ctx.metadata['plan_failure_gate'] = 'post_plan_revalidation'
            ctx.metadata['plan_failure_diagnostics'] = {'drift_pct': .5}
            return None
        return winner if final_pass else None
    engine._generate_trade_plan = generate
    result = engine._cascade_plan_generation(context, 100., ('intraday', 'scalp'))
    assert all('plan_failure_reason' not in metadata for metadata in seen)
    attempts = context.metadata['cascade_attempts']
    assert attempts[0]['reason'] == 'first scale decline'
    assert attempts[0]['gate'] == 'post_plan_revalidation'
    assert attempts[0]['diagnostics'] == {'drift_pct': .5}
    assert all('plan_failure_gate' not in metadata and 'plan_failure_diagnostics' not in metadata for metadata in seen)
    assert context.metadata['chosen_direction'] == direction
    if final_pass:
        assert result is winner
        assert 'plan_failure_reason' not in context.metadata
    else:
        assert result is None
        assert attempts[1]['reason'] == 'Planner returned no plan'
        assert 'first scale decline' in context.metadata['plan_failure_reason']
