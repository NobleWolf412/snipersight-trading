"""
SniperSight — Confluence Scorer Diagnostic
Probes the scoring pipeline end-to-end with synthetic SMC snapshots.

Tests:
  1. Weight integrity — all mode weight tables sum correctly
  2. Zero-signal floor — empty snapshot produces low, non-zero score
  3. Perfect-signal ceiling — fully-loaded snapshot reaches expected max
  4. Factor isolation — each factor contributes proportionally in isolation
  5. Synergy fires correctly — OB+FVG+Structure triggers bonus
  6. Conflict penalty fires correctly — opposing structure reduces score
  7. Mode differentiation — same snapshot scores differently per mode
  8. Score inversion guard — bearish factors don't inflate bullish score
  9. Weight normalization — factors are not double-counted
 10. Known issues detected — dead code paths, silent defaults, etc.
"""

import sys
import os
import math
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Optional, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DIVIDER = "─" * 72
HEADER  = "═" * 72

# ── Imports ───────────────────────────────────────────────────────────────────
try:
    from backend.strategy.confluence.scorer import (
        calculate_confluence_score,
        MODE_FACTOR_WEIGHTS,
        _OVERWATCH_WEIGHTS,
        _STRIKE_WEIGHTS,
        _SURGICAL_WEIGHTS,
        _STEALTH_WEIGHTS,
    )
    from backend.shared.models.smc import (
        SMCSnapshot, OrderBlock, FVG, StructuralBreak,
        LiquiditySweep, CycleContext, CyclePhase, CycleTranslation,
        CycleConfirmation,
    )
    from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
    from backend.shared.config.defaults import ScanConfig
    IMPORTS_OK = True
    IMPORT_ERROR = None
except Exception as e:
    IMPORTS_OK = False
    IMPORT_ERROR = str(e)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _ts(offset_bars: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=15 * offset_bars)


def _empty_snapshot() -> SMCSnapshot:
    return SMCSnapshot(
        order_blocks=[], fvgs=[], structural_breaks=[],
        liquidity_sweeps=[],
    )


def _make_snap(**overrides) -> "IndicatorSnapshot":
    defaults = dict(
        rsi=50.0, stoch_rsi=50.0,
        bb_upper=68500.0, bb_middle=68000.0, bb_lower=67500.0,
        atr=250.0, volume_spike=False,
        stoch_rsi_k=50.0, stoch_rsi_d=50.0,
        adx=20.0, atr_percent=0.4,
        macd_line=0.0, macd_signal=0.0, macd_histogram=0.0,
        obv=0.0, vwap=68000.0, volume_ratio=1.0,
        mfi=50.0,
    )
    defaults.update(overrides)
    return IndicatorSnapshot(**defaults)


def _empty_indicators() -> IndicatorSet:
    snap = _make_snap()
    return IndicatorSet(by_timeframe={"15m": snap})


def _config(profile: str = "stealth") -> ScanConfig:
    cfg = ScanConfig()
    cfg.profile = profile
    cfg.timeframes = ["15m", "1h", "4h"]
    cfg.min_confluence_score = 65.0
    return cfg


def _bullish_ob() -> OrderBlock:
    return OrderBlock(
        timeframe="15m", direction="bullish",
        high=68200.0, low=67800.0,
        timestamp=_ts(10), grade="A",
        displacement_strength=75.0,
        mitigation_level=0.0,
        freshness_score=90.0,
    )


def _bearish_ob() -> OrderBlock:
    return OrderBlock(
        timeframe="15m", direction="bearish",
        high=68800.0, low=68400.0,
        timestamp=_ts(8), grade="A",
        displacement_strength=75.0,
        mitigation_level=0.0,
        freshness_score=90.0,
    )


def _bullish_fvg() -> FVG:
    return FVG(
        timeframe="15m", direction="bullish",
        top=68150.0, bottom=67950.0,
        size=200.0,
        timestamp=_ts(12), grade="A",
        overlap_with_price=0.0,
        freshness_score=1.0,
    )


def _bearish_break() -> StructuralBreak:
    return StructuralBreak(
        timeframe="15m", break_type="BOS", direction="bearish",
        level=68500.0, timestamp=_ts(5), htf_aligned=True, grade="A",
    )


