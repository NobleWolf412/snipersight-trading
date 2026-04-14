from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple


class MacroState(Enum):
    RISK_ON = auto()
    RISK_OFF = auto()
    BTC_LED_EXPANSION = auto()
    ALT_SEASON = auto()
    BTC_ONLY_RALLY = auto()
    STABLE_SCARE = auto()
    CORRELATED_SELLOFF = auto()   # everything dumping (BTC ↓, ALTs ↓)
    CHOPPY = auto()               # mixed signals, high uncertainty
    NEUTRAL = auto()


def _pct_change(current: Optional[float], prev: Optional[float]) -> float:
    if current is None or prev is None or prev == 0:
        return 0.0
    return (current - prev) / prev * 100.0


def _dir_from_pct(p: float, eps: float = 0.1) -> str:
    if p > eps:
        return "up"
    if p < -eps:
        return "down"
    return "flat"


@dataclass
class MacroContext:
    btc_dom: float = 0.0
    alt_dom: float = 0.0
    stable_dom: float = 0.0

    btc_velocity_1h: float = 0.0
    alt_velocity_1h: float = 0.0
    stable_velocity_1h: float = 0.0
    velocity_spread_1h: float = 0.0  # btc_velocity - alt_velocity

    macro_state: MacroState = MacroState.NEUTRAL
    cluster_score: int = 0  # -3..+3

    percent_alts_up: float = 50.0

    btc_volatility_1h: float = 0.0  # ATR(1h)/price

    macro_score: int = 0
    notes: List[str] = field(default_factory=list)

    # Raw directions (derived, not serialized strictly necessary)
    btc_dir: str = "flat"
    alt_dir: str = "flat"
    stable_dir: str = "flat"


def compute_velocities_1h(
    btc_dom_series: List[Tuple[float, float]],
    alt_dom_series: List[Tuple[float, float]],
    stable_dom_series: List[Tuple[float, float]],
) -> Tuple[float, float, float]:
    """
    Each series is a list of (ts, value), ascending by time.
    Returns pct change over last ~1h for each dominance series.
    If insufficient data, returns 0.0.
    """

    def last_two_pct(series: List[Tuple[float, float]]) -> float:
        if not series or len(series) < 2:
            return 0.0
        return _pct_change(series[-1][1], series[-2][1])

    return (
        last_two_pct(btc_dom_series),
        last_two_pct(alt_dom_series),
        last_two_pct(stable_dom_series),
    )


def classify_macro_state(ctx: MacroContext) -> MacroState:
    # Convenience
    b, a, s = ctx.btc_dir, ctx.alt_dir, ctx.stable_dir

    # Strong stablecoin concern first (overrides)
    if ctx.stable_velocity_1h > 0.5:  # configurable threshold
        return MacroState.STABLE_SCARE

    # BTC-led expansion: BTC up, ALTs up, Stables down
    if b == "up" and a == "up" and s == "down":
        return MacroState.BTC_LED_EXPANSION

    # Risk-on: ALTs up, Stables down, BTC not necessarily up
    if a in ("up",) and s == "down" and b in ("down", "flat"):
        return MacroState.RISK_ON

    # Risk-off: BTC up (relative dominance), ALTs down, Stables up
    if b == "up" and a == "down" and s == "up":
        return MacroState.RISK_OFF

    # BTC-only rally: BTC up, ALTs not participating (flat/down), stables not rising
    if b == "up" and a in ("flat", "down") and s in ("flat", "down"):
        return MacroState.BTC_ONLY_RALLY

    # Alt-season: BTC down, ALTs up, stables flat/down
    if b == "down" and a == "up" and s in ("flat", "down"):
        return MacroState.ALT_SEASON

    # Correlated sell-off: BTC down, ALTs down — everything dumping together.
    # Distinct from RISK_OFF (where BTC holds up while alts bleed).
    # This is the "blood in the streets" scenario — dangerous for trend-following
    # longs, but can produce the best reversal setups (capitulation sweep).
    if b == "down" and a == "down":
        return MacroState.CORRELATED_SELLOFF

    # Choppy: at least one direction is "flat" while others disagree,
    # or stables rising while BTC is flat (quiet risk-off that doesn't match
    # the strict RISK_OFF criteria).  High uncertainty, reduce conviction.
    _flat_count = sum(1 for d in (b, a, s) if d == "flat")
    if _flat_count >= 2 or (s == "up" and b == "flat"):
        return MacroState.CHOPPY

    return MacroState.NEUTRAL


