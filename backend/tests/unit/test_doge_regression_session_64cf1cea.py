"""
Regression test for SniperSight session_64cf1cea (2026-05-04 DOGE/USDT LONG).

Purpose
-------
The DOGE trade exposed two classes of issues:

  (A) Signal-gating fundamentals: a 74.8% confidence LONG was emitted while
      multiple structural conflicts were present (HTF bearish, premium zone,
      MTF divergence on 5 TFs, sweep with HTF bearish divergence, RSI > 70,
      BB %B > 1). Conflict penalty registered as 0.

  (B) Execution / bar resolution: the trade closed in 0 minutes at an
      exit_price ABOVE entry on a LONG, but was logged as a loss with
      exit_reason='target' and targets_hit=[0]. R:R efficiency analytics
      flagged "targets are structurally out of reach".

This file encodes the failing trade as a fixture and tests the EXPECTED
behavior of the corrected predicates. It is self-contained -- it does not
import from backend.* so it can run standalone and serve as a behavioral
specification you can wire your real implementations against.

To wire to real code, replace the reference predicates in
`reference_predicates.py` patterns below with imports from your modules
(e.g. backend.strategy.confluence.scorer, backend.engine.backtest_engine).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal
import pytest


# ---------------------------------------------------------------------------
# Fixture: the actual failing DOGE trade from session_64cf1cea
# ---------------------------------------------------------------------------

@dataclass
class ConfluenceFactor:
    name: str
    score: float          # 0..100
    weight: float
    rationale: str = ""


@dataclass
class TradeSignal:
    symbol: str
    direction: Literal["LONG", "SHORT"]
    confidence: float
    conviction_class: str          # "A", "B", "C"
    trade_type: str                # "scalp", "swing", etc.
    regime: str
    kill_zone: str
    rr: float
    htf_aligned: bool
    htf_composite: float           # 0..100 composite of HTF
    premium_pct: float             # 0..100; 100 = full premium
    mtf_opposed_count: int         # number of MTFs opposed to direction
    sweep_grade: Optional[str]     # "A", "B", "C", or None
    sweep_htf_divergence: bool
    rsi: float
    bb_percent_b: float
    adx: float
    volume_ratio: float
    factors: List[ConfluenceFactor]
    synergy_bonus: float
    conflict_penalty: float
    macro_bonus: float
    entry: float
    stop: float


@dataclass
class FillResult:
    filled: bool
    fill_price: float
    exit_price: Optional[float]
    exit_reason: Optional[str]
    targets_hit: List[int]
    duration_minutes: int
    pnl_pct: float
    mfe_pct: float
    mae_pct: float


# Verbatim from the DOGE decision card:
DOGE_TRADE = TradeSignal(
    symbol="DOGE/USDT",
    direction="LONG",
    confidence=74.8,
    conviction_class="B",
    trade_type="scalp",
    regime="up_compressed",
    kill_zone="asian_open",
    rr=1.8,
    htf_aligned=False,
    htf_composite=38.0,            # "HTF bearish" per card
    premium_pct=77.0,              # "Premium zone (77%)"
    mtf_opposed_count=5,           # "MTF divergence warning (5 opposed)"
    sweep_grade="C",
    sweep_htf_divergence=True,     # "[HTF bearish divergence]"
    rsi=74.7547,
    bb_percent_b=1.4777,
    adx=12.6473,
    volume_ratio=4.7697,
    factors=[
        ConfluenceFactor("Market Structure", 78.0, 9.22),
        ConfluenceFactor("Order Block", 85.0, 7.89),
        ConfluenceFactor("Volatility", 87.4, 4.43),
        ConfluenceFactor("Institutional Sequence", 100.0, 4.22),
        ConfluenceFactor("Volume", 100.0, 3.38),
        ConfluenceFactor("MACD Veto", 100.0, 3.38),
        ConfluenceFactor("Nested Order Block", 80.0, 3.38),
        ConfluenceFactor("Volume Profile", 45.0, 2.85),
        ConfluenceFactor("MTF Indicator Alignment", 66.7, 2.81),
        ConfluenceFactor("Close Momentum", 70.0, 2.66),
        ConfluenceFactor("Multi-Candle Confirmation", 100.0, 2.53),
        ConfluenceFactor("Inside Order Block", 50.0, 2.53),
        ConfluenceFactor("Momentum", 45.0, 2.28),
        ConfluenceFactor("BTC Impulse Gate", 100.0, 2.11),
        ConfluenceFactor("Kill Zone Timing", 25.0, 1.58),
        ConfluenceFactor("Regime Alignment", 67.5, 1.42),
        ConfluenceFactor("HTF Composite", 38.0, 1.28),
        ConfluenceFactor("Liquidity Sweep", 30.0, 1.27),
        ConfluenceFactor("Premium/Discount Zone", 30.0, 1.14),
        ConfluenceFactor("Liquidity Draw", 15.0, 0.95),
        ConfluenceFactor("VWAP Alignment", 40.0, 0.84),
        ConfluenceFactor("Weekly StochRSI Bonus", 50.0, 0.63),
    ],
    synergy_bonus=2.0,
    conflict_penalty=0.0,          # <- the bug: should be > 0
    macro_bonus=15.0,
    entry=0.10894,
    stop=0.10709,
)

# Verbatim observed fill result:
DOGE_OBSERVED_FILL = FillResult(
    filled=True,
    fill_price=0.10894,
    exit_price=0.11180,            # ABOVE entry on a LONG...
    exit_reason="target",          # ...but...
    targets_hit=[0],               # ...zero targets hit. Contradiction.
    duration_minutes=0,
    pnl_pct=-0.03,                 # logged as loss despite higher exit
    mfe_pct=0.0,
    mae_pct=0.01,
)


# ---------------------------------------------------------------------------
# Reference predicates -- the EXPECTED behavior
# ---------------------------------------------------------------------------

def expected_conflict_penalty(sig: TradeSignal) -> float:
    """
    Reference conflict-penalty predicate.

    Each rule contributes a penalty point when the structural condition
    contradicts the signal direction. Total is bounded to a sane range.
    """
    penalty = 0.0

    # 1. HTF unaligned with direction
    if not sig.htf_aligned:
        penalty += 15.0

    # 2. HTF composite leans against direction
    if sig.direction == "LONG" and sig.htf_composite < 50:
        penalty += 10.0
    if sig.direction == "SHORT" and sig.htf_composite > 50:
        penalty += 10.0

    # 3. Direction × premium/discount zone disagreement
    if sig.direction == "LONG" and sig.premium_pct >= 70:
        penalty += 12.0
    if sig.direction == "SHORT" and sig.premium_pct <= 30:
        penalty += 12.0

    # 4. MTF divergence: opposed timeframes
    if sig.mtf_opposed_count >= 4:
        penalty += 8.0
    elif sig.mtf_opposed_count >= 3:
        penalty += 4.0

    # 5. Liquidity sweep grade C with HTF divergence note
    if sig.sweep_grade == "C" and sig.sweep_htf_divergence:
        penalty += 5.0

    # 6. Overbought/extended on a LONG (exhaustion risk)
    if sig.direction == "LONG" and sig.rsi >= 70 and sig.bb_percent_b >= 1.0:
        penalty += 8.0
    if sig.direction == "SHORT" and sig.rsi <= 30 and sig.bb_percent_b <= 0.0:
        penalty += 8.0

    # 7. No-trend tape (low ADX) on a directional thesis
    if sig.adx < 15:
        penalty += 4.0

    return penalty


def expected_should_emit(sig: TradeSignal, recomputed_penalty: float) -> bool:
    """
    Reference signal gate using the corrected penalty plus hard rules.
    """
    # Hard gate: HTF unaligned AND HTF composite bearish for a LONG (or
    # mirror for SHORT) is a no-go regardless of confluence.
    if not sig.htf_aligned and sig.direction == "LONG" and sig.htf_composite < 50:
        return False
    if not sig.htf_aligned and sig.direction == "SHORT" and sig.htf_composite > 50:
        return False

    # Hard gate: premium long / discount short structurally backward.
    if sig.direction == "LONG" and sig.premium_pct >= 70 and sig.htf_composite < 50:
        return False
    if sig.direction == "SHORT" and sig.premium_pct <= 30 and sig.htf_composite > 50:
        return False

    # Soft gate via adjusted confidence:
    adjusted = sig.confidence + sig.synergy_bonus + sig.macro_bonus - recomputed_penalty
    return adjusted >= 65.0


def resolve_same_bar_fill(
    entry: float,
    stop: float,
    targets: List[float],
    bar_high: float,
    bar_low: float,
    direction: str,
    policy: str = "stop_first",
) -> FillResult:
    """
    Reference same-bar fill resolver.

    policy options:
      - "stop_first":  if both stop and target are touched in the same bar,
                       assume stop hit (worst case for us).
      - "no_same_bar": disallow same-bar entry+exit; return unfilled.
    """
    if direction == "LONG":
        target_touched = any(bar_high >= t for t in targets)
        stop_touched = bar_low <= stop
    else:
        target_touched = any(bar_low <= t for t in targets)
        stop_touched = bar_high >= stop

    if not (target_touched or stop_touched):
        return FillResult(True, entry, None, None, [], 0, 0.0, 0.0, 0.0)

    if policy == "no_same_bar":
        return FillResult(True, entry, None, None, [], 0, 0.0, 0.0, 0.0)

    # stop_first
    if stop_touched and target_touched:
        return FillResult(True, entry, stop, "stop", [], 0,
                          ((stop - entry) / entry) * 100.0 *
                          (1 if direction == "LONG" else -1),
                          0.0, abs((stop - entry) / entry) * 100.0)
    if stop_touched:
        return FillResult(True, entry, stop, "stop", [], 0,
                          ((stop - entry) / entry) * 100.0 *
                          (1 if direction == "LONG" else -1),
                          0.0, abs((stop - entry) / entry) * 100.0)
    # target only
    hit_idx = [i for i, t in enumerate(targets)
               if (bar_high >= t if direction == "LONG" else bar_low <= t)]
    fill_target = targets[hit_idx[0]]
    pnl = ((fill_target - entry) / entry) * 100.0 * (1 if direction == "LONG" else -1)
    return FillResult(True, entry, fill_target, "target", hit_idx, 0, pnl, pnl, 0.0)


def fill_self_consistent(fill: FillResult, direction: str) -> bool:
    """
    A fill record must be internally consistent:
      - exit_reason='target'   -> targets_hit must be non-empty
      - exit_reason='stop'     -> targets_hit must be empty
      - LONG  : sign(pnl) must match sign(exit - entry)
      - SHORT : sign(pnl) must match sign(entry - exit)
    """
    if fill.exit_reason == "target" and len(fill.targets_hit) == 0:
        return False
    if fill.exit_reason == "stop" and len(fill.targets_hit) > 0:
        return False
    if fill.exit_price is None:
        return True  # no exit yet, nothing to check
    if direction == "LONG":
        price_delta = fill.exit_price - fill.fill_price
    else:
        price_delta = fill.fill_price - fill.exit_price
    if (price_delta > 0 and fill.pnl_pct < 0) or (price_delta < 0 and fill.pnl_pct > 0):
        return False
    return True


# ---------------------------------------------------------------------------
# Tests -- expected behavior
# ---------------------------------------------------------------------------

class TestConflictPenaltyPredicate:

    def test_doge_trade_should_have_nonzero_conflict_penalty(self):
        """The DOGE card recorded conflict_penalty=0.0 -- that's the bug."""
        recomputed = expected_conflict_penalty(DOGE_TRADE)
        assert recomputed > 0.0, (
            f"Conflict penalty must be > 0 for a signal with HTF bearish + "
            f"premium long + 5 MTF opposed + grade-C sweep w/ HTF divergence + "
            f"RSI>74 + BB%B>1 + ADX<15. Got {recomputed}."
        )

    def test_doge_penalty_above_threshold(self):
        """Specifically: at least 50 points of penalty for this many conflicts."""
        recomputed = expected_conflict_penalty(DOGE_TRADE)
        assert recomputed >= 50.0, (
            f"Expected >= 50 penalty points for the DOGE conflict stack; "
            f"got {recomputed}. Predicate may be missing a rule."
        )

    def test_clean_long_has_zero_penalty(self):
        """Sanity: a clean aligned long shouldn't accumulate penalty."""
        clean = TradeSignal(
            symbol="BTC/USDT", direction="LONG", confidence=80.0,
            conviction_class="A", trade_type="scalp", regime="up_normal",
            kill_zone="ny_open", rr=2.0, htf_aligned=True, htf_composite=78.0,
            premium_pct=25.0, mtf_opposed_count=0, sweep_grade="A",
            sweep_htf_divergence=False, rsi=58.0, bb_percent_b=0.62, adx=28.0,
            volume_ratio=1.8, factors=[], synergy_bonus=0.0,
            conflict_penalty=0.0, macro_bonus=0.0, entry=100.0, stop=98.0,
        )
        assert expected_conflict_penalty(clean) == 0.0