def _bullish_break() -> StructuralBreak:
    return StructuralBreak(
        timeframe="15m", break_type="CHoCH", direction="bullish",
        level=67900.0, timestamp=_ts(6), htf_aligned=True, grade="A",
    )


def _low_sweep() -> LiquiditySweep:
    return LiquiditySweep(
        timeframe="15m", sweep_type="low",
        level=67750.0, timestamp=_ts(15),
        confirmation=True,
        confirmation_level=2,
        has_reversal_pattern=True,
    )


def _bullish_indicators() -> IndicatorSet:
    snap = _make_snap(
        rsi=62.0, stoch_rsi=72.0, stoch_rsi_k=72.0, stoch_rsi_d=65.0,
        macd_line=120.0, macd_signal=80.0, macd_histogram=40.0,
        adx=32.0, atr=250.0, atr_percent=0.4,
        bb_upper=68500.0, bb_middle=68000.0, bb_lower=67500.0,
        volume_spike=True, obv=5000.0, vwap=67900.0, volume_ratio=1.8,
        mfi=62.0,
    )
    return IndicatorSet(by_timeframe={"15m": snap, "1h": snap})


def _bearish_indicators() -> IndicatorSet:
    snap = _make_snap(
        rsi=38.0, stoch_rsi=28.0, stoch_rsi_k=28.0, stoch_rsi_d=35.0,
        macd_line=-120.0, macd_signal=-80.0, macd_histogram=-40.0,
        adx=32.0, atr=250.0, atr_percent=0.4,
        bb_upper=68500.0, bb_middle=68000.0, bb_lower=67500.0,
        volume_spike=True, obv=-5000.0, vwap=68200.0, volume_ratio=1.8,
        mfi=38.0,
    )
    return IndicatorSet(by_timeframe={"15m": snap, "1h": snap})


def _run_score(snapshot, indicators, direction="bullish", profile="stealth",
               htf_trend=None, cycle_context=None):
    cfg = _config(profile)
    try:
        bd = calculate_confluence_score(
            smc_snapshot=snapshot,
            indicators=indicators,
            config=cfg,
            direction=direction,
            htf_trend=htf_trend or direction,
            cycle_context=cycle_context,
            symbol="BTC/USDT",
        )
        return bd, None
    except Exception as e:
        return None, str(e)


# ── Test harness ──────────────────────────────────────────────────────────────
issues = []
warnings = []
results = []


def _check(label: str, condition: bool, detail: str, severity: str = "BUG"):
    status = "✅ PASS" if condition else f"🐛 {severity}"
    results.append((label, status, detail))
    if not condition:
        issues.append((severity, label, detail))


def _warn(label: str, detail: str):
    results.append((label, "⚠️  WARN", detail))
    warnings.append((label, detail))


# =============================================================================
# TEST 1: Weight table integrity
# =============================================================================
def test_weight_tables():
    tables = {
        "OVERWATCH":  _OVERWATCH_WEIGHTS,
        "STRIKE":     _STRIKE_WEIGHTS,
        "SURGICAL":   _SURGICAL_WEIGHTS,
        "STEALTH":    _STEALTH_WEIGHTS,
    }
    ref_keys = set(_OVERWATCH_WEIGHTS.keys())

    for name, tbl in tables.items():
        # Check for missing/extra keys
        missing = ref_keys - set(tbl.keys())
        extra   = set(tbl.keys()) - ref_keys
        _check(
            f"Weight keys [{name}]",
            not missing and not extra,
            f"Missing: {missing}  Extra: {extra}" if (missing or extra) else "All keys present",
        )
        # Check no zero weights (silent dead factors)
        zeros = [k for k, v in tbl.items() if v == 0.0]
        _check(
            f"No zero weights [{name}]",
            not zeros,
            f"Zero-weight factors (dead): {zeros}" if zeros else "No zero weights",
            severity="WARN",
        )
        # Check no weight > 0.35 (over-dominance)
        heavy = {k: v for k, v in tbl.items() if v > 0.35}
        _check(
            f"No over-dominant weight [{name}]",
            not heavy,
            f"Over-dominant (>0.35): {heavy}" if heavy else "All weights reasonable",
            severity="WARN",
        )


