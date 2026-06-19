"""
Regression for BUG #2 — P/D inverted in trends, fixed via regime-blind BOS arbitration.
(decisions/2026-06-18__bugfix-backlog-rescope.md, 2026-06-13__pd-factor-inverted-in-trends-finding.md)

The Premium/Discount factor applied fade-the-extreme (mean-reversion) UNCONDITIONALLY: a with-trend
entry in the "wrong" zone (downtrend SHORT at discount; uptrend LONG advancing into premium) got the
30 penalty. Fix: when an aligned BOS confirms the trade direction, NEUTRALIZE the penalty arm 30->50
(do not reward). Regime-blind (no suspect regime label). Symmetric.

Tests: (1) source-presence guards so the fix can't silently regress, (2) behavioral assertions on a
faithful reimplementation of the scorer branch, (3) bull/bear symmetry, (4) negatives (no BOS / reward
arm unchanged). Per CLAUDE.md §16 rubric 3 (mass/symmetry) + 4 (negative paired with positive) + 12.
"""
from pathlib import Path


_SCORER_SRC = (
    Path(__file__).resolve().parents[2] / "strategy" / "confluence" / "scorer.py"
).read_text(encoding="utf-8")


# ── (1) source-presence guards — the fix exists in the live branch ──────────────
def test_fix_present_in_source():
    assert "_aligned_bos" in _SCORER_SRC, "BOS arbitration removed?"
    assert "50.0 if _aligned_bos else 30.0" in _SCORER_SRC, "neutralize-30->50 arm changed?"
    # regime-blind: the arbitration must NOT consult the regime label (bug #6 is unverified)
    assert "_aligned_bos = any(" in _SCORER_SRC


def test_no_reward_inflation():
    # Conservative: continuation NEUTRALIZES (->50), it must never REWARD (->75/100) the penalty arm.
    assert "else _pen)" in _SCORER_SRC
    assert "_pen = 50.0" in _SCORER_SRC


# ── (2) faithful reimplementation of the scorer branch (scorer.py:2880-2899) ────
def _pd_score(is_long: bool, zone: str, zp: float, aligned_bos: bool) -> float:
    pen = 50.0 if aligned_bos else 30.0
    if is_long:
        return 100.0 if (zone == "discount" and zp < 30) else (75.0 if zone == "discount" else pen)
    return 100.0 if (zone == "premium" and zp > 70) else (75.0 if zone == "premium" else pen)


def test_continuation_neutralizes_penalty_long():
    # uptrend LONG advancing into premium, aligned bullish BOS -> 30 penalty neutralized to 50
    assert _pd_score(True, "premium", 80, aligned_bos=False) == 30.0   # pre-fix behavior
    assert _pd_score(True, "premium", 80, aligned_bos=True) == 50.0    # post-fix


def test_continuation_neutralizes_penalty_short():
    # downtrend SHORT sitting at discount, aligned bearish BOS -> 30 penalty neutralized to 50
    assert _pd_score(False, "discount", 20, aligned_bos=False) == 30.0
    assert _pd_score(False, "discount", 20, aligned_bos=True) == 50.0


# ── (3) bull/bear symmetry (standing fix) ───────────────────────────────────────
def test_bull_bear_symmetry():
    # The mirrored continuation case must score identically on both sides, BOS or not.
    for bos in (False, True):
        long_premium = _pd_score(True, "premium", 80, bos)
        short_discount = _pd_score(False, "discount", 20, bos)
        assert long_premium == short_discount, f"asymmetry at aligned_bos={bos}"


# ── (4) negatives: no BOS, and reward arm unchanged ─────────────────────────────
def test_no_bos_keeps_penalty():
    # No aligned BOS -> mean-reversion penalty preserved (ranges / unconfirmed trends unchanged).
    assert _pd_score(True, "premium", 80, aligned_bos=False) == 30.0
    assert _pd_score(False, "discount", 20, aligned_bos=False) == 30.0


# ── (5) HTF-gate secondary site — the -40 PremiumDiscount_VIOLATION suppression ──
def test_htf_gate_suppression_present_in_source():
    # The -40 violation must be guarded by `not _aligned_bos` (completes the factor fix).
    assert "structure_type\": \"PremiumDiscount_VIOLATION\"" in _SCORER_SRC \
        or 'structure_type": "PremiumDiscount_VIOLATION"' in _SCORER_SRC
    assert "min_aligned_distance > 1.0 and not _aligned_bos" in _SCORER_SRC, \
        "HTF-gate -40 violation no longer suppressed by an aligned BOS"


def _htf_violation_fires(in_optimal_zone: bool, min_aligned_dist: float, aligned_bos: bool) -> bool:
    # faithful reimplementation of scorer.py:1158-1169 elif guard
    return (not in_optimal_zone) and (min_aligned_dist > 1.0) and (not aligned_bos)


def test_htf_gate_bos_suppresses_violation():
    # with-trend continuation past equilibrium (not optimal) + aligned BOS -> NO -40 violation
    assert _htf_violation_fires(in_optimal_zone=False, min_aligned_dist=2.0, aligned_bos=False) is True
    assert _htf_violation_fires(in_optimal_zone=False, min_aligned_dist=2.0, aligned_bos=True) is False


def test_htf_gate_optimal_zone_never_violates():
    # in the optimal zone the violation never fires, BOS or not (non-regression)
    assert _htf_violation_fires(in_optimal_zone=True, min_aligned_dist=2.0, aligned_bos=False) is False
    assert _htf_violation_fires(in_optimal_zone=True, min_aligned_dist=2.0, aligned_bos=True) is False


def test_reward_arm_unchanged_by_fix():
    # The with-trend reward arms must be identical with or without BOS (fix only touches the penalty).
    assert _pd_score(True, "discount", 20, aligned_bos=True) == 100.0   # deep discount long
    assert _pd_score(True, "discount", 50, aligned_bos=True) == 75.0
    assert _pd_score(False, "premium", 80, aligned_bos=True) == 100.0   # deep premium short
    assert _pd_score(False, "premium", 50, aligned_bos=True) == 75.0
    # and the same without BOS
    assert _pd_score(True, "discount", 20, aligned_bos=False) == 100.0
    assert _pd_score(False, "premium", 80, aligned_bos=False) == 100.0
