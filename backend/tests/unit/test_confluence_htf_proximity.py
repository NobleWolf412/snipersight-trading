from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
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


@pytest.mark.parametrize("direction,aligned_type,opposing_type", [
    ("LONG", "support", "resistance"),
    ("SHORT", "resistance", "support"),
])
def test_htf_proximity_contributes_once_to_composite(direction, aligned_type, opposing_type):
    """The old standalone factor was replaced by HTF Composite before this audit."""
    cfg = ScanConfig()
    cfg.primary_planning_timeframe = "4h"
    cfg.structure_timeframes = ("4h",)

    def score(level_type):
        smc = SMCSnapshot(order_blocks=[], fvgs=[], structural_breaks=[], liquidity_sweeps=[])
        smc.htf_levels = [SimpleNamespace(price=100., timeframe="4h", level_type=level_type)]
        result = calculate_confluence_score(
            smc, make_indicators(), cfg, direction, current_price=100.,
            as_of=datetime(2001, 2, 5, 8, tzinfo=timezone.utc),
        )
        composites = [factor for factor in result.factors if factor.name == "HTF Composite"]
        assert len(composites) == 1
        assert not any(factor.name == "HTF Level Proximity" for factor in result.factors)
        return composites[0]

    aligned = score(aligned_type)
    opposing = score(opposing_type)
    assert aligned.score > opposing.score
    assert aligned_type.title() in aligned.rationale
    assert "(opposing)" in opposing.rationale