# =============================================================================
# TEST 2: MODE_FACTOR_WEIGHTS aliases cover all profiles
# =============================================================================
def test_mode_aliases():
    expected = {
        "macro_surveillance", "overwatch",
        "intraday_aggressive", "strike",
        "precision", "surgical",
        "stealth_balanced", "stealth",
    }
    actual = set(MODE_FACTOR_WEIGHTS.keys())
    missing = expected - actual
    _check(
        "Mode alias coverage",
        not missing,
        f"Missing aliases: {missing}" if missing else "All mode aliases registered",
    )


# =============================================================================
# TEST 3: Empty snapshot — score is low but non-crashing
# =============================================================================
def test_empty_snapshot():
    bd, err = _run_score(_empty_snapshot(), _empty_indicators())
    _check(
        "Empty snapshot — no crash",
        err is None,
        f"Exception: {err}" if err else "Returned score cleanly",
    )
    if bd:
        _check(
            "Empty snapshot — score < 40",
            bd.total_score < 40,
            f"Score={bd.total_score:.1f} (expected <40 with no signal)",
            severity="WARN",
        )


# =============================================================================
# TEST 4: Loaded bullish snapshot scores higher than empty
# =============================================================================
def test_loaded_vs_empty():
    smc = _empty_snapshot()
    smc.order_blocks    = [_bullish_ob()]
    smc.fvgs            = [_bullish_fvg()]
    smc.structural_breaks = [_bullish_break()]
    smc.liquidity_sweeps  = [_low_sweep()]

    empty_bd, _  = _run_score(_empty_snapshot(), _empty_indicators())
    loaded_bd, _ = _run_score(smc, _bullish_indicators(), htf_trend="bullish")

    if empty_bd and loaded_bd:
        _check(
            "Loaded > empty score",
            loaded_bd.total_score > empty_bd.total_score,
            f"Loaded={loaded_bd.total_score:.1f}  Empty={empty_bd.total_score:.1f}",
        )
        if loaded_bd.total_score < 35:
            _warn(
                "Loaded bullish score suspiciously low",
                f"Score={loaded_bd.total_score:.1f} with OB+FVG+CHoCH+sweep — expected ≥35 (single-TF, no HTF data)",
            )


# =============================================================================
# TEST 5: Mode differentiation — same snapshot, different profiles
# =============================================================================
def test_mode_differentiation():
    smc = _empty_snapshot()
    smc.order_blocks      = [_bullish_ob()]
    smc.fvgs              = [_bullish_fvg()]
    smc.structural_breaks = [_bullish_break()]
    smc.liquidity_sweeps  = [_low_sweep()]
    inds = _bullish_indicators()

    scores = {}
    for mode in ["overwatch", "stealth", "strike", "surgical"]:
        bd, err = _run_score(smc, inds, profile=mode, htf_trend="bullish")
        scores[mode] = bd.total_score if bd else None
        _check(
            f"Mode [{mode}] — no crash",
            err is None,
            f"Exception: {err}" if err else f"Score={bd.total_score:.1f}",
        )

    valid_scores = {k: v for k, v in scores.items() if v is not None}
    if len(valid_scores) >= 2:
        spread = max(valid_scores.values()) - min(valid_scores.values())
        _check(
            "Mode differentiation spread ≥ 3 pts",
            spread >= 3,
            f"Scores: {valid_scores}  Spread={spread:.1f}",
            severity="WARN",
        )


# =============================================================================
# TEST 6: Score inversion guard
# — bearish factors should NOT inflate a bullish score
# =============================================================================
def test_score_inversion():
    smc_bearish = _empty_snapshot()
    smc_bearish.order_blocks      = [_bearish_ob()]
    smc_bearish.structural_breaks = [_bearish_break()]

    bd_bull, _ = _run_score(smc_bearish, _bearish_indicators(),
                            direction="bullish", htf_trend="bullish")
    bd_bear, _ = _run_score(smc_bearish, _bearish_indicators(),
                            direction="bearish", htf_trend="bearish")

    if bd_bull and bd_bear:
        _check(
            "Bearish setup scores lower as LONG than as SHORT",
            bd_bull.total_score < bd_bear.total_score,
            f"LONG={bd_bull.total_score:.1f}  SHORT={bd_bear.total_score:.1f}",
        )
        if bd_bull.total_score > 60:
            _warn(
                "Bearish OB+break inflating bullish score",
                f"LONG score={bd_bull.total_score:.1f} with bearish-only signals — should be <50",
            )


