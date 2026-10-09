"""Paper/live logs and the trace endpoint preserve scanner rejection evidence."""
import asyncio
import json
from types import SimpleNamespace as S
from unittest.mock import Mock

import pytest

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.tests.integration.test_paper_workflow import workflow


_MISSING = object()


@pytest.fixture
def live_rejection_service(tmp_path):
    from backend.bot.live_trading_service import LiveTradingService
    from backend.bot.paper_trading_service import PaperTradingConfig

    # Exercise the actual scan/log/trace boundaries without clients or execution.
    svc = LiveTradingService.__new__(LiveTradingService)
    svc.config = PaperTradingConfig(sniper_mode='strike', symbols=['BTC/USDT'])
    svc.stats = S(scans_completed=0, signals_generated=0)
    svc._running = True
    svc._generation = 1
    svc.current_scan = None
    svc.signal_log = []
    svc._current_regime_composite = 'unknown'
    svc._session_log_dir = tmp_path
    svc._log_activity = Mock()
    svc.executor = None
    svc.position_manager = None
    return svc


@pytest.mark.parametrize('direction', [_MISSING, None, '', 'UNKNOWN', 'LONG', 'SHORT'],
                         ids=['missing', 'null', 'empty', 'unknown', 'long', 'short'])
@pytest.mark.parametrize('through_scan', [True, False], ids=['scan', 'direct_log'])
def test_rejection_consumers_live_preserves_side_through_jsonl_and_trace(
        live_rejection_service, monkeypatch, direction, through_scan):
    from backend.analysis import pair_selection
    from backend.bot import live_trading_service
    from backend.routers.observability import get_signal_trace

    svc = live_rejection_service
    expected = 'UNKNOWN' if direction is _MISSING or not direction else direction
    fields = {'symbol': 'BTC/USDT', 'confidence_score': 0.0,
              'reason': 'input unavailable', 'reason_type': 'no_data'}
    if direction is not _MISSING:
        fields['direction'] = direction
    if through_scan:
        # Real scan wrapper consumes supplied pre-direction rejection evidence.
        monkeypatch.setattr(pair_selection, 'filter_stale_symbols', lambda symbols, **_: (symbols, []))
        scan = Mock(return_value=([], {'details': {'no_data': [fields]}, 'by_reason': {'no_data': 1}}))
        svc.orchestrator = S(
            scan_with_heartbeat=scan,
            exchange_adapter=S(get_symbol_volumes=lambda _: {'BTC/USDT': 100_000_000.}),
        )
        asyncio.run(svc._run_scan())
        scan.assert_called_once()
        assert svc.current_scan['status'] == 'complete'
        assert svc.current_scan['total_passed'] == 0
        assert svc.current_scan['rejection_funnel'] == {'no_data': 1}
    else:
        svc._log_signal(S(**fields), 'filtered', fields['reason'], reason_type='no_data')

    assert len(svc.signal_log) == 1
    entry = svc.signal_log[0]
    assert entry['direction'] == expected
    assert entry['id'].endswith('_' + expected.lower())
    assert entry['result'] == 'filtered' and entry['confluence'] == 0.0
    assert entry['reason'] == fields['reason']
    persisted = [json.loads(line) for line in (svc._session_log_dir / 'signals.jsonl').read_text().splitlines()]
    assert persisted == [entry]
    assert svc.get_signal_by_id(entry['id']) == entry

    monkeypatch.setattr(live_trading_service, 'get_live_trading_service', lambda: svc)
    response = asyncio.run(get_signal_trace(entry['id']))
    trace = json.loads(response.body)['data']
    assert trace['side'] == expected.lower()
    assert trace['final_state'] == 'filtered:no_data'
    stages = {stage['name']: stage for stage in trace['stages']}
    assert stages['DATA']['pass'] is False and stages['DATA']['killed_at'] is True
    assert stages['EXECUTION']['value'] == 'skipped'
    assert svc.stats.signals_generated == 0 and svc.executor is None


@pytest.mark.parametrize('direction', [None, 'UNKNOWN', 'LONG', 'SHORT'])
def test_rejection_consumers_paper_preserves_known_or_unknown_side(workflow, direction):
    svc = workflow.svc
    svc.config.symbols = ['BTC/USDT']
    svc.mode = get_mode('stealth')
    rejection = {'symbol': 'BTC/USDT', 'reason': 'fixture rejection', 'reason_type': 'errors'}
    if direction is not None:
        rejection['direction'] = direction
    svc.orchestrator = S(
        config=ScanConfig(), apply_mode=Mock(),
        scan_with_heartbeat=Mock(return_value=([], {'details': {'errors': [rejection]}, 'by_reason': {'errors': 1}})),
        regime_detector=S(get_confirmed_regime=lambda: None),
        exchange_adapter=S(get_symbol_volumes=lambda symbols: {symbol: 100_000_000. for symbol in symbols}),
    )
    asyncio.run(svc._run_scan())
    assert not svc.executor.orders
    assert len(svc.signal_log) == 1, svc.activity_log
    assert svc.signal_log[0]['direction'] == (direction or 'UNKNOWN')
    assert svc.signal_log[0]['reason'] == 'fixture rejection'


