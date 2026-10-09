"""Fault injection with real candle ingestion and serial/pickled worker transport."""
from datetime import datetime, timezone

import pytest

from backend.engine import orchestrator as module
from backend.bot.telemetry.logger import TelemetryLogger
from backend.services.indicator_service import IndicatorService
from backend.services.smc_service import SMCDetectionService
from backend.tests.integration.test_core_workflow import core_factory


def configured_core(core_factory, direction='LONG'):
    core = core_factory(mirror=direction == 'SHORT', impulse=.012 if direction == 'LONG' else .01,
                        as_of=datetime(2025, 12, 3, 15, tzinfo=timezone.utc))
    # Retain the original candle tapes. Resolve the supported aggressive preset
    # to reach downstream fault injection; no detector result or gate is replaced.
    from types import SimpleNamespace
    from backend.shared.config.strategy_policy import resolve_bot_sensitivity
    gate, floor, preset = resolve_bot_sensitivity(
        SimpleNamespace(sensitivity_preset='aggressive'), core.engine.config.min_confluence_score)
    core.engine.config.min_confluence_score = gate
    core.engine.config.confluence_soft_floor = floor
    core.engine.config.sensitivity_preset = preset
    return core


def scan_with_evidence(core, symbols):
    from backend.engine import cycle_heartbeat
    plans, summary = core.engine.scan_with_heartbeat(symbols)
    heartbeat = cycle_heartbeat.get_latest()
    assert heartbeat is not None and heartbeat['run_id'] == summary['run_id']
    assert not heartbeat['failed']
    assert 'features' not in heartbeat['signals_per_stage']
    assert heartbeat['total_rejected'] == summary['total_rejected']
    assert heartbeat['plans_emitted'] == len(plans)
    assert len(plans) + sum(heartbeat['signals_per_stage'].values()) == len(symbols)
    return plans, summary


@pytest.mark.parametrize('stage', ['indicator', 'smc'])
def test_scan_rejection_evidence_worker_features_reach_parent(core_factory, monkeypatch, stage):
    core = configured_core(core_factory)
    cls, method, bucket = ((IndicatorService, '_compute_timeframe_indicators', 'indicator_failures')
        if stage == 'indicator' else (SMCDetectionService, '_detect_timeframe_patterns', 'smc_rejections'))
    original = getattr(cls, method)
    def fail_5m(service, timeframe, *args, **kwargs):
        if timeframe == '5m':
            raise ValueError('injected ' + stage + ' failure')
        return original(service, timeframe, *args, **kwargs)
    monkeypatch.setattr(cls, method, fail_5m)
    plans, summary = scan_with_evidence(core, ['BTC/USDT', 'ETH/USDT'])
    records = core.engine.diagnostics[bucket]
    assert len(records) == 2
    assert {row['symbol'] for row in records} == {'BTC/USDT', 'ETH/USDT'}
    assert all(row['timeframe'] == '5m' and row['error'] == 'injected ' + stage + ' failure' for row in records)
    assert summary['features_breakdown'][bucket] == {'count': 2, 'samples': records}
    assert summary['total_rejected'] + len(plans) == 2
    # A clean subsequent run cannot inherit either symbol's prior failures.
    monkeypatch.setattr(cls, method, original)
    _, clean = scan_with_evidence(core, ['BTC/USDT'])
    assert clean['features_breakdown'][bucket] == {'count': 0, 'samples': []}


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('failure', ['planner', 'risk'])
def test_scan_rejection_evidence_terminal_reason_and_direction(core_factory, monkeypatch, direction, failure):
    core = configured_core(core_factory, direction)
    events = []
    original_log = TelemetryLogger.log_event
    def capture(logger, event):
        events.append(event)
        return original_log(logger, event)
    monkeypatch.setattr(TelemetryLogger, 'log_event', capture)
    original_plan = module.Orchestrator._generate_trade_plan
    original_risk = module.Orchestrator._validate_risk
    reason = 'injected ' + failure + ' decline'
    def injected_plan(engine, context, *args, **kwargs):
        plan = original_plan(engine, context, *args, **kwargs)
        assert plan is not None and plan.direction == direction, context.metadata
        if failure == 'planner':
            context.metadata['plan_failure_reason'] = reason
            return None
        plan.metadata['test_risk_decline'] = True
        return plan
    def risk(engine, plan):
        passed = original_risk(engine, plan)
        if plan.metadata.get('test_risk_decline'):
            assert passed
            engine._last_risk_failure = reason
            return False
        return passed
    monkeypatch.setattr(module.Orchestrator, '_generate_trade_plan', injected_plan)
    monkeypatch.setattr(module.Orchestrator, '_validate_risk', risk)
    plans, summary = scan_with_evidence(core, ['BTC/USDT'])
    assert not plans and summary['total_rejected'] == 1
    key = 'no_trade_plan' if failure == 'planner' else 'risk_validation'
    rejection = summary['details'][key][0]
    assert rejection['reason'] == reason
    assert rejection['direction'] == direction
    terminal = [event for event in events if event.event_type.value == 'signal_rejected']
    assert len(terminal) == 1
    assert terminal[0].data['reason'] == rejection['reason']
    assert terminal[0].data['gate_name'] == key
    assert terminal[0].data['diagnostics']['direction'] == direction