class TestSignalGate:

    def test_doge_signal_should_be_rejected(self):
        penalty = expected_conflict_penalty(DOGE_TRADE)
        assert expected_should_emit(DOGE_TRADE, penalty) is False, (
            "DOGE LONG with HTF bearish + premium 77% must NOT pass the gate."
        )

    def test_htf_unaligned_bearish_long_hard_rejected(self):
        sig = TradeSignal(
            symbol="X/USDT", direction="LONG", confidence=85.0,
            conviction_class="A", trade_type="scalp", regime="up_normal",
            kill_zone="ny_open", rr=2.0, htf_aligned=False, htf_composite=40.0,
            premium_pct=50.0, mtf_opposed_count=1, sweep_grade="A",
            sweep_htf_divergence=False, rsi=55.0, bb_percent_b=0.5, adx=22.0,
            volume_ratio=1.5, factors=[], synergy_bonus=10.0,
            conflict_penalty=0.0, macro_bonus=10.0, entry=100.0, stop=98.0,
        )
        # Even at 85 + 10 + 10, it must hard-reject.
        assert expected_should_emit(sig, 0.0) is False

    def test_premium_long_with_bearish_htf_hard_rejected(self):
        sig = TradeSignal(
            symbol="X/USDT", direction="LONG", confidence=80.0,
            conviction_class="A", trade_type="scalp", regime="up_normal",
            kill_zone="ny_open", rr=2.0, htf_aligned=True, htf_composite=45.0,
            premium_pct=80.0, mtf_opposed_count=1, sweep_grade="A",
            sweep_htf_divergence=False, rsi=55.0, bb_percent_b=0.5, adx=22.0,
            volume_ratio=1.5, factors=[], synergy_bonus=0.0,
            conflict_penalty=0.0, macro_bonus=0.0, entry=100.0, stop=98.0,
        )
        assert expected_should_emit(sig, 0.0) is False

    def test_clean_long_passes(self):
        sig = TradeSignal(
            symbol="BTC/USDT", direction="LONG", confidence=72.0,
            conviction_class="B", trade_type="scalp", regime="up_normal",
            kill_zone="ny_open", rr=2.0, htf_aligned=True, htf_composite=72.0,
            premium_pct=30.0, mtf_opposed_count=0, sweep_grade="A",
            sweep_htf_divergence=False, rsi=58.0, bb_percent_b=0.6, adx=24.0,
            volume_ratio=1.6, factors=[], synergy_bonus=2.0,
            conflict_penalty=0.0, macro_bonus=0.0, entry=100.0, stop=98.0,
        )
        assert expected_should_emit(sig, expected_conflict_penalty(sig)) is True