@pytest.mark.parametrize('direction', ['LONG', 'SHORT', 'UNKNOWN'])
def test_rejection_consumers_trace_marks_post_plan_revalidation_failed(monkeypatch, direction):
    from backend.bot import live_trading_service
    from backend.routers.observability import get_signal_trace
    entry = {'id': 'fixture', 'symbol': 'BTC/USDT', 'direction': direction,
             'result': 'filtered', 'reason_type': 'post_plan_revalidation', 'reason': 'entry price drift'}
    monkeypatch.setattr(live_trading_service, 'get_live_trading_service', lambda: S(get_signal_by_id=lambda _: entry))
    response = asyncio.run(get_signal_trace('fixture'))
    trace = json.loads(response.body)['data']
    assert trace['side'] == direction.lower()
    stages = {stage['name']: stage for stage in trace['stages']}
    assert stages['PLANNER']['pass'] is False and stages['PLANNER']['killed_at'] is True
    assert stages['PLANNER']['value'] == 'entry price drift'
    assert stages['RISK_VALIDATION']['pass'] is None
    assert stages['EXECUTION']['value'] == 'skipped'


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
def test_rejection_consumers_trace_evidence_failure_despite_numeric_pass(monkeypatch, direction):
    from backend.bot import live_trading_service
    from backend.routers.observability import get_signal_trace
    entry = {'id': 'fixture', 'symbol': 'BTC/USDT', 'direction': direction,
             'result': 'filtered', 'reason_type': 'evidence_requirements',
             'reason': 'Confirmed structural shift missing', 'confluence': 85., 'threshold': 70.}
    monkeypatch.setattr(live_trading_service, 'get_live_trading_service', lambda: S(get_signal_by_id=lambda _: entry))
    trace = json.loads(asyncio.run(get_signal_trace('fixture')).body)['data']
    stages = {stage['name']: stage for stage in trace['stages']}
    assert stages['CONFLUENCE_SCORE']['pass'] is False
    assert stages['CONFLUENCE_SCORE']['killed_at'] is True
    assert stages['CONFLUENCE_SCORE']['value'] == entry['reason']
    assert stages['PLANNER']['value'] == 'skipped'


def _consumer_breakdown(name, score, **metadata):
    from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor
    return ConfluenceBreakdown(total_score=score-10.,
        factors=[ConfluenceFactor(name, score, 1., 'fixture contribution'),
                 ConfluenceFactor('Raw diagnostic', 100., 0., 'diagnostic only')],
        synergy_bonus=0., conflict_penalty=10., regime='trend', htf_aligned=True,
        btc_impulse_gate=True, metadata=metadata)


@pytest.mark.parametrize('gate', [0., 70., None])
def test_rejection_consumers_confluence_preserves_recorded_policy_and_eligibility(monkeypatch, gate):
    from backend.bot import live_trading_service
    from backend.routers.observability import get_signal_confluence
    from backend.strategy.confluence import cache
    breakdown = _consumer_breakdown('Entry anchor', 85., score_gate=gate,
        score_model_version='family-evidence-v2', score_policy_version='family-policy-v2',
        score_gate_passed=True, evidence_eligible=False, admission_passed=False,
        evidence_missing=['Confirmed structural shift'])
    monkeypatch.setattr(live_trading_service, 'get_live_trading_service', lambda: None)
    monkeypatch.setattr(cache, 'get', lambda _: breakdown)
    data = json.loads(asyncio.run(get_signal_confluence('fixture')).body)['data']
    assert data['threshold'] == (gate if gate is not None else 0.)
    assert data['metadata']['threshold_available'] is (gate is not None)
    assert data['metadata']['score_gate_passed'] is True
    assert data['metadata']['evidence_eligible'] is False
    assert data['metadata']['admission_passed'] is False
    assert data['metadata']['score_model_version'] == 'family-evidence-v2'


def test_rejection_consumers_distribution_conserves_base_and_discloses_mixed_policies(monkeypatch):
    from backend.routers.observability import get_confluence_distribution
    from backend.strategy.confluence import cache
    family = _consumer_breakdown('Entry anchor', 80., score_model_version='family-evidence-v2',
                                 score_policy_version='family-policy-v2')
    legacy = _consumer_breakdown('Legacy anchor', 90.)
    legacy.direction = 'bearish'
    monkeypatch.setattr(cache, 'recent', lambda _: [('new', family), ('old', legacy)])
    response = json.loads(asyncio.run(get_confluence_distribution(n=2, direction='all')).body)
    data = response['data']
    assert data['sample_count'] == 2
    assert data['avg_total_score'] == 75.
    assert sum(f['avg_weighted_score'] for f in data['factors']) == 85.
    assert sum(f['avg_weight'] for f in data['factors']) == 1.
    assert {f['name'] for f in data['factors']} == {'Entry anchor', 'Legacy anchor'}
    assert response['metadata']['reason'] == 'mixed_scoring_provenance'
    assert 'family-evidence-v2' in response['warnings'][0]
    assert [d['sample_count'] for d in data['by_direction']] == [1, 1]
