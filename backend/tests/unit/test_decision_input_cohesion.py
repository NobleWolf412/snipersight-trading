"""Selected modes and consumed order blocks must reach the real analysis services."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from backend.engine import orchestrator as module
from backend.engine.orchestrator import Orchestrator
from backend.services.smc_service import SMCDetectionService
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.smc_config import SMCConfig
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.smc import OrderBlock, FVG


@pytest.fixture
def engine_factory(monkeypatch):
    monkeypatch.setattr(module, 'get_telemetry_logger', lambda: SimpleNamespace(log_event=Mock()))
    monkeypatch.setattr(module, 'CooldownManager', lambda: object())
    from backend.analysis import regime_detector
    monkeypatch.setattr(regime_detector, '_regime_detector', None)
    from backend.services import indicator_service, smc_service, confluence_service
    monkeypatch.setattr(indicator_service, '_indicator_service', None)
    monkeypatch.setattr(smc_service, '_smc_service', None)
    monkeypatch.setattr(confluence_service, '_confluence_service', None)
    return lambda mode='stealth', replay=False: Orchestrator(
        ScanConfig(profile=get_mode(mode).profile), exchange_adapter=object(), replay_mode=replay)


@pytest.mark.parametrize('replay', [False, True])
def test_mode_switch_updates_smc_and_private_detector_without_cross_engine_mutation(engine_factory, replay):
    first = engine_factory(replay=replay)
    second = engine_factory(replay=replay)
    assert first.regime_detector is not second.regime_detector
    for name in ('strike', 'overwatch', 'surgical', 'stealth'):
        mode = get_mode(name)
        old = first.regime_detector
        first.apply_mode(mode)
        assert first.smc_service._mode == name
        assert first.smc_service._mode_profile == mode.profile
        assert first.regime_detector.mode_profile == mode.profile
        assert first.regime_detector is not old
        assert first.regime_detector is not second.regime_detector
        assert second.smc_service._mode == 'stealth'
        assert second.regime_detector.mode_profile == 'stealth_balanced'
        if replay:
            assert first.regime_detector._global_regime_ttl == first.regime_detector._symbol_regime_ttl == 0


def test_reapplying_same_mode_preserves_detector_state(engine_factory):
    engine = engine_factory('strike')
    original = engine.regime_detector
    sentinel = object(); original._global_regime_cache = sentinel
    engine.apply_mode(get_mode('strike'))
    assert engine.regime_detector is original
    assert original._global_regime_cache is sentinel
    engine.apply_mode(get_mode('overwatch'))
    assert engine.regime_detector._global_regime_cache is None


def test_manual_smc_config_keeps_mode_but_explicit_mode_updates_profile():
    service = SMCDetectionService(mode='overwatch')
    service.update_config(SMCConfig())
    assert service._mode == 'overwatch' and service._mode_profile == 'macro_surveillance'
    service.update_config(SMCConfig(), mode='strike')
    assert service._mode == 'strike' and service._mode_profile == 'intraday_aggressive'


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('timeframe', ['15m', '1H', '1h'])
@pytest.mark.parametrize('kind', ['ob', 'fvg'])
def test_consumed_patterns_are_removed_regardless_of_first_available_frame(direction, timeframe, kind):
    now = datetime(2001, 2, 5, tzinfo=timezone.utc)
    frame = pd.DataFrame(dict(open=100., high=110., low=90., close=100., volume=10.),
                         index=pd.date_range('2001-02-03', periods=30, freq='h'))
    frame['timestamp'] = frame.index
    block = OrderBlock(timeframe='1h', direction=direction, high=101., low=99.,
                       timestamp=datetime(2001, 2, 2), displacement_strength=80.,
                       mitigation_level=0., freshness_score=100.)
    data = MultiTimeframeData('BTC/USDT', {timeframe: frame})
    service = SMCDetectionService()
    if kind == 'ob':
        assert service._update_mitigation(data, [block], as_of=now) == []
    else:
        gap = FVG('1h', direction, 101., 99., block.timestamp, 2., 0.)
        assert service._update_fvg_fill(data, [gap]) == []


def test_mitigation_prefers_available_nonempty_15m_and_falls_back_when_empty(monkeypatch):
    from backend.services import smc_service as service_module
    now = datetime(2001, 2, 5, tzinfo=timezone.utc)
    frame = pd.DataFrame(dict(open=100., high=110., low=90., close=100., volume=10.),
                         index=pd.date_range('2001-02-03', periods=30, freq='h'))
    frame['timestamp'] = frame.index
    other = frame.copy(); other['close'] = 101.
    block = OrderBlock(timeframe='1h', direction='bullish', high=95., low=94.,
                       timestamp=now-timedelta(hours=1), displacement_strength=80.,
                       mitigation_level=0., freshness_score=100.)
    seen = []
    def mitigation(blocks, df, **kwargs):
        seen.append(df)
        return blocks, SimpleNamespace(fully_mitigated_count=0)
    monkeypatch.setattr(service_module, 'update_ob_mitigation', mitigation)
    monkeypatch.setattr(service_module, 'update_ob_lifecycle', lambda df, blocks, **kwargs: blocks)
    data = SimpleNamespace(timeframes={'15m': frame, '1H': other})
    service = SMCDetectionService()
    service._update_mitigation(data, [block], as_of=now)
    assert seen[-1] is frame
    data.timeframes['15m'] = frame.iloc[:0]
    service._update_mitigation(data, [block], as_of=now)
    assert seen[-1] is other

def test_paper_advisory_reads_its_own_regime_dimensions(monkeypatch):
    from backend.bot.paper_trading_service import PaperTradingService
    from backend.analysis import regime_detector
    from backend.strategy.planner import regime_engine
    from backend.shared.models.regime import MarketRegime, RegimeDimensions

    regime = MarketRegime(RegimeDimensions('up', 'normal', 'healthy', 'risk_on', 'balanced'),
                          'bullish_risk_on', 75., datetime(2001, 2, 5), 70., 75., 70., 80., 50.)
    service = object.__new__(PaperTradingService)
    service.config = SimpleNamespace(sniper_mode='stealth')
    service.mode = get_mode('stealth')
    service.orchestrator = SimpleNamespace(regime_detector=SimpleNamespace(get_confirmed_regime=lambda: regime))
    monkeypatch.setattr(regime_detector, 'get_regime_detector', Mock(side_effect=AssertionError('foreign singleton')))
    recommendation = Mock(return_value={'mode': 'strike', 'reason': 'controlled fixture'})
    monkeypatch.setattr(regime_engine, 'get_mode_recommendation', recommendation)

    class StopBeforeScan(Exception):
        pass
    events = []
    def activity(kind, payload):
        events.append((kind, payload))
        if kind == 'scan_started':
            raise StopBeforeScan()
    service._log_activity = activity
    with pytest.raises(StopBeforeScan):
        asyncio.run(service._run_scan())
    recommendation.assert_called_once_with('up', 'normal', 'risk_on')
    assert events[0][0] == 'system_update'
    assert service.mode.name == 'stealth'


def test_replay_serializes_real_market_regime_dimensions():
    from backend.engine.replay_engine import _serialize_regime
    from backend.shared.models.regime import MarketRegime, RegimeDimensions
    regime = MarketRegime(RegimeDimensions('down', 'elevated', 'healthy', 'risk_off', 'balanced'),
                          'bearish_risk_off', 65., datetime(2001, 2, 5), 70., 55., 70., 30., 50.)
    result = _serialize_regime(regime)
    assert result['trend'] == 'down'
    assert result['volatility'] == 'elevated'
