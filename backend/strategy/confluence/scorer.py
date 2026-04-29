"""
Confluence Scorer Module

Implements multi-factor confluence scoring system for trade setups.

Evaluates setups across multiple dimensions:
- SMC patterns (order blocks, FVGs, structural breaks, liquidity sweeps)
- Technical indicators (RSI, Stoch RSI, MFI, volume)
- Higher timeframe alignment
- Market regime detection
- BTC impulse gate (for altcoins)
- Mode-aware MACD evaluation (primary/filter/veto based on scanner mode)
- Cycle-aware synergy bonuses (cycle turns, distribution breaks)

Outputs a comprehensive ConfluenceBreakdown with synergy bonuses and conflict penalties.
"""

from typing import List, Dict, Optional, Tuple, TYPE_CHECKING, Any
import json
import time
from datetime import datetime, timezone
from loguru import logger
import threading

from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG, StructuralBreak, LiquiditySweep
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.models.scoring import ConfluenceFactor, ConfluenceBreakdown
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import MACDModeConfig, get_macd_config
from backend.strategy.smc.volume_profile import VolumeProfile, calculate_volume_confluence_factor
from backend.analysis.premium_discount import detect_premium_discount
from backend.analysis.pullback_detector import detect_pullback_setup
from backend.strategy.smc.sessions import get_current_kill_zone
from backend.analysis.macro_context import MacroContext, compute_macro_score
from backend.indicators.divergence import detect_all_divergences
from backend.analysis.fibonacci import (
    calculate_fib_levels,
    find_nearest_fib,
    get_fib_proximity_pct,
)

# === FILE LOGGING FOR CONFLUENCE BREAKDOWN ===
# Uses a RotatingFileHandler so the file never grows unbounded.
# Max 5 MB per file, 3 backups kept (≤15 MB total on disk).

import logging as _stdlib_logging
from logging.handlers import RotatingFileHandler as _RotatingFileHandler

BREAKDOWN_LOG_PATH = "logs/confluence_breakdown.log"
BREAKDOWN_LOG_LOCK = threading.Lock()

def _make_breakdown_logger() -> Optional[_stdlib_logging.Logger]:
    """Create a dedicated rotating-file logger for confluence breakdowns."""
    try:
        import os
        os.makedirs("logs", exist_ok=True)
        _lg = _stdlib_logging.getLogger("confluence_breakdown")
        _lg.setLevel(_stdlib_logging.DEBUG)
        if not _lg.handlers:
            _rh = _RotatingFileHandler(
                BREAKDOWN_LOG_PATH,
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=3,
                encoding="utf-8",
            )
            _rh.setFormatter(_stdlib_logging.Formatter("%(message)s"))
            _lg.addHandler(_rh)
            _lg.propagate = False  # don't bubble up to root logger
        return _lg
    except Exception as _e:
        logger.warning(f"Could not create breakdown logger: {_e}")
        return None

BREAKDOWN_LOG_FILE = _make_breakdown_logger()
if BREAKDOWN_LOG_FILE:
    logger.info(f"📝 Confluence breakdown logging (rotating) to: {BREAKDOWN_LOG_PATH}")

# Conditional imports for type hints
if TYPE_CHECKING:
    from backend.shared.models.smc import CycleContext, ReversalContext
    from backend.shared.models.regime import SymbolRegime


# ==============================================================================
# PRE-SCORING GATE SYSTEM
# ==============================================================================
# Hard gates that run BEFORE the confluence scoring engine.
# If any gate fails, scoring is skipped entirely and the symbol is rejected
# with a reason code. This prevents soft penalties being offset by synergy bonuses.


from dataclasses import dataclass as _dataclass, field as _field


@_dataclass
class GateResult:
    """Result of a pre-scoring gate check."""
    passed: bool
    gate_name: str = ""
    reason: str = ""
    metadata: dict = _field(default_factory=dict)


def run_pre_scoring_gates(
    smc_snapshot: "SMCSnapshot",
    config: "ScanConfig",
    direction: str,
    regime: Optional[Any] = None,
    btc_impulse: Optional[str] = None,
    is_btc: bool = False,
    cycle_context: Optional[Any] = None,
    relevant_timeframes: Optional[set] = None,
) -> GateResult:
    """
    Run all pre-scoring hard gates. Returns on the first failure.

    Gates (in order):
      1. Structural Anchor  — at least one quality OB, FVG, or confirmed Sweep
      2. Regime Alignment   — mode-aware hard block on counter-trend in strong trend
      3. BTC Impulse        — reject alts when BTC in opposing strong impulse
      4. Conflict Density   — reject if 3+ conflict conditions simultaneously active

    Args:
        relevant_timeframes: When provided, conflict_density only counts structures
            from these timeframes. Allows per-scale filtering so scalp trades are not
            blocked by HTF structure irrelevant to their trade duration. When None,
            all timeframes are counted (current default behavior).
    """
    profile = getattr(config, "profile", "stealth_balanced").lower()
    norm_dir = direction.lower()
    is_long = norm_dir in ("long", "bullish")

    # ── Gate 1: Structural Anchor (ALL modes) ──────────────────────────────────
    # At least one of OB (grade A/B, fresh), FVG (grade A/B, size ≥ 1 ATR),
    # or confirmed Sweep must be present.
    #
    # Sweep confirmation threshold is mode-aware:
    #   OVERWATCH / STEALTH — require level ≥ 2 (volume + pattern or 2× volume)
    #   STRIKE / SURGICAL / intraday modes — accept level ≥ 1 (pattern OR volume)
    #     These modes operate in faster, lower-volume conditions where institutional
    #     volume spikes are rare; a reversal pattern alone is sufficient evidence.
    ob_direction = "bullish" if is_long else "bearish"
    fvg_direction = "bullish" if is_long else "bearish"
    sweep_type = "low" if is_long else "high"

    # Profiles that accept a lower sweep confirmation bar (pattern-only counts)
    _SWEEP_LEVEL1_PROFILES = {
        "strike", "intraday_aggressive", "surgical", "precision",
        "intraday_aggressive_alt", "precision_alt",
    }
    _min_sweep_level = 1 if profile in _SWEEP_LEVEL1_PROFILES else 2

    has_quality_ob = any(
        ob.grade in ("A", "B")
        and ob.freshness_score >= 50.0
        and not ob.invalidated
        and ob.direction == ob_direction
        for ob in smc_snapshot.order_blocks
    )
    has_quality_fvg = any(
        fvg.grade in ("A", "B")
        and fvg.size_atr >= 1.0
        and fvg.overlap_with_price < _FVG_FILL_THRESHOLD
        and fvg.direction == fvg_direction
        for fvg in smc_snapshot.fvgs
    )
    has_confirmed_sweep = any(
        s.confirmation_level >= _min_sweep_level and s.sweep_type == sweep_type
        for s in smc_snapshot.liquidity_sweeps
    )

    if not (has_quality_ob or has_quality_fvg or has_confirmed_sweep):
        return GateResult(
            passed=False,
            gate_name="structural_anchor",
            reason=(
                f"No quality structural anchor for {direction}: "
                f"need OB(grade A/B, fresh) or FVG(grade A/B, ≥1 ATR) "
                f"or Sweep(level ≥{_min_sweep_level})"
            ),
            metadata={
                "has_quality_ob": has_quality_ob,
                "has_quality_fvg": has_quality_fvg,
                "has_confirmed_sweep": has_confirmed_sweep,
                "sweep_min_level": _min_sweep_level,
            },
        )

    # ── Gate 2: Regime Alignment (mode-aware hard block) ──────────────────────
    # OVERWATCH/STEALTH: reject counter-trend trades in strong trends (hard block).
    # STRIKE: reject UNLESS a confirmed structure shift (CHoCH) in trade direction exists
    #         — a CHoCH signals the trend is already reversing, validating the fade.
    # SURGICAL: exempt — scalps can fade extremes.
    if profile not in ("surgical", "precision") and regime is not None:
        regime_trend = getattr(regime, "trend", "sideways")

        # OVERWATCH/STEALTH are patient, high-conviction modes — they should never
        # trade against a trending regime even a regular "down/up" trend (not just
        # "strong_down/strong_up"). Entering LONG into a downtrend for these modes
        # caused consecutive losses (e.g. XRP LONG with HTF bearish every scan).
        # STRIKE/intraday_aggressive are faster and can fade trends WITH a CHoCH
        # confirmation, so they only hard-block on "strong" opposing regime.
        _strict_profiles = {"overwatch", "macro_surveillance", "stealth", "stealth_balanced"}
        if profile in _strict_profiles:
            is_strongly_bearish = regime_trend in ("strong_down", "down")
            is_strongly_bullish = regime_trend in ("strong_up", "up")
        else:
            is_strongly_bearish = regime_trend == "strong_down"
            is_strongly_bullish = regime_trend == "strong_up"

        opposing_long  = is_long and is_strongly_bearish
        opposing_short = not is_long and is_strongly_bullish

        if opposing_long or opposing_short:
            # ── WCL / DCL zone bypass (cycle low exceptions) ─────────────────
            # A Weekly Cycle Low (WCL) is exactly the kind of major macro swing
            # bottom that overwatch exists to catch.  When cycle_context confirms
            # we are inside a WCL zone the regime "down" tag reflects the PRIOR
            # trend — not the current opportunity.  Allow counter-trend LONGs
            # through for ALL modes when WCL is active.
            # DCL zones (shorter-term daily cycle lows) grant a bypass only for
            # faster modes (strike / intraday_aggressive) — overwatch should wait
            # for the stronger WCL confirmation.
            _in_wcl = cycle_context is not None and getattr(cycle_context, "in_wcl_zone", False)
            _in_dcl = cycle_context is not None and getattr(cycle_context, "in_dcl_zone", False)
            _wcl_bypass = opposing_long and _in_wcl   # WCL → long bypass for all modes
            _dcl_bypass = (
                opposing_long
                and _in_dcl
                and not _in_wcl  # WCL bypass already covers this
                and profile in ("strike", "intraday_aggressive")
            )

            if _wcl_bypass:
                logger.debug(
                    "Gate 2 WCL bypass: in_wcl_zone → counter-trend LONG allowed (regime=%s, mode=%s)",
                    regime_trend, profile,
                )
                pass  # allow scoring — confluence must still pass
            elif _dcl_bypass:
                logger.debug(
                    "Gate 2 DCL bypass: in_dcl_zone → counter-trend LONG allowed (regime=%s, mode=%s)",
                    regime_trend, profile,
                )
                pass  # allow scoring — confluence must still pass

            # ── STRIKE/intraday_aggressive: CHoCH exception (no cycle zone needed) ──
            elif profile in ("strike", "intraday_aggressive"):
                _confirmed_choch = False
                for _sb in smc_snapshot.structural_breaks:
                    _sb_type = getattr(_sb, "break_type", "").upper()
                    _sb_dir  = getattr(_sb, "direction", "")
                    if _sb_type == "CHOCH":
                        _sb_bullish = _sb_dir in ("bullish", "up", "LONG")
                        if is_long and _sb_bullish:
                            _confirmed_choch = True
                            break
                        if not is_long and not _sb_bullish:
                            _confirmed_choch = True
                            break
                if _confirmed_choch:
                    pass  # CHoCH confirms trend reversal, allow scoring
                else:
                    return GateResult(
                        passed=False,
                        gate_name="regime_alignment",
                        reason=(
                            f"{'LONG' if is_long else 'SHORT'} rejected: regime is "
                            f"{'strong_down' if is_long else 'strong_up'} with no confirming CHoCH (mode={profile})"
                        ),
                        metadata={"regime_trend": regime_trend, "direction": direction, "choch_checked": True},
                    )

            # ── STEALTH/stealth_balanced: CHoCH exception for scalp bounces ──────
            # Stealth is a patient swing mode, so it never trades against a trend
            # for swing/intraday setups. However, a confirmed CHoCH on the 15m+
            # represents a genuine short-term reversal (the engulfing/BOS flip that
            # creates a scalp bounce opportunity). Allowing CHoCH-confirmed counter-
            # trend LONGs through to scoring lets the confluence gate decide whether
            # the bounce has enough quality — overwatch/macro_surveillance remain
            # fully hard-blocked (no scalp cascade, no CHoCH exception).
            elif profile in ("stealth", "stealth_balanced"):
                _confirmed_choch = False
                for _sb in smc_snapshot.structural_breaks:
                    _sb_type = getattr(_sb, "break_type", "").upper()
                    _sb_dir  = getattr(_sb, "direction", "")
                    if _sb_type == "CHOCH":
                        _sb_bullish = _sb_dir in ("bullish", "up", "LONG")
                        if is_long and _sb_bullish:
                            _confirmed_choch = True
                            break
                        if not is_long and not _sb_bullish:
                            _confirmed_choch = True
                            break
                if _confirmed_choch:
                    logger.debug(
                        "Gate 2 stealth CHoCH bypass: confirming CHoCH → counter-trend allowed "
                        "(regime=%s, mode=%s) — confluence gate still applies",
                        regime_trend, profile,
                    )
                    pass  # allow to scoring — confluence + MACD still must clear
                else:
                    return GateResult(
                        passed=False,
                        gate_name="regime_alignment",
                        reason=(
                            f"{'LONG' if is_long else 'SHORT'} rejected: regime is "
                            f"{'strong_down' if is_long else 'strong_up'} with no confirming CHoCH (mode={profile})"
                        ),
                        metadata={"regime_trend": regime_trend, "direction": direction, "choch_checked": True},
                    )
            else:
                # OVERWATCH/macro_surveillance: hard block — no exceptions.
                # These are pure swing modes; counter-trend scalps are out of scope.
                # WCL/DCL bypass above handles the only legitimate counter-trend case.
                return GateResult(
                    passed=False,
                    gate_name="regime_alignment",
                    reason=f"{'LONG' if is_long else 'SHORT'} rejected: regime is {'strong_down' if is_long else 'strong_up'} (mode={profile})",
                    metadata={"regime_trend": regime_trend, "direction": direction},
                )

    # ── Gate 3: BTC Impulse (alts only) ───────────────────────────────────────
    # OVERWATCH / macro_surveillance: bypass this gate.
    #
    # Overwatch targets weekly/daily macro swing setups. A short-term BTC
    # impulse tag (computed from the hourly/daily btc_dir) does not invalidate
    # a weekly demand zone — the macro structure itself is the anchor. If the
    # regime_alignment gate (Gate 2) already rejected a counter-trend setup
    # for overwatch, re-checking BTC's short-term impulse is redundant and
    # causes all alt longs to be killed even when BTC's weekly trend is mixed
    # or the setup is a deep-pullback entry on a confirmed HTF OB.
    _btc_impulse_applies = (
        not is_btc
        and btc_impulse is not None
        and profile not in ("overwatch", "macro_surveillance")
    )
    if _btc_impulse_applies:
        btc_strongly_up = btc_impulse in ("strong_up", "extreme_up")
        btc_strongly_down = btc_impulse in ("strong_down", "extreme_down")
        if is_long and btc_strongly_down:
            return GateResult(
                passed=False,
                gate_name="btc_impulse",
                reason=f"LONG alt rejected: BTC in opposing strong impulse ({btc_impulse})",
                metadata={"btc_impulse": btc_impulse},
            )
        if not is_long and btc_strongly_up:
            # Bypass for BTC dominance expansion: when BTC pumps but the specific
            # alt has its own local bearish regime (down/strong_down), the alt is
            # diverging — not correlated. The gate was designed for correlated moves
            # (BTC pumps → alts pump); it should not block genuinely bearish alts.
            _alt_local_trend = getattr(regime, "trend", "sideways") if regime else "sideways"
            if _alt_local_trend not in ("down", "strong_down"):
                return GateResult(
                    passed=False,
                    gate_name="btc_impulse",
                    reason=f"SHORT alt rejected: BTC in opposing strong impulse ({btc_impulse})",
                    metadata={"btc_impulse": btc_impulse},
                )

    # ── Gate 4: Conflict Density (ALL modes) ──────────────────────────────────
    # Count active conflict signals (opposing structural breaks and OBs).
    # Build a human-readable list of each condition so the UI can surface
    # exactly which structures are causing the conflict, not just the count.
    #
    # IMPORTANT: Only BOS (Break of Structure) counts as a conflict.
    # CHoCH (Change of Character) is a REVERSAL MARKER — it shows where the
    # prior trend already flipped. Counting historical CHoCH patterns as
    # "opposing active conditions" is wrong because:
    #   1. A bearish CHoCH may be what CREATED the long opportunity (sweep +
    #      CHoCH + OB retest is a textbook SMC long setup).
    #   2. CHoCH accumulates across TFs — overwatch's weekly/daily data will
    #      always have several from prior swings, drowning valid setups.
    #   3. Gate 2 (regime alignment) already handles CHoCH for counter-trend
    #      logic; double-penalising here is redundant.
    # BOS confirms trend CONTINUATION in the opposing direction — that is
    # genuinely a reason to question a trade and belongs in this gate.
    conflict_count = 0
    conflict_conditions: list = []

    for sb in smc_snapshot.structural_breaks:
        sb_dir = getattr(sb, "direction", "bullish")
        break_type = getattr(sb, "break_type", "BOS").upper()

        # Skip CHoCH — reversal markers, not continuation signals
        if break_type == "CHOCH":
            continue

        # Skip structures outside the trade's relevant timeframes when scoped
        tf = getattr(sb, "timeframe", None)
        if relevant_timeframes and tf and tf.lower() not in relevant_timeframes:
            continue

        is_opposing = (is_long and sb_dir == "bearish") or (not is_long and sb_dir == "bullish")
        if is_opposing:
            conflict_count += 1
            level = getattr(sb, "level", None) or getattr(sb, "price_level", None)
            label = f"{sb_dir} {break_type}"
            if level is not None:
                label += f" @ {float(level):.4f}"
            if tf:
                label += f" [{tf}]"
            conflict_conditions.append(label)

    for ob in smc_snapshot.order_blocks:
        if ob.direction != ob_direction and not ob.invalidated and ob.grade in ("A", "B"):
            # Skip structures outside the trade's relevant timeframes when scoped
            tf = getattr(ob, "timeframe", None)
            if relevant_timeframes and tf and tf.lower() not in relevant_timeframes:
                continue
            conflict_count += 1
            tf = getattr(ob, "timeframe", None)
            top = getattr(ob, "top", None)
            bot = getattr(ob, "bottom", None)
            level_str = ""
            if top is not None and bot is not None:
                level_str = f" @ {float(bot):.4f}–{float(top):.4f}"
            elif top is not None:
                level_str = f" @ {float(top):.4f}"
            elif bot is not None:
                level_str = f" @ {float(bot):.4f}"
            label = f"{ob.direction} OB({ob.grade}){level_str}"
            if tf:
                label += f" [{tf}]"
            conflict_conditions.append(label)

    # Raise the threshold for overwatch/macro modes: they use weekly/daily data
    # which naturally produces more historical OBs and structural breaks. The
    # standard threshold of 3 fires on every legitimate swing setup and
    # produces nothing but rejections. 5 is still conservative for HTF scans.
    _conflict_threshold = 5 if profile in ("overwatch", "macro_surveillance") else 3

    if conflict_count >= _conflict_threshold:
        return GateResult(
            passed=False,
            gate_name="conflict_density",
            reason=f"{conflict_count} simultaneous conflict conditions detected",
            metadata={
                "conflict_count": conflict_count,
                "conflict_conditions": conflict_conditions,
            },
        )

    return GateResult(passed=True)


# ==============================================================================
# SCORING CALIBRATION CONSTANTS
# ==============================================================================
# Tuning parameters for gradient scoring and category capping.
# Adjust these values to calibrate signal sensitivity and prevent score inflation.

MOMENTUM_SLOPE_MULTIPLIER = 2.0  # Gradient multiplier for RSI/Stoch scoring
VOLUME_RATIO_MULTIPLIER = 20.0  # Multiplier for volume spike scoring
MOMENTUM_CATEGORY_CAP = 40.0  # Max points from momentum category (raised from 25 for extreme RSI signals)
NESTED_OB_CONTAINMENT_MIN = (
    0.5  # Minimum overlap % for nested OB (50% = half of LTF must be inside HTF)
)

# ==============================================================================
# MODE-AWARE PENALTY MULTIPLIERS
# ==============================================================================
# Scales penalties based on mode risk tolerance.
# Conservative modes apply full/heavier penalties, aggressive modes reduce them.

MODE_PENALTY_MULTIPLIERS = {
    "overwatch": 1.2,           # Conservative: heavier penalties
    "macro_surveillance": 1.2,
    "stealth_balanced": 1.0,    # Balanced: standard penalties
    "stealth": 1.0,
    "strike": 0.75,             # Aggressive: reduced penalties
    "intraday_aggressive": 0.75,
    "surgical": 0.6,            # Scalping: minimal penalties
    "precision": 0.6,
}

# FVG fill threshold — above this the gap is considered materially consumed and penalized.
# Must stay in sync with the structural proximity filter in evaluate_htf_structural_proximity().
_FVG_FILL_THRESHOLD = 0.7

# ==============================================================================
# MODE-AWARE SYNERGY CAPS
# ==============================================================================
# Maximum synergy bonus per mode. Aggressive modes allow more synergy to offset penalties.

MODE_SYNERGY_CAPS = {
    "overwatch": 18.0,
    "macro_surveillance": 18.0,
    "stealth_balanced": 15.0,
    "stealth": 15.0,
    "strike": 10.0,             # Tightened from 15 — prevents noise-score inflation past gate
    "intraday_aggressive": 10.0,
    "surgical": 12.0,           # Tightened from 18 — still highest but bounded
    "precision": 12.0,
}



# ==============================================================================
# MODE-SPECIFIC FACTOR WEIGHTS
# ==============================================================================
# Tunes the scoring engine to prioritize factors relevant to each trading style.
#
# OVERWATCH (Swing): HTF alignment, institutional structure, deep confirmation.
# STRIKE (Intraday): Momentum, divergence, structure breaks, flow.
# SURGICAL (Scalp): Precision entries, OB quality, kill zones, close quality.
# STEALTH (Balanced): Balanced spread across all factor categories.
#
# NOTE: Weights are renormalized to sum=1.0 at score calculation time (see
# FINAL WEIGHT NORMALIZATION block in calculate_confluence_score). These values
# represent RELATIVE importance — higher = more influence on the final score.
# Aliases (overwatch, strike, surgical, stealth) reference the same dict as
# their canonical counterpart to guarantee identical behaviour.
#
# COMPLETE FACTOR KEY REFERENCE (all keys used by get_w() in this module):
#   SMC Core:        order_block, fvg, market_structure, liquidity_sweep
#   OB Precision:    inside_ob, nested_ob, opposing_structure
#   Indicators:      momentum, divergence, volume, vwap, volatility
#   Close Quality:   close_momentum, multi_close_confirm
#   MACD:            macd_veto
#   HTF / Regime:    htf_alignment, htf_structure_bias, htf_proximity,
#                    htf_momentum_gate, htf_inflection, regime_alignment
#   BTC / Macro:     btc_impulse, weekly_stoch_rsi, fibonacci
#   Timing:          kill_zone, premium_discount
#   Sequence:        institutional_sequence, multi_tf_reversal, liquidity_draw

_OVERWATCH_WEIGHTS = {
    # --- SMC Core (structural anchors promoted — entry needs a real level) ---
    "order_block":           0.30,  # Primary entry anchor; must be present
    "fvg":                   0.22,  # Secondary anchor; imbalance confirmation
    "market_structure":      0.22,  # BOS/CHoCH; directional bias
    "liquidity_sweep":       0.22,  # Sweep precedes real move; critical for swing
    # --- OB Precision ---
    "inside_ob":             0.10,
    "nested_ob":             0.10,
    "opposing_structure":    0.06,
    # --- Indicators ---
    "momentum":              0.08,
    "divergence":            0.15,
    "volume":                0.10,
    "vwap":                  0.04,
    "volatility":            0.08,
    # --- Close Quality ---
    "close_momentum":        0.06,
    "multi_close_confirm":   0.08,
    # --- MACD ---
    "macd_veto":             0.08,
    # --- HTF / Regime (5 correlated inputs collapsed to 1 composite) ---
    "htf_composite":         0.30,  # Replaces htf_alignment+bias+proximity+momentum+inflection
    "regime_alignment":      0.18,  # Promoted from 0.10 — regime is now a meaningful filter
    # --- BTC / Macro ---
    "btc_impulse":           0.12,
    "weekly_stoch_rsi":      0.12,
    "fibonacci":             0.08,
    # --- Timing ---
    "kill_zone":             0.03,
    "premium_discount":      0.12,
    # --- Sequence ---
    "institutional_sequence": 0.15,
    "multi_tf_reversal":     0.12,
    "liquidity_draw":        0.08,
}

_STRIKE_WEIGHTS = {
    # --- SMC Core (OB/FVG now required contributors — no pure indicator path) ---
    "order_block":           0.22,  # was 0.18 — structural entry level required
    "fvg":                   0.16,  # was 0.12 — imbalance confirmation required
    "market_structure":      0.28,
    "liquidity_sweep":       0.12,
    # --- OB Precision ---
    "inside_ob":             0.10,
    "nested_ob":             0.08,
    "opposing_structure":    0.10,
    # --- Indicators ---
    "momentum":              0.15,
    "divergence":            0.18,
    "volume":                0.10,
    "vwap":                  0.08,
    "volatility":            0.10,
    # --- Close Quality ---
    "close_momentum":        0.08,
    "multi_close_confirm":   0.07,
    # --- MACD ---
    "macd_veto":             0.08,
    # --- HTF / Regime ---
    "htf_composite":         0.15,  # Replaces 5 HTF factors
    "regime_alignment":      0.10,  # was 0.07
    # --- BTC / Macro ---
    "btc_impulse":           0.08,
    "weekly_stoch_rsi":      0.06,
    "fibonacci":             0.05,
    # --- Timing ---
    "kill_zone":             0.08,
    "premium_discount":      0.07,
    # --- Sequence ---
    "institutional_sequence": 0.12,
    "multi_tf_reversal":     0.12,
    "liquidity_draw":        0.12,
}

_SURGICAL_WEIGHTS = {
    # --- SMC Core (entry needs a real level even for scalps) ---
    "order_block":           0.22,  # was 0.15 — scalp entries need a structural level
    "fvg":                   0.16,  # was 0.10
    "market_structure":      0.28,  # was 0.30 — slight reduction to make room
    "liquidity_sweep":       0.10,
    # --- OB Precision ---
    "inside_ob":             0.12,
    "nested_ob":             0.10,
    "opposing_structure":    0.12,
    # --- Indicators ---
    "momentum":              0.12,
    "divergence":            0.10,
    "volume":                0.08,
    "vwap":                  0.05,
    "volatility":            0.12,
    # --- Close Quality ---
    "close_momentum":        0.09,
    "multi_close_confirm":   0.06,
    # --- MACD ---
    "macd_veto":             0.08,
    # --- HTF / Regime (scalp: HTF is a light backdrop only) ---
    "htf_composite":         0.08,  # Replaces 5 HTF factors; low weight for scalps
    "regime_alignment":      0.05,
    # --- BTC / Macro ---
    "btc_impulse":           0.05,
    "weekly_stoch_rsi":      0.03,
    "fibonacci":             0.06,
    # --- Timing ---
    "kill_zone":             0.15,  # Kill zones are high-priority for scalp entries
    "premium_discount":      0.09,
    # --- Sequence ---
    "institutional_sequence": 0.10,
    "multi_tf_reversal":     0.10,
    "liquidity_draw":        0.15,
}

_STEALTH_WEIGHTS = {
    # --- SMC Core ---
    "order_block":           0.18,  # was 0.15
    "fvg":                   0.10,
    "market_structure":      0.20,
    "liquidity_sweep":       0.12,  # was 0.10
    # --- OB Precision ---
    "inside_ob":             0.08,
    "nested_ob":             0.06,
    "opposing_structure":    0.08,
    # --- Indicators ---
    "momentum":              0.10,
    "divergence":            0.10,
    "volume":                0.10,
    "vwap":                  0.05,
    "volatility":            0.05,
    # --- Close Quality ---
    "close_momentum":        0.05,
    "multi_close_confirm":   0.05,
    # --- MACD ---
    "macd_veto":             0.05,
    # --- HTF / Regime ---
    "htf_composite":         0.22,  # Replaces 5 HTF factors
    "regime_alignment":      0.10,  # was 0.08
    # --- BTC / Macro ---
    "btc_impulse":           0.07,
    "weekly_stoch_rsi":      0.06,
    "fibonacci":             0.05,
    # --- Timing ---
    "kill_zone":             0.08,
    "premium_discount":      0.08,
    # --- Sequence ---
    "institutional_sequence": 0.10,
    "multi_tf_reversal":     0.10,
    "liquidity_draw":        0.08,
}

MODE_FACTOR_WEIGHTS = {
    # Canonical mode names
    "macro_surveillance": _OVERWATCH_WEIGHTS,
    "overwatch":          _OVERWATCH_WEIGHTS,   # alias
    "intraday_aggressive": _STRIKE_WEIGHTS,
    "strike":             _STRIKE_WEIGHTS,       # alias
    "precision":          _SURGICAL_WEIGHTS,
    "surgical":           _SURGICAL_WEIGHTS,     # alias
    "stealth_balanced":   _STEALTH_WEIGHTS,
    "stealth":            _STEALTH_WEIGHTS,       # alias
}


