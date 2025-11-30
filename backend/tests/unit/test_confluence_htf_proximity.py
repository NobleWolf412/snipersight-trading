import math
from backend.strategy.confluence.scorer import calculate_confluence_score
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.config.defaults import ScanConfig


def make_indicators(atr: float = 2.0) -> IndicatorSet:
    snap = IndicatorSnapshot(
        rsi=50.0,
        stoch_rsi=50.0,
        bb_upper=102.0,
        bb_middle=100.0,
        bb_lower=98.0,
        atr=atr,
        volume_spike=False,
        mfi=50.0,
        obv=0.0,
    )
    return IndicatorSet(by_timeframe={"4H": snap})


def test_htf_proximity_factor_added_and_carries_context():
    smc = SMCSnapshot(order_blocks=[], fvgs=[], structural_breaks=[], liquidity_sweeps=[])
    indicators = make_indicators(atr=2.0)
    cfg = ScanConfig()
    cfg.htf_proximity_enabled = True
    cfg.htf_proximity_weight = 0.12
    cfg.primary_planning_timeframe = "4H"
    htf_ctx = {"within_atr": 0.5, "within_pct": 1.0, "timeframe": "1d", "type": "support"}

    breakdown = calculate_confluence_score(
        smc_snapshot=smc,
        indicators=indicators,
        config=cfg,
        direction="LONG",
        htf_context=htf_ctx,
    )

    # Ensure factor exists
    names = [f.name for f in breakdown.factors]
    assert "HTF Level Proximity" in names

    # Carried fields
    assert math.isclose(breakdown.htf_proximity_atr or 0, 0.5, rel_tol=1e-6)
    assert math.isclose(breakdown.htf_proximity_pct or 0, 1.0, rel_tol=1e-6)
    assert breakdown.nearest_htf_level_timeframe == "1d"
    assert breakdown.nearest_htf_level_type == "support"

    # Score should be > 0
    assert breakdown.total_score >= 0.0
