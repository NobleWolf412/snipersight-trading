"""Regime evidence, fixed playbook and paper routing contract regressions."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as S
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from backend.analysis.mode_recommendation import recommend_mode, AdaptiveModeSelector
from backend.analysis.regime_detector import RegimeDetector
from backend.services.market_regime_service import MarketRegimeService, MarketRegimeUnavailable
from backend.indicators.momentum import compute_adx, compute_macd
from backend.services.indicator_service import IndicatorService
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.strategy_policy import validate_strategy_selection, resolve_bot_sensitivity, strategy_snapshot
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.live_trading_config import LiveTradingConfig
from backend.bot.paper_trading_service import PaperTradingConfig, PaperTradingService
from backend.bot.live_trading_service import LiveTradingService
from backend.engine.orchestrator import Orchestrator


def candles(tf='4h', count=120, now=None):
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    hours = {'1w': 168, '1d': 24, '4h': 4}[tf]
    end = now.floor('4h') - pd.Timedelta(hours=hours)
    price = 100 + np.arange(count) * .2 + np.sin(np.arange(count) / 4)
    return pd.DataFrame({'open': price, 'high': price + 1, 'low': price - 1,
                         'close': price + .1, 'volume': np.full(count, 1000.)},
                        index=pd.date_range(end=end, periods=count, freq=f'{hours}h', tz='UTC'))


def snapshot(daily='up', intermediate='up', weekly='sideways', volatility='normal', now=None):
    now = now or datetime.now(timezone.utc)
    return {'timestamp': now.isoformat(), 'expires_at': (now + timedelta(seconds=120)).isoformat(),
            'reference_timeframe': '1d', 'dimensions': {'trend': daily, 'volatility': volatility,
               'liquidity': 'healthy', 'risk_appetite': 'balanced'},
            'matrix': {'1d': {'trend': daily}, '4h': {'trend': intermediate}, '1w': {'trend': weekly}},
            'source_times': {'1d': now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                             '4h': (now - timedelta(hours=1)).isoformat(),
                             '1w': (now - timedelta(days=1)).isoformat()}}


@pytest.mark.parametrize('direction', ['up', 'down', 'strong_up', 'strong_down'])
def test_mode_regime_advice_is_direction_symmetric(direction):
    result = recommend_mode(snapshot(direction, direction))
    assert (result['status'], result['mode'], result['recommended_confluence']) == ('available', 'strike', 65.)


def test_mode_regime_advice_requires_swing_permission_and_never_falls_back():
    data = snapshot('up', 'up', 'up')
    assert recommend_mode(data)['mode'] == 'overwatch'
    assert recommend_mode(data, ['strike', 'surgical', 'stealth'])['mode'] == 'strike'
    result = recommend_mode(snapshot(), ['surgical'])
    assert result['mode'] is None and result['reason_code'] == 'MODE_NOT_ALLOWED'


@pytest.mark.parametrize('change', ['expired', 'future', 'missing', 'wrong_reference', 'chaotic'])
def test_mode_regime_bad_or_unsuitable_evidence_never_recommends_a_default(change):
    data = snapshot()
    if change == 'expired': data['expires_at'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    if change == 'future': data['timestamp'] = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    if change == 'missing': data['matrix'].pop('4h')
    if change == 'wrong_reference': data['reference_timeframe'] = '1w'
    if change == 'chaotic': data['dimensions']['volatility'] = 'chaotic'
    result = recommend_mode(data)
    assert result['mode'] is None and result['status'] != 'available'


def test_mode_regime_adaptive_counts_new_candles_not_polls():
    selector = AdaptiveModeSelector()
    assert selector.select(snapshot(), ['strike', 'surgical'])['mode'] == 'strike'
    ranging = snapshot('sideways', 'sideways')
    for _ in range(5):
        assert selector.select(ranging, ['strike', 'surgical'])['reason_code'] == 'MODE_CHANGE_PENDING'
    ranging['source_times']['4h'] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert selector.select(ranging, ['strike', 'surgical'])['mode'] == 'surgical'


def test_mode_regime_daily_reference_missing_cannot_use_weekly():
    detector = RegimeDetector()
    with pytest.raises(ValueError, match='daily BTC'):
        detector.detect_global_regime(S(timeframes={'1w': candles('1w')}), S(by_timeframe={'1w': object()}))


@pytest.mark.parametrize('bad', ['missing', 'stale', 'forming', 'short', 'nan', 'gap', 'crossed'])
def test_mode_regime_source_validation(bad):
    frames = {tf: candles(tf) for tf in ('1d', '4h', '1w')}
    if bad == 'missing': frames.pop('1d')
    if bad == 'stale': frames['1d'].index -= pd.Timedelta(days=3)
    if bad == 'forming': frames['4h'].index += pd.Timedelta(hours=8)
    if bad == 'short': frames['4h'] = frames['4h'].tail(20)
    if bad == 'nan': frames['4h'].iloc[-1, 3] = float('nan')
    if bad == 'gap': frames['4h'] = frames['4h'].drop(frames['4h'].index[-3])
    if bad == 'crossed': frames['4h'].iloc[-1, 1] = 1.
    with pytest.raises(MarketRegimeUnavailable):
        MarketRegimeService._source_times(S(timeframes=frames), datetime.now(timezone.utc))


def test_mode_regime_wilder_adx_ties_and_reflection():
    frame = candles()
    reflected = frame.copy()
    reflected['high'], reflected['low'], reflected['close'] = 500 - frame.low, 500 - frame.high, 500 - frame.close
    adx, plus, minus = compute_adx(frame)
    mirror_adx, mirror_plus, mirror_minus = compute_adx(reflected)
    assert (adx, plus, minus) == pytest.approx((mirror_adx, mirror_minus, mirror_plus))
    count = len(frame)
    frame['high'], frame['low'], frame['close'] = 250 + np.arange(count), 250 - np.arange(count), 250.
    assert compute_adx(frame) == (0., 0., 0.)


def test_mode_regime_wilder_matches_reference_library():
    from ta.trend import ADXIndicator
    frame = candles(count=300)
    reference = ADXIndicator(frame.high, frame.low, frame.close, window=14)
    assert compute_adx(frame) == pytest.approx((reference.adx().iloc[-1], reference.adx_pos().iloc[-1], reference.adx_neg().iloc[-1]), abs=1e-6)


@pytest.mark.parametrize('mode_name', ['overwatch', 'strike', 'surgical', 'stealth'])
def test_mode_regime_fixed_mode_and_macd_are_applied_together(mode_name):
    mode = get_mode(mode_name)
    engine = Orchestrator(config=ScanConfig(profile=mode.profile), exchange_adapter=object())
    assert engine.scanner_mode is mode
    assert engine.indicator_service._scanner_mode is mode
    assert engine.config.profile == mode.profile
    assert engine.config.primary_planning_timeframe == mode.primary_planning_timeframe
    from backend.strategy.planner.entry_engine import _get_zone_and_trigger_tfs
    from backend.strategy.planner.risk_engine import _resolve_htf_swing_allowed
    assert _get_zone_and_trigger_tfs(engine.config) == (mode.zone_timeframes, mode.entry_trigger_timeframes)
    assert set(mode.entry_trigger_timeframes) <= set(engine.config.timeframes)
    assert isinstance(engine.config.planner.htf_swing_allowed, dict)
    assert set(_resolve_htf_swing_allowed(engine.config, engine.config.planner, mode.profile)) <= set(mode.stop_timeframes)
    assert engine.config.overrides == mode.overrides
    assert engine.config.min_confluence_score == mode.min_confluence_score
    assert not engine.config.enable_fusion and mode.cascade_trade_types is None
    frame = candles(count=200)
    actual = engine.indicator_service._safe_compute_macd(frame, '4h')
    settings = (24, 52, 9) if mode_name == 'surgical' else (12, 26, 9)
    expected = compute_macd(frame, fast=settings[0], slow=settings[1], signal=settings[2])
    for left, right in zip(actual, expected):
        pd.testing.assert_series_equal(left, right)
    frozen = strategy_snapshot(mode, engine.config)
    engine.apply_mode(get_mode('strike'))
    assert engine.config.min_confluence_score == 65
    assert frozen['mode'] == mode_name and frozen['macd_settings'] == list(settings)


@pytest.mark.parametrize('bad', ['missing', 'stale', 'future', 'naive'])
def test_mode_regime_weekly_advice_requires_valid_source(bad):
    data = snapshot('up', 'up', 'up')
    now = datetime.now(timezone.utc)
    if bad == 'missing': data['source_times'].pop('1w')
    if bad == 'stale': data['source_times']['1w'] = (now - timedelta(days=8)).isoformat()
    if bad == 'future': data['source_times']['1w'] = (now + timedelta(days=1)).isoformat()
    if bad == 'naive': data['source_times']['1w'] = now.replace(tzinfo=None).isoformat()
    assert recommend_mode(data)['mode'] == 'strike'


def test_mode_regime_adaptive_reversed_observation_cannot_confirm():
    selector = AdaptiveModeSelector()
    assert selector.select(snapshot(), ['strike', 'surgical'])['mode'] == 'strike'
    ranging = snapshot('sideways', 'sideways')
    assert selector.select(ranging, ['strike', 'surgical'])['reason_code'] == 'MODE_CHANGE_PENDING'
    ranging['source_times']['4h'] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert selector.select(ranging, ['strike', 'surgical'])['reason_code'] == 'MODE_CHANGE_PENDING'
    assert selector.active_mode == 'strike'


def test_mode_regime_canonicalizes_selection_before_routing():
    config = PaperTradingConfig(sniper_mode='STRIKE', selection_mode='adaptive', allowed_modes=['STRIKE', 'strike'])
    validate_strategy_selection(config, paper=True)
    assert config.sniper_mode == 'strike' and config.allowed_modes == ['strike']
    assert recommend_mode(snapshot(), config.allowed_modes)['mode'] == 'strike'


def test_mode_regime_core_rejects_stale_daily_before_classification():
    frame = candles('1d')
    frame.index -= pd.Timedelta(days=3)
    detector = RegimeDetector()
    with pytest.raises(ValueError, match='stale'):
        detector.detect_global_regime(S(timeframes={'1d': frame}), S(by_timeframe={'1d': object()}))
    assert detector._confirmed_regime is None


def test_mode_regime_repeated_bar_cannot_confirm_but_current_risk_is_visible():
    from backend.shared.models.regime import MarketRegime, RegimeDimensions
    def observed(trend, volatility='normal', risk='balanced'):
        return MarketRegime(RegimeDimensions(trend, volatility, 'healthy', risk, 'balanced'),
                            'fixture', 70., datetime.now(timezone.utc), 70., 40., 60., 20., 50.)
    detector = RegimeDetector()
    detector._apply_hysteresis(observed('up'), evidence_id='daily-1')
    changed = observed('down', 'chaotic', 'extreme_risk_off')
    for _ in range(10):
        detector._apply_hysteresis(changed, evidence_id='daily-2')
    detector._apply_hysteresis(changed, evidence_id='daily-1')
    detector._apply_hysteresis(changed, evidence_id='daily-2')
    assert detector._pending_count == 1
    view = detector._confirmed_view(changed)
    assert view.dimensions.trend == 'up'
    assert view.dimensions.volatility == 'chaotic' and view.dimensions.risk_appetite == 'extreme_risk_off'
    assert view.composite == 'chaotic_volatile'


def test_mode_regime_expiry_during_construction_is_unavailable(monkeypatch):
    from backend.shared.models.regime import MarketRegime, RegimeDimensions
    service = MarketRegimeService(lambda: None)
    now = datetime.now(timezone.utc)
    regime = MarketRegime(RegimeDimensions('up', 'normal', 'healthy', 'balanced', 'balanced'),
                         'up_normal', 70., now, 70., 70., 70., 70., 50.)
    service._inputs = Mock(return_value=(S(timeframes={'1d': candles('1d'), '4h': candles()}), regime,
        S(btc_dom=54., alt_dom=38., stable_dom=8., timestamp=now.timestamp()),
        {'1d': (now-timedelta(days=2)).isoformat(), '4h': now.isoformat()}))
    assert service._read_recommendation()['status'] == 'unavailable'
    assert service._cached_display is None


@pytest.mark.parametrize('mode_name', ['overwatch', 'strike', 'surgical', 'stealth'])
@pytest.mark.parametrize('preset', ['balanced', 'aggressive', 'conservative', 'custom'])
def test_mode_regime_bot_restrictions_never_weaken_strategy(mode_name, preset):
    mode = get_mode(mode_name)
    config = PaperTradingConfig(sniper_mode=mode_name, sensitivity_preset=preset, min_confluence=0)
    gate, floor, _ = resolve_bot_sensitivity(config, mode.min_confluence_score)
    assert gate >= floor >= mode.min_confluence_score


def test_mode_regime_adaptive_execution_guards_run_before_side_effects():
    live = LiveTradingService()
    live._start_session = Mock(side_effect=AssertionError('must not start'))
    with pytest.raises(ValueError, match='simulated paper'):
        asyncio.run(live.start(LiveTradingConfig(selection_mode='adaptive', dry_run=True)))
    paper = PaperTradingService()
    paper._start_session = Mock(side_effect=AssertionError('must not start'))
    with pytest.raises(ValueError, match='simulated paper'):
        asyncio.run(paper.start(PaperTradingConfig(selection_mode='adaptive', use_testnet=True)))
    assert not live._start_session.called and not paper._start_session.called
    assert validate_strategy_selection(PaperTradingConfig(selection_mode='adaptive'), paper=True).name == 'stealth'
