"""
Tests for classify_conviction() — calibrated on the 2026-05-26
taken_trade_forensics finding that 67/67 closed trades had
conviction_class="B" (the dataclass default at planner.py:162) because
the classifier was an orphan from commit 8b9b081 (2025-11-28): defined
but never called from any production code path. The companion wire-up
in planner_service.py routes the classifier output into every
TradePlan as it's constructed.

These tests pin:
  1. classify_conviction's band logic (A/B/C across plan_types and inputs)
  2. The wire-up at planner_service.py — a static source-grep that fails
     if the call is ever removed (mirrors the regression pattern from
     test_stale_counter_main_process_accounting + test_breakdown_field_regression)

Per CLAUDE.md §11 (silent-bug surfacing: an unused classifier is the
classic loudfailure-vs-silent-failure trade-off — defining a function
without calling it is the silent path) + §14 (verification discipline:
prove the bug is gone with a test that catches its return).
"""

from __future__ import annotations

import pytest

from backend.shared.config.rr_matrix import classify_conviction


# ──────────────────────────────────────────────────────────────────────
# Class A — best-of-best (requires SMC structure + ideal R:R +
# high confluence + all critical TFs)
# ──────────────────────────────────────────────────────────────────────


def test_class_a_requires_smc_structure():
    """ATR_FALLBACK can NEVER reach A — even with perfect inputs."""
    result = classify_conviction(
        plan_type="ATR_FALLBACK",
        risk_reward=5.0,
        confluence_score=95.0,
        has_all_critical_tfs=True,
        mode_profile="stealth_balanced",
    )
    assert result == "B", (
        "ATR_FALLBACK with perfect inputs should cap at B, never A. "
        "Got: {!r}".format(result)
    )


def test_class_a_smc_ideal_rr_high_conf_full_tfs():
    """SMC + ideal R:R + confluence >= 80 + full TFs → A."""
    result = classify_conviction(
        plan_type="SMC",
        risk_reward=3.0,   # ideal_rr for SMC is typically 2.0-2.5
        confluence_score=85.0,
        has_all_critical_tfs=True,
        mode_profile="stealth_balanced",
    )
    assert result == "A"


def test_class_a_blocked_by_missing_critical_tfs():
    """Drop critical TFs → cannot be A even with everything else perfect."""
    result = classify_conviction(
        plan_type="SMC",
        risk_reward=3.0,
        confluence_score=85.0,
        has_all_critical_tfs=False,
        mode_profile="stealth_balanced",
    )
    assert result != "A"


def test_class_a_blocked_by_low_confluence():
    """Confluence < 80 → cannot be A."""
    result = classify_conviction(
        plan_type="SMC",
        risk_reward=3.0,
        confluence_score=70.0,
        has_all_critical_tfs=True,
        mode_profile="stealth_balanced",
    )
    assert result != "A"


# ──────────────────────────────────────────────────────────────────────
# Class B — close-to-ideal or decent confluence (the broad middle)
# ──────────────────────────────────────────────────────────────────────


def test_class_b_near_ideal_rr_decent_confluence():
    """R:R near ideal (>= 80% of ideal) + confluence >= 65 → B."""
    result = classify_conviction(
        plan_type="SMC",
        risk_reward=2.0,   # near ideal but not perfect
        confluence_score=70.0,
        has_all_critical_tfs=True,
        mode_profile="stealth_balanced",
    )
    assert result == "B"


def test_class_b_atr_fallback_decent():
    """ATR_FALLBACK with min_rr met + confluence >= 60 → B (capped)."""
    result = classify_conviction(
        plan_type="ATR_FALLBACK",
        risk_reward=1.5,
        confluence_score=65.0,
        has_all_critical_tfs=True,
        mode_profile="stealth_balanced",
    )
    assert result == "B"


def test_class_b_smc_decent_rr_only():
    """SMC/HYBRID with min_rr + decent confluence → B even without ideal R:R."""
    result = classify_conviction(
        plan_type="HYBRID",
        risk_reward=1.5,
        confluence_score=70.0,
        has_all_critical_tfs=True,
        mode_profile="stealth_balanced",
    )
    assert result == "B"