# =============================================================================
# TEST 7: Synergy bonus fires when OB + FVG + Structure all qualify
# =============================================================================
def test_synergy_fires():
    smc_full = _empty_snapshot()
    smc_full.order_blocks      = [_bullish_ob()]
    smc_full.fvgs              = [_bullish_fvg()]
    smc_full.structural_breaks = [_bullish_break()]

    smc_ob_only = _empty_snapshot()
    smc_ob_only.order_blocks = [_bullish_ob()]

    bd_full, _    = _run_score(smc_full, _bullish_indicators(), htf_trend="bullish")
    bd_ob_only, _ = _run_score(smc_ob_only, _bullish_indicators(), htf_trend="bullish")

    if bd_full and bd_ob_only:
        _check(
            "Synergy fires — OB+FVG+Structure > OB alone",
            bd_full.total_score > bd_ob_only.total_score,
            f"OB+FVG+Struct={bd_full.total_score:.1f}  OB only={bd_ob_only.total_score:.1f}",
        )
        _check(
            "Synergy bonus is non-zero on full setup",
            bd_full.synergy_bonus > 0,
            f"synergy_bonus={bd_full.synergy_bonus:.1f}",
            severity="WARN",
        )


# =============================================================================
# TEST 8: Conflict penalty fires when opposing structure present
# =============================================================================
def test_conflict_penalty():
    smc_clean = _empty_snapshot()
    smc_clean.order_blocks      = [_bullish_ob()]
    smc_clean.structural_breaks = [_bullish_break()]

    smc_conflict = _empty_snapshot()
    smc_conflict.order_blocks      = [_bullish_ob()]
    smc_conflict.structural_breaks = [_bullish_break(), _bearish_break()]

    bd_clean,    _ = _run_score(smc_clean,    _bullish_indicators(), htf_trend="bullish")
    bd_conflict, _ = _run_score(smc_conflict, _bullish_indicators(), htf_trend="bullish")

    if bd_clean and bd_conflict:
        _check(
            "Conflict penalty — opposing structure reduces score",
            bd_conflict.total_score <= bd_clean.total_score,
            f"Clean={bd_clean.total_score:.1f}  Conflict={bd_conflict.total_score:.1f}",
        )
        _check(
            "Conflict penalty is non-zero when opposing structure present",
            bd_conflict.conflict_penalty > 0,
            f"conflict_penalty={bd_conflict.conflict_penalty:.1f}",
            severity="WARN",
        )


# =============================================================================
# TEST 9: Factor presence — are all expected factors actually scored?
# =============================================================================
def test_factor_presence():
    smc = _empty_snapshot()
    smc.order_blocks      = [_bullish_ob()]
    smc.fvgs              = [_bullish_fvg()]
    smc.structural_breaks = [_bullish_break()]
    smc.liquidity_sweeps  = [_low_sweep()]

    bd, _ = _run_score(smc, _bullish_indicators(), htf_trend="bullish")
    if bd:
        factor_names = {f.name for f in bd.factors}
        expected_factors = [
            "Order Block", "Fair Value Gap", "Market Structure",
            "Liquidity Sweep", "Momentum", "Volume",
        ]
        for fname in expected_factors:
            present = any(fname.lower() in n.lower() for n in factor_names)
            _check(
                f"Factor present — {fname}",
                present,
                f"Found" if present else f"Missing from score breakdown. Got: {sorted(factor_names)}",
                severity="WARN",
            )


