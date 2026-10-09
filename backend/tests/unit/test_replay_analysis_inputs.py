"""Historical candle analysis must use its as-of time and price, not today's."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from backend.engine.orchestrator import Orchestrator
from backend.engine.replay_engine import ReplayEngine
from backend.services.smc_service import SMCDetectionService
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.smc import OrderBlock, SMCSnapshot
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.strategy.smc.order_blocks import calculate_freshness
from backend.tests.unit.test_confluence_htf_proximity import make_indicators
from backend.tests.unit.test_ev_none_plan_reason_mask import _ctx, _orch

AS_OF = datetime(2001, 2, 5, 8, tzinfo=timezone.utc)


def candles():
    frame = pd.DataFrame(dict(open=100., high=102., low=98., close=100., volume=10.),
                         index=pd.date_range(end=AS_OF - timedelta(hours=1), periods=60, freq='h'))
    frame['timestamp'] = frame.index
    return frame


def ob(direction, timestamp):
    return OrderBlock(timeframe='1h', direction=direction,
                      high=95. if direction == 'bullish' else 106.,
                      low=94. if direction == 'bullish' else 105.,
                      timestamp=timestamp, displacement_strength=80.,
                      mitigation_level=0., freshness_score=100.)


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('ob_aware,clock_aware', [(False, True), (True, False), (True, True)])
def test_freshness_compares_naive_utc_and_offset_aware_times(direction, ob_aware, clock_aware):
    formed = AS_OF - timedelta(hours=48)
    if not ob_aware:
        formed = formed.replace(tzinfo=None)
    clock = AS_OF.astimezone(timezone(timedelta(hours=-5))) if clock_aware else AS_OF.replace(tzinfo=None)
    assert calculate_freshness(ob(direction, formed), clock) == pytest.approx(50.)


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
def test_smc_service_keeps_historically_fresh_ob_and_recomputes_age(monkeypatch, direction):
    from backend.services import smc_service as module
    formed = (AS_OF - timedelta(hours=24)).replace(tzinfo=None)
    monkeypatch.setattr(module, 'detect_order_blocks', lambda *a, **k: [ob(direction, formed)])
    monkeypatch.setattr(module, 'detect_order_blocks_structural', lambda *a, **k: [])
    monkeypatch.setattr(module, 'detect_obs_from_bos', lambda *a, **k: [])
    data = MultiTimeframeData(symbol='BTC/USDT', timeframes={'1h': candles()})
    snapshot = SMCDetectionService(mode='stealth').detect(data, 100., as_of=AS_OF)
    assert len(snapshot.order_blocks) == 1
    assert snapshot.order_blocks[0].freshness_score == pytest.approx(2 ** (-.5) * 100.)
    expired = SMCDetectionService(mode='stealth').detect(data, 100., as_of=AS_OF + timedelta(days=30))
    assert expired.order_blocks == []


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
def test_score_kill_zone_uses_explicit_historical_clock(monkeypatch, direction):
    from backend.strategy.confluence import scorer
    seen = []
    original = scorer.get_current_kill_zone
    monkeypatch.setattr(scorer, 'get_current_kill_zone', lambda now: (seen.append(now), original(now))[1])
    scorer.calculate_confluence_score(SMCSnapshot([], [], [], []), make_indicators(), ScanConfig(),
                                     direction, as_of=AS_OF)
    assert seen == [AS_OF]


@pytest.mark.parametrize('replay', [False, True])
def test_confluence_service_passes_replay_clock_only(monkeypatch, replay):
    from backend.services import confluence_service as module
    context = _ctx(); context.timestamp = AS_OF
    if replay:
        context.metadata['replay_session_id'] = 'historical'
    score = Mock(return_value=object())
    monkeypatch.setattr(module, 'calculate_confluence_score', score)
    module.ConfluenceService(config=ScanConfig())._score_direction(context, 'LONG', True, None, None, None, 100.)
    assert score.call_args.kwargs.get('as_of') == (AS_OF if replay else None)


def test_orchestrator_passes_replay_timestamp_into_smc():
    engine = ReplayEngine(object())._build_orchestrator(get_mode('stealth'))
    engine._check_critical_timeframes = lambda data: []
    engine.regime_detector = None
    engine.indicator_service = SimpleNamespace(compute=lambda data: make_indicators(), diagnostics={})
    engine.smc_service = SimpleNamespace(detect=Mock(side_effect=ValueError('stop after clock inspection')),
                                         diagnostics={'smc_rejections': []})
    data = MultiTimeframeData(symbol='BTC/USDT', timeframes={'1h': candles()})
    engine.process_symbol_for_replay('BTC/USDT', data, AS_OF, 'test', 0, 'session')
    assert engine.smc_service.detect.call_args.kwargs.get('as_of') == AS_OF


@pytest.mark.parametrize('replay', [False, True])
def test_direct_fresh_price_cannot_fetch_todays_quote_in_replay(monkeypatch, replay):
    monkeypatch.setenv('SS_FRESH_ENTRY_PRICE', '1')
    engine = _orch(); engine._Orchestrator__replay_mode = replay
    ticker = Mock(return_value={'last': 150.})
    engine.exchange_adapter = SimpleNamespace(exchange=SimpleNamespace(fetch_ticker=ticker))
    assert engine._fetch_fresh_price('BTC/USDT') == (None if replay else 150.)
    assert ticker.call_count == (0 if replay else 1)


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('replay', [False, True])
def test_plan_validation_uses_historical_price_in_replay_but_current_ticker_in_live(monkeypatch, direction, replay):
    from backend.engine import orchestrator as module
    engine, context = _orch(), _ctx()
    engine._Orchestrator__replay_mode = replay
    context.timestamp = AS_OF; context.metadata['chosen_direction'] = direction
    context.multi_tf_data = MultiTimeframeData(symbol='BTC/USDT', timeframes={'1h': candles()})
    engine.telemetry = SimpleNamespace(log_event=Mock())
    ticker = Mock(return_value={'last': 150.})
    engine.exchange_adapter = SimpleNamespace(exchange=SimpleNamespace(fetch_ticker=ticker))
    plan = SimpleNamespace(risk_reward=2., metadata={}, targets=[], setup_type='Test', direction=direction,
                           entry_zone=SimpleNamespace(near_entry=100., far_entry=99. if direction=='LONG' else 101.))
    monkeypatch.setattr(module, 'generate_trade_plan', lambda **kwargs: plan)
    result = engine._generate_trade_plan(context, 100.)
    if replay:
        assert result is plan
        assert ticker.call_count == 0
        assert result.metadata['live_price_revalidation']['live_price'] == 100.
        assert result.metadata['live_price_revalidation']['price_source'] == 'replay_candle_close'
    else:
        assert result is None
        assert ticker.call_count == 1
        assert 'revalidation' in context.metadata['plan_failure_reason']