def compute_cluster_score(ctx: MacroContext) -> int:
    score = 0
    state = ctx.macro_state

    # Award/subtract based on consistency of directions with state
    if state == MacroState.BTC_LED_EXPANSION:
        score += 1 if ctx.btc_dir == "up" else -1
        score += 1 if ctx.alt_dir == "up" else -1
        score += 1 if ctx.stable_dir == "down" else -1
    elif state == MacroState.RISK_ON:
        score += 1 if ctx.alt_dir == "up" else -1
        score += 1 if ctx.stable_dir == "down" else -1
        score += 0 if ctx.btc_dir in ("down", "flat") else -1
    elif state == MacroState.RISK_OFF:
        score += 1 if ctx.btc_dir == "up" else -1
        score += 1 if ctx.alt_dir == "down" else -1
        score += 1 if ctx.stable_dir == "up" else -1
    elif state == MacroState.BTC_ONLY_RALLY:
        score += 1 if ctx.btc_dir == "up" else -1
        score += 0 if ctx.alt_dir in ("flat", "down") else -1
        score += 0 if ctx.stable_dir in ("flat", "down") else -1
    elif state == MacroState.ALT_SEASON:
        score += 1 if ctx.alt_dir == "up" else -1
        score += 0 if ctx.stable_dir in ("flat", "down") else -1
        score += 0 if ctx.btc_dir == "down" else -1
    elif state == MacroState.STABLE_SCARE:
        score += 1 if ctx.stable_dir == "up" else -1

    # Clamp -3..+3
    return max(-3, min(3, score))


def compute_macro_score(
    ctx: MacroContext,
    direction: str,  # "LONG" | "SHORT"
    is_btc: bool,
    is_alt: bool,
    trade_type: str = "swing",       # "scalp" | "intraday" | "swing"
    is_reversal: bool = False,       # True when counter-HTF / discount bounce
) -> int:
    """Return macro score adjustment for a given setup.

    Trade-type and reversal awareness:
      - Scalp reversals in RISK_OFF get a reduced penalty (-1 vs -3)
        because short-duration trades carry less directional exposure.
      - Intraday reversals get a moderate penalty (-2 vs -3).
      - Swing counter-trend longs keep the full -3 penalty.

    This prevents the macro overlay from killing valid liquidity-sweep
    bounces (e.g., BTC sweeps $65k discount zone and recovers) while
    still correctly penalising trend-following longs into a falling market.
    """
    score = 0
    notes = ctx.notes
    state = ctx.macro_state

    # Helper for cluster amplification
    def amplify(base: int) -> int:
        return int(round(base + (base * abs(ctx.cluster_score) * 0.15)))  # ~±15% per cluster point

    # Volatility dampening for alts on high BTC vol
    def damp_for_alt_on_high_btc_vol(x: int) -> int:
        if is_alt and ctx.btc_volatility_1h > 0.02:  # ~2% ATR/price threshold
            return int(round(x * 0.7))
        return x

    # ── Helper: reversal-aware penalty ────────────────────────────────────
    # Applies a reduced penalty when the setup is a confirmed reversal
    # (liquidity sweep / discount-premium bounce).  Scalps get the lightest
    # penalty because they exit quickly; swings keep most of the penalty
    # because they hold through extended exposure.
    def _reversal_penalty(full_base: int, label: str) -> int:
        if is_reversal and trade_type == "scalp":
            notes.append(f"{label}: soft penalty (scalp reversal)")
            return amplify(max(full_base, -1) if full_base < 0 else min(full_base, 1))
        if is_reversal and trade_type == "intraday":
            notes.append(f"{label}: reduced penalty (intraday reversal)")
            return amplify(max(full_base, -1) if full_base < 0 else min(full_base, 1))
        if is_reversal:
            notes.append(f"{label}: moderate penalty (swing reversal)")
            return amplify(max(full_base, -2) if full_base < 0 else min(full_base, 2))
        notes.append(f"{label}: penalize {'longs' if full_base < 0 else 'shorts'}")
        return amplify(full_base)

    # BTC-LED EXPANSION
    if state == MacroState.BTC_LED_EXPANSION:
        if direction == "SHORT":
            score += _reversal_penalty(-3, "BTC-led expansion")
        else:
            if is_btc:
                score += amplify(3)
                notes.append("BTC-led expansion: boost BTC longs")
            if is_alt:
                bonus = 2 if ctx.alt_velocity_1h > 0.3 else 1
                score += damp_for_alt_on_high_btc_vol(amplify(bonus))
                notes.append("BTC-led expansion: slight bonus for alt longs")

        # Caution flag: BTC fast up, ALTs slow/flat, stables flat
        if (
            ctx.btc_velocity_1h > 0.6
            and ctx.alt_velocity_1h < 0.15
            and -0.1 <= ctx.stable_velocity_1h <= 0.1
        ):
            if is_alt and direction == "LONG":
                score += -1
                notes.append("Caution: BTC spike with lagging ALTs; reduce alt-long by 1")

    elif state == MacroState.RISK_ON:
        if direction == "SHORT":
            score += _reversal_penalty(-2, "Risk-on")
        else:
            if is_alt:
                score += damp_for_alt_on_high_btc_vol(amplify(2))
                notes.append("Risk-on: favor alt longs")
            if is_btc:
                score += amplify(1)
                notes.append("Risk-on: slight boost for BTC longs")

    elif state in (MacroState.RISK_OFF, MacroState.STABLE_SCARE):
        if direction == "LONG":
            score += _reversal_penalty(-3, "Risk-off/Stable scare")
        else:
            score += amplify(2)
            if is_alt:
                score += 1  # stronger for alt shorts
            notes.append("Risk-off/Stable scare: favor shorts")

    elif state == MacroState.BTC_ONLY_RALLY:
        if direction == "LONG":
            if is_btc:
                score += amplify(2)
                notes.append("BTC-only rally: favor BTC longs")
            if is_alt:
                score += _reversal_penalty(-3, "BTC-only rally (alt long)")
        else:
            if is_alt:
                score += amplify(2)
                notes.append("BTC-only rally: slight favor alt shorts")

    elif state == MacroState.ALT_SEASON:
        if direction == "LONG":
            if is_alt:
                score += damp_for_alt_on_high_btc_vol(amplify(3))
                notes.append("Alt-season: boost alt longs")
            if is_btc:
                score += amplify(0)
        else:
            score += _reversal_penalty(-2, "Alt-season")

    elif state == MacroState.CORRELATED_SELLOFF:
        # Everything dumping — dangerous for longs, but capitulation sweeps
        # produce the best reversal entries.  Reversals get softened;
        # trend-following longs get full penalty.
        if direction == "LONG":
            score += _reversal_penalty(-3, "Correlated sell-off")
        else:
            # Shorts are naturally aligned — small boost
            score += amplify(1)
            notes.append("Correlated sell-off: slight favor for shorts")

    elif state == MacroState.CHOPPY:
        # Mixed signals, high uncertainty.  Reduce conviction on both sides
        # but don't outright penalise — the market can break either way.
        # Swing trades carry more risk in chop; scalps are fine.
        if trade_type == "swing":
            score += amplify(-1)
            notes.append("Choppy: reduce swing conviction")
        elif trade_type == "intraday":
            # Slight dampening — still tradeable but lower confidence
            score += 0
            notes.append("Choppy: intraday neutral")
        else:
            # Scalps thrive in chop — mean reversion territory
            score += amplify(1)
            notes.append("Choppy: scalp-friendly (mean reversion)")

    # Bound final macro score gently
    score = max(-4, min(4, score))
    ctx.macro_score = score
    return score