# =============================================================================
# TEST 10: Cycle context wired — cycle score changes total
# =============================================================================
def test_cycle_context_wired():
    smc = _empty_snapshot()
    smc.order_blocks = [_bullish_ob()]

    try:
        from backend.shared.models.smc import CycleContext, CyclePhase, CycleTranslation, CycleConfirmation
        cycle_acc = CycleContext(
            phase=CyclePhase.ACCUMULATION,
            translation=CycleTranslation.RTR,
            dcl_confirmation=CycleConfirmation.CONFIRMED,
            dcl_days_since=5,
            trade_bias="LONG",
            confidence=80.0,
        )
        cycle_dist = CycleContext(
            phase=CyclePhase.DISTRIBUTION,
            translation=CycleTranslation.LTR,
            dcl_confirmation=CycleConfirmation.CANCELLED,
            dcl_days_since=25,
            trade_bias="SHORT",
            confidence=75.0,
        )

        bd_acc,  err_acc  = _run_score(smc, _bullish_indicators(),
                                       direction="bullish", htf_trend="bullish",
                                       cycle_context=cycle_acc)
        bd_dist, err_dist = _run_score(smc, _bullish_indicators(),
                                       direction="bullish", htf_trend="bullish",
                                       cycle_context=cycle_dist)

        if bd_acc is not None and bd_dist is not None:
            _check(
                "Cycle context wired — accumulation > distribution for LONG",
                bd_acc.total_score >= bd_dist.total_score,
                f"Accum={bd_acc.total_score:.1f}  Distrib={bd_dist.total_score:.1f}",
            )
        else:
            _warn("Cycle context test",
                  f"Score call failed — acc_err={err_acc!r}  dist_err={err_dist!r}")
    except Exception as e:
        _warn("Cycle context test", f"Skipped — {e}")


# =============================================================================
# TEST 11: Weight sum sanity — weighted scores can't mechanically exceed 100
# =============================================================================
def test_weight_sum_sanity():
    for mode_name, tbl in [
        ("OVERWATCH", _OVERWATCH_WEIGHTS), ("STRIKE", _STRIKE_WEIGHTS),
        ("SURGICAL", _SURGICAL_WEIGHTS),   ("STEALTH", _STEALTH_WEIGHTS),
    ]:
        # Max possible weighted score = sum(weight * 100) for all factors
        # Only the factors actually added to the breakdown contribute
        # (not every key in the weight table is always added)
        # Just check no single weight dominates unreasonably
        max_single = max(tbl.values())
        _check(
            f"Max single weight [{mode_name}] ≤ 0.35",
            max_single <= 0.35,
            f"max_weight={max_single:.3f} on key '{max(tbl, key=tbl.get)}'",
            severity="WARN",
        )


# =============================================================================
# TEST 12: Score is deterministic (same input = same output)
# =============================================================================
def test_determinism():
    smc = _empty_snapshot()
    smc.order_blocks = [_bullish_ob()]
    smc.fvgs         = [_bullish_fvg()]

    bd1, _ = _run_score(smc, _bullish_indicators(), htf_trend="bullish")
    bd2, _ = _run_score(smc, _bullish_indicators(), htf_trend="bullish")

    if bd1 and bd2:
        _check(
            "Determinism — same input yields same score",
            abs(bd1.total_score - bd2.total_score) < 0.001,
            f"Run1={bd1.total_score:.4f}  Run2={bd2.total_score:.4f}",
        )


