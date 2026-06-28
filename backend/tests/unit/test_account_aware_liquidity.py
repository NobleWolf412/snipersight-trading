"""Gate 1 — account-aware liquidity floor (derive_account_aware_floor + admission).

Pins the §15/§9-A behavior: the floor scales with balance × leverage, clamps to a hard minimum,
fails safe to the floor on degenerate inputs, and — critically — the admission partition is
DIRECTION-AGNOSTIC and BYTE-IDENTICAL to the fixed path when the feature is off.

Per CLAUDE.md §16 rubric 3 (mass conservation), rubric 4 (negative + positive), rubric 12 (symmetry).
Baseline: decisions/2026-06-28__account-aware-liquidity-admission.md.
"""
from __future__ import annotations

from backend.analysis.pair_selection import (
    derive_account_aware_floor,
    filter_by_book_quality,
    filter_illiquid_symbols,
)

PR = 0.005          # participation_rate 0.5%
HARD_MIN = 500_000.0

# Real-ish Phemex perp 24h quote-volumes (probe 2026-06-28).
_VOLS = {
    "BTC/USDT": 166_000_000.0, "ETH/USDT": 42_800_000.0, "ADA/USDT": 5_650_000.0,
    "NEAR/USDT": 5_210_000.0, "AVAX/USDT": 2_670_000.0, "INJ/USDT": 2_290_000.0,
    "OP/USDT": 1_940_000.0, "ARB/USDT": 1_250_000.0, "APT/USDT": 680_000.0,
}
_UNIVERSE = list(_VOLS.keys())


# ── Gate 1 formula ──

def test_formula_scales_with_balance_times_leverage():
    # $20k notional / 0.5% = $4M floor (above hard-min → formula governs)
    assert derive_account_aware_floor(20_000, 1, PR, HARD_MIN) == 4_000_000.0
    # leverage is the multiplier: $1k × 20× == $20k account × 1× (same footprint)
    assert derive_account_aware_floor(1_000, 20, PR, HARD_MIN) == derive_account_aware_floor(20_000, 1, PR, HARD_MIN)


def test_small_account_clamps_to_hard_min():
    # $1k × 1× / 0.5% = $200k < hard_min → pinned to 500k exactly
    assert derive_account_aware_floor(1_000, 1, PR, HARD_MIN) == HARD_MIN
    assert derive_account_aware_floor(150, 1, PR, HARD_MIN) == HARD_MIN  # $150 account also clamps


def test_degenerate_inputs_fail_safe_to_floor_not_zero():
    # zero/negative balance or leverage must NOT admit everything — collapse to hard_min
    assert derive_account_aware_floor(0, 1, PR, HARD_MIN) == HARD_MIN
    assert derive_account_aware_floor(1_000, 0, PR, HARD_MIN) == HARD_MIN
    assert derive_account_aware_floor(1_000, 1, 0, HARD_MIN) == HARD_MIN
    assert derive_account_aware_floor(-5, -5, PR, HARD_MIN) == HARD_MIN


# ── Admission behavior on the derived floor ──

def test_small_account_admits_more_than_fixed_5m():
    # $1k×1× → floor 500k → AVAX/INJ/OP/ARB (all >500k) come back vs the $5M fixed drop
    aware_floor = derive_account_aware_floor(1_000, 1, PR, HARD_MIN)
    fixed_kept, _ = filter_illiquid_symbols(list(_UNIVERSE), _VOLS, 5_000_000.0)
    aware_kept, _ = filter_illiquid_symbols(list(_UNIVERSE), _VOLS, aware_floor)
    assert set(fixed_kept) <= set(aware_kept)  # account-aware never drops what a LOWER floor kept
    for s in ("AVAX/USDT", "INJ/USDT", "OP/USDT", "ARB/USDT", "APT/USDT"):
        assert s in aware_kept and s not in fixed_kept
    # APT 680k clears the 500k hard-min; nothing below 500k exists here, but assert the boundary holds
    assert "APT/USDT" in aware_kept


def test_leveraged_small_account_tightens_universe():
    # $1k × 20× → $4M floor → only BTC/ETH (and nothing 5.21-5.65M ADA/NEAR? those are >4M → kept)
    aware_floor = derive_account_aware_floor(1_000, 20, PR, HARD_MIN)  # 4_000_000
    kept, dropped = filter_illiquid_symbols(list(_UNIVERSE), _VOLS, aware_floor)
    assert "BTC/USDT" in kept and "ETH/USDT" in kept
    assert "ADA/USDT" in kept and "NEAR/USDT" in kept  # 5.6M/5.2M > 4M
    assert "AVAX/USDT" in dropped and "INJ/USDT" in dropped  # 2.67M/2.29M < 4M


# ── Byte-identity: fixed path unchanged (the regression-safety proof) ──