def build_macro_context(
    btc_dom: float,
    alt_dom: float,
    stable_dom: float,
    btc_dom_series: List[Tuple[float, float]],
    alt_dom_series: List[Tuple[float, float]],
    stable_dom_series: List[Tuple[float, float]],
    percent_alts_up: Optional[float] = None,
    btc_volatility_1h: Optional[float] = None,
) -> MacroContext:
    ctx = MacroContext(
        btc_dom=btc_dom or 0.0,
        alt_dom=alt_dom or 0.0,
        stable_dom=stable_dom or 0.0,
        percent_alts_up=percent_alts_up if percent_alts_up is not None else 50.0,
        btc_volatility_1h=btc_volatility_1h or 0.0,
    )

    b_v, a_v, s_v = compute_velocities_1h(btc_dom_series, alt_dom_series, stable_dom_series)
    ctx.btc_velocity_1h = b_v
    ctx.alt_velocity_1h = a_v
    ctx.stable_velocity_1h = s_v
    ctx.velocity_spread_1h = b_v - a_v

    ctx.btc_dir = _dir_from_pct(b_v)
    ctx.alt_dir = _dir_from_pct(a_v)
    ctx.stable_dir = _dir_from_pct(s_v)

    ctx.macro_state = classify_macro_state(ctx)
    ctx.cluster_score = compute_cluster_score(ctx)

    # Breadth notes
    if ctx.percent_alts_up > 70:
        ctx.notes.append("Breadth: broad alt strength")
    elif ctx.percent_alts_up < 30:
        ctx.notes.append("Breadth: broad alt weakness")

    return ctx
