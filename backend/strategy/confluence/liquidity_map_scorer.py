"""
Liquidity Map Scorer

Scores a trade based on its alignment with the liquidity draw —
the path from recently swept liquidity (origin) to the nearest
unswept pool (target/magnet).

Markets move from liquidity to liquidity. A trade long toward an
unswept equal-highs cluster is inherently higher probability than
one with no visible target.

Data sources (all already detected):
  - SMCSnapshot.liquidity_pools  — equal highs/lows (LiquidityPool objects)
  - SMCSnapshot.liquidity_sweeps — recent sweeps (origin confirmation)
  - SMCSnapshot.key_levels       — dict with pwh/pwl/pdh/pdl
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.shared.models.smc import LiquidityPool, SMCSnapshot

logger = logging.getLogger(__name__)


def score_liquidity_draw(
    direction: str,
    current_price: float,
    smc: SMCSnapshot,
    atr: float,
    max_target_atr: float = 15.0,
) -> Dict[str, Any]:
    """
    Score a trade based on the liquidity draw in the trade direction.

    Args:
        direction:       "bullish" or "bearish"
        current_price:   Current market price
        smc:             SMC snapshot containing pools, sweeps, key_levels
        atr:             ATR value for distance normalization
        max_target_atr:  Maximum ATR distance to consider a pool as a relevant target

    Returns dict with:
        score:                 float [0–100], weighted confluence contribution
        factors:               list of (name, score, detail) tuples
        nearest_target:        LiquidityPool or None
        target_distance_atr:   float or None
    """
    is_long = direction == "bullish"
    raw_score = 0.0
    factors: List[Tuple[str, float, str]] = []

    # ── 1. Nearest unswept pool in trade direction ────────────────────────
    target_pool = _find_nearest_target(is_long, current_price, smc, atr, max_target_atr)

    if target_pool:
        distance_atr = abs(target_pool.level - current_price) / atr if atr > 0 else 999.0
        grade_score = {"A": 30.0, "B": 20.0, "C": 12.0}.get(str(target_pool.grade), 10.0)

        # Distance multiplier — ideal range is 2–5 ATR from entry
        if distance_atr < 2.0:
            dist_mult = 0.7   # Already at the target, not ideal for entry
        elif distance_atr <= 5.0:
            dist_mult = 1.0   # Sweet spot
        elif distance_atr <= 10.0:
            dist_mult = 0.8
        else:
            dist_mult = 0.5

        pool_score = grade_score * dist_mult
        raw_score += pool_score
        factors.append((
            "Liquidity Target",
            pool_score,
            f"Grade {target_pool.grade} {target_pool.pool_type.replace('_', ' ')} "
            f"at {target_pool.level:.2f} ({distance_atr:.1f} ATR ahead)",
        ))

    # ── 2. Recent sweep behind price (origin confirmation) ───────────────
    # A confirmed sweep of lows (for longs) or highs (for shorts) means price
    # has grabbed liquidity and is now likely drawing toward the opposite side.
    origin_sweep_type = "low" if is_long else "high"
    origin_sweeps = [
        s for s in (smc.liquidity_sweeps or [])
        if getattr(s, "sweep_type", "") == origin_sweep_type
        and getattr(s, "confirmation_level", 1 if getattr(s, "confirmation", False) else 0) >= 1
    ]
    if origin_sweeps:
        sweep_bonus = 15.0
        raw_score += sweep_bonus
        factors.append((
            "Liquidity Origin Sweep",
            sweep_bonus,
            f"Confirmed {origin_sweep_type} sweep — price drawing opposite",
        ))

    # ── 3. Key level proximity (session/weekly as reference) ─────────────
    key_levels: Optional[Dict[str, Any]] = smc.key_levels  # Stored as dict via to_dict()
    if key_levels and atr > 0:
        kl_score = _score_key_level_proximity(is_long, current_price, key_levels, atr)
        if kl_score > 0:
            raw_score += kl_score
            factors.append((
                "Session/Weekly Level",
                kl_score,
                "Entry near key liquidity reference level (PDH/PDL/PWH/PWL)",
            ))

    normalized = min(100.0, raw_score)
    target_dist = (
        abs(target_pool.level - current_price) / atr
        if target_pool and atr > 0
        else None
    )

    return {
        "score": normalized,
        "factors": factors,
        "nearest_target": target_pool,
        "target_distance_atr": target_dist,
    }


# ─── helpers ─────────────────────────────────────────────────────────────────


def _find_nearest_target(
    is_long: bool,
    current_price: float,
    smc: SMCSnapshot,
    atr: float,
    max_target_atr: float,
) -> Optional[LiquidityPool]:
    """Find the nearest unswept liquidity pool in the trade direction."""
    candidates: List[LiquidityPool] = []

    # Equal highs / lows from SMC detection
    for pool in (smc.liquidity_pools or []):
        if pool.swept:
            continue
        if is_long and pool.pool_type == "equal_highs" and pool.level > current_price:
            candidates.append(pool)
        elif not is_long and pool.pool_type == "equal_lows" and pool.level < current_price:
            candidates.append(pool)

    # Add key levels (PWH, PDH for longs; PWL, PDL for shorts) as synthetic pools
    key_levels: Optional[Dict[str, Any]] = smc.key_levels
    if key_levels:
        if is_long:
            for key in ("pwh", "pdh"):
                lvl = key_levels.get(key)
                if lvl and not lvl.get("swept") and lvl.get("price", 0) > current_price:
                    candidates.append(LiquidityPool(
                        level=lvl["price"],
                        pool_type="equal_highs",
                        touches=2,
                        timeframe="1d",
                        grade="B",
                    ))
        else:
            for key in ("pwl", "pdl"):
                lvl = key_levels.get(key)
                if lvl and not lvl.get("swept") and 0 < lvl.get("price", 0) < current_price:
                    candidates.append(LiquidityPool(
                        level=lvl["price"],
                        pool_type="equal_lows",
                        touches=2,
                        timeframe="1d",
                        grade="B",
                    ))

    if not candidates:
        return None

    # Filter by max distance
    if atr > 0:
        candidates = [
            p for p in candidates
            if abs(p.level - current_price) / atr <= max_target_atr
        ]

    if not candidates:
        return None

    return min(candidates, key=lambda p: abs(p.level - current_price))


def _score_key_level_proximity(
    is_long: bool,
    current_price: float,
    key_levels: Dict[str, Any],
    atr: float,
    proximity_atr: float = 1.5,
) -> float:
    """Bonus when entry is near a session/weekly reference level acting as support/resistance."""
    # For longs: entering near PDL or PWL (support)
    # For shorts: entering near PDH or PWH (resistance)
    check_keys = ("pdl", "pwl") if is_long else ("pdh", "pwh")
    for key in check_keys:
        lvl = key_levels.get(key)
        if lvl and lvl.get("price"):
            if abs(current_price - lvl["price"]) / atr <= proximity_atr:
                return 10.0
    return 0.0