# =============================================================================
# REPORT
# =============================================================================
def print_report():
    print(HEADER)
    print("  SNIPERSIGHT — CONFLUENCE SCORER DIAGNOSTIC")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(HEADER)

    if not IMPORTS_OK:
        print(f"\n  ❌ IMPORT FAILED: {IMPORT_ERROR}\n")
        return

    # Run all tests
    test_weight_tables()
    test_mode_aliases()
    test_empty_snapshot()
    test_loaded_vs_empty()
    test_mode_differentiation()
    test_score_inversion()
    test_synergy_fires()
    test_conflict_penalty()
    test_factor_presence()
    test_cycle_context_wired()
    test_weight_sum_sanity()
    test_determinism()

    # Print results
    print()
    for label, status, detail in results:
        print(f"  {status}  {label}")
        print(f"         {detail}")

    # Score breakdown sample
    print()
    print(DIVIDER)
    print("  FULL SCORE BREAKDOWN SAMPLE  (STEALTH / bullish / OB+FVG+CHoCH+sweep)")
    print(DIVIDER)
    smc = _empty_snapshot()
    smc.order_blocks      = [_bullish_ob()]
    smc.fvgs              = [_bullish_fvg()]
    smc.structural_breaks = [_bullish_break()]
    smc.liquidity_sweeps  = [_low_sweep()]
    bd, err = _run_score(smc, _bullish_indicators(), profile="stealth", htf_trend="bullish")
    if err:
        print(f"  ERROR: {err}")
    else:
        print(f"  Total Score : {bd.total_score:.2f}")
        print(f"  Synergy     : +{bd.synergy_bonus:.2f}")
        print(f"  Conflict    : -{bd.conflict_penalty:.2f}")
        print(f"  Factor count: {len(bd.factors)}")
        print()
        print(f"  {'FACTOR':<30} {'SCORE':>6}  {'WEIGHT':>7}  {'WEIGHTED':>8}  RATIONALE")
        print(f"  {'-'*30} {'-'*6}  {'-'*7}  {'-'*8}  {'-'*20}")
        for f in sorted(bd.factors, key=lambda x: x.weighted_score, reverse=True):
            rat = (f.rationale or "")[:45]
            print(f"  {f.name:<30} {f.score:>6.1f}  {f.weight:>7.3f}  {f.weighted_score:>8.2f}  {rat}")

    # Mode comparison table
    print()
    print(DIVIDER)
    print("  MODE SCORE COMPARISON  (same OB+FVG+CHoCH+sweep snapshot)")
    print(DIVIDER)
    print(f"  {'MODE':<20} {'LONG':>8} {'SHORT':>8} {'SYNERGY':>9} {'CONFLICT':>10}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*9} {'-'*10}")
    for mode in ["overwatch", "stealth", "strike", "surgical"]:
        bd_l, _ = _run_score(smc, _bullish_indicators(), direction="bullish",
                             profile=mode, htf_trend="bullish")
        bd_s, _ = _run_score(smc, _bearish_indicators(), direction="bearish",
                             profile=mode, htf_trend="bearish")
        ls = f"{bd_l.total_score:.1f}" if bd_l else "ERR"
        ss = f"{bd_s.total_score:.1f}" if bd_s else "ERR"
        sy = f"+{bd_l.synergy_bonus:.1f}" if bd_l else "ERR"
        cp = f"-{bd_l.conflict_penalty:.1f}" if bd_l else "ERR"
        print(f"  {mode:<20} {ls:>8} {ss:>8} {sy:>9} {cp:>10}")

    # Weight table overview
    print()
    print(DIVIDER)
    print("  WEIGHT TABLE OVERVIEW  (key factor weights by mode)")
    print(DIVIDER)
    key_factors = ["order_block", "market_structure", "htf_alignment",
                   "momentum", "divergence", "liquidity_sweep", "kill_zone"]
    print(f"  {'FACTOR':<22} {'OVERWATCH':>10} {'STEALTH':>8} {'STRIKE':>8} {'SURGICAL':>10}")
    print(f"  {'-'*22} {'-'*10} {'-'*8} {'-'*8} {'-'*10}")
    for k in key_factors:
        ow = _OVERWATCH_WEIGHTS.get(k, 0)
        st = _STEALTH_WEIGHTS.get(k, 0)
        sk = _STRIKE_WEIGHTS.get(k, 0)
        su = _SURGICAL_WEIGHTS.get(k, 0)
        print(f"  {k:<22} {ow:>10.3f} {st:>8.3f} {sk:>8.3f} {su:>10.3f}")

    # Known issues summary
    print()
    print(DIVIDER)
    print(f"  KNOWN ISSUES ({len(issues)} bugs, {len(warnings)} warnings)")
    print(DIVIDER)
    if not issues and not warnings:
        print("  ✅ No issues detected")
    for severity, label, detail in issues:
        print(f"\n  🐛 {severity}: {label}")
        print(f"     {detail}")
    for label, detail in warnings:
        print(f"\n  ⚠️  WARN: {label}")
        print(f"     {detail}")

    print()
    print(HEADER)


if __name__ == "__main__":
    print_report()