# ──────────────────────────────────────────────────────────────────────
# Class C — barely acceptable (residual)
# ──────────────────────────────────────────────────────────────────────


def test_class_c_below_decent_confluence():
    """Below 65 confluence + ATR_FALLBACK style → C."""
    result = classify_conviction(
        plan_type="SMC",
        risk_reward=1.2,
        confluence_score=55.0,
        has_all_critical_tfs=True,
        mode_profile="stealth_balanced",
    )
    assert result == "C"


def test_class_c_atr_fallback_marginal():
    """ATR_FALLBACK at the floor → C."""
    result = classify_conviction(
        plan_type="ATR_FALLBACK",
        risk_reward=1.1,
        confluence_score=55.0,
        has_all_critical_tfs=False,
        mode_profile="stealth_balanced",
    )
    assert result == "C"


# ──────────────────────────────────────────────────────────────────────
# Output sanity — only A / B / C
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "plan_type,rr,conf,full_tfs",
    [
        ("SMC", 5.0, 99.0, True),         # extreme
        ("ATR_FALLBACK", 0.0, 0.0, False),# floor
        ("HYBRID", 1.4, 64.0, True),      # boundary
        ("SMC", 0.5, 50.0, False),        # below everything
        ("HYBRID", 2.5, 85.0, True),      # high quality but hybrid
    ],
)
def test_output_is_always_one_of_abc(plan_type, rr, conf, full_tfs):
    """No edge case should ever return None / "" / "D" / anything else.
    The Literal["A", "B", "C"] is contractual."""
    result = classify_conviction(
        plan_type=plan_type,
        risk_reward=rr,
        confluence_score=conf,
        has_all_critical_tfs=full_tfs,
        mode_profile="stealth_balanced",
    )
    assert result in ("A", "B", "C"), f"unexpected output {result!r}"


# ──────────────────────────────────────────────────────────────────────
# Wire-up regression — planner_service.py MUST call classify_conviction
# ──────────────────────────────────────────────────────────────────────


def test_planner_service_calls_classify_conviction():
    """Static source-grep: planner_service.py must reference
    classify_conviction in the post-TradePlan-construction wire-up.
    Without this, every TradePlan gets the dataclass default 'B' and
    the field has no signal — which is the bug this fix exists to close.

    If a future refactor removes the call (well-intentioned but wrong),
    this test fails immediately."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "strategy"
        / "planner"
        / "planner_service.py"
    ).read_text(encoding="utf-8")

    assert "from backend.shared.config.rr_matrix import classify_conviction" in src, (
        "planner_service.py must import classify_conviction. If this fails, "
        "the import was removed and conviction_class will default to 'B'."
    )
    assert "plan.conviction_class = classify_conviction(" in src, (
        "planner_service.py must call classify_conviction and assign the "
        "result to plan.conviction_class. If this fails, the wire-up was "
        "removed (regression of the 2026-05-26 fix) and 100% of trades "
        "will revert to conviction_class='B'."
    )


def test_planner_service_wire_up_is_after_tradeplan_construction():
    """The classify_conviction call must come AFTER plan = TradePlan(...)
    construction, otherwise `plan.plan_type` / `plan.risk_reward_ratio` /
    `plan.confidence_score` won't be available yet."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "strategy"
        / "planner"
        / "planner_service.py"
    ).read_text(encoding="utf-8")

    plan_construct = src.find("plan = TradePlan(")
    classify_call = src.find("plan.conviction_class = classify_conviction(")
    assert plan_construct > 0, "TradePlan construction not found in planner_service.py"
    assert classify_call > 0, "classify_conviction wire-up not found in planner_service.py"
    assert classify_call > plan_construct, (
        f"classify_conviction call (offset {classify_call}) must come AFTER "
        f"TradePlan construction (offset {plan_construct}). The call needs "
        f"plan.plan_type / risk_reward_ratio / confidence_score to be set."
    )
