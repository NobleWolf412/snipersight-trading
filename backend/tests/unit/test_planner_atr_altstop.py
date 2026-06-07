import pytest
from backend.strategy.planner.planner_service import generate_trade_plan
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor
from backend.shared.config.defaults import ScanConfig
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import EventType
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot


def make_indicator_set(atr: float, timeframe: str = "4H") -> IndicatorSet:
    # Provide minimal valid snapshot values; only ATR is used by planner logic in tests
    snapshot = IndicatorSnapshot(
        rsi=50.0,
        stoch_rsi=50.0,
        bb_upper=110.0,
        bb_middle=100.0,
        bb_lower=90.0,
        atr=atr,
        volume_spike=False,
    )
    return IndicatorSet(by_timeframe={timeframe: snapshot})


@pytest.fixture(autouse=True)
def reset_telemetry():
    # Reset telemetry logger cache for clean test isolation
    logger = get_telemetry_logger()
    # Directly clear internal cache
    logger._cache.clear()
    yield
    logger._cache.clear()


@pytest.fixture
def base_config():
    return ScanConfig()


@pytest.fixture
def empty_smc():
    return SMCSnapshot(order_blocks=[], fvgs=[], structural_breaks=[], liquidity_sweeps=[])


@pytest.fixture
def confluence():
    return ConfluenceBreakdown(
        total_score=75.0,
        factors=[
            ConfluenceFactor(
                name="Structure", score=80, weight=0.4, rationale="OB + FVG confluence"
            ),
            ConfluenceFactor(name="Momentum", score=70, weight=0.3, rationale="Bullish impulse"),
            ConfluenceFactor(name="Liquidity", score=60, weight=0.3, rationale="Sweep and reclaim"),
        ],
        synergy_bonus=5.0,
        conflict_penalty=0.0,
        regime="trend",
        htf_aligned=True,
        btc_impulse_gate=True,
    )


# ATR% (= atr/price*100, since bb_middle=100) bands are DAILY-TF calibrated in
# regime_detector._detect_volatility — the §10 percentage-ATR standing fix:
#   <2.5% compressed->calm | <5% normal | <7% elevated | >=7% volatile/chaotic->explosive.
# The old 0.8/1.5/2.5/4.0 cut points were 5-minute-TF bands, intentionally retired
# (regime_detector.py:750-757). These expectations were stale against the new bands
# (T13). Do NOT revert to the old values — that re-breaks the standing fix's test.
@pytest.mark.parametrize(
    "atr,current_price,expected_label",
    [
        (1.0, 100.0, "calm"),       # 1.0% < 2.5   -> compressed
        (3.5, 100.0, "normal"),     # 3.5% in [2.5,5)
        (6.0, 100.0, "elevated"),   # 6.0% in [5,7)
        (9.0, 100.0, "explosive"),  # 9.0% in [7,9.5) -> volatile
    ],
)
def test_atr_regime_classification(
    monkeypatch, base_config, empty_smc, confluence, atr, current_price, expected_label
):
    # Monkeypatch entry/stop calculation to simplify
    from backend.strategy.planner import planner_service as ps

    def fake_entry_zone(*args, **kwargs):
        from backend.shared.models.planner import EntryZone

        return (
            EntryZone(near_entry=current_price, far_entry=current_price - 0.1 * atr, rationale="Test"),
            True,
        )

    def fake_stop_loss(*args, **kwargs):
        from backend.shared.models.planner import StopLoss

        # Reachable ATR-proportional stop (0.5 ATR). A fixed 1%-of-price stop was
        # 1.25-5 ATR for these small-ATR cases, which the 2026-05-31 TP1 reachability
        # gate (decisions/2026-05-30__fix-design__tp1-reachability.md) correctly
        # declines → no plan. These tests assert regime/alt-stop behavior, not
        # reachability, so they need a plannable (reachable) stop.
        _sd = min(0.5 * atr, 0.02 * current_price)  # cap stop at 2% so high-ATR clears the 3% scalp cap
        return StopLoss(level=current_price - _sd, distance_atr=(_sd / atr) if atr else 0.5, rationale="Test"), True

    monkeypatch.setattr(ps, "_calculate_entry_zone", fake_entry_zone)
    monkeypatch.setattr(ps, "_calculate_stop_loss", fake_stop_loss)

    indicators = make_indicator_set(atr=atr, timeframe="4H")

    plan = generate_trade_plan(
        symbol="TEST/USDT",
        direction="LONG",
        setup_type="intraday",
        current_price=current_price,
        indicators=indicators,
        smc_snapshot=empty_smc,
        confluence_breakdown=confluence,
        config=base_config,
        multi_tf_data=None,
        missing_critical_timeframes=[],
    )

    regime_meta = plan.metadata.get("atr_regime")
    assert regime_meta is not None, "ATR regime metadata missing"
    assert (
        regime_meta["label"] == expected_label
    ), f"Expected {expected_label}, got {regime_meta['label']}"