class TestSameBarFillResolution:

    def test_observed_doge_fill_is_internally_inconsistent(self):
        """
        The observed fill record violates internal consistency:
          - exit_reason='target' but targets_hit=[0] (no real index, since
            an empty hit ladder cannot reduce to [0])
          - LONG with exit_price > entry but pnl_pct negative
        Either condition alone should fail the consistency check.
        """
        # Note: targets_hit=[0] in the log appears to mean "TP1 reached: 1/1"
        # in summary, but on the card itself it's listed alongside
        # MFE=+0.00% which contradicts. We test the LONG sign mismatch.
        observed = DOGE_OBSERVED_FILL
        # exit_price 0.11180 > entry 0.10894 on LONG, but pnl is negative
        assert observed.exit_price > observed.fill_price
        assert observed.pnl_pct < 0
        assert fill_self_consistent(observed, "LONG") is False, (
            "Observed DOGE fill must fail consistency: long w/ exit>entry "
            "but negative P&L."
        )

    def test_same_bar_stop_first_policy_picks_stop(self):
        # Bar that touches both target and stop.
        result = resolve_same_bar_fill(
            entry=0.10894, stop=0.10709,
            targets=[0.11227],   # roughly 1.8R above entry
            bar_high=0.11300,    # touches target
            bar_low=0.10650,     # also touches stop
            direction="LONG",
            policy="stop_first",
        )
        assert result.exit_reason == "stop"
        assert result.targets_hit == []
        assert result.pnl_pct < 0
        assert fill_self_consistent(result, "LONG") is True

    def test_no_same_bar_policy_disallows_entry_bar_close(self):
        result = resolve_same_bar_fill(
            entry=0.10894, stop=0.10709,
            targets=[0.11227],
            bar_high=0.11300,
            bar_low=0.10650,
            direction="LONG",
            policy="no_same_bar",
        )
        assert result.exit_reason is None
        assert result.targets_hit == []
        assert result.duration_minutes == 0  # still on entry bar

    def test_target_only_hit_produces_consistent_fill(self):
        result = resolve_same_bar_fill(
            entry=0.10894, stop=0.10709,
            targets=[0.11227],
            bar_high=0.11250,    # touches target
            bar_low=0.10800,     # does NOT touch stop
            direction="LONG",
            policy="stop_first",
        )
        assert result.exit_reason == "target"
        assert result.targets_hit == [0]
        assert result.pnl_pct > 0
        assert fill_self_consistent(result, "LONG") is True

    def test_stop_only_hit_produces_consistent_fill(self):
        result = resolve_same_bar_fill(
            entry=0.10894, stop=0.10709,
            targets=[0.11227],
            bar_high=0.11000,    # does NOT touch target
            bar_low=0.10650,     # touches stop
            direction="LONG",
            policy="stop_first",
        )
        assert result.exit_reason == "stop"
        assert result.targets_hit == []
        assert result.pnl_pct < 0
        assert fill_self_consistent(result, "LONG") is True


