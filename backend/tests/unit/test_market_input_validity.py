"""Missing current or historical market inputs cannot become positive evidence."""
import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Query

from backend.analysis import dominance_service as dominance
from backend.analysis.regime_detector import RegimeDetector
from backend.engine.replay_engine import ReplayEngine
from backend.shared.config.scanner_modes import get_mode
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.smc import SMCSnapshot
from backend.tests.unit.test_replay_analysis_inputs import AS_OF, candles
from backend.tests.unit.test_confluence_htf_proximity import make_indicators


@pytest.mark.parametrize('invalid', ['missing', 'stale', 'future', 'nan_time', 'nan_btc', 'negative', 'zero', 'partition'])
def test_decision_dominance_rejects_missing_stale_and_invalid_snapshots(monkeypatch, invalid):
    monkeypatch.setattr(dominance.time, 'time', lambda: 10000.)
    snapshot = SimpleNamespace(timestamp=9999., btc_dom=54., alt_dom=42., stable_dom=4.)
    if invalid == 'missing': snapshot = None
    elif invalid == 'stale': snapshot.timestamp = 10000. - dominance.CACHE_TTL_SECONDS
    elif invalid == 'future': snapshot.timestamp = 10001.
    elif invalid == 'nan_time': snapshot.timestamp = float('nan')
    elif invalid == 'nan_btc': snapshot.btc_dom = float('nan')
    elif invalid == 'negative': snapshot.alt_dom = -1.
    elif invalid == 'zero': snapshot.btc_dom = snapshot.alt_dom = snapshot.stable_dom = 0.
    elif invalid == 'partition': snapshot.btc_dom = 99.
    monkeypatch.setattr(dominance, 'get_current_dominance', lambda: snapshot)
    with pytest.raises(ValueError, match='DOMINANCE_UNAVAILABLE'):
        dominance.get_dominance_for_macro()


def test_valid_real_percentage_partition_and_ttl_boundary_survive(monkeypatch):
    monkeypatch.setattr(dominance.time, 'time', lambda: 10000.)
    snapshot = SimpleNamespace(timestamp=10000.-dominance.CACHE_TTL_SECONDS+1., btc_dom=54.33, alt_dom=41.33, stable_dom=4.33)
    monkeypatch.setattr(dominance, 'get_current_dominance', lambda: snapshot)
    assert dominance.get_dominance_for_macro() == (54.33, 41.33, 4.33)


def test_missing_dominance_does_not_get_a_fabricated_regime_score(monkeypatch):
    monkeypatch.setattr(dominance, 'get_current_dominance', lambda: None)
    with pytest.raises(ValueError, match='DOMINANCE_UNAVAILABLE'):
        RegimeDetector()._detect_risk_appetite()


@pytest.mark.parametrize('age', [-1., float('nan'), float('inf'), 3600.])
def test_cache_validity_rejects_future_invalid_and_expired_time(monkeypatch, age):
    monkeypatch.setattr(dominance.time, 'time', lambda: 10000.)
    service = object.__new__(dominance.DominanceService)
    assert not service._is_cache_valid({'timestamp': 10000.-age})


def test_replay_never_calls_present_day_global_classifier():
    engine = ReplayEngine(object())._build_orchestrator(get_mode('stealth'))
    compute = Mock(return_value=SimpleNamespace(by_timeframe={'1h': object()}))
    classify = Mock(return_value=object())
    engine.indicator_service = SimpleNamespace(compute=compute)
    engine.regime_detector = SimpleNamespace(detect_global_regime=classify)
    assert engine._detect_global_regime(SimpleNamespace(timeframes={'1h': object()})) is None
    assert not compute.called and not classify.called


@pytest.mark.parametrize('replay,macro_enabled', [(True, True), (True, False), (False, True)])
def test_pipeline_reports_missing_context_after_smc_and_before_scoring(replay, macro_enabled):
    engine = ReplayEngine(object())._build_orchestrator(get_mode('stealth'))
    engine._Orchestrator__replay_mode = replay
    engine.config.macro_overlay_enabled = macro_enabled
    engine._next_replay_session_id = 'fixture'
    engine._next_replay_playback_index = 0
    engine._check_critical_timeframes = lambda data: []
    engine._check_cooldown = lambda *args: None
    engine.regime_detector = None
    engine.indicator_service = SimpleNamespace(compute=lambda data: make_indicators(), diagnostics={})
    smc = SMCSnapshot([], [], [], [])
    engine.smc_service = SimpleNamespace(detect=Mock(return_value=smc), diagnostics={})
    engine.confluence_service = SimpleNamespace(score=Mock(side_effect=AssertionError('scoring must not run')))
    engine.telemetry = SimpleNamespace(log_event=Mock())
    data = MultiTimeframeData('BTC/USDT', {'1h': candles()})
    plan, rejection = engine._process_symbol('BTC/USDT', 'fixture', AS_OF, prefetched_data=data)
    assert plan is None
    assert rejection['reason_type'] == ('historical_context_unavailable' if replay else 'market_context_unavailable')
    assert not engine.confluence_service.score.called
    assert engine.smc_service.detect.called
    if replay:
        assert engine._last_replay_context.smc_snapshot is smc