# ==============================================================================
# CONFLUENCE OVERRIDE SYSTEM
# ==============================================================================
# Reduces penalties when multiple strong confluence factors align.
# A textbook reversal setup should not be penalized just because it's counter-trend.


def calculate_confluence_override(
    factors: List["ConfluenceFactor"],
    smc: SMCSnapshot,
    mode_config: "ScanConfig",
    direction: str,
    regime: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Calculate penalty reduction based on confluence strength.

    When multiple SMC/indicator confirmations align, penalties should be
    reduced or eliminated. A complete Institutional Sequence (Sweep->Shift->OB)
    provides maximum override.

    Regime-aware: counter-trend trades in strongly trending or compressed markets
    have their override cap halved so regime penalties are never fully wiped out.

    Args:
        factors: List of scored confluence factors
        smc: SMC snapshot with patterns
        mode_config: Scan configuration with mode profile
        direction: Trade direction ('bullish'/'bearish' or 'long'/'short')
        regime: Optional SymbolRegime or MarketRegime for counter-trend cap logic

    Returns:
        Dict with:
            - reduction: 0.0-1.0 (penalty multiplier reduction)
            - triggered_by: str (which override pattern matched)
            - matches: int (number of conditions met)
            - rationale: str (explanation of the override)
    """
    profile = getattr(mode_config, "profile", "balanced").lower()
    
    # Normalize direction
    norm_dir = direction.lower()
    is_long = norm_dir in ("long", "bullish")
    
    # Build factor lookup dict for easy access
    factor_dict = {f.name: f for f in factors}
    
    override_result = {
        "reduction": 0.0,
        "triggered_by": None,
        "matches": 0,
        "rationale": "",
    }
    
    # === UNIVERSAL: Institutional Sequence (highest priority) ===
    # Sweep -> Shift -> OB = complete institutional play
    target_sweep_type = "low" if is_long else "high"
    sweep_confirmed = any(
        getattr(s, "confirmation_level", 1 if s.confirmation else 0) >= 2
        for s in smc.liquidity_sweeps
        if s.sweep_type == target_sweep_type
    )
    
    has_structure_shift = any(
        b.break_type in ("CHoCH", "BOS")
        and getattr(b, "direction", "bullish") == ("bullish" if is_long else "bearish")
        for b in smc.structural_breaks
    )
    
    ob_factor = factor_dict.get("Order Block")
    has_ob = ob_factor is not None and ob_factor.score > 50
    
    inst_seq_matches = sum([sweep_confirmed, has_structure_shift, has_ob])
    if inst_seq_matches >= 3:
        logger.info(
            "🎯 INSTITUTIONAL SEQUENCE OVERRIDE: Sweep=%s, Shift=%s, OB=%s → 100%% penalty reduction",
            sweep_confirmed, has_structure_shift, has_ob
        )
        _inst_reduction = 1.0
        # In sideways/ranging regimes, cap override at 50% so conflict penalties
        # are never fully erased — choppy markets remain costly.
        _regime_composite = getattr(regime, "composite", "") or ""
        if any(s in _regime_composite.lower() for s in ("sideways", "ranging", "chop", "compressed")):
            _inst_reduction = min(_inst_reduction, 0.50)
        return {
            "reduction": _inst_reduction,
            "triggered_by": "institutional_sequence",
            "matches": inst_seq_matches,
            "rationale": "Complete Sweep→Shift→OB sequence detected",
        }
    
    # === MODE-SPECIFIC OVERRIDES ===
    
    # Helper to safely get factor score
    def get_score(name: str) -> float:
        f = factor_dict.get(name)
        return f.score if f else 0.0
    
    if profile in ("strike", "intraday_aggressive"):
        # STRIKE: Momentum + Structure Break
        conditions = [
            get_score("Market Structure") > 70,
            get_score("Momentum") > 50,
            get_score("LTF Structure Shift") > 50,
            get_score("Volume") > 40,
        ]
        matches = sum(conditions)
        if matches >= 3:
            logger.info(
                "🎯 STRIKE OVERRIDE: Structure=%.0f, Mom=%.0f, LTF=%.0f, Vol=%.0f → 80%% reduction",
                get_score("Market Structure"), get_score("Momentum"),
                get_score("LTF Structure Shift"), get_score("Volume")
            )
            return {
                "reduction": 0.80,
                "triggered_by": "strike_momentum_break",
                "matches": matches,
                "rationale": "Momentum-confirmed structure break",
            }
        
        # Divergence reversal (secondary Strike override)
        div_conditions = [
            get_score("Price-Indicator Divergence") > 60,
            get_score("Market Structure") > 50,
            get_score("Momentum") > 40,
        ]
        div_matches = sum(div_conditions)
        if div_matches >= 3:
            return {
                "reduction": 0.75,
                "triggered_by": "strike_divergence_reversal",
                "matches": div_matches,
                "rationale": "Divergence with structural confirmation",
            }
            
    elif profile in ("surgical", "precision"):
        # SURGICAL: Precision Reversal
        conditions = [
            get_score("Market Structure") > 70,
            get_score("LTF Structure Shift") > 60,
            get_score("Close Momentum") > 50,
            get_score("Premium/Discount Zone") > 50,
        ]
        matches = sum(conditions)
        if matches >= 3:
            logger.info(
                "🎯 SURGICAL OVERRIDE: Structure=%.0f, LTF=%.0f, Close=%.0f → 85%% reduction",
                get_score("Market Structure"), get_score("LTF Structure Shift"),
                get_score("Close Momentum")
            )
            return {
                "reduction": 0.85,
                "triggered_by": "surgical_precision",
                "matches": matches,
                "rationale": "Precision entry at validated level",
            }
            
    elif profile in ("overwatch", "macro_surveillance"):
        # OVERWATCH: HTF Structure Confluence
        conditions = [
            get_score("HTF_Structural_Proximity") > 70,
            get_score("Order Block") > 60,
            get_score("Market Structure") > 60,
            get_score("HTF Structure Bias") > 50,
        ]
        matches = sum(conditions)
        if matches >= 3:
            logger.info(
                "🎯 OVERWATCH OVERRIDE: HTF_Prox=%.0f, OB=%.0f, Struct=%.0f → 70%% reduction",
                get_score("HTF_Structural_Proximity"), get_score("Order Block"),
                get_score("Market Structure")
            )
            return {
                "reduction": 0.70,
                "triggered_by": "overwatch_htf_confluence",
                "matches": matches,
                "rationale": "HTF confluence at major structure",
            }
    
    else:  # Stealth/Balanced
        conditions = [
            get_score("Market Structure") > 60,
            get_score("Order Block") > 50,
            get_score("Liquidity Sweep") > 40,
            get_score("HTF Structure Bias") > 40,
        ]
        matches = sum(conditions)
        if matches >= 3:
            return {
                "reduction": 0.60,
                "triggered_by": "stealth_balanced",
                "matches": matches,
                "rationale": "Balanced multi-factor confluence",
            }
    
    # === FALLBACK: Partial override for 2+ strong factors ===
    strong_factors = sum(1 for f in factors if f.score >= 70)
    if strong_factors >= 4:
        return {
            "reduction": 0.40,
            "triggered_by": "strong_factor_density",
            "matches": strong_factors,
            "rationale": f"{strong_factors} factors scored 70+",
        }
    elif strong_factors >= 3:
        return {
            "reduction": 0.25,
            "triggered_by": "moderate_factor_density",
            "matches": strong_factors,
            "rationale": f"{strong_factors} factors scored 70+",
        }

    return override_result


def _apply_sideways_override_cap(result: Dict[str, Any], regime: Optional[Any]) -> Dict[str, Any]:
    """Cap override reduction at 50% in sideways/ranging regimes."""
    _composite = getattr(regime, "composite", "") or ""
    if any(s in _composite.lower() for s in ("sideways", "ranging", "chop", "compressed")):
        result = dict(result)
        result["reduction"] = min(result.get("reduction", 0.0), 0.50)
    return result


# ==============================================================================
# HTF CRITICAL GATES - These filter out low-quality signals
# ==============================================================================


def evaluate_htf_structural_proximity(
    smc: SMCSnapshot,
    indicators: IndicatorSet,
    entry_price: float,
    direction: str,
    mode_config: ScanConfig,
    swing_structure: Optional[Dict] = None,
) -> Dict:
    """
    DIRECTION-AWARE HTF Structural Proximity Gate.

    Validates that entry occurs at a meaningful HTF structural level aligned
    with the trade direction. Penalizes trades that enter into opposing structure.

    Aligned (bonus):
    - LONG: Bullish OB/FVG, Support levels, HL/LL swing points, discount zone
    - SHORT: Bearish OB/FVG, Resistance levels, HH/LH swing points, premium zone

    Opposing (penalty/block):
    - LONG entering into bearish supply OB/resistance = wall above
    - SHORT entering into bullish demand OB/support = floor below
    """
    # Get HTF timeframes from mode config
    structure_tfs = getattr(mode_config, "structure_timeframes", ("4h", "1d"))

    # Get ATR from primary planning timeframe
    primary_tf = getattr(mode_config, "primary_planning_timeframe", "1h")
    primary_ind = _get_tf_indicators(indicators, primary_tf)

    if not primary_ind or not primary_ind.atr:
        return {
            "valid": True,
            "score_adjustment": 0.0,
            "proximity_atr": None,
            "nearest_structure": "ATR unavailable for validation",
            "structure_type": "unknown",
        }

    atr = primary_ind.atr
    max_distance_atr = getattr(mode_config, "htf_proximity_atr", 5.0)

    # Normalize direction
    direction_lower = direction.lower()
    is_bullish = direction_lower in ("long", "bullish")

    # Track aligned structures (support our direction) and opposing structures (walls we'd enter into)
    min_aligned_distance = float("inf")
    nearest_aligned = None
    aligned_type = None

    min_opposing_distance = float("inf")
    nearest_opposing = None
    opposing_type = None

    def _is_aligned_ob(ob_direction: str) -> bool:
        """Bullish OB = demand zone = aligned with long. Bearish OB = supply zone = aligned with short."""
        ob_dir_lower = ob_direction.lower()
        return (is_bullish and ob_dir_lower == "bullish") or (not is_bullish and ob_dir_lower == "bearish")

    # 1. Check HTF Order Blocks (direction-aware)
    for ob in smc.order_blocks:
        if ob.timeframe not in structure_tfs:
            continue
        ob_grade = getattr(ob, "grade", "B")
        if ob_grade not in ("A", "B"):
            continue
        if ob.freshness_score < 50.0:  # freshness_score is 0-100 scale (calculate_freshness returns * 100)
            continue

        ob_center = (ob.high + ob.low) / 2
        # If price is inside the OB, distance is 0
        if ob.low <= entry_price <= ob.high:
            distance_atr = 0.0
        else:
            distance_atr = abs(entry_price - ob_center) / atr

        if _is_aligned_ob(ob.direction):
            if distance_atr < min_aligned_distance:
                min_aligned_distance = distance_atr
                nearest_aligned = f"{ob.timeframe} {ob.direction} OB @ {ob_center:.5f}"
                aligned_type = "OrderBlock"
        else:
            if distance_atr < min_opposing_distance:
                min_opposing_distance = distance_atr
                nearest_opposing = f"{ob.timeframe} {ob.direction} OB @ {ob_center:.5f} (opposing)"
                opposing_type = "OrderBlock_OPPOSING"

    # 2. Check HTF FVGs (direction-aware)
    for fvg in smc.fvgs:
        if fvg.timeframe not in structure_tfs:
            continue
        
        atr_ind = _get_tf_indicators(indicators, fvg.timeframe) or primary_ind
        if not atr_ind or not atr_ind.atr:
            continue

        # Use the FVG's OWN timeframe ATR for the size gate, not the primary entry TF ATR.
        # Bug: previously used `atr` (primary 1H/15m ATR) which caused valid 4H/1D FVGs to be
        # rejected because their absolute gap size was smaller than the entry TF's ATR — even
        # though those FVGs were correctly sized relative to their own timeframe volatility.
        _fvg_atr = atr_ind.atr

        fvg_grade = getattr(fvg, "grade", "B")
        if fvg_grade not in ("A", "B"):
            continue
        if fvg.size < _fvg_atr * 0.3:  # 30% of own-TF ATR — was 100% (too strict, filtered valid FVGs)
            continue
        if fvg.overlap_with_price > _FVG_FILL_THRESHOLD:
            continue

        fvg_dir_lower = fvg.direction.lower()
        is_aligned_fvg = (is_bullish and fvg_dir_lower == "bullish") or (not is_bullish and fvg_dir_lower == "bearish")

        if fvg.bottom <= entry_price <= fvg.top:
            distance_atr = 0.0
        else:
            distance = min(abs(entry_price - fvg.top), abs(entry_price - fvg.bottom))
            distance_atr = distance / atr

        if is_aligned_fvg:
            if distance_atr < min_aligned_distance:
                min_aligned_distance = distance_atr
                nearest_aligned = f"{fvg.timeframe} {fvg.direction} FVG"
                aligned_type = "FVG"
        else:
            if distance_atr < min_opposing_distance:
                min_opposing_distance = distance_atr
                nearest_opposing = f"{fvg.timeframe} {fvg.direction} FVG (opposing)"
                opposing_type = "FVG_OPPOSING"

    # 3. Check Pre-Calculated HTF Levels (direction-aware)
    if hasattr(smc, "htf_levels") and smc.htf_levels:
        for level in smc.htf_levels:
            if not hasattr(level, "price") or not hasattr(level, "level_type"):
                continue
            if level.timeframe not in structure_tfs:
                continue

            distance = abs(entry_price - level.price)
            distance_atr = distance / atr
            lt = level.level_type.lower()

            # Support aligned for longs; resistance aligned for shorts; fib neutral (aligned)
            is_aligned_level = (is_bullish and ("support" in lt or "fib" in lt)) or \
                                (not is_bullish and ("resistance" in lt or "fib" in lt))

            if is_aligned_level:
                if distance_atr < min_aligned_distance:
                    min_aligned_distance = distance_atr
                    nearest_aligned = f"{level.timeframe} {level.level_type.title()} @ {level.price:.5f}"
                    aligned_type = "HTF_Level"
            else:
                if distance_atr < min_opposing_distance:
                    min_opposing_distance = distance_atr
                    nearest_opposing = f"{level.timeframe} {level.level_type.title()} @ {level.price:.5f} (opposing)"
                    opposing_type = "HTF_Level_OPPOSING"

    # 4. Check HTF Swing Points (direction-aware)
    # Longs: HL/LL = support (aligned); HH/LH = resistance (opposing)
    # Shorts: HH/LH = resistance (aligned); HL/LL = support (opposing)
    if swing_structure:
        aligned_swings = ["last_hl", "last_ll"] if is_bullish else ["last_hh", "last_lh"]
        opposing_swings = ["last_hh", "last_lh"] if is_bullish else ["last_hl", "last_ll"]

        for tf in structure_tfs:
            if tf not in swing_structure:
                continue
            ss = swing_structure[tf]

            for swing_type in aligned_swings:
                swing_price = ss.get(swing_type)
                if swing_price:
                    distance_atr = abs(entry_price - swing_price) / atr
                    if distance_atr < min_aligned_distance:
                        min_aligned_distance = distance_atr
                        nearest_aligned = f"{tf} {swing_type.upper()} @ {swing_price:.5f}"
                        aligned_type = "SwingPoint"

            for swing_type in opposing_swings:
                swing_price = ss.get(swing_type)
                if swing_price:
                    distance_atr = abs(entry_price - swing_price) / atr
                    if distance_atr < min_opposing_distance:
                        min_opposing_distance = distance_atr
                        nearest_opposing = f"{tf} {swing_type.upper()} @ {swing_price:.5f} (opposing)"
                        opposing_type = "SwingPoint_OPPOSING"

    # 5. Check Premium/Discount Zone Boundaries
    htf = max(
        structure_tfs,
        key=lambda x: {"5m": 0, "15m": 1, "1h": 2, "4h": 3, "1d": 4, "1w": 5}.get(x, 0),
    )
    htf_ind = _get_tf_indicators(indicators, htf)

    if htf_ind and hasattr(htf_ind, "dataframe"):
        try:
            df = htf_ind.dataframe
            pd_zone = detect_premium_discount(df, lookback=50, current_price=entry_price)

            eq_distance = abs(entry_price - pd_zone.equilibrium)
            eq_distance_atr = eq_distance / atr

            # Equilibrium is an aligned structure if in correct zone
            in_optimal_zone = (is_bullish and entry_price <= pd_zone.equilibrium) or (
                not is_bullish and entry_price >= pd_zone.equilibrium
            )

            if in_optimal_zone and eq_distance_atr < min_aligned_distance:
                min_aligned_distance = eq_distance_atr
                nearest_aligned = f"{htf} Equilibrium @ {pd_zone.equilibrium:.5f}"
                aligned_type = "PremiumDiscount"
            elif not in_optimal_zone and min_aligned_distance > 1.0:
                return {
                    "valid": False,
                    "score_adjustment": -40.0,
                    "proximity_atr": min_aligned_distance if min_aligned_distance != float("inf") else eq_distance_atr,
                    "nearest_structure": f"Entry in {pd_zone.current_zone} zone (wrong for {direction})",
                    "structure_type": "PremiumDiscount_VIOLATION",
                }
        except Exception:
            pass

    # ==========================================================================
    # DIRECTION-AWARE DECISION LOGIC
    # Priority 1: Penalize/block entries into opposing structure (the core fix)
    # ==========================================================================

    if min_opposing_distance <= 0.5:
        # Hard block: entering directly into a wall
        logger.warning(
            "🚫 HTF OPPOSING STRUCTURE BLOCK: %s trade entering into %s (%.2f ATR away)",
            direction,
            nearest_opposing,
            min_opposing_distance,
        )
        return {
            "valid": False,
            "score_adjustment": -25.0,
            "proximity_atr": min_opposing_distance,
            "nearest_structure": nearest_opposing or "Opposing HTF structure",
            "structure_type": opposing_type or "OPPOSING_BLOCK",
        }

    if min_opposing_distance <= 1.5 and min_aligned_distance > 2.0:
        # Soft penalty: approaching an opposing structure without aligned structure nearby
        logger.debug(
            "⚠️ HTF OPPOSING STRUCTURE caution: %.2f ATR from %s",
            min_opposing_distance,
            nearest_opposing,
        )
        return {
            "valid": False,
            "score_adjustment": -10.0,
            "proximity_atr": min_opposing_distance,
            "nearest_structure": nearest_opposing or "Approaching opposing structure",
            "structure_type": opposing_type or "OPPOSING_CAUTION",
        }

    # Priority 2: Reward proximity to aligned structure
    if min_aligned_distance <= max_distance_atr:
        bonus = 0.0
        if min_aligned_distance < 0.5:
            bonus = 15.0
        elif min_aligned_distance < 1.0:
            bonus = 10.0
        elif min_aligned_distance < 1.5:
            bonus = 5.0

        # Reduce bonus if opposing structure is also close (conflicted zone)
        if min_opposing_distance <= 3.0:
            bonus = max(0.0, bonus - 5.0)

        return {
            "valid": True,
            "score_adjustment": bonus,
            "proximity_atr": min_aligned_distance,
            "nearest_structure": nearest_aligned or "HTF aligned structure present",
            "structure_type": aligned_type or "unknown",
        }
    else:
        if min_aligned_distance == float("inf"):
            return {
                "valid": True,
                "score_adjustment": -5.0,
                "proximity_atr": None,
                "nearest_structure": "No aligned HTF structure detected",
                "structure_type": "NONE_FOUND",
            }

        penalty = max(-20.0, -5.0 * (min_aligned_distance - max_distance_atr))
        return {
            "valid": False,
            "score_adjustment": penalty,
            "proximity_atr": min_aligned_distance,
            "nearest_structure": nearest_aligned or "No aligned HTF structure nearby",
            "structure_type": "NONE_NEARBY",
        }


def evaluate_htf_momentum_gate(
    indicators: IndicatorSet,
    direction: str,
    mode_config: ScanConfig,
    swing_structure: Optional[Dict] = None,
    reversal_context: Optional[dict] = None,  # Kept for API compatibility
) -> Dict:
    """
    UNIVERSAL MOMENTUM GATE (FINAL).

    A unified gate that handles Scalp, Intraday, and Swing logic correctly.

    Improvements over basic version:
    1. "Elastic" Timeframes: Checks the *driver* timeframe (e.g. 15m -> 4H), not just the macro.
    2. Mode-Aware Risk:
       - Surgical/Strike: Allows fading standard extensions (RSI 70+).
       - Overwatch: Requires EXTREME extensions (RSI 80+) to fade.
    3. Climax Logic: Distinguishes between "Strong Trend" (Block Fades) and "Parabolic" (Allow Fades).
    """

    # 1. MODE IDENTIFICATION & SETTINGS
    profile = getattr(mode_config, "profile", "balanced")
    mode_name = getattr(mode_config, "name", "stealth").lower()

    # Defaults
    momentum_tf = "4h"
    fade_threshold_rsi = 75.0  # Standard extension

    # Configure per Mode
    if mode_name == "overwatch" or profile == "macro_surveillance":
        # SWING: Look at Daily. Hard to turn. Needs extreme evidence.
        # FIX: was 75.0 → threshold = 25. RSI 26 wasn't recognized as oversold for fades.
        # Changed to 70.0 → threshold = 30, aligning with industry standard.
        momentum_tf = "1d"
        fade_threshold_rsi = 70.0

    elif mode_name == "stealth" or profile == "stealth_balanced":
        # BALANCED: Look at 4H.
        # FIX: was 75.0 → threshold = 100-75 = 25. RSI 26 (deep oversold) wasn't triggering climax.
        # Changed to 70.0 → threshold = 30, matching standard oversold definition.
        momentum_tf = "4h"
        fade_threshold_rsi = 70.0

    elif mode_name in ["surgical", "strike"] or profile in ("precision", "intraday_aggressive"):
        # SCALP: Look at 1H/4H. Quick turns allowed.
        momentum_tf = "1h"
        fade_threshold_rsi = 70.0  # RSI > 70 is enough for a scalp fade

    # 2. GET DATA
    # Elastic fallback if specific TF is missing
    ind = _get_tf_indicators(indicators, momentum_tf)
    if not ind:
        # Fallback to any available timeframe if the preferred one is missing
        available = sorted(
            list(indicators.by_timeframe.keys()),
            key=lambda x: {
                "1m": 1,
                "5m": 5,
                "15m": 15,
                "1h": 60,
                "4h": 240,
                "1d": 1440,
                "1w": 10080,
            }.get(x, 0),
        )
        momentum_tf = available[-1] if available else None
        ind = _get_tf_indicators(indicators, momentum_tf) if momentum_tf else None

    if not ind:
        return {
            "allowed": True,
            "score_adjustment": 0.0,
            "htf_momentum": "unknown",
            "htf_trend": "unknown",
            "reason": "No indicator data available",
        }

    # 3. ANALYZE MOMENTUM
    adx = getattr(ind, "adx", None)
    rsi = getattr(ind, "rsi", 50.0)

    # Determine Trend Strength (0-100)
    momentum_state = "neutral"

    if adx is not None:
        if adx > 50:
            momentum_state = "extreme"
        elif adx > 30:
            momentum_state = "strong"
        elif adx > 20:
            momentum_state = "building"
        else:
            momentum_state = "weak"
    else:
        # Fallback to ATR Slope
        atr_series = getattr(ind, "atr_series", None) or []
        if len(atr_series) >= 5:
            slope = (atr_series[-1] - atr_series[0]) / atr_series[0] if atr_series[0] > 0 else 0
            if slope > 0.10:
                momentum_state = "strong"
            elif slope > 0.02:
                momentum_state = "building"

    # 4. ALIGNMENT CHECK
    htf_trend_dir = "neutral"
    if swing_structure and momentum_tf in swing_structure:
        htf_trend_dir = swing_structure[momentum_tf].get("trend", "neutral")
    # Also check uppercase version for compatibility
    if htf_trend_dir == "neutral" and swing_structure and momentum_tf.upper() in swing_structure:
        htf_trend_dir = swing_structure[momentum_tf.upper()].get("trend", "neutral")

    is_long = direction.lower() in ("bullish", "long")

    # Define alignment
    is_aligned = (is_long and htf_trend_dir == "bullish") or (
        not is_long and htf_trend_dir == "bearish"
    )
    is_opposed = (is_long and htf_trend_dir == "bearish") or (
        not is_long and htf_trend_dir == "bullish"
    )

    # === LOGIC BRANCHES ===

    # A. TREND FOLLOWING (Aligned)
    if is_aligned:
        # Overwatch/Trend modes love strong momentum
        if momentum_state in ["strong", "extreme"]:
            bonus = 20.0 if mode_name == "overwatch" else 15.0
            return {
                "allowed": True,
                "score_adjustment": bonus,
                "htf_momentum": momentum_state,
                "htf_trend": htf_trend_dir,
                "reason": f"Perfect alignment with strong {momentum_tf} momentum",
            }
        elif momentum_state == "building":
            return {
                "allowed": True,
                "score_adjustment": 10.0,
                "htf_momentum": momentum_state,
                "htf_trend": htf_trend_dir,
                "reason": f"{momentum_tf} momentum building in direction",
            }
        else:
            return {
                "allowed": True,
                "score_adjustment": 0.0,
                "htf_momentum": momentum_state,
                "htf_trend": htf_trend_dir,
                "reason": f"Aligned with {htf_trend_dir} {momentum_tf} trend",
            }

    # B. COUNTER-TREND (Opposed)
    if is_opposed:
        # 0. Check for HTF Hidden Divergence — continuation signal that justifies
        #    counter-trend entry without needing RSI climax
        htf_hidden_div = False
        if hasattr(ind, "dataframe") and ind.dataframe is not None and len(ind.dataframe) >= 50:
            try:
                htf_divs = detect_all_divergences(
                    df=ind.dataframe,
                    direction=direction,
                    lookback=5,
                    min_pivot_distance=10,
                    max_lookback_bars=100,
                )
                htf_hidden_div = bool(
                    any("hidden" in d.divergence_type for d in htf_divs.get("rsi", []))
                    or any("hidden" in d.divergence_type for d in htf_divs.get("macd", []))
                )
            except Exception:
                pass

        if htf_hidden_div:
            return {
                "allowed": True,
                "score_adjustment": 15.0,
                "htf_momentum": momentum_state,
                "htf_trend": htf_trend_dir,
                "reason": f"HTF hidden divergence on {momentum_tf} justifies counter-trend entry",
            }

        # 1. Check for CLIMAX (The only valid reason to fade a strong trend)
        is_climax = False
        current_rsi = rsi if rsi else 50.0

        if is_long:  # Trying to catch a bottom
            # Oversold condition
            threshold = 100.0 - fade_threshold_rsi  # e.g., 30 or 20
            if current_rsi < threshold:
                is_climax = True
        else:  # Trying to catch a top
            # Overbought condition
            if current_rsi > fade_threshold_rsi:
                is_climax = True

        # 2. Decision Time
        if is_climax:
            # ALLOW the fade, specifically because it's overextended
            # Bonus usually higher for Scalp modes (they thrive on this)
            climax_bonus = 10.0 if mode_name in ["surgical", "strike"] else 5.0

            return {
                "allowed": True,
                "score_adjustment": climax_bonus,
                "htf_momentum": momentum_state,
                "htf_trend": htf_trend_dir,
                "reason": f"CLIMAX DETECTED: {momentum_tf} RSI {current_rsi:.1f} allows counter-trend fade",
            }

        elif momentum_state in ["strong", "extreme", "building"]:
            # BLOCK the fade. Trend is strong and NOT overextended.
            # This is the "Suicide Prevention" block.
            penalty = -100.0 if mode_name == "overwatch" else -40.0

            return {
                "allowed": False,
                "score_adjustment": penalty,
                "htf_momentum": momentum_state,
                "htf_trend": htf_trend_dir,
                "reason": f"BLOCKED: Fighting strong {momentum_tf} trend without climax (RSI {current_rsi:.1f})",
            }

        else:
            # Trend is weak/neutral. Counter-trading allowed but risky.
            return {
                "allowed": True,
                "score_adjustment": -5.0,  # Small penalty for counter-trend
                "htf_momentum": momentum_state,
                "htf_trend": htf_trend_dir,
                "reason": f"Counter-trend allowed (weak {momentum_tf} momentum)",
            }

    # C. NEUTRAL/CHOP
    return {
        "allowed": True,
        "score_adjustment": 0.0,
        "htf_momentum": momentum_state,
        "htf_trend": htf_trend_dir,
        "reason": f"{momentum_tf} context neutral",
    }


def resolve_timeframe_conflicts(
    indicators: IndicatorSet,
    direction: str,
    mode_config: ScanConfig,
    swing_structure: Optional[Dict] = None,
    htf_proximity: Optional[Dict] = None,
) -> Dict:
    """
    Resolve timeframe conflicts with explicit hierarchical rules.
    """
    profile = getattr(mode_config, "profile", "balanced")
    is_scalp_mode = profile in ("intraday_aggressive", "precision")
    is_swing_mode = profile in ("macro_surveillance", "stealth_balanced")

    conflicts = []
    resolution_reason_parts = []
    score_adjustment = 0.0
    resolution = "allowed"

    # Get all timeframe trends
    timeframes = ["1w", "1d", "4h", "1h", "15m"]
    tf_trends = {}

    for tf in timeframes:
        if swing_structure and tf in swing_structure:
            ss = swing_structure[tf]
            tf_trends[tf] = ss.get("trend", "neutral")

    # Define primary bias TF based on mode
    if is_scalp_mode:
        primary_tf = "1h"
        filter_tfs = ["4h"]
    elif is_swing_mode:
        primary_tf = "4h"
        filter_tfs = ["1d", "1w"]
    else:
        primary_tf = "1h"
        filter_tfs = ["4h", "1d"]

    primary_trend = tf_trends.get(primary_tf, "neutral")
    is_bullish_trade = direction.lower() in ("bullish", "long")

    # Check alignment with tiered scoring
    if primary_trend == "neutral":
        # Ranging/no data - slight caution, not full conflict
        score_adjustment -= 5.0
        resolution_reason_parts.append(f"Primary TF ({primary_tf}) neutral/ranging")
        resolution = "caution"
    elif (is_bullish_trade and primary_trend == "bearish") or (
        not is_bullish_trade and primary_trend == "bullish"
    ):
        # Actual conflict - larger penalty
        conflicts.append(f"{primary_tf} {primary_trend} (primary)")
        resolution_reason_parts.append(
            f"Primary TF ({primary_tf}) {primary_trend} conflicts with {direction}"
        )
        score_adjustment -= 10.0
        resolution = "caution"
    # else: aligned - no penalty

    # Check filter timeframes
    for tf in filter_tfs:
        if tf not in tf_trends:
            continue

        htf_trend = tf_trends[tf]
        htf_aligned = (is_bullish_trade and htf_trend == "bullish") or (
            not is_bullish_trade and htf_trend == "bearish"
        )

        if not htf_aligned and htf_trend != "neutral":
            conflicts.append(f"{tf} {htf_trend}")

            htf_ind = _get_tf_indicators(indicators, tf)
            is_strong_momentum = False

            if htf_ind and htf_ind.atr:
                atr_series = getattr(htf_ind, "atr_series", [])
                if len(atr_series) >= 5:
                    recent_atr = atr_series[-5:]
                    expanding_bars = sum(
                        1 for i in range(1, len(recent_atr)) if recent_atr[i] > recent_atr[i - 1]
                    )
                    is_strong_momentum = expanding_bars >= 4

            if is_strong_momentum:
                resolution = "blocked"
                score_adjustment -= 40.0
                resolution_reason_parts.append(
                    f"{tf} in strong {htf_trend} momentum, blocking {direction}"
                )
                break
            else:
                resolution = "caution"
                score_adjustment -= 10.0
                resolution_reason_parts.append(f"{tf} {htf_trend} but not strong momentum")

    # Exception: At major HTF structure, reduce penalty
    proximity_atr = htf_proximity.get("proximity_atr") if htf_proximity else None
    if (
        htf_proximity
        and htf_proximity.get("valid")
        and proximity_atr is not None
        and proximity_atr < 1.0
    ):
        score_adjustment += 15.0
        resolution_reason_parts.append("At major HTF structure (overrides conflict penalty)")
        if resolution == "blocked" and score_adjustment > -30.0:
            resolution = "caution"

    if not conflicts:
        resolution = "allowed"
        # Check for positive alignment to award bonus
        # If primary is aligned and at least one HTF is aligned (and none conflict)
        is_primary_aligned = (is_bullish_trade and primary_trend == "bullish") or (
            not is_bullish_trade and primary_trend == "bearish"
        )

        has_htf_alignment = False
        for tf in filter_tfs:
            htf_trend = tf_trends.get(tf, "neutral")
            if (is_bullish_trade and htf_trend == "bullish") or (
                not is_bullish_trade and htf_trend == "bearish"
            ):
                has_htf_alignment = True
                break

        if is_primary_aligned:
            score_adjustment += 25.0
            if has_htf_alignment:
                score_adjustment += 25.0  # Total +50 (Score 100)
                resolution_reason_parts.append("Perfect multi-timeframe alignment")
            else:
                resolution_reason_parts.append("Primary timeframe aligned")
        else:
            resolution_reason_parts.append("No conflicts (neutral alignment)")

    return {
        "resolution": resolution,
        "score_adjustment": score_adjustment,
        "conflicts": conflicts,
        "resolution_reason": (
            "; ".join(resolution_reason_parts) if resolution_reason_parts else "No conflicts"
        ),
    }


# --- Mode-Aware MACD Evaluation ---


def evaluate_macd_for_mode(
    indicators: IndicatorSnapshot,
    direction: str,
    macd_config: MACDModeConfig,
    htf_indicators: Optional[IndicatorSnapshot] = None,
    timeframe: str = "15m",
) -> Dict:
    """
    Evaluate MACD based on scanner mode configuration.

    Different modes use MACD differently:
    - HTF/Swing (treat_as_primary=True): MACD drives directional scoring (high weight)
    - Balanced (treat_as_primary=False): MACD is weighted confluence factor
    - Scalp/Surgical (allow_ltf_veto=True): HTF MACD for bias, LTF only vetoes

    Args:
        indicators: Current timeframe indicators with MACD data
        direction: Trade direction ("bullish" or "bearish")
        macd_config: Mode-specific MACD configuration
        htf_indicators: Higher timeframe indicators for HTF bias (optional)
        timeframe: Current timeframe string for logging

    Returns:
        Dict with score, reasons, role, and veto_active flag
    """
    score = 0.0  # Start at 0 (neutral). Veto must push below 0 to be meaningful.
    reasons = []
    veto_active = False
    role = "PRIMARY" if macd_config.treat_as_primary else "FILTER"

    # Extract MACD values
    macd_line = getattr(indicators, "macd_line", None)
    macd_signal = getattr(indicators, "macd_signal", None)
    macd_histogram = getattr(indicators, "macd_histogram", None)
    macd_line_series = getattr(indicators, "macd_line_series", None) or []
    macd_signal_series = getattr(indicators, "macd_signal_series", None) or []
    histogram_series = getattr(indicators, "macd_histogram_series", None) or []

    if macd_line is None or macd_signal is None:
        return {
            "score": 0.0,
            "reasons": ["MACD data unavailable"],
            "role": role,
            "veto_active": False,
        }

    # Check minimum amplitude filter (avoid chop)
    amplitude = abs(macd_line - macd_signal)
    if macd_config.min_amplitude > 0 and amplitude < macd_config.min_amplitude:
        return {
            "score": 0.0,
            "reasons": ["MACD in chop zone (below amplitude threshold)"],
            "role": "NEUTRAL",
            "veto_active": False,
        }

    is_bullish = direction.lower() in ("bullish", "long")

    # --- HTF Bias Check (if enabled and HTF indicators available) ---
    # Incremental scoring based on 3 factors:
    # 1. MACD vs Signal (crossover position)
    # 2. Zero-line position (bullish/bearish momentum context)
    # 3. Histogram slope (momentum building vs waning)
    htf_bias = "neutral"
    htf_bias_score = 0.0
    htf_bias_reasons = []
    
    if macd_config.use_htf_bias and htf_indicators:
        htf_macd = getattr(htf_indicators, "macd_line", None)
        htf_signal = getattr(htf_indicators, "macd_signal", None)
        htf_histogram = getattr(htf_indicators, "macd_histogram", None)
        htf_histogram_series = getattr(htf_indicators, "macd_histogram_series", None) or []

        if htf_macd is not None and htf_signal is not None:
            # Factor 1: MACD vs Signal position (±6 points)
            if htf_macd > htf_signal:
                crossover_bias = "bullish"
                htf_bias_reasons.append("MACD>Signal(bullish)")
            elif htf_macd < htf_signal:
                crossover_bias = "bearish"
                htf_bias_reasons.append("MACD<Signal(bearish)")
            else:
                crossover_bias = "neutral"
            
            # Factor 2: Zero-line position (±5 points)
            if htf_macd > 0:
                zero_bias = "bullish"
                htf_bias_reasons.append("above_zero")
            elif htf_macd < 0:
                zero_bias = "bearish"
                htf_bias_reasons.append("below_zero")
            else:
                zero_bias = "neutral"
            
            # Factor 3: Histogram slope (±4 points)
            hist_slope = "neutral"
            if len(htf_histogram_series) >= 2:
                curr_hist = htf_histogram_series[-1]
                prev_hist = htf_histogram_series[-2]
                if curr_hist > prev_hist:
                    hist_slope = "rising"  # Momentum building
                    htf_bias_reasons.append("hist_rising")
                elif curr_hist < prev_hist:
                    hist_slope = "falling"  # Momentum waning
                    htf_bias_reasons.append("hist_falling")
            elif htf_histogram is not None:
                # Fallback: positive histogram = bullish momentum building
                if htf_histogram > 0:
                    hist_slope = "rising"
                    htf_bias_reasons.append("hist>0")
                else:
                    hist_slope = "falling"
                    htf_bias_reasons.append("hist<0")
            
            # Determine overall HTF bias based on majority vote
            bullish_count = sum([
                crossover_bias == "bullish",
                zero_bias == "bullish",
                hist_slope == "rising"
            ])
            bearish_count = sum([
                crossover_bias == "bearish",
                zero_bias == "bearish",
                hist_slope == "falling"
            ])
            
            if bullish_count >= 2:
                htf_bias = "bullish"
            elif bearish_count >= 2:
                htf_bias = "bearish"
            else:
                htf_bias = "mixed"  # Conflicting signals
            
            # --- Incremental Scoring ---
            # For bullish trades:
            #   Bullish factors add points, bearish factors subtract
            # For bearish trades:
            #   Bearish factors add points, bullish factors subtract
            
            if is_bullish:
                # Factor 1: Crossover (±6 pts)
                if crossover_bias == "bullish":
                    htf_bias_score += 6.0
                elif crossover_bias == "bearish":
                    htf_bias_score -= 6.0
                
                # Factor 2: Zero-line (±5 pts)
                if zero_bias == "bullish":
                    htf_bias_score += 5.0
                elif zero_bias == "bearish":
                    htf_bias_score -= 5.0
                
                # Factor 3: Histogram slope (±4 pts)
                if hist_slope == "rising":
                    htf_bias_score += 4.0
                elif hist_slope == "falling":
                    htf_bias_score -= 4.0
            else:  # Bearish trade
                # Factor 1: Crossover (±6 pts)
                if crossover_bias == "bearish":
                    htf_bias_score += 6.0
                elif crossover_bias == "bullish":
                    htf_bias_score -= 6.0
                
                # Factor 2: Zero-line (±5 pts)
                if zero_bias == "bearish":
                    htf_bias_score += 5.0
                elif zero_bias == "bullish":
                    htf_bias_score -= 5.0
                
                # Factor 3: Histogram slope (±4 pts)
                if hist_slope == "falling":
                    htf_bias_score += 4.0
                elif hist_slope == "rising":
                    htf_bias_score -= 4.0
            
            # Apply weighted score
            score += htf_bias_score * macd_config.weight
            
            # Generate descriptive reason
            if htf_bias_score > 0:
                reasons.append(f"HTF MACD supports {direction} (+{htf_bias_score:.0f}): {', '.join(htf_bias_reasons)}")
            elif htf_bias_score < 0:
                reasons.append(f"HTF MACD conflicts with {direction} ({htf_bias_score:.0f}): {', '.join(htf_bias_reasons)}")
            else:
                reasons.append(f"HTF MACD neutral for {direction}: {', '.join(htf_bias_reasons)}")

    # --- Persistence Check ---
    # Check if MACD/Signal relationship held for min_persistence_bars
    n_persist = min(
        macd_config.min_persistence_bars, len(macd_line_series), len(macd_signal_series)
    )

    bullish_persistent = False
    bearish_persistent = False

    if (
        n_persist >= 2
        and len(macd_line_series) >= n_persist
        and len(macd_signal_series) >= n_persist
    ):
        recent_macd = macd_line_series[-n_persist:]
        recent_signal = macd_signal_series[-n_persist:]
        bullish_persistent = all(m > s for m, s in zip(recent_macd, recent_signal))
        bearish_persistent = all(m < s for m, s in zip(recent_macd, recent_signal))

    # --- Primary vs Filter Scoring ---
    if macd_config.treat_as_primary:
        # HTF/Swing mode: MACD is a decision-maker with heavy impact
        if is_bullish and bullish_persistent:
            score += 25.0 * macd_config.weight
            reasons.append(f"{timeframe} MACD > Signal with {n_persist}-bar persistence (PRIMARY)")
            if macd_line > 0:
                score += 10.0 * macd_config.weight
                reasons.append(f"{timeframe} MACD above zero line (strong bullish)")
        elif not is_bullish and bearish_persistent:
            score += 25.0 * macd_config.weight
            reasons.append(f"{timeframe} MACD < Signal with {n_persist}-bar persistence (PRIMARY)")
            if macd_line < 0:
                score += 10.0 * macd_config.weight
                reasons.append(f"{timeframe} MACD below zero line (strong bearish)")
        elif (is_bullish and bearish_persistent) or (not is_bullish and bullish_persistent):
            score -= 20.0 * macd_config.weight
            reasons.append(
                f"{timeframe} MACD opposing direction with persistence (PRIMARY CONFLICT)"
            )
        else:
            # No persistence - current bar only
            if is_bullish and macd_line > macd_signal:
                score += 8.0 * macd_config.weight
                reasons.append(f"{timeframe} MACD > Signal (no persistence)")
            elif not is_bullish and macd_line < macd_signal:
                score += 8.0 * macd_config.weight
                reasons.append(f"{timeframe} MACD < Signal (no persistence)")
    else:
        # Filter/Veto mode: MACD supports but doesn't drive
        if is_bullish and bullish_persistent:
            score += 10.0 * macd_config.weight
            reasons.append(f"{timeframe} MACD supportive bullish (FILTER)")
        elif not is_bullish and bearish_persistent:
            score += 10.0 * macd_config.weight
            reasons.append(f"{timeframe} MACD supportive bearish (FILTER)")
        elif macd_config.allow_ltf_veto:
            # Check for veto conditions
            if is_bullish and bearish_persistent:
                score -= 15.0 * macd_config.weight
                veto_active = True
                role = "VETO"
                reasons.append(f"{timeframe} MACD bearish veto active against bullish setup")
            elif not is_bullish and bullish_persistent:
                score -= 15.0 * macd_config.weight
                veto_active = True
                role = "VETO"
                reasons.append(f"{timeframe} MACD bullish veto active against bearish setup")

    # --- Histogram Analysis (if strict mode enabled) ---
    if macd_config.use_histogram_strict and len(histogram_series) >= 2:
        hist_expanding = histogram_series[-1] > histogram_series[-2]
        hist_contracting = histogram_series[-1] < histogram_series[-2]

        # Histogram should expand in trend direction
        if is_bullish:
            if macd_histogram and macd_histogram > 0 and hist_expanding:
                score += 8.0 * macd_config.weight
                reasons.append(f"{timeframe} histogram expanding bullish")
            elif macd_histogram and macd_histogram < 0 and hist_contracting:
                score -= 5.0 * macd_config.weight
                reasons.append(f"{timeframe} histogram contracting against bullish")
        else:
            if macd_histogram and macd_histogram < 0 and hist_expanding:
                # For bearish, "expanding" means histogram getting more negative
                score += 8.0 * macd_config.weight
                reasons.append(f"{timeframe} histogram expanding bearish")
            elif macd_histogram and macd_histogram > 0 and hist_contracting:
                score -= 5.0 * macd_config.weight
                reasons.append(f"{timeframe} histogram contracting against bearish")

    # Clamp score: allow negative values if veto is active, otherwise clamp to 0
    if veto_active:
        score = max(-50.0, min(100.0, score))
    else:
        score = max(0.0, min(100.0, score))

    return {
        "score": score,
        "reasons": reasons,
        "role": role,
        "veto_active": veto_active,
        "htf_bias": htf_bias,
        "persistent_bars": n_persist if (bullish_persistent or bearish_persistent) else 0,
    }


def evaluate_weekly_stoch_rsi_bonus(
    indicators: IndicatorSet,
    direction: str,
    oversold_threshold: float = 20.0,
    overbought_threshold: float = 80.0,
    max_bonus: float = 15.0,
    max_penalty: float = 10.0,
) -> Dict:
    """
    Evaluate Weekly StochRSI as a directional BONUS system (not a hard gate).

    This function calculates a score bonus/penalty based on Weekly StochRSI position
    and crossover events. It influences direction selection through scoring, not gating.

    Bonus Logic:
    - K line crossing ABOVE 20 (from oversold): +15 bonus for LONG, -10 for SHORT
    - K line crossing BELOW 80 (from overbought): +15 bonus for SHORT, -10 for LONG
    - K in oversold zone (<20): +10 for LONG (anticipation), +5 for SHORT (momentum)
    - K in overbought zone (>80): +10 for SHORT (anticipation), +5 for LONG (momentum)
    - K in neutral zone (20-80): No bonus either direction

    The bonus system means BOTH directions can still trade, but the direction aligned
    with Weekly StochRSI gets a meaningful score advantage.

    Args:
        indicators: Technical indicators across timeframes (must contain '1W')
        direction: Trade direction ("bullish" or "bearish")
        oversold_threshold: K value below this is oversold (default 20)
        overbought_threshold: K value above this is overbought (default 80)
        max_bonus: Maximum bonus for aligned direction (default 15)
        max_penalty: Maximum penalty for contra direction (default 10)

    Returns:
        Dict with:
            - bonus: float - score adjustment for this direction (can be negative)
            - reason: str - explanation of bonus calculation
            - weekly_k: float - current Weekly StochRSI K value
            - weekly_k_prev: float - previous Weekly StochRSI K value
            - crossover_type: str - 'bullish_cross', 'bearish_cross', 'entering_oversold',
                              'entering_overbought', 'in_oversold', 'in_overbought', 'neutral'
            - aligned: bool - whether this direction is aligned with Weekly StochRSI
    """
    result = {
        "bonus": 0.0,
        "reason": "Weekly StochRSI data unavailable",
        "weekly_k": None,
        "weekly_k_prev": None,
        "crossover_type": "neutral",
        "aligned": True,  # Default to aligned if no data
    }

    # Get weekly indicators - explicit None checks to avoid potential truthiness errors
    weekly_ind = _get_tf_indicators(indicators, "1W")
    if not weekly_ind:
        return result

    # Get current and previous K values
    k_current = getattr(weekly_ind, "stoch_rsi_k", None)
    if k_current is None:
        k_current = getattr(weekly_ind, "stoch_rsi", None)
    k_prev = getattr(weekly_ind, "stoch_rsi_k_prev", None)

    if k_current is None:
        return result

    result["weekly_k"] = k_current
    result["weekly_k_prev"] = k_prev

    is_bullish = direction.lower() in ("bullish", "long")

    # === CROSSOVER DETECTION (requires previous value) ===
    if k_prev is not None:
        # Bullish crossover: K crosses UP through oversold threshold (20)
        bullish_cross = k_prev < oversold_threshold and k_current >= oversold_threshold

        # Bearish crossover: K crosses DOWN through overbought threshold (80)
        bearish_cross = k_prev > overbought_threshold and k_current <= overbought_threshold

        # Entering oversold (bearish momentum building)
        entering_oversold = k_prev >= oversold_threshold and k_current < oversold_threshold

        # Entering overbought (bullish momentum building)
        entering_overbought = k_prev <= overbought_threshold and k_current > overbought_threshold

        if bullish_cross:
            result["crossover_type"] = "bullish_cross"
            if is_bullish:
                result["bonus"] = max_bonus
                result["aligned"] = True
                result["reason"] = (
                    f"Weekly StochRSI bullish cross ({k_prev:.1f}→{k_current:.1f}) - LONG strongly favored (+{max_bonus:.0f})"
                )
            else:
                result["bonus"] = -max_penalty
                result["aligned"] = False
                result["reason"] = (
                    f"Weekly StochRSI bullish cross conflicts with SHORT (-{max_penalty:.0f})"
                )

        elif bearish_cross:
            result["crossover_type"] = "bearish_cross"
            if not is_bullish:
                result["bonus"] = max_bonus
                result["aligned"] = True
                result["reason"] = (
                    f"Weekly StochRSI bearish cross ({k_prev:.1f}→{k_current:.1f}) - SHORT strongly favored (+{max_bonus:.0f})"
                )
            else:
                result["bonus"] = -max_penalty
                result["aligned"] = False
                result["reason"] = (
                    f"Weekly StochRSI bearish cross conflicts with LONG (-{max_penalty:.0f})"
                )

        elif entering_oversold:
            result["crossover_type"] = "entering_oversold"
            if not is_bullish:
                result["bonus"] = 8.0  # Following momentum
                result["aligned"] = True
                result["reason"] = (
                    f"Weekly StochRSI entering oversold ({k_current:.1f}) - SHORT momentum bonus (+8)"
                )
            else:
                result["bonus"] = 5.0  # Anticipation (could reverse soon)
                result["aligned"] = True  # Not contra, just waiting
                result["reason"] = (
                    f"Weekly StochRSI entering oversold ({k_current:.1f}) - LONG anticipation (+5)"
                )

        elif entering_overbought:
            result["crossover_type"] = "entering_overbought"
            if is_bullish:
                result["bonus"] = 8.0  # Following momentum
                result["aligned"] = True
                result["reason"] = (
                    f"Weekly StochRSI entering overbought ({k_current:.1f}) - LONG momentum bonus (+8)"
                )
            else:
                result["bonus"] = 5.0  # Anticipation (could reverse soon)
                result["aligned"] = True  # Not contra, just waiting
                result["reason"] = (
                    f"Weekly StochRSI entering overbought ({k_current:.1f}) - SHORT anticipation (+5)"
                )
        else:
            # No crossover - use position-based bonuses
            result = _position_based_stoch_bonus(
                k_current, is_bullish, oversold_threshold, overbought_threshold, result
            )
    else:
        # No previous value - use position-based bonuses only
        result = _position_based_stoch_bonus(
            k_current, is_bullish, oversold_threshold, overbought_threshold, result
        )

    return result


def _position_based_stoch_bonus(
    k_current: float,
    is_bullish: bool,
    oversold_threshold: float,
    overbought_threshold: float,
    result: Dict,
) -> Dict:
    """
    Calculate position-based Weekly StochRSI bonus when no crossover detected.
    """
    if k_current < oversold_threshold:
        result["crossover_type"] = "in_oversold"
        if is_bullish:
            result["bonus"] = 10.0  # In prime reversal zone
            result["aligned"] = True
            result["reason"] = (
                f"Weekly StochRSI oversold ({k_current:.1f}) - LONG reversal zone (+10)"
            )
        else:
            result["bonus"] = 5.0  # Following momentum, but may reverse
            result["aligned"] = True
            result["reason"] = f"Weekly StochRSI oversold ({k_current:.1f}) - SHORT momentum (+5)"

    elif k_current > overbought_threshold:
        result["crossover_type"] = "in_overbought"
        if not is_bullish:
            result["bonus"] = 10.0  # In prime reversal zone
            result["aligned"] = True
            result["reason"] = (
                f"Weekly StochRSI overbought ({k_current:.1f}) - SHORT reversal zone (+10)"
            )
        else:
            result["bonus"] = 5.0  # Following momentum, but may reverse
            result["aligned"] = True
            result["reason"] = f"Weekly StochRSI overbought ({k_current:.1f}) - LONG momentum (+5)"
    else:
        result["crossover_type"] = "neutral"
        result["bonus"] = 0.0
        result["aligned"] = True
        result["reason"] = f"Weekly StochRSI neutral ({k_current:.1f}) - no directional bonus"

    return result


# Legacy alias for backward compatibility
def evaluate_weekly_stoch_rsi_gate(
    indicators: IndicatorSet,
    direction: str,
    oversold_threshold: float = 20.0,
    overbought_threshold: float = 80.0,
) -> Dict:
    """
    Legacy gate function - now wraps the bonus system.

    For backward compatibility, converts bonus to gate_passed based on whether
    the bonus is negative (failed gate) or non-negative (passed gate).
    """
    bonus_result = evaluate_weekly_stoch_rsi_bonus(
        indicators, direction, oversold_threshold, overbought_threshold
    )

    return {
        "gate_passed": bonus_result["bonus"] >= 0,
        "reason": bonus_result["reason"],
        "weekly_k": bonus_result["weekly_k"],
        "weekly_k_prev": bonus_result["weekly_k_prev"],
        "crossover_type": bonus_result["crossover_type"],
        "bonus": bonus_result["bonus"],
        "aligned": bonus_result["aligned"],
    }


def _score_regime_alignment(
    regime: Any,
    direction: str,
    max_bonus: float = 10.0,
    max_penalty: float = 10.0,
    scanner_profile: str = "balanced",
) -> Dict[str, Any]:
    """
    Calculate regime alignment bonus/penalty for confluence scoring.

    Rewards trades aligned with the symbol's local regime (trend + volatility).
    Penalizes trades that fight the regime.

    Logic:
    - ALIGNED (strong_up/up + long OR strong_down/down + short): +Bonus scaled by regime.score
    - OPPOSED (strong_up/up + short OR strong_down/down + long): -Penalty scaled by regime.score
    - SIDEWAYS/NEUTRAL: Small penalty for lack of directional edge

    Args:
        regime: SymbolRegime from RegimeDetector (trend, volatility, score)
        direction: Trade direction ("bullish"/"bearish" or "long"/"short")
        max_bonus: Maximum bonus for perfect alignment (default 15)
        max_penalty: Maximum penalty for opposing strong regime (default 12)

    Returns:
        Dict with:
            - adjustment: float - score adjustment (positive=bonus, negative=penalty)
            - aligned: bool - whether direction aligns with regime
            - reason: str - explanation
            - factor_score: float - 0-100 scaled score for ConfluenceFactor
    """
    result = {
        "adjustment": 0.0,
        "aligned": True,
        "reason": "No regime data available",
        "factor_score": 50.0,  # Neutral
    }

    if regime is None:
        return result

    trend = getattr(regime, "trend", "sideways")
    regime_score = getattr(regime, "score", 50.0)
    volatility = getattr(regime, "volatility", "normal")

    # Normalize direction
    is_long = direction.lower() in ("bullish", "long")

    # Calculate regime strength (0 to 1.0 scale)
    # score=50 (neutral) → strength=0, score=100 (strong) → strength=1.0
    regime_strength = max(0.0, min(1.0, (regime_score - 50) / 50))

    # Alignment logic
    bullish_trends = ("strong_up", "up")
    bearish_trends = ("strong_down", "down")

    if trend in bullish_trends:
        if is_long:
            # Aligned with bullish regime
            is_strong = trend == "strong_up"
            base_bonus = max_bonus if is_strong else max_bonus * 0.7

            # NEW: Scale by regime strength (Gap #3)
            # Weak regime (score=60) gets 50% of bonus, strong (score=90) gets 100%
            strength_multiplier = 0.5 + (regime_strength * 0.5)
            result["adjustment"] = base_bonus * strength_multiplier
            result["aligned"] = True
            result["reason"] = (
                f"LONG aligned with {trend} regime (score={regime_score:.0f}, strength={regime_strength:.1f})"
            )
            result["factor_score"] = max(0.0, min(100.0, 50.0 + result["adjustment"] * 3.33))
        else:
            # Shorting into bullish regime
            is_strong = trend == "strong_up"
            base_penalty = max_penalty if is_strong else max_penalty * 0.7

            # NEW: Scale penalty by regime strength
            strength_multiplier = 0.5 + (regime_strength * 0.5)
            result["adjustment"] = -base_penalty * strength_multiplier
            result["aligned"] = False
            result["reason"] = (
                f"SHORT opposes {trend} regime (score={regime_score:.0f}, strength={regime_strength:.1f})"
            )
            result["factor_score"] = max(0.0, min(100.0, 50.0 + result["adjustment"] * 5.0))

    elif trend in bearish_trends:
        if not is_long:
            # Aligned with bearish regime
            is_strong = trend == "strong_down"
            base_bonus = max_bonus if is_strong else max_bonus * 0.7

            # NEW: Scale by regime strength
            strength_multiplier = 0.5 + (regime_strength * 0.5)
            result["adjustment"] = base_bonus * strength_multiplier
            result["aligned"] = True
            result["reason"] = (
                f"SHORT aligned with {trend} regime (score={regime_score:.0f}, strength={regime_strength:.1f})"
            )
            result["factor_score"] = max(0.0, min(100.0, 50.0 + result["adjustment"] * 3.33))
        else:
            # Longing into bearish regime
            is_strong = trend == "strong_down"
            base_penalty = max_penalty if is_strong else max_penalty * 0.7

            # NEW: Scale penalty by regime strength
            strength_multiplier = 0.5 + (regime_strength * 0.5)
            result["adjustment"] = -base_penalty * strength_multiplier
            result["aligned"] = False
            result["reason"] = (
                f"LONG opposes {trend} regime (score={regime_score:.0f}, strength={regime_strength:.1f})"
            )
            result["factor_score"] = max(0.0, min(100.0, 50.0 + result["adjustment"] * 5.0))

    else:  # sideways
        # Mode-aware scoring for ranging markets
        profile = scanner_profile.lower()
        is_scalp_mode = profile in ("precision", "surgical")
        is_breakout_mode = profile in ("overwatch", "strike")
        is_stealth_mode = "stealth" in profile or "balanced" in profile
        
        if is_scalp_mode:
            # Scalp modes LOVE ranges (support/resistance bounces)
            if volatility == "compressed":
                 # Compressed = breakout soon (risky for scalp but good for direction if caught)
                result["adjustment"] = 2.0
                result["factor_score"] = 65.0
                result["reason"] = f"Sideways/Compressed regime - coiled range (good for {profile} scalping)"
            elif volatility == "normal":
                # Normal volatility in range = Perfect for scalping levels
                result["adjustment"] = 1.0
                result["factor_score"] = 60.0
                result["reason"] = f"Sideways regime - tradable range for {profile} mode"
            else:
                # High/Excessive = risky chop
                result["adjustment"] = 0.0
                result["factor_score"] = 50.0
                result["reason"] = f"Sideways regime with {volatility} volatility - risky chop"
        
        elif is_stealth_mode:
            # Stealth/Balanced mode: Opportunistic
            # Likes compressed (accumulation/distributions) but cautious of undefined chop
            if volatility == "compressed":
                result["adjustment"] = 1.0
                result["factor_score"] = 60.0
                result["reason"] = f"Sideways/Compressed regime - accumulation potential (Stealth entry)"
            elif volatility == "normal":
                # Neutral - rely on other confluence factors
                result["adjustment"] = -1.0
                result["factor_score"] = 45.0
                result["reason"] = f"Sideways regime - neutral structure (rely on SMC)"
            else:
                # High volatility in range = noise
                result["adjustment"] = -5.0
                result["factor_score"] = 35.0
                result["reason"] = f"Sideways regime with {volatility} volatility - avoid noise"

        elif is_breakout_mode and volatility == "compressed":
            # Breakout modes like compressed ranges
            result["adjustment"] = 1.0
            result["factor_score"] = 60.0
            result["reason"] = f"Sideways/Compressed regime - potential breakout setup for {profile}"
            
        else:
            # Swing modes (macro, intraday) or breakout with wrong volatility
            # Ranging market = bad for swing trading
            if volatility == "compressed":
                result["adjustment"] = 0.0
                result["factor_score"] = 50.0
                result["reason"] = f"Sideways regime with {volatility} volatility (breakout potential)"
            else:
                # Normal/elevated volatility in range = penalize (chop)
                result["adjustment"] = -5.0
                result["factor_score"] = 35.0 # Increased penalty from 40->35
                result["reason"] = f"Sideways regime - no directional edge (bad for {profile})"
        
        result["aligned"] = True # Not opposing, just different quality levels

    return result


def _score_ob_rejection_quality(df: Any, direction: str) -> Dict:
    """
    Checks if recent price action shows active rejection at a structural level.
    Used to confirm if an Order Block/FVG is actually holding.
    """
    if df is None or len(df) < 3:
        return {"score": 50.0, "reason": "Insufficient data for rejection check"}
    
    # Look at last 3 candles
    recent = df.iloc[-3:]
    score = 50.0
    reason = "Neutral/No clear rejection"
    rejection_found = False

    # Normalize direction
    direction_lower = direction.lower()
    is_bullish = direction_lower in ("long", "bullish")

    for idx, row in recent.iterrows():
        try:
            body_size = abs(row['close'] - row['open'])
            candle_range = row['high'] - row['low']
            if candle_range <= 0:
                continue
                
            if is_bullish:
                lower_wick = min(row['open'], row['close']) - row['low']
                # Bullish pinbar/rejection definition: lower wick > 1.5x body AND > 40% of candle range
                if lower_wick > body_size * 1.5 and (lower_wick / candle_range) > 0.4:
                    rejection_found = True
                    score = max(score, 75.0)
                    reason = "Bullish rejection wick detected"
                    if lower_wick > body_size * 2.5:
                        score = 100.0
                        reason = "Strong bullish pinbar rejection"
            else:
                upper_wick = row['high'] - max(row['open'], row['close'])
                # Bearish pinbar/rejection definition: upper wick > 1.5x body AND > 40% of candle range
                if upper_wick > body_size * 1.5 and (upper_wick / candle_range) > 0.4:
                    rejection_found = True
                    score = max(score, 75.0)
                    reason = "Bearish rejection wick detected"
                    if upper_wick > body_size * 2.5:
                        score = 100.0
                        reason = "Strong bearish pinbar rejection"
        except Exception:
            pass
                    
    if not rejection_found:
        # Fallback: Check for engulfing momentum in our direction
        try:
            last_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            if is_bullish:
                if last_candle['close'] > last_candle['open'] and last_candle['close'] > prev_candle['high']:
                    score = 80.0
                    reason = "Bullish engulfing momentum off level"
                else:
                    score = 15.0  # HEAVY penalty for lack of rejection at OB
                    reason = "No bullish rejection or momentum at OB"
            else:
                if last_candle['close'] < last_candle['open'] and last_candle['close'] < prev_candle['low']:
                    score = 80.0
                    reason = "Bearish engulfing momentum off level"
                else:
                    score = 15.0  # HEAVY penalty for lack of rejection at OB
                    reason = "No bearish rejection or momentum at OB"
        except Exception:
            pass
                
    return {"score": score, "reason": reason}


def _get_tf_indicators(indicators: IndicatorSet, timeframe: str) -> Optional[IndicatorSnapshot]:
    """Case-insensitive indicators lookup."""
    if not indicators or not indicators.by_timeframe or not timeframe:
        return None
    
    # Try direct match
    if timeframe in indicators.by_timeframe:
        return indicators.by_timeframe[timeframe]
        
    # Try case-insensitive match
    tf_lower = timeframe.lower()
    for actual_tf, snapshot in indicators.by_timeframe.items():
        if actual_tf.lower() == tf_lower:
            return snapshot
            
    return None


def calculate_confluence_score(
    smc_snapshot: SMCSnapshot,
    indicators: IndicatorSet,
    config: ScanConfig,
    direction: str,
    htf_trend: Optional[str] = None,
    btc_impulse: Optional[str] = None,
    htf_context: Optional[dict] = None,
    cycle_context: Optional["CycleContext"] = None,
    reversal_context: Optional["ReversalContext"] = None,
    volume_profile: Optional[VolumeProfile] = None,
    current_price: Optional[float] = None,
    # Macro context injection
    macro_context: Optional[MacroContext] = None,
    is_btc: bool = False,
    is_alt: bool = True,
    # Symbol-specific regime from RegimeDetector
    regime: Optional["SymbolRegime"] = None,
    symbol: str = "Unknown",
) -> ConfluenceBreakdown:
    """
    Calculate comprehensive confluence score for a trade setup.

    Args:
        smc_snapshot: SMC patterns detected across timeframes
        indicators: Technical indicators across timeframes
        config: Scan configuration with weights and thresholds
        direction: Trade direction ("bullish" or "bearish")
        htf_trend: Higher timeframe trend ("bullish", "bearish", "neutral")
        btc_impulse: BTC trend for altcoin gate ("bullish", "bearish", "neutral")
        htf_context: HTF level proximity context
        cycle_context: Optional cycle timing context for cycle-aware bonuses
        reversal_context: Optional reversal detection context for synergy bonuses
        volume_profile: Optional volume profile for institutional-grade VAP analysis
        current_price: Optional current price for volume profile entry analysis
        macro_context: Global macro/dominance context (Macro Overlay)
        is_btc: Whether symbol is Bitcoin
        is_alt: Whether symbol is an Altcoin

    Returns:
        ConfluenceBreakdown: Complete scoring breakdown with factors
    """
    factors = []
    primary_tf = None
    macd_analysis = None

    # Normalize direction at entry: LONG/SHORT -> bullish/bearish
    # This ensures consistent format throughout all scoring functions
    direction = _normalize_direction(direction)
    current_profile = getattr(config, "profile", "balanced").lower()

    # Helper to get dynamic weights
    def get_w(key: str, default: float) -> float:
        return MODE_FACTOR_WEIGHTS.get(current_profile, {}).get(key, default)


    # --- SMC Pattern Scoring ---

    # Order Blocks
    ob_result = _score_order_blocks_incremental(smc_snapshot.order_blocks, direction)
    ob_score = ob_result["score"]
    factors.append(
        ConfluenceFactor(
            name="Order Block",
            score=ob_score,
            weight=get_w("order_block", 0.15),
            rationale=(ob_result["rationale"] if ob_score > 0 else "No valid order block in direction") or "Order Block analysis available",
        )
    )

    # Fair Value Gaps
    fvg_result = _score_fvgs_incremental(smc_snapshot.fvgs, direction)
    fvg_score = fvg_result["score"]
    factors.append(
        ConfluenceFactor(
            name="Fair Value Gap",
            score=fvg_score,
            weight=get_w("fvg", 0.05),
            rationale=(fvg_result["rationale"] if fvg_score > 0 else "No fair value gaps identified") or "FVG analysis available",
        )
    )

    # Market Structure (CHoCH / BOS)
    ms_result = _score_market_structure_incremental(smc_snapshot, direction)
    ms_score = ms_result["score"]
    factors.append(
        ConfluenceFactor(
            name="Market Structure",
            score=ms_score,
            weight=get_w("market_structure", 0.20),
            rationale=ms_result["rationale"] or "Structure bias neutral",
        )
    )

    # Liquidity Sweeps
    sweep_result = _score_liquidity_sweeps_incremental(smc_snapshot.liquidity_sweeps, direction)
    sweep_score = sweep_result["score"]

    # LONG BIAS FIX: Apply HTF trend discount to sweep scoring.
    # In a strong downtrend (1D or 4H swing structure = bearish), "sweep of lows" events are
    # continuation traps, not reversals — they should NOT score 45-85 pts for LONG.
    # Cap bullish sweep score at 30 when macro structure is bearish (and vice versa for shorts).
    if sweep_score > 30.0 and smc_snapshot.swing_structure:
        is_bullish_direction = _normalize_direction(direction) == "bullish"
        htf_trend = "neutral"
        for htf_tf in ["1d", "1D", "4h", "4H"]:
            ss = smc_snapshot.swing_structure.get(htf_tf)
            if ss:
                htf_trend = ss.get("trend", "neutral") if isinstance(ss, dict) else getattr(ss, "trend", "neutral")
                if htf_trend != "neutral":
                    break
        # If sweeping against the HTF trend (e.g., LONG sweep in a bearish trend): discount
        if (is_bullish_direction and htf_trend == "bearish") or (not is_bullish_direction and htf_trend == "bullish"):
            sweep_score = min(sweep_score, 30.0)
            sweep_result = {**sweep_result, "score": sweep_score, "rationale": sweep_result.get("rationale", "") + f" [HTF {htf_trend} discount applied]"}

    factors.append(
        ConfluenceFactor(
            name="Liquidity Sweep",
            score=sweep_score,
            weight=get_w("liquidity_sweep", 0.10),
            rationale=(sweep_result["rationale"] if sweep_score > 0 else "No recent liquidity sweep detected") or "Liquidity sweep analysis available",
        )
    )

    # Kill Zone Timing
    try:
        # FIX: removed circular self-import; get_current_kill_zone is imported from sessions at top of file
        # and _score_kill_zone_incremental is defined in this same module — both are already in scope
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        curr_kz = get_current_kill_zone(now)
        kz_result = _score_kill_zone_incremental(now, curr_kz)
        kz_score = kz_result["score"]
        factors.append(
            ConfluenceFactor(
                name="Kill Zone Timing",
                score=kz_score,
                weight=get_w("kill_zone", 0.05),
                rationale=kz_result["rationale"] or "Outside kill zones",
            )
        )
    except Exception as kz_err:
        logger.debug(f"Kill zone check failed: {kz_err}")

    # --- MODE-AWARE STRUCTURAL MINIMUM GATE ---
    # Swing modes (overwatch, stealth, macro_surveillance) require at least ONE
    # structural element (OB, FVG, or sweep) to generate a valid signal.
    # This prevents pure HTF alignment setups with no valid entry structure.
    # Scalp/precision modes are exempt - they can trade isolated setups.

    SWING_PROFILES = ("macro_surveillance", "stealth_balanced", "overwatch", "swing")
    is_swing_mode = current_profile in SWING_PROFILES

    has_structural_element = ob_score > 0 or fvg_score > 0 or sweep_score > 0

    structural_minimum_failed = False
    if is_swing_mode and not has_structural_element:
        structural_minimum_failed = True
        # Apply severe penalty instead of hard rejection (still shows in scan with explanation)
        logger.info(
            "⚠️ STRUCTURAL MINIMUM: %s mode requires OB/FVG/Sweep but none found (%s direction)",
            current_profile,
            direction,
        )
        factors.append(
            ConfluenceFactor(
                name="Structural Minimum",
                score=0.0,  # Zero score
                weight=0.30,  # High weight penalty
                rationale=f"Swing mode requires OB, FVG, or Sweep - none detected for {direction}",
            )
        )

    # --- Indicator Scoring ---

    # Select primary timeframe (Anchor Chart)
    # 1. Use config preference if valid
    if config and getattr(config, "primary_planning_timeframe", None):
        cfg_tf = config.primary_planning_timeframe
        if indicators.has_timeframe(cfg_tf):
            primary_tf = cfg_tf
        # Try case-insensitive fallback for config TF
        elif indicators.by_timeframe:
            for tf in indicators.by_timeframe.keys():
                if tf.lower() == cfg_tf.lower():
                    primary_tf = tf
                    break

    # 2. Sequential search through candidates if still not set
    if not primary_tf:
        candidates = ["1h", "15m", "4h", "1d"]
        for cand in candidates:
            # Check direct match
            if indicators.has_timeframe(cand):
                primary_tf = cand
                break
            # Check case-insensitive match
            for actual_tf in indicators.by_timeframe.keys():
                if actual_tf.lower() == cand.lower():
                    primary_tf = actual_tf
                    break
            if primary_tf:
                break

    # 3. Last resort fallback to any available timeframe
    if not primary_tf and indicators.by_timeframe:
        primary_tf = list(indicators.by_timeframe.keys())[0]

    # --- Price Initialization ---
    entry_price = current_price
    if not entry_price and primary_tf:
        prim_ind = _get_tf_indicators(indicators, primary_tf)
        if prim_ind and hasattr(prim_ind, "dataframe") and prim_ind.dataframe is not None:
            if len(prim_ind.dataframe) > 0:
                entry_price = float(prim_ind.dataframe["close"].iloc[-1])

    profile_name = getattr(config, "profile", "balanced")
    macd_config = get_macd_config(profile_name)
    htf_indicators = _get_tf_indicators(indicators, macd_config.htf_timeframe)

    if primary_tf:
        primary_indicators = _get_tf_indicators(indicators, primary_tf)
        if not primary_indicators:
            # Fallback for UI robustness
            primary_indicators = list(indicators.by_timeframe.values())[0] if indicators.by_timeframe else None

    if primary_indicators:
        momentum_score, m_analysis = _score_momentum(
            primary_indicators, direction, macd_config=macd_config, htf_indicators=htf_indicators, timeframe=primary_tf
        )
        momentum_rationale = _get_momentum_rationale(primary_indicators, direction)
        if m_analysis and m_analysis.get("reasons"):
            momentum_rationale += f" | MACD [{m_analysis['role']}]: {'; '.join(m_analysis['reasons'][:2])}"
        
        factors.append(
            ConfluenceFactor(
                name="Momentum",
                score=momentum_score,
                weight=get_w("momentum", 0.10),
                rationale=(momentum_rationale if momentum_score > 0 else "Weak momentum bias") or "Momentum analysis available",
            )
        )
        macd_analysis = m_analysis

        # Divergence Detection
        div_score = 0.0
        div_rationale = "No divergence detected"
        if hasattr(primary_indicators, "dataframe") and primary_indicators.dataframe is not None:
            df = primary_indicators.dataframe
            if len(df) >= 50:
                try:
                    divergences = detect_all_divergences(df=df, direction=direction, lookback=5, min_pivot_distance=10, max_lookback_bars=100)
                    div_res = _score_divergences_incremental(divergences, direction)
                    div_score = div_res["score"]
                    div_rationale = div_res["rationale"]
                except Exception as e:
                    logger.warning("Divergence scoring failed: %s", e)

        factors.append(
            ConfluenceFactor(
                name="Price-Indicator Divergence",
                score=div_score,
                weight=get_w("divergence", 0.05),
                rationale=div_rationale or "No divergence detected",
            )
        )

        # Volume confirmation
        volume_score = _score_volume(primary_indicators, direction)
        factors.append(
            ConfluenceFactor(
                name="Volume",
                score=volume_score,
                weight=get_w("volume", 0.05),
                rationale=(_get_volume_rationale(primary_indicators) if volume_score > 0 else "Low volume relative to avg") or "Volume analysis neutral",
            )
        )

        # VWAP Alignment
        vwap_score = 40.0
        vwap_rationale = "Neutral VWAP alignment"
        vwap = getattr(primary_indicators, "vwap", None)
        if vwap and entry_price:
            if (direction in ("bullish", "long") and entry_price < vwap) or (direction in ("bearish", "short") and entry_price > vwap):
                vwap_score = 80.0
                vwap_rationale = f"Price ({entry_price:.2f}) at premium/discount relative to VWAP"
            elif (direction in ("bullish", "long") and entry_price < vwap * 1.01) or (direction in ("bearish", "short") and entry_price > vwap * 0.99):
                vwap_score = 60.0
                vwap_rationale = "Price near VWAP equilibrium"
        
        factors.append(
            ConfluenceFactor(
                name="VWAP Alignment",
                score=vwap_score,
                weight=get_w("vwap", 0.05),
                rationale=vwap_rationale or "Neutral VWAP alignment",
            )
        )

        # Volatility
        volatility_score = _score_volatility(primary_indicators)
        factors.append(
            ConfluenceFactor(
                name="Volatility",
                score=volatility_score,
                weight=get_w("volatility", 0.05),
                rationale=_get_volatility_rationale(primary_indicators),
            )
        )

        # MTF Indicator Confluence
        mtf_score, mtf_rationale = _score_mtf_indicator_confluence(indicators, direction)
        mtf_final_score = 50.0 + (mtf_score * 3.33)
        factors.append(
            ConfluenceFactor(
                name="MTF Indicator Alignment",
                score=min(100.0, max(0.0, mtf_final_score)),
                weight=get_w("multi_tf_reversal", 0.10),
                rationale=(mtf_rationale if mtf_score != 0 else "Neutral indicator alignment across timeframes") or "MTF alignment neutral",
            )
        )

        # Close Momentum
        close_mom_score, close_mom_rationale = _score_close_momentum(indicators=indicators, direction=direction, primary_tf=primary_tf)
        factors.append(
            ConfluenceFactor(
                name="Close Momentum",
                score=close_mom_score,
                weight=get_w("close_momentum", 0.05),
                rationale=(close_mom_rationale if close_mom_score > 0 else "Weak candle close momentum") or "Neutral candle closes",
            )
        )
        
        # Multi-Candle Confirmation
        multi_close_score = 0.0
        multi_close_rationale = "No multi-candle confirmation"
        if current_price:
            multi_close_score, multi_close_rationale = _score_multi_close_confirmation(indicators=indicators, smc_snapshot=smc_snapshot, direction=direction, current_price=current_price, primary_tf=primary_tf)
        
        factors.append(
            ConfluenceFactor(
                name="Multi-Candle Confirmation",
                score=multi_close_score,
                weight=get_w("multi_close_confirm", 0.05),
                rationale=(multi_close_rationale if multi_close_score > 0 else "Lack of consecutive close confirmation") or "No multi-candle trigger",
            )
        )

    # --- Volume Profile (Institutional VAP Analysis) ---
    if volume_profile and current_price:
        try:
            vp_factor = calculate_volume_confluence_factor(entry_price=current_price, volume_profile=volume_profile, direction=direction)
            if vp_factor and vp_factor.get("score", 0) > 0:
                factors.append(ConfluenceFactor(
                    name=vp_factor["name"], 
                    score=vp_factor["score"], 
                    weight=vp_factor.get("weight", 0.05), 
                    rationale=vp_factor["rationale"] or "Volume Profile context neutral"
                ))
        except Exception as e:
            logger.warning("Volume profile scoring failed: %s", e)

    # --- MACD Veto Confirmation ---
    if macd_analysis and macd_analysis.get("veto_active"):
        factors.append(ConfluenceFactor(
            name="MACD Veto", 
            score=0.0, 
            weight=get_w("macd_veto", 0.05), 
            rationale=f"MACD Veto: {'; '.join(macd_analysis.get('reasons', []))}" or "MACD veto active"
        ))
    else:
        factors.append(ConfluenceFactor(name="MACD Veto", score=100.0, weight=get_w("macd_veto", 0.05), rationale="MACD alignment confirmed"))

    # --- HTF Composite Sub-scores (aggregated below into a single factor) ---
    # Collecting 5 correlated HTF inputs so they contribute as one composite weight,
    # preventing cascade inflation when all score high in a trending market.
    _htf_sub_scores: Dict[str, float] = {}
    _htf_sub_rationale: Dict[str, str] = {}

    # --- HTF Alignment ---
    if htf_trend:
        htf_align_res = _score_htf_alignment_incremental(htf_trend, direction, htf_indicators=htf_indicators, indicator_set=indicators)
        _htf_sub_scores["htf_alignment"] = htf_align_res["score"]
        _htf_sub_rationale["htf_alignment"] = htf_align_res["rationale"] or f"HTF {htf_trend} baseline"

    # --- BTC Impulse Gate ---
    if btc_impulse:
        btc_score = 100.0 if (btc_impulse == direction or btc_impulse == "neutral") else 40.0
        factors.append(ConfluenceFactor(name="BTC Impulse Gate", score=btc_score, weight=get_w("btc_impulse", 0.05), rationale=f"BTC trend: {btc_impulse}"))

    # --- Fibonacci Proximity ---
    if current_price and smc_snapshot.swing_structure:
        try:
            fib_res = _score_fibonacci_incremental(current_price, smc_snapshot.swing_structure, direction)
            if fib_res["score"] > 0 or get_w("fibonacci", 0) > 0:
                factors.append(ConfluenceFactor(name="Fibonacci Proximity", score=fib_res["score"], weight=get_w("fibonacci", 0.05), rationale=fib_res["rationale"] or "Near Fibonacci levels"))
        except Exception as e:
            logger.warning("Fibonacci proximity scoring failed: %s", e)

    # --- Weekly StochRSI Bonus/Penalty ---
    if getattr(config, "weekly_stoch_rsi_gate_enabled", True):
        w_analysis = evaluate_weekly_stoch_rsi_bonus(indicators=indicators, direction=direction)
        w_bonus = w_analysis["bonus"]
        w_score = min(100.0, max(0.0, 50.0 + w_bonus * 3.33))
        factors.append(ConfluenceFactor(name="Weekly StochRSI Bonus", score=w_score, weight=get_w("weekly_stoch_rsi", 0.05), rationale=w_analysis["reason"] or "Weekly StochRSI neutral"))

    # --- HTF Structure Bias ---
    if smc_snapshot.swing_structure:
        bias_res = _score_htf_structure_bias(swing_structure=smc_snapshot.swing_structure, direction=direction)
        _htf_sub_scores["htf_structure_bias"] = max(0.0, min(100.0, 50.0 + bias_res["bonus"] * 5.0))
        _htf_sub_rationale["htf_structure_bias"] = bias_res["reason"] or "HTF structure bias neutral"

    # ===========================================================================
    # === CRITICAL HTF GATES ===
    # ===========================================================================

    # === Gate 1: HTF STRUCTURAL PROXIMITY GATE ===
    # Entry must be at meaningful HTF structural level
    # === Gate 1: HTF Structural Proximity ===
    if entry_price:
        prox_res = evaluate_htf_structural_proximity(smc_snapshot, indicators, entry_price, direction, config)
        prox_base = 100.0 if prox_res.get("valid", True) else 0.0
        prox_score = max(0.0, min(100.0, prox_base + prox_res.get("score_adjustment", 0.0)))
        _htf_sub_scores["htf_proximity"] = prox_score
        _htf_sub_rationale["htf_proximity"] = prox_res.get("nearest_structure", "HTF structural proximity check")

    # === HTF Momentum Gate ===
    m_gate = evaluate_htf_momentum_gate(indicators=indicators, direction=direction, mode_config=config, swing_structure=smc_snapshot.swing_structure, reversal_context=reversal_context)
    m_gate_base = 100.0 if m_gate["allowed"] else 0.0
    m_gate_score = max(0.0, min(100.0, m_gate_base + m_gate.get("score_adjustment", 0.0)))
    _htf_sub_scores["htf_momentum_gate"] = m_gate_score
    _htf_sub_rationale["htf_momentum_gate"] = m_gate["reason"] or "HTF momentum allowed"

    # --- Premium/Discount Zone ---
    pd_score, pd_rat = 50.0, "Equilibrium zone"
    try:
        p_tf = getattr(config, "primary_planning_timeframe", "4h")
        pd_z = smc_snapshot.premium_discount.get(p_tf) or smc_snapshot.premium_discount.get(p_tf.upper())
        if pd_z:
            c_z, z_p = pd_z.get("current_zone", "neutral"), pd_z.get("zone_percentage", 50)
            if direction in ("bullish", "long"):
                pd_score = 100.0 if (c_z == "discount" and z_p < 30) else (75.0 if c_z == "discount" else 30.0)
            else:
                pd_score = 100.0 if (c_z == "premium" and z_p > 70) else (75.0 if c_z == "premium" else 30.0)
            pd_rat = f"{c_z.capitalize()} zone ({z_p:.0f}%)"
    except Exception as e:
        logger.warning("Premium/discount zone scoring failed: %s", e)
    factors.append(ConfluenceFactor(name="Premium/Discount Zone", score=pd_score, weight=get_w("premium_discount", 0.05), rationale=pd_rat or "Equilibrium zone"))

    # --- Regime Alignment ---
    reg_score, reg_rat = 50.0, "Neutral regime"
    if regime:
        try:
            r_res = _score_regime_alignment(regime=regime, direction=direction, scanner_profile=current_profile)
            reg_score, reg_rat = r_res["factor_score"], r_res["reason"]
        except Exception as e:
            logger.warning("Regime alignment scoring failed: %s", e)
    factors.append(ConfluenceFactor(name="Regime Alignment", score=reg_score, weight=get_w("regime_alignment", 0.08), rationale=reg_rat or "Regime neutral"))

    # --- Inside Order Block Confirmation ---
    in_ob_score, in_ob_rat = 50.0, "No active OB detected"
    try:
        if entry_price:
            for ob in smc_snapshot.order_blocks:
                if ob.low <= entry_price <= ob.high and ((direction in ("long", "bullish") and ob.direction == "bullish") or (direction in ("short", "bearish") and ob.direction == "bearish")):
                    df_rej = getattr(_get_tf_indicators(indicators, ob.timeframe) or _get_tf_indicators(indicators, primary_tf or "4h"), "dataframe", None)
                    rej_res = _score_ob_rejection_quality(df_rej, direction) if df_rej is not None else {"score": 50, "reason": "Inside OB"}
                    in_ob_score, in_ob_rat = rej_res["score"], rej_res["reason"]
                    break
    except Exception as e:
        logger.warning("Inside order block scoring failed: %s", e)
    factors.append(ConfluenceFactor(name="Inside Order Block", score=in_ob_score, weight=get_w("inside_ob", 0.05), rationale=in_ob_rat or "No active OB detected"))

    # --- Nested Order Block Bonus ---
    nested_score, nested_rat = 0.0, "No nested OB found"
    try:
        if _detect_nested_ob(smc_snapshot, direction): # Uses NESTED_OB_CONTAINMENT_MIN (50%)
            nested_score, nested_rat = 80.0, "LTF OB nested in HTF OB"
    except Exception as e:
        logger.warning("Nested order block scoring failed: %s", e)
    factors.append(ConfluenceFactor(name="Nested Order Block", score=nested_score, weight=get_w("nested_ob", 0.04), rationale=nested_rat or "No nested OB found"))

    # --- NEW: Opposing Structure Penalty ---
    # Penalty when opposing OB/FVG is near the entry (immediate resistance/support)
    try:
        if in_ob_score <= 50.0:
            # Rejection logic if NOT inside OB
            atr = 0.0
            atr_ind = _get_tf_indicators(indicators, getattr(config, "primary_planning_timeframe", "4h"))
            if atr_ind and atr_ind.atr:
                atr = atr_ind.atr

            if atr > 0:
                opposing_atr_threshold = 2.0  # Within 2 ATR

                for ob in smc_snapshot.order_blocks:
                    ob_direction = getattr(ob, "direction", None)
                    ob_low = getattr(ob, "low", 0)
                    ob_high = getattr(ob, "high", 0)
                     # For LONG, check for bearish OBs above price (resistance)
                    if direction in ("bullish", "long") and ob_direction == "bearish":
                        if ob_low > current_price:
                            dist = (ob_low - current_price) / atr
                            if dist <= opposing_atr_threshold:
                                tf = getattr(ob, "timeframe", "unknown")
                                penalty_score = min(50.0, dist * 25.0)  # max penalty (0) when distance is 0
                                factors.append(
                                    ConfluenceFactor(
                                        name="Opposing Structure",
                                        score=penalty_score,
                                        weight=get_w("opposing_structure", 0.08),
                                        rationale=f"Bearish {tf} OB {dist:.1f} ATR above - resistance threat",
                                    )
                                )
                                break  # Only count nearest opposing

                    # For SHORT, check for bullish OBs below price (support)
                    elif direction in ("bearish", "short") and ob_direction == "bullish":
                        if ob_high < current_price:
                            dist = (current_price - ob_high) / atr
                            if dist <= opposing_atr_threshold:
                                tf = getattr(ob, "timeframe", "unknown")
                                penalty_score = min(50.0, dist * 25.0)  # max penalty (0) when distance is 0
                                factors.append(
                                    ConfluenceFactor(
                                        name="Opposing Structure",
                                        score=penalty_score,
                                        weight=get_w("opposing_structure", 0.08),
                                        rationale=f"Bullish {tf} OB {dist:.1f} ATR below - support threat",
                                    )
                                )
                                break  # Only count nearest opposing
    except Exception as e:
        logger.debug("Opposing structure penalty failed: %s", e)

    # --- HTF Inflection Point ---
    try:
        if current_price and smc_snapshot.order_blocks:
            target_tf = getattr(config, "primary_planning_timeframe", "4h")
            atr_ind = indicators.by_timeframe.get(target_tf)
            atr_val = getattr(atr_ind, "atr", current_price * 0.01) if atr_ind else current_price * 0.01
            if atr_val > 0:
                for ob in smc_snapshot.order_blocks:
                    if ob.timeframe in ("1w", "1d", "4h"):
                        target_price = ob.high if direction in ("long", "bullish") else ob.low
                        dist_atr = abs(current_price - target_price) / atr_val
                        if dist_atr < 1.0:
                            inflection_score = min(100.0, max(0.0, 100.0 - (dist_atr * 50.0)))
                            _htf_sub_scores["htf_inflection"] = inflection_score
                            _htf_sub_rationale["htf_inflection"] = f"Near {ob.timeframe} HTF inflection zone ({dist_atr:.1f} ATR)"
                            break
    except Exception as e:
        logger.debug("HTF inflection point scoring failed: %s", e)

    # --- HTF Composite Factor (single aggregated factor replacing 5 correlated inputs) ---
    # Internal sub-weights are fixed — only htf_composite weight participates in normalization.
    _HTF_INTERNAL_WEIGHTS = {
        "htf_alignment":      0.35,
        "htf_structure_bias": 0.25,
        "htf_proximity":      0.20,
        "htf_momentum_gate":  0.12,
        "htf_inflection":     0.08,
    }
    _htf_total_w = sum(_HTF_INTERNAL_WEIGHTS[k] for k in _HTF_INTERNAL_WEIGHTS if k in _htf_sub_scores)
    if _htf_total_w > 0:
        _htf_composite = sum(
            _htf_sub_scores[k] * _HTF_INTERNAL_WEIGHTS[k]
            for k in _HTF_INTERNAL_WEIGHTS if k in _htf_sub_scores
        ) / _htf_total_w
        _htf_composite = max(0.0, min(100.0, _htf_composite))
        _htf_top_rationale = next(
            (_htf_sub_rationale[k] for k in ("htf_alignment", "htf_proximity", "htf_structure_bias") if k in _htf_sub_rationale),
            "HTF composite"
        )
        factors.append(ConfluenceFactor(
            name="HTF Composite",
            score=_htf_composite,
            weight=get_w("htf_composite", 0.15),
            rationale=_htf_top_rationale,
        ))

    # --- Institutional Sequence ---
    seq_score, seq_rat = _score_institutional_sequence(smc_snapshot, direction)
    factors.append(ConfluenceFactor(name="Institutional Sequence", score=seq_score, weight=get_w("institutional_sequence", 0.10), rationale=seq_rat or "No institutional sequence detected"))

    # --- Liquidity Draw Factor ---
    try:
        from backend.strategy.confluence.liquidity_map_scorer import score_liquidity_draw as _score_ld
        l_prim = indicators.by_timeframe.get(primary_tf)
        l_atr = getattr(l_prim, "atr", current_price * 0.01) if current_price else 0
        l_res = _score_ld(direction=direction, current_price=current_price, smc=smc_snapshot, atr=l_atr)
        factors.append(ConfluenceFactor(name="Liquidity Draw", score=l_res["score"], weight=get_w("liquidity_draw", 0.10), rationale="Liquidity targets active"))
    except Exception as e:
        logger.warning("Liquidity draw scoring failed: %s", e)

    # --- FINAL WEIGHT NORMALIZATION (FIX #1: Absent-factor weight redistribution) ---
    # Only normalise across factors that have actual data to contribute (score > 0).
    # Factors that score 0 because the pattern is simply absent in the market
    # (no FVG, no Sweep, no Divergence) carry ZERO information and should not eat
    # the weight budget. Their weight is redistributed to informative factors so the
    # weighted average reflects what IS present, not what is absent.
    # Exception: factors with a non-zero weight that are explicitly structural
    # requirements (e.g. Structural Minimum gate) keep weight=0 to preserve the cap.
    informative_w = sum(f.weight for f in factors if f.score > 0)
    if informative_w > 0:
        norm_factors = []
        for f in factors:
            if f.score > 0:
                norm_factors.append(
                    ConfluenceFactor(
                        name=f.name,
                        score=f.score,
                        weight=f.weight / informative_w,
                        rationale=f.rationale or "Factor details",
                    )
                )
            else:
                # Absent factor — zero weight so it doesn't dilute the pool
                norm_factors.append(
                    ConfluenceFactor(
                        name=f.name,
                        score=0.0,
                        weight=0.0,
                        rationale=f.rationale or "Factor not present in current market",
                    )
                )
        factors = norm_factors
    else:
        # All factors scored 0 — normalise uniformly (edge case, score will be 0)
        total_w = sum(f.weight for f in factors)
        if total_w > 0:
            factors = [
                ConfluenceFactor(name=f.name, score=0.0, weight=f.weight / total_w,
                                 rationale=f.rationale or "Factor details")
                for f in factors
            ]


    # --- Final Score Calculation ---
    weighted_score = sum(f.score * f.weight for f in factors)
    synergy_bonus = _calculate_synergy_bonus(factors, smc_snapshot, cycle_context=cycle_context, reversal_context=reversal_context, direction=direction, mode_config=config)
    conflict_penalty = _calculate_conflict_penalty(factors, direction, smc=smc_snapshot, mode_config=config, regime=regime, btc_impulse=btc_impulse)

    # --- FIX #2: Mode-aware coverage penalty (no double-counting) ---
    # The old fixed threshold of 6 quality factors with 3pts/missing was double-penalising:
    # absent factors already score 0 (dragging weighted_score down), then the coverage
    # penalty hit them AGAIN. With FIX #1 in place (weight redistribution) the weighted
    # sum already reflects real signal density. Coverage penalty is now a small,
    # mode-calibrated safety net for setups with very few quality signals, not a
    # second punch for the absence of optional patterns like FVG or Sweep.
    #
    # Mode thresholds (quality_factors = factors scoring >= 50):
    #   Swing/Macro (overwatch, stealth_balanced):  require 5 quality factors
    #   Intraday (strike, intraday_aggressive):      require 4 quality factors
    #   Scalp/Precision (surgical, precision):       require 3 quality factors
    coverage_penalty = 0.0
    quality_factors = len([f for f in factors if f.score >= 50])
    active_factors  = len([f for f in factors if f.score > 0])

    _cp_profile = current_profile
    if _cp_profile in ("macro_surveillance", "overwatch", "stealth_balanced", "stealth"):
        _cp_threshold, _cp_pts, _cp_cap = 4, 2.5, 10.0   # Swing: need 4 quality signals
    elif _cp_profile in ("intraday_aggressive", "strike"):
        _cp_threshold, _cp_pts, _cp_cap = 3, 2.0, 8.0    # Intraday: need 3
    else:  # surgical, precision, balanced
        _cp_threshold, _cp_pts, _cp_cap = 4, 1.5, 6.0    # Scalp: need 4 quality signals

    if quality_factors < _cp_threshold:
        coverage_penalty = min(_cp_cap, (_cp_threshold - quality_factors) * _cp_pts)
        logger.debug(
            "📉 Coverage penalty [%s]: quality_factors=%d < threshold=%d → -%.1f pts",
            _cp_profile, quality_factors, _cp_threshold, coverage_penalty,
        )


    # Macro Adjustment — trade-type and reversal aware
    macro_adj = 0.0
    if config and getattr(config, "macro_overlay_enabled", False) and macro_context:
        _expected_tt = getattr(config, "expected_trade_type", None) or "swing"
        _tt_clean = (
            "scalp" if "scalp" in str(_expected_tt).lower()
            else "intraday" if "intraday" in str(_expected_tt).lower()
            else "swing"
        )
        _is_reversal = (
            reversal_context is not None
            and getattr(reversal_context, "is_reversal_setup", False)
        )
        macro_adj = compute_macro_score(
            macro_context, direction, is_btc, is_alt,
            trade_type=_tt_clean,
            is_reversal=_is_reversal,
        ) * 5.0
        logger.info(
            "🌐 MACRO [%s %s]: state=%s score=%+.0f (trade_type=%s, reversal=%s)",
            symbol,
            direction, macro_context.macro_state.value if macro_context.macro_state else "?",
            macro_adj, _tt_clean, _is_reversal,
        )

    raw_score = weighted_score + synergy_bonus - conflict_penalty - coverage_penalty + macro_adj
    raw_score = max(0.0, min(100.0, raw_score))

    # Structural Minimum Gate — hard-cap at 30 when swing mode has no OB/FVG/Sweep
    if structural_minimum_failed:
        raw_score = min(raw_score, 30.0)

    # --- FIX #3: Replace quadratic decay with a gentle linear floor ---
    # The old quadratic (raw * raw/40) was far too aggressive — a legitimate 38-point
    # setup (good structure, missing one or two rare events) was crushed to 36.1,
    # making it mathematically impossible to reach any mode gate from below 40.
    # New rule: only hard-compress TRUE garbage (raw < 20) by a modest 15%;
    # everything else passes through linearly so real-world setups can reach their gate.
    if raw_score < 20.0:
        # Below 20 = noise (equivalent to the old below-40 quadratic zone for garbage)
        final_score = raw_score * 0.85
    else:
        final_score = raw_score

    final_score = max(0.0, min(100.0, final_score))


    # ── Signal Tier — per-anchor conviction (Section 5, scoring audit) ───────────
    #
    # Anchor factors are the structural/directional pillars each mode depends on.
    # Tier is determined by how many of those pillars individually exceed quality
    # thresholds — NOT by averaging them.  A single anchor at 40 and another at 100
    # averaging to 70 is NOT a conviction signal; both must be genuinely strong.
    #
    # An anchor entry that is itself a list = OR logic: the best-scoring factor of
    # that group counts (used for "Order Block OR Fair Value Gap" in Strike mode).
    #
    # Tier definitions:
    #   APEX — every anchor >= 70 AND score >= gate+10 AND no active vetoes
    #   A    — 3+ anchors >= 70    AND score >= gate+5  AND no active vetoes
    #   B    — 2+ anchors >= 60    AND score >= gate
    #   C    — passed gate, but anchors too weak for A/B
    _TIER_ANCHOR_FACTORS: Dict[str, list] = {
        # Overwatch: macro swing mode — HTF structure + institutional footprint mandatory
        "overwatch":          ["Order Block", "Market Structure", "Liquidity Sweep",
                               "HTF Composite", "Institutional Sequence"],
        "macro_surveillance": ["Order Block", "Market Structure", "Liquidity Sweep",
                               "HTF Composite", "Institutional Sequence"],
        # Strike: intraday momentum — structure + momentum + entry level + timing
        "strike":             ["Market Structure", "Momentum",
                               ["Order Block", "Fair Value Gap"],   # OR: either entry level counts
                               "Kill Zone Timing"],
        "intraday_aggressive":["Market Structure", "Momentum",
                               ["Order Block", "Fair Value Gap"],
                               "Kill Zone Timing"],
        # Surgical: precision scalp — nested OB entry + timing + premium/discount zone
        "surgical":           ["Order Block", "Inside Order Block", "Momentum",
                               "Kill Zone Timing", "Premium/Discount Zone"],
        "precision":          ["Order Block", "Inside Order Block", "Momentum",
                               "Kill Zone Timing", "Premium/Discount Zone"],
        # Stealth: balanced swing/intraday — HTF structure + institutional footprint
        "stealth":            ["Order Block", "Market Structure",
                               "HTF Composite", "Institutional Sequence"],
        "stealth_balanced":   ["Order Block", "Market Structure",
                               "HTF Composite", "Institutional Sequence"],
    }
    _default_anchors: list = ["Order Block", "Market Structure", "HTF Composite", "Liquidity Sweep"]
    _raw_anchors = _TIER_ANCHOR_FACTORS.get(current_profile, _default_anchors)
    _fm_tier = {f.name: f.score for f in factors}

    def _resolve_anchor(req: object) -> float:
        """Score for one anchor requirement.  List = OR (best of group)."""
        if isinstance(req, list):
            return max(_fm_tier.get(n, 0.0) for n in req)
        return _fm_tier.get(req, 0.0)  # type: ignore[arg-type]

    _resolved = [_resolve_anchor(req) for req in _raw_anchors]
    _n_anchors         = len(_resolved)
    _all_above_70      = _n_anchors > 0 and all(s >= 70 for s in _resolved)
    _count_above_70    = sum(1 for s in _resolved if s >= 70)
    _count_above_60    = sum(1 for s in _resolved if s >= 60)

    # Veto check: MACD Veto factor < 50 = hard block (blocks APEX and A)
    _tier_has_veto = _fm_tier.get("MACD Veto", 100.0) < 50.0

    # Gate threshold — same T the confluence gate uses
    _T = getattr(config, "min_confluence_score", None) or 60.0

    tier = (
        "APEX" if (_all_above_70 and final_score >= _T + 10 and not _tier_has_veto) else
        "A"    if (_count_above_70 >= 3 and final_score >= _T + 5 and not _tier_has_veto) else
        "B"    if (_count_above_60 >= 2 and final_score >= _T) else
        "C"
    )
    # ── end tier ──────────────────────────────────────────────────────────────

    breakdown = ConfluenceBreakdown(
        total_score=final_score,
        factors=factors,
        synergy_bonus=synergy_bonus,
        conflict_penalty=conflict_penalty,
        regime=_detect_regime(smc_snapshot, indicators),
        htf_aligned=any(f.name in ("HTF Alignment", "HTF Structure Bias") and f.score > 55 for f in factors),
        btc_impulse_gate=not any(f.name == "BTC Impulse Gate" and f.score < 50 for f in factors),
        weekly_stoch_rsi_gate=True,
        weekly_stoch_rsi_bonus=next((f.score-50 for f in factors if f.name == "Weekly StochRSI Bonus"), 0.0),
        macro_score=macro_adj,
        symbol=symbol,
        direction=direction,
        profile=current_profile
    )
    if not hasattr(breakdown, "metadata") or breakdown.metadata is None: breakdown.metadata = {}
    breakdown.metadata["signal_tier"] = tier

    # ── Critical Factor Convergence ────────────────────────────────────────────
    # These are the factors that genuinely matter for a high-probability setup.
    # Weighted average can be dragged down by zeroed factors (no FVG in market,
    # compressed regime, etc.). Convergence tells us: of the things that CAN fire,
    # how many are actually aligned? Used to surface DEVELOPING setups in the UI.
    CRITICAL_FACTORS: dict = {
        "Order Block":               65,   # must have a valid OB to trade from
        "Fair Value Gap":            60,   # imbalance zone — fast momentum setups need this
        "Market Structure":          55,   # BOS/CHoCH — structural shift required
        "Liquidity Sweep":           50,   # confirmed sweep of buy/sell-side liq
        "Multi-Candle Confirmation": 70,   # momentum confirmation candles
        # NOTE: "HTF Structure Bias", "HTF Structural Proximity", "HTF Momentum Gate"
        # are computed internally but NEVER emitted as standalone ConfluenceFactor
        # entries — they are aggregated into "HTF Composite". Using their names here
        # caused convergence to show them as permanently missing. Fixed: single entry.
        "HTF Composite":             65,   # rolls up structure bias + proximity + momentum gate
        "BTC Impulse Gate":          70,   # BTC not in opposing impulse
    }
    # NOTE: FVG and Order Block are complementary — a setup strong in one but not
    # the other still achieves convergence. This is intentional: momentum moves
    # often lack an OB but have a clear FVG, and vice versa for structural setups.
    VETO_FACTORS = {"MACD Veto"}           # score < 50 → hard block

    # Count how many critical factors are present AND above their threshold
    # (factors not scored this run are simply absent from `factors` list)
    factor_map = {f.name: f.score for f in factors}
    critical_firing = sum(
        1 for name, threshold in CRITICAL_FACTORS.items()
        if factor_map.get(name, 0) >= threshold
    )
    critical_total = len(CRITICAL_FACTORS)
    convergence_pct = round(critical_firing / critical_total * 100, 1)

    # Hard vetoes — any veto factor scoring < 50 means signal is blocked
    veto_blocked = any(
        factor_map.get(name, 100) < 50 for name in VETO_FACTORS
    )

    # Missing critical factors (present in map but below threshold, or absent)
    missing_critical = [
        name for name, threshold in CRITICAL_FACTORS.items()
        if factor_map.get(name, 0) < threshold
    ]
    active_vetoes = [
        name for name in VETO_FACTORS
        if factor_map.get(name, 100) < 50
    ]

    # Setup state: what does this setup look like right now?
    # Anchored to factor counts (not percentages) so adding/removing factors
    # doesn't silently shift the bar.  With 9 critical factors:
    #   DEVELOPING = 5+ firing  (≈55.6%)
    #   WATCHING   = 4+ firing  (≈44.4%)
    # T comes from the user's mode config — the same threshold the trade gate uses.
    # Fallback to 60 only if config doesn't carry a threshold (e.g. bare test fixtures).
    T = getattr(config, "min_confluence_score", None) or 60.0
    if final_score >= T and not veto_blocked:
        setup_state = "READY"          # fires normally through gate
    elif critical_firing >= 5 and not veto_blocked:
        setup_state = "DEVELOPING"     # 5/9 critical factors aligned, no veto
    elif critical_firing >= 4:
        setup_state = "WATCHING"       # 4/9 aligned — worth monitoring
    else:
        setup_state = "NOISE"          # not enough confluence even directionally

    breakdown.metadata["convergence_score"]          = convergence_pct
    breakdown.metadata["convergence_critical_count"] = critical_firing
    breakdown.metadata["convergence_critical_total"] = critical_total
    breakdown.metadata["convergence_missing"]        = missing_critical
    breakdown.metadata["veto_blocked"]               = veto_blocked
    breakdown.metadata["active_vetoes"]              = active_vetoes
    breakdown.metadata["setup_state"]                = setup_state
    # ── End Critical Factor Convergence ───────────────────────────────────────


    # Final Logging
    _macro_tag = f" | Macro: {macro_adj:+.0f}" if macro_adj != 0.0 else ""
    logger.info(f"📊 CONFLUENCE [{symbol} {direction}]: {final_score:.1f} ({tier}) | Factors: {active_factors} | Synergy: +{synergy_bonus:.1f} | Conflict: -{conflict_penalty:.1f}{_macro_tag}")

    return breakdown


def _score_multi_tf_reversal_confluence(
    smc_snapshot: SMCSnapshot, direction: str
) -> Tuple[int, List[str]]:
    """
    Calculate the number of reversal signals aligned with the trade direction.
    Signals include liquidity sweeps, structural breaks (BOS/ChoCH), and swing structure trends.
    """
    reversal_signals: int = 0
    reversal_reasons: List[str] = []

    # Check for liquidity sweeps in direction
    if smc_snapshot.liquidity_sweeps:
        for sweep in smc_snapshot.liquidity_sweeps:
            sweep_type = getattr(sweep, "sweep_type", "")
            sweep_dir = "bullish" if sweep_type == "low" else ("bearish" if sweep_type == "high" else None)
            if (direction in ("bullish", "long") and sweep_dir == "bullish") or (
                direction in ("bearish", "short") and sweep_dir == "bearish"
            ):
                reversal_signals += 1  # type: ignore
                reversal_reasons.append(f"{getattr(sweep, 'timeframe', 'unknown')} sweep")
                break

    # Check for structural breaks in direction
    if smc_snapshot.structural_breaks:
        for brk in smc_snapshot.structural_breaks:
            brk_dir = getattr(brk, "direction", None)
            brk_type = getattr(brk, "break_type", "")
            if (direction in ("bullish", "long") and brk_dir == "bullish") or (
                direction in ("bearish", "short") and brk_dir == "bearish"
            ):
                if str(brk_type).lower() in ("bos", "choch"):
                    reversal_signals += 1  # type: ignore
                    reversal_reasons.append(
                        f"{getattr(brk, 'timeframe', 'unknown')} {brk_type}"
                    )
                    break

    # Check swing structure for bias alignment
    if smc_snapshot.swing_structure:
        for tf, ss in smc_snapshot.swing_structure.items():
            trend = (
                ss.get("trend", "neutral")
                if isinstance(ss, dict)
                else getattr(ss, "trend", "neutral")
            )
            if (direction in ("bullish", "long") and trend == "bullish") or (
                direction in ("bearish", "short") and trend == "bearish"
            ):
                reversal_signals += 1  # type: ignore
                reversal_reasons.append(f"{tf} trend={trend}")
                break

    return reversal_signals, reversal_reasons


# --- HTF Structure Bias Scoring ---


def _score_htf_structure_bias(swing_structure: dict, direction: str) -> dict:
    """
    Score setup based on HTF swing structure (HH/HL/LH/LL).

    This is the key function for pullback trading:
    - If Weekly/Daily shows bullish structure (HH/HL), LONG setups get bonus
    - If Weekly/Daily shows bearish structure (LH/LL), SHORT setups get bonus
    - Pullback entries (LTF against HTF → BOS back toward HTF) score highest

    Args:
        swing_structure: Dict of {timeframe: SwingStructure.to_dict()}
        direction: "LONG" or "SHORT"

    Returns:
        dict with 'bonus' (float), 'reason' (str), 'htf_bias' (str)
    """
    if not swing_structure:
        return {"bonus": 0.0, "reason": "No HTF swing structure data", "htf_bias": "neutral"}

    # Prioritize timeframes: Weekly > Daily > 4H
    # NOTE: Use lowercase to match scanner mode timeframe conventions
    htf_priority = ["1w", "1d", "4h"]

    bullish_tfs = []
    bearish_tfs = []

    for tf in htf_priority:
        # Check both lowercase and uppercase for compatibility - explicit None check
        ss = swing_structure.get(tf)
        if ss is None:
            ss = swing_structure.get(tf.upper())
        if ss:
            trend = ss.get("trend", "neutral")
            if trend == "bullish":
                bullish_tfs.append(tf)
            elif trend == "bearish":
                bearish_tfs.append(tf)

    # Calculate bias strength based on HTF alignment
    # Weekly trend = 2 points, Daily = 1.5 points, 4H = 1 point
    tf_weights = {"1w": 2.0, "1d": 1.5, "4h": 1.0}

    bullish_strength = sum(tf_weights.get(tf, 0) for tf in bullish_tfs)
    bearish_strength = sum(tf_weights.get(tf, 0) for tf in bearish_tfs)

    # Determine overall HTF bias
    if bullish_strength > bearish_strength + 0.5:
        htf_bias = "bullish"
        bias_strength = bullish_strength
    elif bearish_strength > bullish_strength + 0.5:
        htf_bias = "bearish"
        bias_strength = bearish_strength
    else:
        htf_bias = "neutral"
        bias_strength = 0.0

    # Calculate directional bonus
    # NOTE: direction is normalized to 'bullish' or 'bearish' (lowercase)
    bonus = 0.0
    reason_parts = []

    # Direction aligns with HTF bias → strong bonus
    if direction in ("long", "bullish") and htf_bias == "bullish":
        # Bonus scales with strength: max +15 for full Weekly+Daily+4H alignment
        bonus = min(15.0, bias_strength * 3.5)
        reason_parts.append(f"HTF structure bullish ({', '.join(bullish_tfs)})")
        reason_parts.append("LONG aligns with HTF trend")

    elif direction in ("short", "bearish") and htf_bias == "bearish":
        bonus = min(15.0, bias_strength * 3.5)
        reason_parts.append(f"HTF structure bearish ({', '.join(bearish_tfs)})")
        reason_parts.append("SHORT aligns with HTF trend")

    # Counter-trend setup → penalty (but not blocking)
    elif direction in ("long", "bullish") and htf_bias == "bearish":
        bonus = max(-8.0, -bias_strength * 2.0)
        reason_parts.append(f"HTF structure bearish ({', '.join(bearish_tfs)})")
        reason_parts.append("LONG is counter-trend (caution)")

    elif direction in ("short", "bearish") and htf_bias == "bullish":
        bonus = max(-8.0, -bias_strength * 2.0)
        reason_parts.append(f"HTF structure bullish ({', '.join(bullish_tfs)})")
        reason_parts.append("SHORT is counter-trend (caution)")

    else:
        # Neutral HTF - no bonus or penalty
        reason_parts.append("HTF structure neutral/mixed")

    return {
        "bonus": bonus,
        "reason": "; ".join(reason_parts) if reason_parts else "No HTF bias detected",
        "htf_bias": htf_bias,
        "bullish_tfs": bullish_tfs,
        "bearish_tfs": bearish_tfs,
    }


# --- Grade Weighting Constants ---
# Pattern grades affect base score: A = 100%, B = 70%, C = 40%
GRADE_WEIGHTS = {"A": 1.0, "B": 0.7, "C": 0.4}


def _get_grade_weight(grade: str) -> float:
    """Get weight multiplier for a pattern grade."""
    return GRADE_WEIGHTS.get(grade, 0.7)  # Default to B weight if unknown


# --- Timeframe Weighting Constants ---
# HTF patterns (institutional) should score higher than LTF patterns (noise)
# 4H is the reference baseline (1.0), weekly patterns most significant
TIMEFRAME_WEIGHTS = {
    "1w": 1.5,  # Weekly patterns are most significant
    "1W": 1.5,
    "1d": 1.3,  # Daily
    "1D": 1.3,
    "4h": 1.0,  # Base reference
    "4H": 1.0,
    "1h": 0.85,  # Intraday
    "1H": 0.85,
    "15m": 0.6,  # LTF patterns worth less
    "5m": 0.3,  # Minimal weight - mostly noise
}


def _get_timeframe_weight(timeframe: str) -> float:
    """Get weight multiplier for pattern timeframe."""
    if not timeframe:
        return 0.7  # Default if unknown
    return TIMEFRAME_WEIGHTS.get(timeframe, 0.7)


def _normalize_direction(direction: str) -> str:
    """Normalize direction format: LONG/SHORT -> bullish/bearish."""
    d = direction.lower()
    if d in ("long", "bullish"):
        return "bullish"
    elif d in ("short", "bearish"):
        return "bearish"
    return d


# --- SMC Scoring Functions ---





def _score_order_blocks_incremental(
    order_blocks: List[OrderBlock], direction: str
) -> Dict[str, Any]:
    """
    Score order blocks with detailed incremental factors.
    
    Factors:
    1. Base Score by Grade (A=40, B=30, C=20)
    2. Mitigation Bonus (+15): <10% mitigated (Fresh)
    3. Displacement Bonus (+15): >80 strength
    4. HTF Bonus (+15): 4H or 1D Order Block
    5. Recency/Freshness (+15): freshness_score > 80
    6. Penalty: Heavily mitigated (>50%) or old (<50 freshness)
    
    Returns detailed score dict.
    """
    normalized_dir = _normalize_direction(direction)
    aligned_obs = [ob for ob in order_blocks if ob.direction == normalized_dir]
    
    if not aligned_obs:
        return {"score": 0.0, "rationale": "No aligned Order Blocks", "components": []}
        
    # Find best OB based on raw quality metrics
    best_ob = max(
        aligned_obs,
        key=lambda ob: (
            ob.freshness_score * 0.3
            + ob.displacement_strength * 0.3
            + (1.0 - ob.mitigation_level) * 0.4
        )
    )
    
    score = 0.0
    components = []
    
    # 1. Base Score by Grade
    grade = getattr(best_ob, "grade", "B")
    if grade == "A":
        score += 40.0
        components.append(("Grade A", 40.0, "Excellent structure"))
    elif grade == "B":
        score += 30.0
        components.append(("Grade B", 30.0, "Good structure"))
    else:
        score += 20.0
        components.append(("Grade C", 20.0, "Marginal structure"))
        
    # 2. Mitigation Bonus (Freshness)
    if best_ob.mitigation_level < 0.1:
        score += 15.0
        components.append(("Fresh OB", 15.0, f"Unmitigated ({best_ob.mitigation_level:.0%})"))
    elif best_ob.mitigation_level > 0.5:
        score -= 10.0
        components.append(("Mitigated", -10.0, f"Heavily mitigated ({best_ob.mitigation_level:.0%})"))
        
    # 3. Displacement Bonus
    if best_ob.displacement_strength > 80:
        score += 15.0
        components.append(("Strong Move", 15.0, "High displacement > 80"))
    elif best_ob.displacement_strength < 40:
        score -= 5.0
        components.append(("Weak Move", -5.0, "Low displacement"))
        
    # 4. HTF Bonus
    tf = best_ob.timeframe.lower()
    if tf in ["4h", "1d", "1w"]:
        score += 15.0
        components.append(("HTF OB", 15.0, f"{best_ob.timeframe} timeframe"))
        
    # 5. Recency
    if best_ob.freshness_score > 80:
        score += 15.0
        components.append(("Recent", 15.0, "Formed recently"))
    elif best_ob.freshness_score < 40:
        score -= 10.0
        components.append(("Stale", -10.0, "Old/stale zone"))

    return {
        "score": max(0.0, min(100.0, score)),
        "rationale": f"OB ({grade}): " + ", ".join([f"{c[0]}({c[1]:+.0f})" for c in components]),
        "components": components,
        "best_ob": best_ob
    }


def _score_fvgs_incremental(
    fvgs: List[FVG], direction: str
) -> Dict[str, Any]:
    """
    Score FVGs with detailed incremental factors.
    
    Factors:
    1. Base Score by Grade (A=40, B=30, C=20)
    2. Unfilled Bonus (+20): overlap == 0
    3. Size Bonus (+15): size_atr > 1.0 (Large gap)
    4. Stacking Bonus (+10): Multiple aligned FVGs
    5. Penalty: Filled > 50%
    
    Returns detailed score dict.
    """
    normalized_dir = _normalize_direction(direction)
    aligned_fvgs = [fvg for fvg in fvgs if fvg.direction == normalized_dir]
    
    if not aligned_fvgs:
        return {"score": 0.0, "rationale": "No aligned FVGs", "components": []}
        
    # Find best FVG (prioritize unfilled size)
    best_fvg = max(
        aligned_fvgs,
        key=lambda fvg: fvg.size * (1.0 - fvg.overlap_with_price)
    )
    
    score = 0.0
    components = []
    
    # 1. Base Score by Grade
    grade = getattr(best_fvg, "grade", "B")
    if grade == "A":
        score += 40.0
        components.append(("Grade A", 40.0, "Excellent Gap"))
    elif grade == "B":
        score += 30.0
        components.append(("Grade B", 30.0, "Good Gap"))
    else:
        score += 20.0
        components.append(("Grade C", 20.0, "Marginal Gap"))
        
    # 2. Unfilled Bonus
    if best_fvg.overlap_with_price == 0:
        score += 20.0
        components.append(("Virgin FVG", 20.0, "Completely unfilled"))
    elif best_fvg.overlap_with_price > _FVG_FILL_THRESHOLD:
        score -= 15.0
        components.append(("Filled", -15.0, f">{_FVG_FILL_THRESHOLD:.0%} filled ({best_fvg.overlap_with_price:.0%})"))
        
    # 3. Size Bonus
    if getattr(best_fvg, "size_atr", 0.0) > 1.0:
        score += 15.0
        components.append(("Large Gap", 15.0, f">1.0 ATR ({best_fvg.size_atr:.1f})"))
        
    # 4. Stacking Bonus
    if len(aligned_fvgs) > 1:
        score += 10.0
        components.append(("Stacked", 10.0, f"{len(aligned_fvgs)} FVGs detected"))
        
    # 5. HTF Bonus
    tf = best_fvg.timeframe.lower()
    if tf in ["4h", "1d", "1w"]:
        score += 10.0
        components.append(("HTF FVG", 10.0, f"{best_fvg.timeframe} timeframe"))

    return {
        "score": max(0.0, min(100.0, score)),
        "rationale": f"FVG ({grade}): " + ", ".join([f"{c[0]}({c[1]:+.0f})" for c in components]),
        "components": components,
        "best_fvg": best_fvg
    }

def _score_market_structure_incremental(
    smc_snapshot: SMCSnapshot, direction: str
) -> Dict[str, Any]:
    """
    Score market structure (BOS/ChoCH) with detailed incremental factors.
    """
    score = _score_structural_breaks(smc_snapshot.structural_breaks, direction)
    
    # Add swing structure alignment bonus
    components = []
    if score > 0:
        components.append(("Structure Break", score, "Aligned BOS/ChoCH"))
    
    # Check Swing Structure (HH/HL etc)
    bias_res = _score_htf_structure_bias(smc_snapshot.swing_structure, direction)
    if bias_res["bonus"] > 0:
        bonus = bias_res["bonus"]
        score += bonus
        components.append(("Swing Bias", bonus, bias_res["reason"]))
    elif bias_res["bonus"] < 0:
        penalty = bias_res["bonus"]
        score += penalty
        components.append(("Swing Conflict", penalty, bias_res["reason"]))

    return {
        "score": max(0.0, min(100.0, score)),
        "rationale": _get_structure_rationale(smc_snapshot.structural_breaks, direction),
        "components": components
    }


def _score_liquidity_sweeps_incremental(
    sweeps: List[LiquiditySweep], direction: str
) -> Dict[str, Any]:
    """
    Score liquidity sweeps with detailed incremental factors.
    """
    score = _score_liquidity_sweeps(sweeps, direction)
    
    return {
        "score": max(0.0, min(100.0, score)),
        "rationale": _get_sweep_rationale(sweeps, direction),
        "components": [("Sweep Confirmation", score, "Liquidity sweep detected")] if score > 0 else []
    }


def _score_institutional_sequence(
    smc_snapshot: SMCSnapshot, direction: str
) -> Tuple[float, str]:
    """
    Score institutional sequence (Sweep -> Shift -> Return to OB).
    
    This is the highest probability entry pattern.
    """
    score = 0.0
    reason_parts = []
    
    # 1. Look for recent sweep in direction
    norm_dir = _normalize_direction(direction)
    target_type = "low" if norm_dir == "bullish" else "high"
    has_sweep = any(getattr(s, "sweep_type", "") == target_type for s in smc_snapshot.liquidity_sweeps)
    
    # 2. Look for recent BOS/ChoCH in direction
    has_shift = any(getattr(b, "direction", "") == norm_dir for b in smc_snapshot.structural_breaks)
    
    # 3. Look for recent OB in direction
    has_ob = any(ob.direction == norm_dir for ob in smc_snapshot.order_blocks)
    
    if has_sweep and has_shift and has_ob:
        score = 100.0
        reason_parts.append("Institutional Sequence confirmed (Sweep + Shift + OB)")
    elif has_sweep and has_shift:
        score = 70.0
        reason_parts.append("Incomplete sequence (Sweep + Shift, missing OB confirmation)")
    elif has_shift and has_ob:
        score = 50.0
        reason_parts.append("Partial sequence (Shift + OB, no preceding sweep)")
        
    return score, " | ".join(reason_parts) if reason_parts else "No institutional sequence detected"


def _detect_nested_ob(smc: SMCSnapshot, direction: str) -> bool:
    """Detect if a lower timeframe OB is nested within a higher timeframe OB."""
    norm_dir = _normalize_direction(direction)
    obs = [ob for ob in smc.order_blocks if ob.direction == norm_dir]
    
    # Need at least two OBs to have nesting
    if len(obs) < 2:
        return False
        
    # Group by timeframe
    tf_groups = {}
    for ob in obs:
        tf = ob.timeframe
        if tf not in tf_groups:
            tf_groups[tf] = []
        tf_groups[tf].append(ob)
        
    tfs = sorted(tf_groups.keys(), key=lambda x: _get_timeframe_weight(x), reverse=True)
    
    for i in range(len(tfs)):
        htf = tfs[i]
        for j in range(i + 1, len(tfs)):
            ltf = tfs[j]
            
            for h_ob in tf_groups[htf]:
                for l_ob in tf_groups[ltf]:
                    # Calculate overlap percentage
                    range_low = max(l_ob.low, h_ob.low)
                    range_high = min(l_ob.high, h_ob.high)
                    overlap = 0.0
                    if range_high > range_low:
                        overlap_size = range_high - range_low
                        l_ob_size = l_ob.high - l_ob.low
                        if l_ob_size > 0:
                            overlap = overlap_size / l_ob_size
                            
                    # Check if l_ob is nested in h_ob based on containment constant
                    if overlap >= NESTED_OB_CONTAINMENT_MIN:
                        return True
    return False


def _score_divergences_incremental(
    divergences: Dict[str, List[Any]], 
    direction: str
) -> Dict[str, Any]:
    """
    Score divergences with incremental logic.
    
    Factors:
    1. Divergence Type: Regular (Reversal) > Hidden (Continuation)
    2. Strength: Linear scaling 0-100
    3. Multi-Indicator: RSI + MACD = higher confidence
    4. Count: Multiple divergences = higher confidence
    
    Returns detailed score dict.
    """
    normalized_dir = _normalize_direction(direction)
    score = 0.0
    components = []
    
    # Process RSI Divergences
    rsi_divs = divergences.get("rsi", [])
    for div in rsi_divs:
        # Check direction match (divs are usually pre-filtered but safety check)
        is_bullish = div.divergence_type.endswith("bullish")
        target_bullish = normalized_dir == "bullish"
        
        if is_bullish != target_bullish:
            continue
            
        strength_score = div.strength * 0.4
        
        if "regular" in div.divergence_type:
             # Regular divergence = Reversal signal (Stronger)
             score += 15.0 + strength_score
             components.append((f"RSI Regular", 15.0 + strength_score, f"{div.strength:.0f}% strength"))
        else:
             # Hidden divergence = Continuation signal (Weaker but valuable)
             score += 10.0 + strength_score
             components.append((f"RSI Hidden", 10.0 + strength_score, f"{div.strength:.0f}% strength"))

    # Process MACD Divergences
    macd_divs = divergences.get("macd", [])
    for div in macd_divs:
        is_bullish = div.divergence_type.endswith("bullish")
        target_bullish = normalized_dir == "bullish"
        
        if is_bullish != target_bullish:
            continue

        strength_score = div.strength * 0.3 # Slightly less weight than RSI
        
        if "regular" in div.divergence_type:
            score += 12.0 + strength_score
            components.append((f"MACD Regular", 12.0 + strength_score, f"{div.strength:.0f}% strength"))
        else:
            score += 8.0 + strength_score
            components.append((f"MACD Hidden", 8.0 + strength_score, f"{div.strength:.0f}% strength"))
            
    # Bonuses
    if rsi_divs and macd_divs:
        score += 15.0
        components.append(("Confluence", 15.0, "RSI + MACD aligned"))

    return {
        "score": max(0.0, min(100.0, score)),
        "rationale": "Divergence: " + ", ".join([f"{c[0]}({c[1]:+.0f})" for c in components]) if components else "",
        "components": components,
        "has_divergence": bool(components)
    }


def _score_fibonacci_incremental(
    current_price: float,
    swing_structure: Dict[str, Any],
    direction: str
) -> Dict[str, Any]:
    """
    Score Fibonacci confluence with incremental logic.
    
    Factors:
    1. Proximity: Closer = higher score (<0.5% = 100pts)
    2. Key Level: 61.8% (Golden) > 50%
    3. Timeframe: HTF (1D/4H) > LTF
    
    Returns detailed score dict.
    """
    if not current_price or not swing_structure:
         return {"score": 0.0, "rationale": "", "components": []}

    score = 0.0
    components = []
    
    fib_timeframes = ["1d", "1D", "4h", "4H"]
    best_proximity = float("inf")
    
    # Check HTF Fibs
    for tf in fib_timeframes:
        ss = swing_structure.get(tf) or swing_structure.get(tf.lower())
        if not ss:
            continue
            
        # Extract swings (handle dict or object)
        swing_high = ss.get("last_hh") or ss.get("last_lh") if isinstance(ss, dict) else getattr(ss, "last_hh", None) or getattr(ss, "last_lh", None)
        swing_low = ss.get("last_ll") or ss.get("last_hl") if isinstance(ss, dict) else getattr(ss, "last_ll", None) or getattr(ss, "last_hl", None)
        
        if not (swing_high and swing_low and swing_high > swing_low):
            continue
            
        # Determine trend for Fib calc
        midpoint = (swing_high + swing_low) / 2
        # If trading bullish, we want price at a discount (low), retracing from a high
        # So trend direction for fib tool is UP (Low -> High)
        # Wait, calculate_fib_levels expects the trend direction
        # If trend is bullish (Up), levels are below price (retracement targets)
        # If we are looking for LONGs (bullish), we want to buy at a support level below current price? 
        # No, current price IS at the level.
        # If we are LONGING, we expect price to bounce UP from a level.
        # So the prior move was likely UP (Bullish), and we are retracing DOWN.
        # So trend_direction = "bullish"
        
        fib_trend = "bullish" if direction.lower() in ["bullish", "long"] else "bearish"
        
        levels = calculate_fib_levels(swing_high, swing_low, fib_trend, tf)
        nearest = find_nearest_fib(current_price, levels)
        
        if nearest:
            prox = get_fib_proximity_pct(current_price, nearest)
            best_proximity = min(best_proximity, prox)
            
            # Score this level
            level_score = 0.0
            
            # 1. Proximity Score
            if prox <= 0.3:
                level_score += 60.0
            elif prox <= 0.6:
                level_score += 40.0
            elif prox <= 1.2:
                level_score += 20.0
            else:
                continue # Too far
                
            # 2. Key Level Bonus (Golden Pocket)
            if 0.61 <= nearest.ratio <= 0.66:
                level_score += 25.0
                level_name = "Golden Pocket"
            elif 0.5 <= nearest.ratio <= 0.61:
                 level_score += 15.0
                 level_name = f"{nearest.ratio:.3f} Fib"
            else:
                 level_name = f"{nearest.ratio:.3f} Fib"
                 
            # 3. TF Weight
            if tf.lower() == "1d":
                level_score *= 1.2
            
            if level_score > score:
                score = level_score
                components = [(f"{tf} {level_name}", level_score, f"{prox:.2f}% away")]

    return {
        "score": max(0.0, min(100.0, score)),
        "rationale": f"Fibonacci: {components[0][0]} ({components[0][2]})" if components else "",
        "components": components
    }


def _score_structural_breaks(breaks: List[StructuralBreak], direction: str) -> float:
    """Score structural breaks (BOS/CHoCH) with grade and TF weighting.

    Note: Filters to direction-aligned breaks and meaningful HTF breaks (1H+).
    LTF breaks are heavily penalized to prevent 5m BOS from driving the structure score.
    """
    if not breaks:
        return 0.0

    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)

    # Filter to direction-aligned breaks FIRST
    aligned_breaks = [b for b in breaks if getattr(b, "direction", "bullish") == normalized_dir]

    if not aligned_breaks:
        # No aligned breaks - log and return 0
        opposite_dir = "bearish" if normalized_dir == "bullish" else "bullish"
        opposite_count = len(
            [b for b in breaks if getattr(b, "direction", "bullish") == opposite_dir]
        )
        logger.debug(
            "📊 Structure Score: 0 aligned (looking for %s) | %d total | %d %s breaks exist",
            normalized_dir,
            len(breaks),
            opposite_count,
            opposite_dir,
        )
        return 0.0

    # Filter to meaningful timeframes (1H+) - LTF breaks are noise
    meaningful_tfs = {"1w", "1W", "1d", "1D", "4h", "4H", "1h", "1H"}
    meaningful_breaks = [
        b for b in aligned_breaks if getattr(b, "timeframe", "1h") in meaningful_tfs
    ]

    if not meaningful_breaks:
        # Fallback to any aligned break but heavily penalized (LTF-only)
        latest_break = max(aligned_breaks, key=lambda b: b.timestamp)
        base_score = 30.0  # Much lower base for LTF-only
        tf_weight = 0.3  # Additional penalty
    else:
        # Use most recent meaningful break
        latest_break = max(meaningful_breaks, key=lambda b: b.timestamp)
        # BOS in trend direction is strongest
        if latest_break.break_type == "BOS":
            base_score = 80.0
        else:  # CHoCH
            base_score = 60.0
        # Bonus for HTF alignment
        if latest_break.htf_aligned:
            base_score += 20.0
        tf_weight = _get_timeframe_weight(getattr(latest_break, "timeframe", "1h"))

    # Apply grade weighting and timeframe weighting
    grade_weight = _get_grade_weight(getattr(latest_break, "grade", "B"))
    score = base_score * grade_weight * tf_weight

    logger.debug(
        "📊 Structure Score: %.1f (%s %s | base=%.1f, grade=%s, tf=%s)",
        score,
        latest_break.break_type,
        normalized_dir,
        base_score,
        getattr(latest_break, "grade", "B"),
        getattr(latest_break, "timeframe", "?"),
    )

    return min(100.0, score)


def _score_liquidity_sweeps(sweeps: List[LiquiditySweep], direction: str) -> float:
    """Score liquidity sweeps with grade and TF weighting."""
    if not sweeps:
        return 0.0

    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)

    # Look for recent sweeps that align with direction
    # Bullish setup benefits from low sweeps, bearish from high sweeps
    target_type = "low" if normalized_dir == "bullish" else "high"

    aligned_sweeps = [s for s in sweeps if s.sweep_type == target_type]

    if not aligned_sweeps:
        return 0.0

    # Prefer HTF sweeps (they're institutional), then confirmation level, then timestamp
    best_sweep = max(
        aligned_sweeps,
        key=lambda s: (
            _get_timeframe_weight(getattr(s, "timeframe", "1h")),
            getattr(s, "confirmation_level", 1 if s.confirmation else 0),
            s.timestamp,
        ),
    )

    # Phase 4: Score based on confirmation level (0-3)
    conf_level = getattr(best_sweep, "confirmation_level", 1 if best_sweep.confirmation else 0)

    if conf_level >= 3:
        base_score = 85.0  # Structure-validated = strongest
    elif conf_level == 2:
        base_score = 75.0  # Volume + pattern
    elif conf_level == 1:
        base_score = 60.0  # Volume or pattern only
    else:
        base_score = 45.0  # Unconfirmed sweep

    # Apply grade weighting and timeframe weighting
    grade_weight = _get_grade_weight(getattr(best_sweep, "grade", "B"))
    tf_weight = _get_timeframe_weight(getattr(best_sweep, "timeframe", "1h"))
    score = base_score * grade_weight * tf_weight

    logger.debug(
        "💧 Sweep Score: %.1f (conf_lvl=%d, base=%.1f, grade=%s, tf=%s)",
        score,
        conf_level,
        base_score,
        getattr(best_sweep, "grade", "B"),
        getattr(best_sweep, "timeframe", "?"),
    )

    return min(100.0, score)


# --- Indicator Scoring Functions ---


def _calculate_gradient_score(
    value: float,
    neutral_low: float,
    neutral_high: float,
    extreme_low: float,
    extreme_high: float,
    direction: str,
    multiplier: float = 1.0,
    max_points: float = 50.0,
) -> float:
    """
    Calculate gradient score for oscillator values.

    Implements smooth scoring curve instead of binary thresholds:
    - Neutral Zone (between neutral_low and neutral_high): 0 points
    - Gradient from neutral to extreme: linear scaling
    - Beyond extreme: capped at max_points

    Args:
        value: Current indicator value
        neutral_low: Lower boundary of neutral zone
        neutral_high: Upper boundary of neutral zone
        extreme_low: Extreme oversold threshold
        extreme_high: Extreme overbought threshold
        direction: 'bullish' or 'bearish'
        multiplier: Gradient slope multiplier
        max_points: Maximum points awarded

    Returns:
        Score from 0 to max_points
    """
    if direction == "bullish":
        # Looking for oversold conditions (low values)
        if value >= neutral_low:
            return 0.0  # Neutral or overbought - no score
        # Clamp value to extreme_low
        clamped = max(extreme_low, value)
        delta = neutral_low - clamped
        return min(max_points, delta * multiplier)
    else:  # bearish
        # Looking for overbought conditions (high values)
        if value <= neutral_high:
            return 0.0  # Neutral or oversold - no score
        # Clamp value to extreme_high
        clamped = min(extreme_high, value)
        delta = clamped - neutral_high
        return min(max_points, delta * multiplier)


def _score_momentum(
    indicators: IndicatorSnapshot,
    direction: str,
    macd_config: Optional[MACDModeConfig] = None,
    htf_indicators: Optional[IndicatorSnapshot] = None,
    timeframe: str = "15m",
) -> Tuple[float, Optional[Dict]]:
    """
    Score momentum indicators with mode-aware MACD evaluation.

    Args:
        indicators: Current timeframe indicators
        direction: Trade direction ("bullish"/"bearish" or "LONG"/"SHORT")
        macd_config: Mode-specific MACD configuration (if None, uses legacy scoring)
        htf_indicators: HTF indicators for MACD bias check
        timeframe: Current timeframe string

    Returns:
        Tuple of (score, macd_analysis_dict or None)
    """
    score = 0.0
    macd_analysis = None

    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)

    # ==============================================================================
    # GRADIENT SCORING WITH CATEGORY CAPPING
    # ==============================================================================
    # Prior issue: RSI, Stoch, MFI are highly correlated (all reflect same momentum).
    # Summing them inflated scores (e.g., RSI 30 + Stoch 20 + MFI 25 = 3x signal for one move).
    #
    # Solution: Weighted average with hard cap (MOMENTUM_CATEGORY_CAP).
    # - RSI: Primary (1.0 weight)
    # - Stoch: Secondary (0.5 weight) - adds confirmation, not full signal
    # - MFI: Tertiary (0.5 weight) - volume-weighted RSI, confirms but doesn't triple count
    #
    # This prevents multicollinearity while preserving nuance.
    # ==============================================================================

    rsi_score = 0.0
    stoch_score = 0.0
    mfi_score = 0.0

    if normalized_dir == "bullish":
        # Bullish momentum: oversold RSI, low Stoch RSI, low MFI
        if indicators.rsi is not None:
            # Neutral zone: 45-55 (no score)
            # Gradient: 45 -> 20 (extreme oversold)
            # Multiplier: 2.0 (from MOMENTUM_SLOPE_MULTIPLIER)
            rsi_score = _calculate_gradient_score(
                value=indicators.rsi,
                neutral_low=45.0,
                neutral_high=55.0,
                extreme_low=20.0,
                extreme_high=80.0,
                direction="bullish",
                multiplier=MOMENTUM_SLOPE_MULTIPLIER,
                max_points=50.0,
            )

        if indicators.stoch_rsi is not None:
            stoch_score = _calculate_gradient_score(
                value=indicators.stoch_rsi,
                neutral_low=40.0,
                neutral_high=60.0,
                extreme_low=0.0,
                extreme_high=100.0,
                direction="bullish",
                multiplier=1.5,
                max_points=45.0,
            )

        if indicators.mfi is not None:
            mfi_score = _calculate_gradient_score(
                value=indicators.mfi,
                neutral_low=40.0,
                neutral_high=60.0,
                extreme_low=0.0,
                extreme_high=100.0,
                direction="bullish",
                multiplier=1.5,
                max_points=40.0,
            )

    else:  # bearish
        # Bearish momentum: overbought RSI, high Stoch RSI, high MFI
        if indicators.rsi is not None:
            rsi_score = _calculate_gradient_score(
                value=indicators.rsi,
                neutral_low=45.0,
                neutral_high=55.0,
                extreme_low=20.0,
                extreme_high=80.0,
                direction="bearish",
                multiplier=MOMENTUM_SLOPE_MULTIPLIER,
                max_points=50.0,
            )

        if indicators.stoch_rsi is not None:
            stoch_score = _calculate_gradient_score(
                value=indicators.stoch_rsi,
                neutral_low=40.0,
                neutral_high=60.0,
                extreme_low=0.0,
                extreme_high=100.0,
                direction="bearish",
                multiplier=1.5,
                max_points=45.0,
            )

        if indicators.mfi is not None:
            mfi_score = _calculate_gradient_score(
                value=indicators.mfi,
                neutral_low=40.0,
                neutral_high=60.0,
                extreme_low=0.0,
                extreme_high=100.0,
                direction="bearish",
                multiplier=1.5,
                max_points=40.0,
            )

    # Weighted sum: RSI (primary) + Stoch (secondary) + MFI (tertiary)
    raw_momentum = (rsi_score * 1.0) + (stoch_score * 0.5) + (mfi_score * 0.5)

    # --- Mode-Aware MACD Evaluation ---
    macd_score_contrib = 0.0
    if macd_config:
        # Use new mode-aware MACD scoring
        macd_analysis = evaluate_macd_for_mode(
            indicators=indicators,
            direction=normalized_dir,
            macd_config=macd_config,
            htf_indicators=htf_indicators,
            timeframe=timeframe,
        )
        macd_score_contrib = macd_analysis["score"]

        # CRITICAL FIX: Include MACD in category cap BEFORE capping
        # Otherwise MACD can add 50-80 points on top of the 25pt cap, defeating the purpose
        raw_momentum_with_macd = raw_momentum + macd_score_contrib

        # Apply category cap to prevent inflation (includes MACD now)
        score = min(MOMENTUM_CATEGORY_CAP, raw_momentum_with_macd)
    else:
        # Legacy MACD scoring (fallback for backward compatibility)
        macd_line = getattr(indicators, "macd_line", None)
        macd_signal = getattr(indicators, "macd_signal", None)
        if macd_line is not None and macd_signal is not None:
            if normalized_dir == "bullish":
                if macd_line > macd_signal and macd_line > 0:
                    score += 20.0
                elif macd_line > macd_signal:
                    score += 12.0
                # Neutral MACD (opposing) gives 0 points - removed legacy +5 fallback
            else:  # bearish
                if macd_line < macd_signal and macd_line < 0:
                    score += 20.0
                elif macd_line < macd_signal:
                    score += 12.0
                # Neutral MACD (opposing) gives 0 points - removed legacy +5 fallback

        # Apply category cap for legacy path too
        score = min(MOMENTUM_CATEGORY_CAP, raw_momentum)

    # Stoch RSI K/D crossover enhancement (debounced by minimum separation)
    kd_bonus = 0.0
    k = getattr(indicators, "stoch_rsi_k", None)
    d = getattr(indicators, "stoch_rsi_d", None)
    if k is not None and d is not None:
        separation = abs(k - d)
        # Require minimum separation to reduce whipsaws
        if separation >= 2.0:  # simple debounce threshold
            if normalized_dir == "bullish" and k > d:
                # Region-sensitive weighting
                if k < 20:
                    kd_bonus += 25.0  # early oversold bullish cross
                elif k < 50:
                    kd_bonus += 15.0  # moderate bullish cross
                elif k < 80:
                    kd_bonus += 8.0
                else:
                    kd_bonus += 5.0  # late/exhaustive

                # Check previous values for FRESH crossover (just happened)
                k_prev = getattr(indicators, "stoch_rsi_k_prev", None)
                d_prev = getattr(indicators, "stoch_rsi_d_prev", None)
                if k_prev is not None and d_prev is not None and k_prev <= d_prev:
                    kd_bonus += 10.0  # Just crossed over!

            elif normalized_dir == "bearish" and k < d:
                if k > 80:
                    kd_bonus += 25.0  # overbought bearish cross
                elif k > 50:
                    kd_bonus += 15.0  # moderate bearish cross
                elif k > 20:
                    kd_bonus += 8.0
                else:
                    kd_bonus += 5.0

                # Check previous values for FRESH crossover (just happened)
                k_prev = getattr(indicators, "stoch_rsi_k_prev", None)
                d_prev = getattr(indicators, "stoch_rsi_d_prev", None)
                if k_prev is not None and d_prev is not None and k_prev >= d_prev:
                    kd_bonus += 10.0  # Just crossed under!
            else:
                # Opposing crossover strong penalty (avoid chasing into momentum shift)
                if separation >= 5.0:
                    kd_bonus -= 10.0

    # Re-apply cap after K/D bonus to prevent cap bypass
    score = min(MOMENTUM_CATEGORY_CAP, score + kd_bonus)

    # ADX Trend Strength & DI Confirmation
    adx = getattr(indicators, "adx", None)
    plus_di = getattr(indicators, "adx_plus_di", None)
    minus_di = getattr(indicators, "adx_minus_di", None)

    if adx is not None and plus_di is not None and minus_di is not None:
        di_bullish = plus_di > minus_di
        di_aligned = (normalized_dir == "bullish" and di_bullish) or (
            normalized_dir == "bearish" and not di_bullish
        )

        if adx > 25:
            if di_aligned:
                score += 20.0  # Strong trend confirmed
                if adx > 40:
                    score += 5.0  # Very strong trend
            else:
                score -= 15.0  # Counter-trend warning

        elif adx < 20:
            score -= 10.0  # Ranging/Weak trend

    # EMA Trend Alignment (EMA stacking)
    ema_9 = getattr(indicators, "ema_9", None)
    ema_21 = getattr(indicators, "ema_21", None)
    ema_50 = getattr(indicators, "ema_50", None)

    if ema_9 and ema_21 and ema_50:
        if normalized_dir == "bullish":
            if ema_9 > ema_21 > ema_50:
                score += 15.0  # Strong trend alignment
            elif ema_9 > ema_21:
                score += 5.0  # Moderate trend
        elif normalized_dir == "bearish":
            if ema_9 < ema_21 < ema_50:
                score += 15.0  # Strong trend alignment
            elif ema_9 < ema_21:
                score += 5.0  # Moderate trend

    # Bollinger Band %B - Mean Reversion / Breakout
    # %B > 1.0 = Above Upper Band (Strong Momentum or Overbought)
    # %B < 0.0 = Below Lower Band (Strong Momentum or Oversold)
    # In trend-following, riding the bands is good. In mean-reversion, it's an entry signal.
    pct_b = getattr(indicators, "bb_percent_b", None)
    if pct_b is not None:
        if normalized_dir == "bullish":
            # For bullish trend, we want price supported, not necessarily blown out
            # But if we are catching a dip, pct_b < 0 is great (oversold)
            if pct_b < 0.05:
                score += 20.0  # Deep discount / Oversold
            elif 0.4 <= pct_b <= 0.6:
                score += 5.0  # Supported at mid-band (continuation)
        elif normalized_dir == "bearish":
            if pct_b > 0.95:
                score += 20.0  # Premium / Overbought
            elif 0.4 <= pct_b <= 0.6:
                score += 5.0  # Resisting at mid-band

    # Clamp lower bound after penalties
    if score < 0:
        score = 0.0

    return (min(100.0, score), macd_analysis)


def _score_volume(indicators: IndicatorSnapshot, direction: str) -> float:
    """
    Score volume confirmation with acceleration bonuses.

    Scoring logic:
    - Base: 50 (neutral)
    - Volume spike: +30 (base 80)
    - Acceleration aligned with trade direction: +10-20
    - High consecutive increases (3+): +10-15
    - Volume exhaustion in opposite direction: +10 (reversal confirmation)
    - Acceleration against trade direction: -10-15 (momentum opposition)

    Args:
        indicators: Technical indicators including volume acceleration
        direction: Trade direction ('LONG', 'SHORT', 'bullish', 'bearish')

    Returns:
        Volume score 0-100
    """
    score = 40.0  # Base neutral score (lowered from 50 to penalize lack of signals)

    # Volume spike bonus
    if indicators.volume_spike:
        score += 35.0  # 40 -> 75 with spike

    # OBV trend confirmation
    obv_trend = getattr(indicators, "obv_trend", None)
    if obv_trend:
        is_bullish_trade = direction.lower() in ("long", "bullish")
        if is_bullish_trade and obv_trend == "rising":
            score += 15.0  # Accumulation confirms bullish
        elif not is_bullish_trade and obv_trend == "falling":
            score += 15.0  # Distribution confirms bearish
        elif (
            obv_trend != "flat"
            and obv_trend != "neutral"
            and obv_trend != ("rising" if is_bullish_trade else "falling")
        ):
            score -= 10.0  # OBV divergence warning

    # Volume acceleration bonuses
    vol_accel = getattr(indicators, "volume_acceleration", None)
    vol_accel_dir = getattr(indicators, "volume_accel_direction", None)
    vol_is_accel = getattr(indicators, "volume_is_accelerating", False)
    vol_consec = getattr(indicators, "volume_consecutive_increases", 0)
    vol_exhaust = getattr(indicators, "volume_exhaustion", False)

    # Normalize direction for comparison
    is_bullish_trade = direction.lower() in ("long", "bullish")

    if vol_accel is not None and vol_accel_dir is not None:
        # Direction alignment check
        accel_aligns_with_trade = (is_bullish_trade and vol_accel_dir == "bullish") or (
            not is_bullish_trade and vol_accel_dir == "bearish"
        )
        accel_opposes_trade = (is_bullish_trade and vol_accel_dir == "bearish") or (
            not is_bullish_trade and vol_accel_dir == "bullish"
        )

        if vol_is_accel and accel_aligns_with_trade:
            # Strong acceleration in trade direction - momentum confirmation
            if vol_accel > 0.2:
                score += 20.0  # Strong acceleration bonus
            elif vol_accel > 0.1:
                score += 10.0  # Moderate acceleration bonus

        elif accel_opposes_trade and vol_is_accel:
            # Acceleration AGAINST our trade direction - momentum opposition
            # This is a warning for continuation trades, but could be GOOD for reversal trades
            # For now, penalize slightly - reversal_detector handles reversal bonuses separately
            if vol_accel > 0.2:
                score -= 15.0  # Strong opposing momentum
            elif vol_accel > 0.1:
                score -= 10.0  # Moderate opposing momentum

    # Consecutive increases bonus (volume building up)
    if vol_consec is not None and vol_consec >= 3:
        if vol_consec >= 4:
            score += 15.0  # Strong sustained volume increase
        else:
            score += 10.0  # Moderate volume buildup

    # Volume exhaustion bonus (good for reversals)
    # When volume was spiking but now declining - indicates move may be exhausting
    if vol_exhaust:
        # This is most valuable when paired with reversal detection
        # Adds confidence that the prior move is losing steam
        score += 10.0

    # Volume Ratio / Magnitude Score (New Incremental Logic)
    vol_ratio = getattr(indicators, "volume_ratio", 1.0)
    if vol_ratio:
        if vol_ratio > 3.0:
            score += 25.0  # Extreme volume conviction
        elif vol_ratio > 2.0:
            score += 15.0  # High relative volume
        elif vol_ratio > 1.2:
            score += 5.0   # Above average
        elif vol_ratio < 0.5:
            score -= 10.0  # Very low likelihood

    return max(0.0, min(100.0, score))


def _score_kill_zone_incremental(
    current_time: datetime,
    kill_zone: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Score Kill Zone timing with incremental time-based precision.
    
    Evaluates:
    1. Session Active (+25 pts)
    2. Peak Hours (+20 pts) - First 2 hours of session
    3. Overlap (+15 pts) - London/NY overlap
    
    Note: No weekend penalty for crypto - markets trade 24/7.
    
    Returns detailed score and rationale components.
    """
    score = 0.0
    components = []
    
    # NOTE: No weekend penalty for crypto - markets trade 24/7
    # (Traditional markets have liquidity drought on weekends, crypto does not)
        
    # 1. Session Active (+25 pts)
    if kill_zone:
        score += 25.0
        kz_name = kill_zone.value.replace("_", " ").title() if hasattr(kill_zone, "value") else str(kill_zone)
        components.append(("Active KZ", 25.0, f"{kz_name} active"))
        
    # 3. Overlap / Prime Session Check (+10 pts)
    # Simple heuristic without timezone math: NY Open and London Open are prime
    if kill_zone:
        kz_str = str(kill_zone).lower()
        if "new_york" in kz_str or "london_open" in kz_str:
             # Major sessions get a "Prime Session" bonus
            score += 10.0
            components.append(("Prime Session", 10.0, "Major volume session"))
            
    return {
        "score": max(0.0, min(100.0, score)),
        "rationale": ", ".join([f"{c[0]}({c[1]:+.0f})" for c in components]) if components else "Outside kill zones",
        "components": components,
        "in_zone": bool(kill_zone)
    }


def _score_volatility(indicators: IndicatorSnapshot) -> float:
    """Score volatility using ATR% (price-normalized ATR). Prefer moderate volatility.

    Bracket logic (atr_pct in % terms):
    - <0.25%: very low -> 30 (risk of chop)
    - 0.25% - 0.75%: linear ramp to 100 (ideal development range)
    - 0.75% - 1.5%: gentle decline from 95 to 70 (still acceptable)
    - 1.5% - 3.0%: decline from 70 to 40 (moves become erratic)
    - >3.0%: 25 (excessive volatility, unreliable structure)
    """
    atr_pct = getattr(indicators, "atr_percent", None)
    if atr_pct is None:
        # Default to neutral/weak score if data unavailable (prevent "Missing")
        return 40.0

    # Ensure positive
    if atr_pct <= 0:
        return 0.0

    # Convert fraction to percent if given as ratio (heuristic: assume atr_pct already % if > 1.0)
    val = atr_pct

    if val < 0.25:
        return 40.0  # Weak (Caution) instead of Missing/Fail
    if val < 0.75:
        # Map 0.25 -> 40 up to 0.75 -> 100
        return 40.0 + (val - 0.25) / (0.75 - 0.25) * (100.0 - 40.0)
    if val < 1.5:
        # 0.75 -> 95 down to 1.5 -> 70
        return 95.0 - (val - 0.75) / (1.5 - 0.75) * (95.0 - 70.0)
    if val < 3.0:
        # 1.5 -> 70 down to 3.0 -> 40
        return 70.0 - (val - 1.5) / (3.0 - 1.5) * (70.0 - 40.0)
    # >3.0
    # >3.0
    score = 25.0

    # Apply TTM Squeeze Modifiers
    if getattr(indicators, "ttm_squeeze_firing", False):
        score += 15.0  # Expansion likely - volatility developing
    elif getattr(indicators, "ttm_squeeze_on", False):
        score -= 5.0  # Compression - low volatility warning

    return max(0.0, min(100.0, score))



def _score_htf_alignment_incremental(
    htf_trend: str,
    direction: str,
    htf_indicators: Optional[IndicatorSnapshot] = None,
    indicator_set: Optional[IndicatorSet] = None,
) -> Dict[str, Any]:
    """
    Score HTF alignment with incremental multi-factor scoring.
    
    Evaluates 4 factors:
    1. Trend Direction Match (±40 pts) - Does HTF trend align with trade direction?
    2. Trend Strength via ADX (±25 pts) - How strong is the trend (ADX > 25)?
    3. Multi-TF Alignment (±15 pts) - Do multiple timeframes agree?
    4. DI Crossover (±10 pts) - Is +DI > -DI for bullish (or opposite for bearish)?
    
    Args:
        htf_trend: Higher timeframe trend ("bullish", "bearish", "neutral")
        direction: Trade direction ("bullish", "bearish")
        htf_indicators: Optional HTF indicator snapshot (4H/1D) for ADX data
        indicator_set: Optional full indicator set for multi-TF checks
    
    Returns:
        Dict with:
            - score: float (0-100)
            - aligned: bool
            - rationale: str
            - components: list of (factor_name, points, description)
    """
    score = 50.0  # Start neutral
    components = []
    is_bullish_trade = direction.lower() in ("bullish", "long")
    
    # --- Factor 1: Trend Direction Match (±40 pts) ---
    if htf_trend == direction:
        score += 40.0
        components.append(("Trend Match", 40.0, f"HTF trend {htf_trend} aligns"))
    elif htf_trend == "neutral":
        # Neutral is neither bonus nor penalty
        components.append(("Trend Neutral", 0.0, "HTF trend is neutral"))
    else:
        score -= 40.0
        components.append(("Trend Conflict", -40.0, f"HTF trend {htf_trend} opposes"))
    
    # --- Factor 2: Trend Strength via ADX (±25 pts) ---
    adx_score = 0.0
    if htf_indicators and htf_indicators.adx is not None:
        adx = htf_indicators.adx
        
        if adx >= 50:
            # Very strong trend
            if htf_trend == direction:
                adx_score = 25.0
                components.append(("Strong Trend", 25.0, f"ADX {adx:.0f} (very strong)"))
            elif htf_trend != "neutral":
                adx_score = -25.0
                components.append(("Strong Opposing", -25.0, f"ADX {adx:.0f} strongly against"))
        elif adx >= 25:
            # Trending
            if htf_trend == direction:
                # Scale linearly: ADX 25 = +12.5, ADX 50 = +25
                adx_score = 12.5 + (adx - 25) * 0.5
                components.append(("Trending", adx_score, f"ADX {adx:.0f} (trending)"))
            elif htf_trend != "neutral":
                adx_score = -(12.5 + (adx - 25) * 0.5)
                components.append(("Trending Against", adx_score, f"ADX {adx:.0f} against"))
        else:
            # Weak/ranging market (ADX < 25)
            # Small penalty for lack of trend
            adx_score = -5.0
            components.append(("Weak Trend", -5.0, f"ADX {adx:.0f} (ranging)"))
        
        score += adx_score
    
    # --- Factor 3: Multi-TF Alignment (±15 pts) ---
    mtf_score = 0.0
    if indicator_set:
        aligned_tfs = 0
        opposed_tfs = 0
        
        # Check trend across HTF timeframes by comparing EMAs
        for tf in ["1d", "1D", "4h", "4H", "1h", "1H"]:
            if tf.lower() in [t.lower() for t in indicator_set.get_timeframes()]:
                try:
                    tf_key = next(t for t in indicator_set.get_timeframes() if t.lower() == tf.lower())
                    tf_ind = indicator_set.get_indicator(tf_key)
                    # Use EMA alignment as proxy for trend
                    if tf_ind.ema_21 and tf_ind.ema_50:
                        if tf_ind.ema_21 > tf_ind.ema_50:
                            if is_bullish_trade:
                                aligned_tfs += 1
                            else:
                                opposed_tfs += 1
                        else:
                            if is_bullish_trade:
                                opposed_tfs += 1
                            else:
                                aligned_tfs += 1
                except (KeyError, StopIteration):
                    pass
        
        if aligned_tfs >= 2:
            mtf_score = min(15.0, aligned_tfs * 5.0)
            components.append(("MTF Aligned", mtf_score, f"{aligned_tfs} TFs aligned"))
        elif opposed_tfs >= 2:
            mtf_score = max(-15.0, -opposed_tfs * 5.0)
            components.append(("MTF Conflict", mtf_score, f"{opposed_tfs} TFs opposed"))
        
        score += mtf_score
    
    # --- Factor 4: DI Crossover Confirmation (±10 pts) ---
    di_score = 0.0
    if htf_indicators:
        plus_di = htf_indicators.adx_plus_di
        minus_di = htf_indicators.adx_minus_di
        
        if plus_di is not None and minus_di is not None:
            if is_bullish_trade:
                if plus_di > minus_di:
                    di_score = 10.0
                    components.append(("+DI Lead", 10.0, f"+DI {plus_di:.0f} > -DI {minus_di:.0f}"))
                elif minus_di > plus_di:
                    di_score = -10.0
                    components.append(("-DI Lead", -10.0, f"-DI {minus_di:.0f} > +DI {plus_di:.0f}"))
            else:  # Bearish trade
                if minus_di > plus_di:
                    di_score = 10.0
                    components.append(("-DI Lead", 10.0, f"-DI {minus_di:.0f} > +DI {plus_di:.0f}"))
                elif plus_di > minus_di:
                    di_score = -10.0
                    components.append(("+DI Lead", -10.0, f"+DI {plus_di:.0f} > -DI {minus_di:.0f}"))
        
        score += di_score
    
    # Clamp to 0-100
    score = max(0.0, min(100.0, score))
    
    # Build rationale string
    rationale_parts = [f"{c[0]}({c[1]:+.0f})" for c in components if c[1] != 0]
    rationale = f"HTF {htf_trend}: " + ", ".join(rationale_parts) if rationale_parts else f"HTF {htf_trend}"
    
    return {
        "score": score,
        "aligned": htf_trend == direction,
        "rationale": rationale,
        "components": components,
    }



# --- Synergy and Conflict ---


def _calculate_synergy_bonus(
    factors: List[ConfluenceFactor],
    smc: SMCSnapshot,
    cycle_context: Optional["CycleContext"] = None,
    reversal_context: Optional["ReversalContext"] = None,
    direction: str = "",
    mode_config: Optional["ScanConfig"] = None,
) -> float:
    """
    Calculate synergy bonus when multiple strong factors align.

    Includes cycle-aware bonuses when cycle/reversal context provided:
    - Cycle Turn Bonus (+15): CHoCH + cycle extreme + volume
    - Distribution Break Bonus (+15): CHoCH + LTR + distribution phase
    - Accumulation Zone Bonus (+12): Liquidity sweep + DCL/WCL + bullish OB

    Args:
        factors: List of confluence factors
        smc: SMC snapshot with patterns
        cycle_context: Optional cycle timing context
        reversal_context: Optional reversal detection context
        direction: Trade direction ("LONG" or "SHORT")

    Returns:
        Total synergy bonus
    """
    bonus = 0.0

    factor_names = [f.name for f in factors]

    # --- EXISTING SYNERGIES ---
    # Bug Fix: Previously awarded bonuses on name-presence only (no score check).
    # Now requires score >= 60 on each contributing factor — prevents C-grade
    # setups inflating past the confluence threshold via unearned synergy points.

    def _factor_score(name: str) -> float:
        """Get score for a named factor, 0 if not present."""
        f = next((x for x in factors if x.name == name), None)
        return f.score if f else 0.0

    # Order Block + FVG + Structure = strong institutional setup
    ob_score = _factor_score("Order Block")
    fvg_score = _factor_score("Fair Value Gap")
    struct_score = _factor_score("Market Structure")
    if ob_score >= 60 and fvg_score >= 60 and struct_score >= 60:
        bonus += 5.0
    elif ob_score > 0 and fvg_score > 0 and struct_score > 0:
        bonus += 2.0  # Partial: factors exist but below quality threshold

    # Liquidity Sweep + Structure = institutional trap reversal
    sweep_score = _factor_score("Liquidity Sweep")
    if sweep_score >= 60 and struct_score >= 60:
        bonus += 4.0
    elif sweep_score > 0 and struct_score > 0:
        bonus += 2.0  # Partial: weak sweep or weak structure

    # --- HTF SWEEP → LTF ENTRY SYNERGY ---
    # When HTF sweep detected, LTF entries in expected direction get bonus
    htf_context = getattr(smc, "htf_sweep_context", None)
    if htf_context and htf_context.get("has_recent_htf_sweep"):
        expected_dir = htf_context.get("expected_ltf_direction", "")
        direction_lower = direction.lower() if direction else ""

        # Check alignment: HTF swept low → expect bullish → LONG gets bonus
        # HTF swept high → expect bearish → SHORT gets bonus
        if expected_dir == "bullish" and direction_lower in ("long", "bullish"):
            bonus += 6.0  # REDUCED: was 12.0 - still strong but not excessive
            logger.debug(
                "📊 HTF sweep → LTF long alignment (+6): %s sweep signaled bullish",
                htf_context.get("sweep_timeframe", "?"),
            )
        elif expected_dir == "bearish" and direction_lower in ("short", "bearish"):
            bonus += 6.0  # REDUCED: was 12.0 - still strong but not excessive
            logger.debug(
                "📊 HTF sweep → LTF short alignment (+6): %s sweep signaled bearish",
                htf_context.get("sweep_timeframe", "?"),
            )

    # HTF Alignment + strong momentum
    if "HTF Alignment" in factor_names and "Momentum" in factor_names:
        momentum_factor = next((f for f in factors if f.name == "Momentum"), None)
        if momentum_factor and momentum_factor.score > 70:
            bonus += 5.0

    # --- CYCLE-AWARE SYNERGIES & GATES ---

    # Resolve profile and direction once, used by all cycle logic below
    profile = getattr(mode_config, "profile", "balanced").lower() if mode_config else "balanced"
    # FIX: _normalize_direction converts to "bullish"/"bearish", but cycle gates
    # compare against "LONG"/"SHORT". Map correctly so cycle context actually fires.
    _dir_lower = direction.lower() if direction else ""
    if _dir_lower in ("long", "bullish"):
        direction_upper = "LONG"
    elif _dir_lower in ("short", "bearish"):
        direction_upper = "SHORT"
    else:
        direction_upper = direction.upper() if direction else ""

    # Check if reversal_context qualifies for Surgical/Strike bypass of cycle gates
    htf_bypass = bool(
        reversal_context
        and getattr(reversal_context, "htf_bypass_active", False)
        and profile in ("surgical", "precision", "strike", "intraday_aggressive")
    )

    # Use reversal_context if available (combines cycle + SMC)
    if reversal_context and reversal_context.is_reversal_setup:
        try:
            from backend.strategy.smc.reversal_detector import combine_reversal_with_cycle_bonus
            if cycle_context:
                cycle_bonus = combine_reversal_with_cycle_bonus(reversal_context, cycle_context)
                bonus += cycle_bonus
                if cycle_bonus > 0:
                    logger.debug("Cycle synergy bonus: +%.1f", cycle_bonus)
        except ImportError:
            pass

        # Conflict penalty — opposing direction also qualified, reduce conviction
        if reversal_context.conflict_detected:
            margin = reversal_context.confidence - reversal_context.conflict_confidence
            # Small margin (< 10 pts) = near-tie = heavy penalty; wide margin = mild penalty
            conflict_penalty = max(5.0, 15.0 - margin * 0.5)
            bonus -= conflict_penalty
            logger.debug(
                "Conflict penalty: -%.1f (margin %.1f vs opposing %.1f)",
                conflict_penalty, margin, reversal_context.conflict_confidence,
            )

    # Direct cycle context bonuses/gates (when reversal_context not available or not a setup)
    if cycle_context:
        try:
            from backend.shared.models.smc import CyclePhase, CycleTranslation, CycleConfirmation

            # ── GATE 1: WCL FAILURE ─────────────────────────────────────────
            # When weekly cycle is broken, LONGs face mode-scaled penalties and
            # SHORTs get a mild contextual boost. Surgical/Strike can bypass via htf_bypass.
            #
            # SOFTENED: Cycle failures are informational signals, not hard directional
            # overrides. Previous penalties (-30, -999) caused massive SHORT bias
            # that destroyed win rate. Now penalties are soft nudges that let
            # confluence scoring drive direction based on the full signal picture.
            #
            # Penalty table — softened for balanced directional exposure:
            #   Overwatch:       moderate penalty (no more hard veto)
            #   Stealth/Strike:  soft penalty (confluence still decides)
            #   Surgical:        minimal penalty (counter-trend scalps are its wheelhouse)
            WCL_FAIL_LONG_PENALTY = {
                "macro_surveillance": -12, "overwatch": -12,
                "stealth_balanced":    -8,  "stealth":   -8,
                "intraday_aggressive": -5,  "strike":    -5,
                "precision":           -3,  "surgical":  -3,
            }
            WCL_FAIL_SHORT_BOOST = 5  # Softened from 20 → 5 (informational, not directional override)

            wcl_failed = getattr(cycle_context, "wcl_failed", False)
            dcl_failed = getattr(cycle_context, "dcl_failed", False)

            if wcl_failed:
                if direction_upper == "LONG" and not htf_bypass:
                    penalty_val = WCL_FAIL_LONG_PENALTY.get(profile, -5)
                    # No more hard veto (-999) — let confluence decide
                    bonus += penalty_val
                    logger.debug("WCL FAILED — LONG soft penalty %.1f for %s", penalty_val, profile)
                elif direction_upper == "SHORT":
                    bonus += WCL_FAIL_SHORT_BOOST
                    logger.debug("WCL FAILED — SHORT soft boost +%d", WCL_FAIL_SHORT_BOOST)

            elif dcl_failed and not wcl_failed:
                # DCL failure only (shorter-term bearish signal, softened)
                DCL_FAIL_LONG_PENALTY = {
                    "macro_surveillance": -8, "overwatch": -8,
                    "stealth_balanced":   -5,  "stealth":  -5,
                    "intraday_aggressive": -3, "strike":   -3,
                    "precision":           -2,  "surgical": -2,
                }
                if direction_upper == "LONG" and not htf_bypass:
                    pen = DCL_FAIL_LONG_PENALTY.get(profile, -3)
                    bonus += pen
                    logger.debug("DCL FAILED — LONG soft penalty %.1f for %s", pen, profile)
                elif direction_upper == "SHORT":
                    bonus += 3  # Softened from 8 → 3 (informational, not directional override)
                    logger.debug("DCL FAILED — SHORT soft boost +3")

            # ── GATE 2: MARKDOWN + LTR PHASE GATE ───────────────────────────
            # Penalise LONG signals in a left-translated markdown market.
            # FIX: Only fire when WCL/DCL did NOT already apply a penalty.
            # Previously this was a separate `if` that stacked with Gate 1,
            # creating up to -18 combined penalty for LONG (vs +5 for SHORT)
            # which overwhelmed the 8-point DIRECTION_MARGIN and forced
            # all trades to SHORT.
            MARKDOWN_LTR_LONG_PENALTY = {
                "macro_surveillance": -10, "overwatch": -10,
                "stealth_balanced":    -6,  "stealth":   -6,
                "intraday_aggressive": -4,  "strike":    -4,
                "precision":           -2,  "surgical":  -2,
            }
            # FIX: Symmetric SHORT penalty in bullish accumulation/markup
            ACCUMULATION_RTR_SHORT_PENALTY = {
                "macro_surveillance": -10, "overwatch": -10,
                "stealth_balanced":    -6,  "stealth":   -6,
                "intraday_aggressive": -4,  "strike":    -4,
                "precision":           -2,  "surgical":  -2,
            }
            if not wcl_failed and not dcl_failed:
                # Only apply phase gate when cycle failures haven't already penalized
                if (
                    direction_upper == "LONG"
                    and not htf_bypass
                    and cycle_context.phase in [CyclePhase.DISTRIBUTION, CyclePhase.MARKDOWN]
                    and cycle_context.translation == CycleTranslation.LTR
                ):
                    pen = MARKDOWN_LTR_LONG_PENALTY.get(profile, -10)
                    bonus += pen
                    logger.debug(
                        "%s + LTR phase gate — LONG penalty %.1f for %s",
                        cycle_context.phase.value, pen, profile,
                    )
                # FIX: Symmetric — penalize SHORT in bullish accumulation/markup + RTR
                elif (
                    direction_upper == "SHORT"
                    and not htf_bypass
                    and cycle_context.phase in [CyclePhase.ACCUMULATION, CyclePhase.MARKUP]
                    and cycle_context.translation == CycleTranslation.RTR
                ):
                    pen = ACCUMULATION_RTR_SHORT_PENALTY.get(profile, -10)
                    bonus += pen
                    logger.debug(
                        "%s + RTR phase gate — SHORT penalty %.1f for %s",
                        cycle_context.phase.value, pen, profile,
                    )

            # ── BONUS: Standard cycle bonuses (only when no failure) ─────────
            if not wcl_failed and not dcl_failed:
                if direction_upper == "LONG":
                    # Accumulation + structure → long turn bonus
                    if (
                        cycle_context.phase == CyclePhase.ACCUMULATION
                        and "Market Structure" in factor_names
                    ):
                        bonus += 10.0
                        logger.debug("Accumulation + Structure bonus (+10)")

                    # Confirmed DCL/WCL zone
                    if (
                        cycle_context.in_dcl_zone or cycle_context.in_wcl_zone
                    ) and cycle_context.dcl_confirmation == CycleConfirmation.CONFIRMED:
                        bonus += 8.0
                        logger.debug("Confirmed cycle low bonus (+8)")

                    # ── GATE 3: RTR + HTF alignment — multiplicative, not additive ──
                    # When both RTR translation AND HTF alignment agree on LONG,
                    # apply a multiplied bonus instead of two separate additive ones.
                    htf_factor = next((f for f in factors if f.name == "HTF Alignment"), None)
                    rtr_active = cycle_context.translation == CycleTranslation.RTR
                    htf_bullish = htf_factor and htf_factor.score >= 60

                    if rtr_active and htf_bullish:
                        # Multiplicative synergy: existing bonus * 1.25 + flat bonus
                        mult_bonus = (bonus * 0.25) + 8.0
                        bonus += mult_bonus
                        logger.debug(
                            "RTR + HTF alignment multiplicative synergy: +%.1f", mult_bonus
                        )
                    elif rtr_active:
                        bonus += 5.0
                        logger.debug("RTR translation bonus (+5)")

                elif direction_upper == "SHORT":
                    # LTR + distribution/markdown
                    if cycle_context.translation == CycleTranslation.LTR and cycle_context.phase in [
                        CyclePhase.DISTRIBUTION,
                        CyclePhase.MARKDOWN,
                    ]:
                        bonus += 12.0
                        logger.debug("LTR Distribution bonus (+12)")

                    # Distribution + structure
                    if (
                        cycle_context.phase == CyclePhase.DISTRIBUTION
                        and "Market Structure" in factor_names
                    ):
                        bonus += 8.0
                        logger.debug("Distribution + Structure bonus (+8)")
                    elif cycle_context.translation == CycleTranslation.LTR:
                        bonus += 5.0
                        logger.debug("LTR translation bonus (+5)")

        except ImportError:
            pass  # Cycle models not available

    # Apply diminishing returns after ±8 points (symmetric for both directions)
    if bonus > 8.0:
        excess = bonus - 8.0
        bonus = 8.0 + (excess * 0.4)
        logger.debug("Synergy diminishing applied (positive): excess %.1f -> %.1f", excess, excess * 0.4)
    elif bonus < -8.0:
        excess = abs(bonus) - 8.0
        bonus = -8.0 - (excess * 0.4)
        logger.debug("Synergy diminishing applied (negative): excess %.1f -> %.1f", excess, excess * 0.4)

    # Mode-aware synergy cap.
    # Clamp to [0, cap]: synergy_bonus is additive-only in the scoring formula.
    # Negative cycle penalties (Gate 1/2) reduce synergy to 0 at worst — they
    # don't push the value below zero. Actual opposing-signal penalization lives
    # in _calculate_conflict_penalty, which has its own validated channel.
    cap = MODE_SYNERGY_CAPS.get(profile, 12.0)
    result = max(0.0, min(bonus, cap))
    logger.debug("Synergy bonus: %.1f (cap=%.1f for %s mode)", result, cap, profile)
    return result



def _calculate_conflict_penalty(
    factors: List[ConfluenceFactor],
    direction: str,
    smc: Optional[SMCSnapshot] = None,
    mode_config: Optional["ScanConfig"] = None,
    regime: Optional[Any] = None,
    btc_impulse: Optional[str] = None,
) -> float:
    """
    Calculate penalty for conflicting signals with mode-awareness and confluence override.

    Penalties are reduced when strong confluence exists (Institutional Sequence, etc.)
    and scaled by mode risk tolerance (Surgical = 0.6x, Strike = 0.75x, etc.)

    Regime-aware: the override cap is halved for counter-trend trades in strongly
    trending or compressed markets so regime penalties are never fully wiped out.
    """
    penalty = 0.0

    # BTC conflict — asymmetric by direction of opposition.
    # Alts correlate strongly with BTC in current conditions:
    #   SHORT alt while BTC is bullish: BTC drags alts up against the short — worst case, full penalty.
    #   LONG alt while BTC is bearish: alt may show relative strength or decouple — lower penalty.
    btc_factor = next((f for f in factors if f.name == "BTC Impulse Gate"), None)
    if btc_factor and btc_factor.score < 50.0:
        _is_long = direction.lower() in ("long", "bullish")
        _btc_up = btc_impulse in ("bullish", "strong_up", "extreme_up", "up")
        _btc_dn = btc_impulse in ("bearish", "strong_down", "extreme_down", "down")
        if _btc_up and not _is_long:
            _btc_conflict = 20.0  # SHORT alt while BTC bullish — squeezed by macro tide
        elif _btc_dn and _is_long:
            _btc_conflict = 8.0   # LONG alt while BTC bearish — possible decouple, lower risk
        elif btc_impulse is None and regime is not None:
            # BTC direction unknown, but regime trend gives a proxy.
            # An up-trending alt in a correlated market almost certainly means BTC is also
            # bullish — shorting into that is riskier than the neutral +10 implies.
            _regime_trend = getattr(regime, "trend", None)
            if _regime_trend is None and hasattr(regime, "dimensions"):
                _regime_trend = getattr(getattr(regime, "dimensions", None), "trend", None)
            if _regime_trend in ("up", "strong_up") and not _is_long:
                _btc_conflict = 15.0  # Up regime + SHORT + no BTC data → assume correlation
            else:
                _btc_conflict = 10.0
        else:
            _btc_conflict = 10.0  # No directional info available, use prior default
        penalty += _btc_conflict
        logger.debug(
            "BTC conflict: btc=%s dir=%s → +%.1f penalty", btc_impulse, direction, _btc_conflict
        )

    # Weak momentum in strong setup
    # NOTE: Momentum is capped at MOMENTUM_CATEGORY_CAP (25pts), so threshold must be < 25
    momentum_factor = next((f for f in factors if f.name == "Momentum"), None)
    structure_factor = next((f for f in factors if f.name == "Market Structure"), None)

    if momentum_factor and structure_factor:
        # Adjusted threshold: < 12 (half of 25pt cap) = truly weak momentum
        if momentum_factor.score < 12 and structure_factor.score > 70:
            penalty += 10.0  # Structure says go, momentum says no
            logger.debug(
                "Momentum/Structure conflict: Mom %.1f vs Struct %.1f → +10 penalty",
                momentum_factor.score,
                structure_factor.score,
            )

    # === HTF ALIGNMENT PENALTY ===
    # FIXED: Only penalize if HTF Alignment wasn't already scored as a factor
    # (otherwise we double-penalize: score 0 AND conflict penalty)
    htf_factor = next((f for f in factors if f.name == "HTF Alignment"), None)
    htf_already_scored_negative = (
        htf_factor and htf_factor.score < 30
    )  # Already penalized via low score

    if htf_factor and not htf_already_scored_negative:
        if htf_factor.score < 20.0:  # FIXED: was == 0.0 (too strict)
            # HTF opposing direction - major penalty (only if not already scored low)
            penalty += 15.0
            logger.debug("HTF opposition penalty: score %.1f → +15", htf_factor.score)
        elif 40.0 <= htf_factor.score <= 60.0:  # FIXED: was == 50.0 (too strict) - ranging/neutral
            # HTF neutral (ranging) - moderate penalty for counter-trend risk
            penalty += 8.0
            logger.debug("HTF neutral penalty: score %.1f → +8", htf_factor.score)

    # === OPPOSING STRUCTURAL BREAK PENALTY ===
    # BOS/CHoCH in the opposite direction of the trade is a direct structural conflict.
    # Previously this was never checked — opposing breaks were silently ignored.
    if smc:
        breaks = getattr(smc, "structural_breaks", []) or []
        opposing_dir = "bearish" if direction in ("bullish", "long", "LONG") else "bullish"
        opposing_breaks = [b for b in breaks if getattr(b, "direction", "") == opposing_dir]
        aligned_breaks  = [b for b in breaks if getattr(b, "direction", "") != opposing_dir]

        if opposing_breaks:
            # Grade the worst opposing break (A = most concerning)
            best_opposing_grade = min(
                (getattr(b, "grade", "C") for b in opposing_breaks),
                key=lambda g: {"A": 0, "B": 1, "C": 2}.get(g, 2),
            )
            # Penalty is higher when opposing break outgrades or equals the aligned structure
            best_aligned_grade = min(
                (getattr(b, "grade", "C") for b in aligned_breaks),
                key=lambda g: {"A": 0, "B": 1, "C": 2}.get(g, 2),
            ) if aligned_breaks else "C"

            grade_order = {"A": 0, "B": 1, "C": 2}
            if grade_order[best_opposing_grade] <= grade_order[best_aligned_grade]:
                struct_conflict_penalty = 12.0  # Opposing at least as strong as aligned
            else:
                struct_conflict_penalty = 6.0   # Opposing weaker grade than aligned

            penalty += struct_conflict_penalty
            logger.debug(
                "Opposing structure penalty: %d %s break(s) [best grade %s] → +%.1f",
                len(opposing_breaks), opposing_dir, best_opposing_grade, struct_conflict_penalty,
            )

    # Cap penalty to 35 (limit downside impact)
    penalty = min(penalty, 35.0)

    # === APPLY CONFLUENCE OVERRIDE ===
    # Strong confluence can reduce or eliminate penalties — but regime context
    # caps how much reduction is allowed for counter-trend trades in trending markets.
    if smc and mode_config and penalty > 0:
        override = _apply_sideways_override_cap(
            calculate_confluence_override(factors, smc, mode_config, direction, regime=regime),
            regime,
        )
        if override["reduction"] > 0:
            raw_reduction = override["reduction"]

            # --- Regime-aware override cap ---
            # Counter-trend in a clearly trending or compressed market should never
            # fully erase regime penalties even with a perfect institutional sequence.
            # Cap the reduction at 50% (0.5) in those conditions.
            regime_cap_applied = False
            if regime is not None:
                _dims = getattr(regime, "dimensions", None)
                _trend = getattr(_dims, "trend", None) or getattr(regime, "trend", "neutral")
                _vol   = getattr(_dims, "volatility", None) or getattr(regime, "volatility", "normal")
                _norm  = direction.lower()
                _is_counter = (
                    (_trend in ("up", "strong_up")   and _norm in ("bearish", "short")) or
                    (_trend in ("down", "strong_down") and _norm in ("bullish", "long"))
                )
                _is_trending_or_compressed = _trend in ("up", "strong_up", "down", "strong_down") or _vol in ("compressed", "low")
                if _is_counter and _is_trending_or_compressed and raw_reduction > 0.5:
                    raw_reduction = 0.5
                    regime_cap_applied = True

            original_penalty = penalty
            penalty = penalty * (1.0 - raw_reduction)
            logger.info(
                "🎯 Confluence override [%s]: %.0f%% reduction (%.1f → %.1f)%s - %s",
                override["triggered_by"],
                raw_reduction * 100,
                original_penalty,
                penalty,
                " [regime-capped]" if regime_cap_applied else "",
                override["rationale"]
            )
    
    # === APPLY MODE PENALTY MULTIPLIER ===
    # Conservative modes get heavier penalties, aggressive modes get lighter
    if mode_config:
        profile = getattr(mode_config, "profile", "balanced").lower()
        multiplier = MODE_PENALTY_MULTIPLIERS.get(profile, 1.0)
        if multiplier != 1.0:
            original = penalty
            penalty = penalty * multiplier
            logger.debug(
                "📊 Mode penalty multiplier: %.2fx for %s (%.1f → %.1f)",
                multiplier, profile, original, penalty
            )
    
    return penalty


def _detect_regime(smc: SMCSnapshot, indicators: IndicatorSet) -> str:
    """Detect current market regime with enhanced choppy detection.

    Returns:
        str: 'trend', 'risk_off', 'range', or 'choppy'
    """
    # Get primary timeframe indicators for volatility analysis
    if not indicators.by_timeframe:
        return "range"

    primary_tf = list(indicators.by_timeframe.keys())[0]
    primary_ind = indicators.by_timeframe[primary_tf]

    # === ENHANCED CHOPPY DETECTION (RELAXED THRESHOLDS) ===
    # Check ATR% for volatility contraction (choppy market sign)
    atr_pct = getattr(primary_ind, "atr_percent", None)
    rsi = getattr(primary_ind, "rsi", 50)

    # Choppy indicators (RELAXED from original strict thresholds):
    # 1. Low-moderate ATR% (was < 0.4, now < 0.8)
    # 2. RSI in broader neutral zone (was 40-60, now 35-65)
    # 3. Few or no structural breaks (was 0, now <= 2)
    is_low_volatility = atr_pct is not None and atr_pct < 0.8  # RELAXED from 0.4
    is_neutral_momentum = rsi is not None and 35 <= rsi <= 65  # RELAXED from 40-60

    # Check structural breaks
    recent_bos = (
        [b for b in smc.structural_breaks if b.break_type == "BOS"] if smc.structural_breaks else []
    )
    recent_choch = (
        [b for b in smc.structural_breaks if b.break_type == "CHoCH"]
        if smc.structural_breaks
        else []
    )
    
    # Minor BOS count (allow up to 2 without ruling out choppy)
    has_few_structure = len(recent_bos) <= 2 and len(recent_choch) == 0

    # CHOPPY: Low-moderate volatility + neutral RSI + few/no structure
    if is_low_volatility and is_neutral_momentum and has_few_structure:
        logger.debug(
            "Market regime: CHOPPY (ATR%%=%.2f < 0.8, RSI=%.1f in 35-65, BOS=%d <= 2)",
            atr_pct or 0, rsi or 50, len(recent_bos)
        )
        return "choppy"
    
    # ALSO CHOPPY: Moderate volatility but zero momentum
    if is_neutral_momentum and not recent_bos and not recent_choch:
        logger.debug(
            "Market regime: CHOPPY (no structure, neutral RSI=%.1f)",
            rsi or 50
        )
        return "choppy"

    # Check for clear trend via structural breaks
    if smc.structural_breaks:
        latest_break = max(smc.structural_breaks, key=lambda b: b.timestamp)

        if latest_break.break_type == "BOS" and latest_break.htf_aligned:
            return "trend"
        elif latest_break.break_type == "CHoCH":
            return "risk_off"  # Reversal suggests risk-off
        elif latest_break.break_type == "BOS":
            return "trend"  # BOS even without HTF alignment is trend-ish

    # Range: moderate volatility, no clear structure
    return "range"


# --- Rationale Generators ---


def _get_ob_rationale(order_blocks: List[OrderBlock], direction: str) -> str:
    """Generate rationale for order block factor."""
    aligned = [ob for ob in order_blocks if ob.direction == direction]
    if not aligned:
        return "No aligned order blocks"

    best = max(aligned, key=lambda ob: ob.freshness_score)
    grade = getattr(best, "grade", "B")
    return f"Fresh {direction} OB [Grade {grade}] with {best.displacement_strength:.1f}x ATR displacement, {best.mitigation_level*100:.0f}% mitigated"


def _get_fvg_rationale(fvgs: List[FVG], direction: str) -> str:
    """Generate rationale for FVG factor."""
    aligned = [fvg for fvg in fvgs if fvg.direction == direction]
    if not aligned:
        return "No aligned FVGs"

    unfilled = [fvg for fvg in aligned if fvg.overlap_with_price < _FVG_FILL_THRESHOLD]
    if unfilled:
        grades = [getattr(fvg, "grade", "B") for fvg in unfilled]
        grade_summary = (
            f"[Grades: {', '.join(grades)}]" if len(grades) <= 3 else f"[Best: {min(grades)}]"
        )
        return f"{len(unfilled)} unfilled {direction} FVG(s) {grade_summary}"
    else:
        return f"{len(aligned)} {direction} FVG(s), partially filled"


def _get_structure_rationale(breaks: List[StructuralBreak], direction: str) -> str:
    """Generate rationale for structure factor."""
    if not breaks:
        return "No structural breaks detected"

    latest = max(breaks, key=lambda b: b.timestamp)
    htf_status = "HTF aligned" if latest.htf_aligned else "LTF only"
    grade = getattr(latest, "grade", "B")
    return f"Recent {latest.break_type} [Grade {grade}] ({htf_status})"


def _get_sweep_rationale(sweeps: List[LiquiditySweep], direction: str) -> str:
    """Generate rationale for liquidity sweep factor."""
    target_type = "low" if direction == "bullish" else "high"
    aligned = [s for s in sweeps if s.sweep_type == target_type]

    if not aligned:
        return "No relevant liquidity sweeps"

    # Synchronized with _score_liquidity_sweeps: prioritize TF and confirmation over timestamp
    latest = max(
        aligned,
        key=lambda s: (
            _get_timeframe_weight(getattr(s, "timeframe", "1h")),
            getattr(s, "confirmation_level", 1 if s.confirmation else 0),
            s.timestamp,
        ),
    )
    conf_status = "volume confirmed" if latest.confirmation else "no volume confirmation"
    grade = getattr(latest, "grade", "B")
    return f"Recent {target_type} sweep [Grade {grade}] ({conf_status})"


def _get_momentum_rationale(indicators: IndicatorSnapshot, direction: str) -> str:
    """Generate rationale for momentum factor."""
    parts = []
    
    # Determine actual momentum state based on indicator values
    rsi_state = None
    stoch_state = None
    mfi_state = None

    if indicators.rsi is not None:
        parts.append(f"RSI {indicators.rsi:.1f}")
        if indicators.rsi < 30:
            rsi_state = "oversold"
        elif indicators.rsi > 70:
            rsi_state = "overbought"
        else:
            rsi_state = "neutral"

    if indicators.stoch_rsi is not None:
        parts.append(f"Stoch {indicators.stoch_rsi:.1f}")
        if indicators.stoch_rsi < 20:
            stoch_state = "oversold"
        elif indicators.stoch_rsi > 80:
            stoch_state = "overbought"
        else:
            stoch_state = "neutral"
            
    # Include K/D relationship if available
    k = getattr(indicators, "stoch_rsi_k", None)
    d = getattr(indicators, "stoch_rsi_d", None)
    if k is not None and d is not None:
        relation = "above" if k > d else "below" if k < d else "equal"
        parts.append(f"K {k:.1f} {relation} D {d:.1f}")
        sep = abs(k - d)
        if sep >= 2.0:
            if direction == "bullish" and k > d and k < 20:
                parts.append("bullish oversold K/D crossover")
            elif direction == "bearish" and k < d and k > 80:
                parts.append("bearish overbought K/D crossover")

    if indicators.mfi is not None:
        parts.append(f"MFI {indicators.mfi:.1f}")
        if indicators.mfi < 20:
            mfi_state = "oversold"
        elif indicators.mfi > 80:
            mfi_state = "overbought"
        else:
            mfi_state = "neutral"
            
    if (
        getattr(indicators, "macd_line", None) is not None
        and getattr(indicators, "macd_signal", None) is not None
    ):
        parts.append(f"MACD {indicators.macd_line:.3f} vs signal {indicators.macd_signal:.3f}")

    # Determine dominant state (prioritize RSI > Stoch > MFI)
    states = [s for s in [rsi_state, stoch_state, mfi_state] if s is not None]
    if not states:
        status_text = "Momentum indicators"
    else:
        # Count occurrences
        from collections import Counter
        state_counts = Counter(states)
        
        # Determine most common state
        if len(state_counts) == 1:
            # All agree
            dominant_state = states[0]
            status_text = f"Momentum indicators show {dominant_state}"
        else:
            # Mixed - report what's actually happening
            status_parts = []
            if state_counts.get("overbought", 0) > 0:
                status_parts.append(f"{state_counts['overbought']} overbought")
            if state_counts.get("oversold", 0) > 0:
                status_parts.append(f"{state_counts['oversold']} oversold")
            if state_counts.get("neutral", 0) > 0:
                status_parts.append(f"{state_counts['neutral']} neutral")
            status_text = f"Mixed momentum: {', '.join(status_parts)}"
    
    return f"{status_text}: {', '.join(parts)}"



def _get_volume_rationale(indicators: IndicatorSnapshot) -> str:
    """Generate rationale for volume factor."""
    if indicators.volume_spike:
        return "Elevated volume confirms price action"
    else:
        return "Normal volume levels"


def _get_volatility_rationale(indicators: IndicatorSnapshot) -> str:
    """Generate rationale for volatility factor."""
    atr_pct = getattr(indicators, "atr_percent", None)
    if atr_pct:
        val = atr_pct
        if val < 0.25:
            return f"Very low volatility ({val:.2f}%) - chop risk"
        if val < 0.75:
            return f"Healthy volatility expansion ({val:.2f}%)"
        if val < 1.5:
            return f"Moderate volatility ({val:.2f}%)"
        if val < 3.0:
            return f"High volatility ({val:.2f}%)"
        return f"Excessive volatility ({val:.2f}%) - unpredictable"
    return "Volatility data unavailable"


def _score_mtf_indicator_confluence(indicators: IndicatorSet, direction: str) -> Tuple[float, str]:
    """
    Check if indicators align across timeframes.

    Enhanced to check:
    - RSI/MACD alignment (original)
    - MACD slope consistency across TFs
    - Volume trend alignment
    - ADX strength consistency
    """
    norm_dir = _normalize_direction(direction)
    is_bullish = norm_dir == "bullish"

    # Track alignment across different indicator types
    rsi_aligned_count = 0
    macd_slope_aligned = 0
    volume_trend_aligned = 0
    adx_strong_count = 0

    opposed_count = 0
    total_tfs_checked = 0

    # Priority TFs for MTF alignment (focus on meaningful timeframes)
    priority_tfs = ["1d", "4h", "1h", "15m", "5m"]

    for tf in priority_tfs:
        # Try both lowercase and current case
        ind = indicators.by_timeframe.get(tf) or indicators.by_timeframe.get(tf.upper())
        if not ind:
            continue

        total_tfs_checked += 1

        # --- 1. RSI & MACD Crossover (Original Logic) ---
        rsi = getattr(ind, "rsi", None)
        if rsi is not None:
            # Handle None values for MACD (getattr returns None if attr exists but is None)
            macd_line = getattr(ind, "macd_line", 0) or 0
            macd_signal = getattr(ind, "macd_signal", 0) or 0
            
            if is_bullish:
                # Bullish alignment: RSI < 40 (strongly oversold) or MACD bullish crossover
                # Tightened from 45 to prevent neutral zones counting for both directions
                if rsi < 40 or (macd_line > macd_signal and rsi < 55):
                    rsi_aligned_count += 1
                elif rsi > 55:
                    # Neutral or bearish indication in bullish trade
                    opposed_count += 1
            else:  # Bearish
                # Bearish alignment: RSI > 60 (strongly overbought) or MACD bearish crossover
                if rsi > 60 or (macd_line < macd_signal and rsi > 45):
                    rsi_aligned_count += 1
                elif rsi < 45:
                    # Neutral or bullish indication in bearish trade
                    opposed_count += 1

        # --- 2. MACD Slope Alignment (NEW) ---
        # Check if MACD histogram is sloping in trade direction
        macd_hist = getattr(ind, "macd_histogram", None)
        if macd_hist is not None:
            # Need at least 2 values to determine slope
            # Assuming macd_histogram is a Series/array, get last 2 values
            try:
                if hasattr(macd_hist, "iloc"):
                    # It's a Series
                    if len(macd_hist) >= 2:
                        current_hist = float(macd_hist.iloc[-1])
                        prev_hist = float(macd_hist.iloc[-2])
                        slope_up = current_hist > prev_hist
                    else:
                        slope_up = None
                else:
                    # It's a scalar (current value only)
                    current_hist = float(macd_hist)
                    slope_up = current_hist > 0  # Positive histogram = bullish slope

                if slope_up is not None:
                    if (is_bullish and slope_up) or (not is_bullish and not slope_up):
                        macd_slope_aligned += 1
            except Exception:
                pass  # Skip if can't extract slope

        # --- 3. Volume Trend Alignment (NEW) ---
        # Check if volume is rising (indicates conviction)
        volume = getattr(ind, "volume_sma", None)  # or 'volume_ema' if available
        if volume is None:
            volume = getattr(ind, "volume", None)

        if volume is not None:
            try:
                if hasattr(volume, "iloc"):
                    # Series - compare last 5 bars for trend
                    if len(volume) >= 5:
                        recent_vol = float(volume.iloc[-1:].mean())
                        older_vol = float(volume.iloc[-5:-1].mean())
                        volume_rising = recent_vol > older_vol
                    else:
                        volume_rising = None
                else:
                    # Scalar - can't determine trend without history
                    volume_rising = None

                if volume_rising:
                    volume_trend_aligned += 1
            except Exception:
                pass

        # --- 4. ADX Strength Consistency (NEW) ---
        # Check if ADX > 25 (strong trend)
        adx = getattr(ind, "adx", None)
        if adx is not None:
            try:
                adx_val = float(adx.iloc[-1]) if hasattr(adx, "iloc") else float(adx)
                if adx_val > 25:
                    adx_strong_count += 1
            except Exception:
                pass

    if total_tfs_checked == 0:
        return 0.0, ""

    # --- Scoring Logic ---
    rationale_parts = []
    score = 0.0

    # RSI/MACD alignment (original)
    if rsi_aligned_count >= 3 and opposed_count == 0:
        score += 15.0
        rationale_parts.append(f"Strong MTF RSI/MACD alignment ({rsi_aligned_count} TFs)")
    elif opposed_count >= 2:
        score -= 10.0
        rationale_parts.append(f"MTF divergence warning ({opposed_count} opposed)")

    # MACD slope alignment bonus
    if macd_slope_aligned >= 3:
        score += 8.0
        rationale_parts.append(f"MACD slope aligned ({macd_slope_aligned} TFs)")
    elif macd_slope_aligned >= 2:
        score += 4.0
        rationale_parts.append(f"MACD slope partial ({macd_slope_aligned} TFs)")

    # Volume trend bonus
    if volume_trend_aligned >= 2:
        score += 5.0
        rationale_parts.append(f"Volume rising across TFs ({volume_trend_aligned})")

    # ADX strength bonus
    if adx_strong_count >= 3:
        score += 7.0
        rationale_parts.append(f"Strong trend (ADX>25 on {adx_strong_count} TFs)")
    elif adx_strong_count >= 2:
        score += 3.0
        rationale_parts.append(f"Moderate trend (ADX>25 on {adx_strong_count} TFs)")

    # Cap total MTF bonus to prevent inflation
    score = min(score, 25.0)  # Max 25 points from MTF alignment

    rationale = " | ".join(rationale_parts) if rationale_parts else ""
    return score, rationale


# ==============================================================================
# CLOSE-QUALITY CONFLUENCE HELPERS
# ==============================================================================


def _calculate_close_strength(close: float, level: float, atr: float) -> float:
    """
    Calculate ATR-normalized close distance from a level.
    
    Used to measure how far a candle closed beyond a structural level,
    normalized by ATR to make it comparable across different volatilities.
    
    Args:
        close: Candle close price
        level: Structural level (BOS level, sweep level, etc.)
        atr: Average True Range for normalization
        
    Returns:
        float: Close distance in ATR units (positive = bullish, negative = bearish)
    """
    if atr <= 0:
        return 0.0
    
    return (close - level) / atr


def _score_close_momentum(
    indicators: IndicatorSet,
    direction: str,
    primary_tf: str = "4h",
) -> tuple[float, str]:
    """
    Score candle close momentum based on position within candle range.
    
    Bullish setups reward closes near candle highs (top 15% of range).
    Bearish setups reward closes near candle lows (bottom 15% of range).
    
    Args:
        indicators: IndicatorSet with dataframe access
        direction: 'bullish' or 'bearish'
        primary_tf: Primary timeframe to check (default: '4h')
        
    Returns:
        tuple: (score 0-100, rationale string)
    """
    try:
        # Get dataframe for primary timeframe
        if not indicators.has_timeframe(primary_tf):
            return 0.0, ""
        
        ind = indicators.by_timeframe[primary_tf]
        if not hasattr(ind, 'dataframe') or ind.dataframe is None or len(ind.dataframe) == 0:
            return 0.0, ""
        
        df = ind.dataframe
        latest = df.iloc[-1]
        
        high = latest['high']
        low = latest['low']
        close = latest['close']
        
        candle_range = high - low
        if candle_range <= 0:
            return 0.0, ""
        
        # Calculate close position (0 = low, 1 = high)
        close_position = (close - low) / candle_range
        
        # Score based on direction
        if direction in ('bullish', 'long'):
            # Bullish: reward closes near highs  
            if close_position >= 0.85:  # Top 15%
                score = 100.0
                rationale = f"Bullish close near highs ({close_position*100:.0f}% of range)"
            elif close_position >= 0.70:  # Top 30%
                score = 70.0
                rationale = f"Strong bullish close ({close_position*100:.0f}% of range)"
            elif close_position >= 0.50:  # Above midpoint
                score = 40.0
                rationale = f"Moderate bullish close ({close_position*100:.0f}% of range)"
            else:
                return 0.0, ""  # Weak close, no bonus
                
        else:  # bearish/short
            # Bearish: reward closes near lows
            if close_position <= 0.15:  # Bottom 15%
                score = 100.0
                rationale = f"Bearish close near lows ({(1-close_position)*100:.0f}% from high)"
            elif close_position <= 0.30:  # Bottom 30%
                score = 70.0
                rationale = f"Strong bearish close ({(1-close_position)*100:.0f}% from high)"
            elif close_position <= 0.50:  # Below midpoint
                score = 40.0
                rationale = f"Moderate bearish close ({(1-close_position)*100:.0f}% from high)"
            else:
                return 0.0, ""  # Weak close, no bonus
        
        return score, rationale
        
    except Exception as e:
        logger.debug(f"Close momentum scoring failed: {e}")
        return 0.0, ""


def _score_multi_close_confirmation(
    indicators: IndicatorSet,
    smc_snapshot: SMCSnapshot,
    direction: str,
    current_price: float,
    primary_tf: str = "4h",
) -> tuple[float, str]:
    """
    Score multi-candle close confirmation beyond structural levels.
    
    Awards bonus when multiple consecutive closes stay beyond a key level,
    showing sustained commitment rather than a brief spike.
    
    Args:
        indicators: IndicatorSet with dataframe access
        smc_snapshot: SMCSnapshot with structural levels
        direction: 'bullish' or 'bearish'
        current_price: Current market price
        primary_tf: Primary timeframe to check (default: '4h')
        
    Returns:
        tuple: (score 0-100, rationale string)
    """
    try:
        # Get dataframe
        if not indicators.has_timeframe(primary_tf):
            return 0.0, ""
        
        ind = indicators.by_timeframe[primary_tf]
        if not hasattr(ind, 'dataframe') or ind.dataframe is None or len(ind.dataframe) < 3:
            return 0.0, ""
        
        df = ind.dataframe
        recent_closes = df['close'].tail(3).values  # Last 3 closes
        
        # Find nearest structural level in our direction
        nearest_level = None
        level_type = ""
        
        if direction in ('bullish', 'long'):
            # For longs, look for support levels we've closed above
            candidates = []
            
            # Check BOS/CHoCH levels (bullish breaks)
            for brk in smc_snapshot.structural_breaks:
                if getattr(brk, 'direction', '') == 'bullish' and brk.level < current_price:
                    candidates.append((brk.level, f"{brk.break_type} level"))
            
            # Check liquidity sweep lows
            for sweep in smc_snapshot.liquidity_sweeps:
                if sweep.sweep_type == 'low' and sweep.level < current_price:
                    candidates.append((sweep.level, "sweep low"))
            
            # Get nearest below current price
            if candidates:
                nearest_level, level_type = max(candidates, key=lambda x: x[0])
        
        else:  # bearish/short
            # For shorts, look for resistance levels we've closed below
            candidates = []
            
            # Check BOS/CHoCH levels (bearish breaks)
            for brk in smc_snapshot.structural_breaks:
                if getattr(brk, 'direction', '') == 'bearish' and brk.level > current_price:
                    candidates.append((brk.level, f"{brk.break_type} level"))
            
            # Check liquidity sweep highs
            for sweep in smc_snapshot.liquidity_sweeps:
                if sweep.sweep_type == 'high' and sweep.level > current_price:
                    candidates.append((sweep.level, "sweep high"))
            
            # Get nearest above current price
            if candidates:
                nearest_level, level_type = min(candidates, key=lambda x: x[0])
        
        if nearest_level is None:
            return 0.0, ""
        
        # Check how many consecutive closes are beyond the level
        closes_beyond = 0
        if direction in ('bullish', 'long'):
            # Count closes above level
            for close in recent_closes:
                if close > nearest_level:
                    closes_beyond += 1
                else:
                    break  # Stop at first close that's not beyond
        else:
            # Count closes below level
            for close in recent_closes:
                if close < nearest_level:
                    closes_beyond += 1
                else:
                    break
        
        # Score based on number of confirmed closes
        if closes_beyond >= 3:
            score = 100.0
            rationale = f"3 consecutive closes beyond {level_type} - strong confirmation"
        elif closes_beyond == 2:
            score = 70.0
            rationale = f"2 consecutive closes beyond {level_type} - good confirmation"
        elif closes_beyond == 1:
            # Only 1 close beyond - minimal confirmation
            return 0.0, ""
        else:
            return 0.0, ""
        
        return score, rationale
        
    except Exception as e:
        logger.debug(f"Multi-close confirmation scoring failed: {e}")
        return 0.0, ""