class TestFactorWeightSanity:

    def test_premium_discount_weight_too_low(self):
        """
        The Premium/Discount factor on the DOGE card has weight 1.14 -- low
        enough that even at score 0/100 it can't materially block a long
        in premium territory. We assert the weight should be raised to at
        least the level of HTF Composite (1.28) at minimum, ideally higher.
        """
        pd = next(f for f in DOGE_TRADE.factors
                  if f.name == "Premium/Discount Zone")
        htf = next(f for f in DOGE_TRADE.factors if f.name == "HTF Composite")
        # Document the bug: PD weight is currently lower than HTF composite.
        # When fix is applied, this assertion can be reversed.
        assert pd.weight < 3.0, (
            "Premium/Discount weight is currently insufficient to gate "
            "premium-zone longs; recommend raising weight >= 3.0 or "
            "moving the check into the conflict-penalty predicate."
        )
        assert pd.weight <= htf.weight, (
            "Currently Premium/Discount weight <= HTF Composite weight; "
            "this is the symptom we're documenting."
        )


class TestKillZoneRegimeMatrix:

    def test_compressed_regime_in_asian_open_should_downgrade_class(self):
        """
        up_compressed regime during asian_open kill zone is a known chop
        trap. Conviction class should be capped at 'C' unless an A-grade
        institutional sequence stacks AND HTF is aligned.
        """
        sig = DOGE_TRADE
        # Reference rule:
        chop_trap = (sig.regime.endswith("compressed") and
                     sig.kill_zone == "asian_open")
        rescued = (sig.htf_aligned and
                   any(f.name == "Institutional Sequence" and f.score >= 95
                       for f in sig.factors))
        max_class = "C" if (chop_trap and not rescued) else sig.conviction_class
        # DOGE was emitted as B; under rule it should be capped at C.
        assert max_class == "C", (
            "DOGE emitted as conviction B during asian_open + up_compressed "
            "without HTF alignment to rescue. Should cap at C."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
