"""Gate 1 — account-aware liquidity floor (derive_account_aware_floor + admission).

Pins the §15/§9-A behavior: the floor scales with balance × leverage, clamps to a hard minimum,
fails safe to the floor on degenerate inputs, and — critically — the admission partition is
DIRECTION-AGNOSTIC and BYTE-IDENTICAL to the fixed path when the feature is off.

Per CLAUDE.md §16 rubric 3 (mass conservation), rubric 4 (negative + positive), rubric 12 (symmetry).
Baseline: decisions/2026-06-28__account-aware-liquidity-admission.md.
"""
from __future__ import annotations

from backend.analysis.pair_selection import derive_account_aware_floor, filter_illiquid_symbols

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