def test_alt_stop_suggested_high_liq_risk(monkeypatch, base_config, empty_smc, confluence):
    current_price = 100.0
    atr = 0.8  # normal regime

    # Force liquidation metadata to report high risk band
    from backend.strategy.planner import planner_service as ps

    def fake_liq_meta(is_bullish, near_entry, stop_level, leverage, mmr=0.004):
        return {
            "assumed_mmr": mmr,
            "approx_liq_price": near_entry * 0.984,
            "cushion_pct": 15.0,  # <30 => high risk
            "risk_band": "high",
            "direction": "long" if is_bullish else "short",
        }

    monkeypatch.setattr(ps, "_calculate_liquidation_metadata", fake_liq_meta)

    def fake_entry_zone(*args, **kwargs):
        from backend.shared.models.planner import EntryZone

        return (
            EntryZone(near_entry=current_price, far_entry=current_price - 0.1 * atr, rationale="Test"),
            True,
        )

    def fake_stop_loss(*args, **kwargs):
        from backend.shared.models.planner import StopLoss

        # Provide a structurally tight stop (near far_entry) so extended buffer suggests widening
        far_entry = current_price * 0.995  # 99.5
        # Tight stop: far_entry - 0.25*ATR = 99.5 - 0.2 = 99.3 (used_stop_buffer_atr = 0.25)
        stop_level = far_entry - 0.25 * atr
        # Distance ATR (logical structural distance) set above min_stop_atr gate to pass validation
        distance_atr = 1.05
        return StopLoss(level=stop_level, distance_atr=distance_atr, rationale="Test"), True

    monkeypatch.setattr(ps, "_calculate_entry_zone", fake_entry_zone)
    monkeypatch.setattr(ps, "_calculate_stop_loss", fake_stop_loss)

    indicators = make_indicator_set(atr=atr, timeframe="4H")

    plan = generate_trade_plan(
        symbol="TEST/USDT",
        direction="LONG",
        setup_type="intraday",
        current_price=current_price,
        indicators=indicators,
        smc_snapshot=empty_smc,
        confluence_breakdown=confluence,
        config=base_config,
        multi_tf_data=None,
        missing_critical_timeframes=[],
    )

    alt_stop = plan.metadata.get("alt_stop")
    assert alt_stop is not None, "Alt stop should be suggested for high liquidation risk"
    assert (
        alt_stop["level"] < plan.stop_loss.level
    ), "Suggested alt stop should extend further (lower for long)"

    # Verify telemetry event emitted
    telemetry = get_telemetry_logger()
    events = telemetry.get_cached_events(limit=10)
    assert any(
        e["event_type"] == EventType.ALT_STOP_SUGGESTED.value for e in events
    ), "ALT_STOP_SUGGESTED event not logged"


def test_no_alt_stop_for_comfortable_liq(monkeypatch, base_config, empty_smc, confluence):
    current_price = 100.0
    atr = 0.8
    from backend.strategy.planner import planner_service as ps

    def fake_liq_meta(is_bullish, near_entry, stop_level, leverage, mmr=0.004):
        return {
            "assumed_mmr": mmr,
            "approx_liq_price": near_entry * 0.95,
            "cushion_pct": 70.0,  # comfortable
            "risk_band": "comfortable",
            "direction": "long" if is_bullish else "short",
        }

    monkeypatch.setattr(ps, "_calculate_liquidation_metadata", fake_liq_meta)

    def fake_entry_zone(*args, **kwargs):
        from backend.shared.models.planner import EntryZone

        return (
            EntryZone(near_entry=current_price, far_entry=current_price - 0.1 * atr, rationale="Test"),
            True,
        )

    def fake_stop_loss(*args, **kwargs):
        from backend.shared.models.planner import StopLoss

        # Reachable ATR-proportional stop (0.5 ATR). A fixed 1%-of-price stop was
        # 1.25-5 ATR for these small-ATR cases, which the 2026-05-31 TP1 reachability
        # gate (decisions/2026-05-30__fix-design__tp1-reachability.md) correctly
        # declines → no plan. These tests assert regime/alt-stop behavior, not
        # reachability, so they need a plannable (reachable) stop.
        _sd = min(0.5 * atr, 0.02 * current_price)  # cap stop at 2% so high-ATR clears the 3% scalp cap
        return StopLoss(level=current_price - _sd, distance_atr=(_sd / atr) if atr else 0.5, rationale="Test"), True

    monkeypatch.setattr(ps, "_calculate_entry_zone", fake_entry_zone)
    monkeypatch.setattr(ps, "_calculate_stop_loss", fake_stop_loss)

    indicators = make_indicator_set(atr=atr, timeframe="4H")

    plan = generate_trade_plan(
        symbol="TEST/USDT",
        direction="LONG",
        setup_type="intraday",
        current_price=current_price,
        indicators=indicators,
        smc_snapshot=empty_smc,
        confluence_breakdown=confluence,
        config=base_config,
        multi_tf_data=None,
        missing_critical_timeframes=[],
    )

    assert (
        plan.metadata.get("alt_stop") is None
    ), "Alt stop should not be suggested for comfortable cushion"
    telemetry = get_telemetry_logger()
    events = telemetry.get_cached_events(limit=5)
    assert not any(
        e["event_type"] == EventType.ALT_STOP_SUGGESTED.value for e in events
    ), "Alt stop event should not be logged"
