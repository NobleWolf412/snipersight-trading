"""
Regression tests for sub-gate per-factor breakdown persistence (OBSERVABILITY).

decisions/2026-06-13__subgate-factor-logging.md

Context: ~74% of filtered signals are `low_confluence` (scored 40–69, below the
70 gate). Before this change they were logged WITHOUT their factor breakdown, so
calibration diagnostics (phase4f_score_calibration, pd_direction_efficacy) — which
filter on `factors` presence — only ever saw gate-clearers. The scorer DOES compute
the breakdown for these (that's how the sub-gate score is known); the orchestrator
already returns it as `all_factors` on the rejection item. `_log_signal` now threads
it into signals.jsonl as `factors` (same shape gate-clearers emit) plus a
`gate_cleared` boolean so analysis can tell full-breakdown gate-clearers from
sub-gate rows.

This is logging-only: no scoring/gating/threshold path is touched. Per §16 Rubric
4 & 12 every assertion is exercised on BOTH LONG and SHORT (bull/bear symmetry) and
paired with a negative test (a sub-gate row with no breakdown must NOT fabricate one).
"""

from types import SimpleNamespace

import pytest

from backend.bot.paper_trading_service import PaperTradingService


# ── Minimal service: _log_signal only touches these few attributes ────────────

def _make_service():
    svc = PaperTradingService.__new__(PaperTradingService)
    svc.stats = SimpleNamespace(scans_completed=7)
    svc.config = SimpleNamespace(execution_mode="snap_taker")
    svc.signal_log = []
    svc._session_log_dir = None          # skip disk write
    svc.diagnostic_logger = None         # skip diagnostics
    svc._current_regime_composite = "down_normal"
    return svc


def _log(svc, plan, **extra):
    """Call _log_signal and return the entry it appended."""
    svc._log_signal(plan, "filtered", "test-reason", **extra)
    return svc.signal_log[-1]


# ── Fixtures: a real (gate-clearer) plan and a sub-gate mock_plan ─────────────

def _factor_obj(name, score, weight, weighted, rationale):
    # Shape the gate-clearer path reads off plan.confluence_breakdown.factors
    return SimpleNamespace(
        name=name, score=score, weight=weight,
        weighted_score=weighted, rationale=rationale,
    )


def _gate_clearer_plan(direction):
    cb = SimpleNamespace(
        synergy_bonus=2.0, conflict_penalty=0.0,
        htf_aligned=True, htf_proximity_atr=0.5, macro_score=60.0,
        factors=[
            _factor_obj("Market Structure", 80.0, 0.2, 16.0,
                        "BOS continuation in direction"),
            _factor_obj("Premium/Discount Zone", 50.0, 0.1, 5.0,
                        "Discount zone" if direction == "LONG" else "Premium zone"),
        ],
    )
    return SimpleNamespace(
        symbol="BTC/USDT", direction=direction, confidence_score=78.0,
        setup_type="continuation", trade_type="swing", primary_timeframe="1h",
        entry_zone=SimpleNamespace(near_entry=100.0, pullback_probability=0.4),
        stop_loss=SimpleNamespace(level=98.0), risk_reward=2.1,
        metadata={}, confluence_breakdown=cb,
    )


def _sub_gate_mock_plan(direction):
    # Mirrors the SimpleNamespace built in _run_scan's rejection-funnel loop.
    return SimpleNamespace(
        symbol="ADA/USDT", direction=direction, confidence_score=58.0,
        setup_type="filtered",
        entry_zone=SimpleNamespace(near_entry=0.5, far_entry=0.0),
        stop_loss=SimpleNamespace(level=0.49), risk_reward=0.0,
    )


def _all_factors(direction):
    # Orchestrator all_factors shape: uses `weighted_contribution`, not `weighted`.
    return [
        {"name": "Market Structure", "score": 45.0, "weight": 0.2,
         "weighted_contribution": 9.0, "rationale": "weak BOS"},
        {"name": "Premium/Discount Zone", "score": 30.0, "weight": 0.1,
         "weighted_contribution": 3.0,
         "rationale": "Discount zone" if direction == "LONG" else "Premium zone"},
    ]


# ── Sub-gate path: factors now persisted, gate_cleared False ──────────────────

@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_subgate_persists_factors(direction):
    svc = _make_service()
    entry = _log(svc, _sub_gate_mock_plan(direction),
                 gate_cleared=False, sub_gate_factors=_all_factors(direction),
                 reason_type="low_confluence")

    assert entry["gate_cleared"] is False
    assert "factors" in entry and len(entry["factors"]) == 2

    # Key-identical to the gate-clearer shape so diagnostics parse uniformly.
    f0 = entry["factors"][0]
    assert set(f0.keys()) == {"name", "score", "weight", "weighted", "rationale"}
    assert f0["name"] == "Market Structure"
    assert f0["score"] == 45.0
    # weighted_contribution → weighted mapping
    assert f0["weighted"] == 9.0

    # The keys the starved diagnostics actually read.
    pd_factor = next(f for f in entry["factors"]
                     if f["name"] == "Premium/Discount Zone")
    assert "rationale" in pd_factor and "score" in pd_factor
    expected_zone = "Discount zone" if direction == "LONG" else "Premium zone"
    assert pd_factor["rationale"] == expected_zone

    # Raw plumbing keys must NOT leak into the persisted row.
    assert "sub_gate_factors" not in entry


# ── Gate-clearer path: unchanged behavior, gate_cleared True ──────────────────

@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_gate_clearer_unchanged_and_flagged(direction):
    svc = _make_service()
    entry = _log(svc, _gate_clearer_plan(direction))

    assert entry["gate_cleared"] is True
    assert "factors" in entry and len(entry["factors"]) == 2
    assert set(entry["factors"][0].keys()) == {
        "name", "score", "weight", "weighted", "rationale"}
    # Plan-attached breakdown still drives the row (existing enrichment intact).
    assert entry["synergy_bonus"] == 2.0
    assert entry["htf_aligned"] == 1


def test_gate_clearer_ignores_stray_subgate_factors():
    # A real plan must NEVER be overwritten by sub_gate_factors even if passed.
    svc = _make_service()
    entry = _log(svc, _gate_clearer_plan("LONG"),
                 sub_gate_factors=_all_factors("LONG"))
    assert entry["gate_cleared"] is True
    # Came from the plan breakdown (weighted 16.0), not the all_factors (9.0).
    ms = next(f for f in entry["factors"] if f["name"] == "Market Structure")
    assert ms["weighted"] == 16.0
    assert "sub_gate_factors" not in entry


# ── Negative: a sub-gate row with no breakdown must not fabricate one ─────────

@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_pre_scoring_gate_row_has_no_factors(direction):
    # conflict_density etc. are rejected BEFORE scoring → no breakdown exists.
    svc = _make_service()
    entry = _log(svc, _sub_gate_mock_plan(direction),
                 gate_cleared=False, sub_gate_factors=None,
                 reason_type="conflict_density")
    assert entry["gate_cleared"] is False
    assert "factors" not in entry