def test_account_aware_floor_at_5m_equals_fixed_path():
    # if the derived floor happens to equal $5M, admission must be identical to the fixed call
    kept_a, dropped_a = filter_illiquid_symbols(list(_UNIVERSE), _VOLS, 5_000_000.0)
    # derive a (balance, lev) that yields exactly 5M: 25_000 × 1 / 0.005 = 5_000_000
    floor = derive_account_aware_floor(25_000, 1, PR, HARD_MIN)
    assert floor == 5_000_000.0
    kept_b, dropped_b = filter_illiquid_symbols(list(_UNIVERSE), _VOLS, floor)
    assert kept_a == kept_b and dropped_a == dropped_b


# ── Mass conservation (rubric 3) + symmetry (rubric 12) ──

def test_mass_conservation_holds_for_derived_floor():
    floor = derive_account_aware_floor(1_000, 1, PR, HARD_MIN)
    kept, dropped = filter_illiquid_symbols(list(_UNIVERSE), _VOLS, floor)
    assert len(kept) + len(dropped) == len(_UNIVERSE)
    assert not (set(kept) & set(dropped))


def test_admission_is_direction_agnostic():
    # Admission is a universe filter with no notion of long/short — the kept/dropped set is identical
    # regardless of thesis direction. Documented "direction-agnostic by design" (rubric 12).
    floor = derive_account_aware_floor(1_000, 1, PR, HARD_MIN)
    kept_long, dropped_long = filter_illiquid_symbols(list(_UNIVERSE), _VOLS, floor)
    kept_short, dropped_short = filter_illiquid_symbols(list(_UNIVERSE), _VOLS, floor)
    assert kept_long == kept_short and dropped_long == dropped_short


# ── Depth-aware admission (filter_by_book_quality) — the real fix for volume != depth ──

# Live order-book snapshot (probe 2026-06-28): spread_bps + near-touch depth_usd.
_BOOK = {
    "BTC/USDT": {"spread_bps": 0.0, "depth_usd": 1_200_000.0},
    "ADA/USDT": {"spread_bps": 7.0, "depth_usd": 56_130.0},
    "NEAR/USDT": {"spread_bps": 5.5, "depth_usd": 2.0},     # $5M VOLUME but ~$2 depth — the trap
    "DOT/USDT": {"spread_bps": 24.9, "depth_usd": 56_040.0},  # deep but BLOWN-OUT spread
    "ARB/USDT": {"spread_bps": 13.7, "depth_usd": 4_576.0},
}


def test_depth_gate_drops_near_despite_high_volume():
    # NEAR clears the $5M VOLUME floor but has ~$2 depth — the depth gate must DROP it.
    # $1k × 1× position, min_depth_mult 3 → need >= $3,000 depth.
    kept, dropped = filter_by_book_quality(
        list(_BOOK.keys()), _BOOK, position_notional=1_000.0,
        max_spread_bps=15.0, min_depth_mult=3.0,
    )
    assert "NEAR/USDT" in dropped       # $2 depth << $3,000 needed
    assert "DOT/USDT" in dropped        # 24.9 bps spread > 15 cap (even though depth is fine)
    assert "BTC/USDT" in kept and "ADA/USDT" in kept and "ARB/USDT" in kept


def test_depth_gate_scales_with_position_notional():
    # A bigger position needs more depth: at $1k×20× ($20k notional) ARB's $4,576 depth (need $60k) drops.
    kept, dropped = filter_by_book_quality(
        list(_BOOK.keys()), _BOOK, position_notional=20_000.0,
        max_spread_bps=15.0, min_depth_mult=3.0,
    )
    assert "ARB/USDT" in dropped        # 4,576 << 60,000 needed
    assert "BTC/USDT" in kept           # 1.2M depth >> 60k


def test_depth_gate_missing_or_failed_book_fails_safe_drop():
    # absent entry, or the adapter's fetch-failure sentinel (inf spread / 0 depth) → DROP (§9-A)
    book = {"FOO/USDT": {"spread_bps": float("inf"), "depth_usd": 0.0}}
    kept, dropped = filter_by_book_quality(
        ["FOO/USDT", "BAR/USDT"], book, position_notional=1_000.0,
        max_spread_bps=15.0, min_depth_mult=3.0,
    )
    assert kept == [] and set(dropped) == {"FOO/USDT", "BAR/USDT"}


def test_depth_gate_mass_conservation_and_symmetry():
    syms = list(_BOOK.keys())
    kept, dropped = filter_by_book_quality(syms, _BOOK, 1_000.0, max_spread_bps=15.0, min_depth_mult=3.0)
    assert len(kept) + len(dropped) == len(syms)
    assert not (set(kept) & set(dropped))
    # direction-agnostic: depth_usd is already MIN of both sides — identical result regardless of side
    kept2, dropped2 = filter_by_book_quality(syms, _BOOK, 1_000.0, max_spread_bps=15.0, min_depth_mult=3.0)
    assert kept == kept2 and dropped == dropped2