@pytest.mark.parametrize('stage', ['indicator', 'smc'])
def test_scan_rejection_evidence_fatal_service_preserves_partial_records(core_factory, monkeypatch, stage):
    core = configured_core(core_factory)
    cls, method, bucket = ((IndicatorService, 'compute', 'indicator_failures')
        if stage == 'indicator' else (SMCDetectionService, 'detect', 'smc_rejections'))
    def crash(service, *args, **kwargs):
        service.diagnostics[bucket].append({'timeframe': '5m', 'error': 'earlier timeframe error'})
        raise RuntimeError('fatal service error')
    monkeypatch.setattr(cls, method, crash)
    plans, summary = scan_with_evidence(core, ['BTC/USDT'])
    assert not plans and summary['total_rejected'] == 1
    assert summary['by_reason']['errors'] == 1
    assert summary['features_breakdown'][bucket]['count'] == 2
    samples = summary['features_breakdown'][bucket]['samples']
    assert {row['error'] for row in samples} == {'earlier timeframe error', 'fatal service error'}
    assert all(row['symbol'] == 'BTC/USDT' for row in samples)
    assert len(core.contexts) == 1 and core.contexts[0].confluence_breakdown is None
    assert summary['details']['errors'][0].get('direction', 'UNKNOWN') == 'UNKNOWN'


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('recover', [False, True])
def test_scan_rejection_evidence_candidate_declines_do_not_duplicate_terminal_events(core_factory, monkeypatch, direction, recover):
    core = configured_core(core_factory, direction)
    events, attempts = [], []
    original_log = TelemetryLogger.log_event
    def capture(logger, event):
        events.append(event)
        return original_log(logger, event)
    monkeypatch.setattr(TelemetryLogger, 'log_event', capture)
    original_plan = module.generate_trade_plan
    def displaced_candidate(**kwargs):
        plan = original_plan(**kwargs)
        if plan is not None:
            attempts.append(plan)
            if not recover:
                # Force the real post-plan drift guard to decline a generated candidate.
                plan.entry_zone.near_entry *= 3.
                plan.entry_zone.far_entry *= 3.
        return plan
    monkeypatch.setattr(module, 'generate_trade_plan', displaced_candidate)
    plans, summary = scan_with_evidence(core, ['BTC/USDT'])
    assert attempts, summary
    terminal = [event for event in events if event.event_type.value == 'signal_rejected']
    if recover:
        assert len(plans) == 1 and plans[0].direction == direction
        assert not terminal
        ctx = core.contexts[0]
        assert 'plan_failure_reason' not in ctx.metadata
        assert 'cascade_attempts' not in ctx.metadata
        assert plans[0].metadata['strategy']['mode'] == 'stealth'
    else:
        assert not plans and len(terminal) == 1
        rejection = summary['details']['post_plan_revalidation'][0]
        assert rejection['direction'] == direction
        assert 'Post-plan revalidation failed' in rejection['reason']
        assert terminal[0].data['gate_name'] == 'post_plan_revalidation'
        assert 'cascade_attempts' not in rejection