def test_explicit_technical_scan_has_no_macro_requirement():
    engine = ReplayEngine(object())._build_orchestrator(get_mode('stealth'))
    engine._Orchestrator__replay_mode = False
    engine.config.macro_overlay_enabled = False
    context = SimpleNamespace(macro_context=None, metadata={}, symbol='BTC/USDT')
    assert engine._analysis_context_rejection(context) is None

def test_macro_scan_with_required_inputs_can_continue():
    engine = ReplayEngine(object())._build_orchestrator(get_mode('stealth'))
    engine._Orchestrator__replay_mode = False
    context = SimpleNamespace(macro_context=object(), metadata={'global_regime': object()}, symbol='BTC/USDT')
    assert engine.config.macro_overlay_enabled
    assert engine._analysis_context_rejection(context) is None


def test_observed_dominance_still_produces_the_existing_risk_label(monkeypatch):
    monkeypatch.setattr(dominance.time, 'time', lambda: 10000.)
    snapshot = SimpleNamespace(timestamp=9999., btc_dom=54., alt_dom=42.5, stable_dom=3.5)
    monkeypatch.setattr(dominance, 'get_current_dominance', lambda: snapshot)
    assert RegimeDetector()._detect_risk_appetite() == ('risk_on', 80.)


@pytest.mark.parametrize('missing', ['regime', 'dominance'])
def test_market_regime_api_reports_unavailable_instead_of_inventing_numbers(missing):
    # Execute the real route body without importing API startup (adapters/.env).
    from typing import Optional
    from backend.shared.models.regime import MarketRegime, RegimeDimensions
    source = Path(__file__).resolve().parents[2] / 'api_server.py'
    tree = ast.parse(source.read_text(encoding='utf8'))
    handler = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'get_market_regime')
    handler.decorator_list = []
    regime = MarketRegime(RegimeDimensions('up', 'normal', 'healthy', 'risk_on', 'balanced'),
                          'bullish_risk_on', 75., datetime(2001, 2, 5), 70., 75., 70., 80., 50.)
    def unavailable(): raise ValueError('DOMINANCE_UNAVAILABLE: fixture')
    namespace = dict(Optional=Optional, Query=Query, HTTPException=HTTPException,
                     logger=Mock(), datetime=datetime, timezone=timezone,
                     REGIME_CACHE=SimpleNamespace(get=lambda key: None, set=Mock()),
                     orchestrator=SimpleNamespace(_detect_global_regime=lambda: None if missing=='regime' else regime),
                     get_dominance_for_macro=unavailable)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[handler], type_ignores=[])), 'regime-api-fixture', 'exec'), namespace)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(namespace['get_market_regime'](symbol=None))
    assert caught.value.status_code == 503

def test_replay_signal_search_stops_at_unavailable_historical_context():
    from backend.tests.unit.test_replay_navigation_state import fixture_engine
    engine, session = fixture_engine()
    compute = engine._compute_step
    def unavailable(session, index):
        result = compute(session, index)
        result.plan = None
        result.rejection = {'reason_type': 'historical_context_unavailable', 'reason': 'missing frozen input'}
        return result
    engine._compute_step = unavailable
    result, advanced = engine.jump_to_next_signal('session', max_lookahead=100)
    assert advanced == 1 and session.step_index == 0
    assert result.rejection['reason_type'] == 'historical_context_unavailable'
    assert not result.signal_fired


def test_replay_jump_response_does_not_call_an_unavailable_step_a_signal(monkeypatch):
    from backend.routers import replay
    from backend.engine.replay_engine import StepResult
    step = StepResult(0, AS_OF, AS_OF, {}, rejection={'reason_type': 'historical_context_unavailable'})
    monkeypatch.setattr(replay, '_engine_or_500', lambda: SimpleNamespace(jump_to_next_signal=lambda *a, **k: (step, 1)))
    result = asyncio.run(replay.jump_to_next_signal('session', replay.JumpToSignalRequest(max_lookahead=100)))
    assert not result.found and result.bars_advanced == 1
    assert result.step.rejection['reason_type'] == 'historical_context_unavailable'
