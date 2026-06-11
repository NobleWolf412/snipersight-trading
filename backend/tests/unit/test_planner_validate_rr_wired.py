"""
Regression test for Fix 6: validate_rr() wired into planner min_RR check.

Verifies:
- validate_rr is imported in planner_service.py (not re-implemented inline)
- The old inline RR_EPSILON/min_rr logic is NOT present (replaced by validate_rr call)
- validate_rr is callable with the correct signature expected by the planner
"""

from __future__ import annotations

import pathlib
import inspect

import pytest


PLANNER_SRC = pathlib.Path("backend/strategy/planner/planner_service.py").read_text(
    encoding="utf-8"
)


class TestValidateRrWired:
    def test_validate_rr_imported_in_planner(self):
        """planner_service.py must import validate_rr from rr_matrix."""
        assert "from backend.shared.config.rr_matrix import" in PLANNER_SRC
        # The import line contains both classify_conviction and validate_rr
        import_lines = [
            l for l in PLANNER_SRC.splitlines()
            if "from backend.shared.config.rr_matrix import" in l
        ]
        assert import_lines, "rr_matrix import line not found"
        assert any("validate_rr" in l for l in import_lines), (
            f"validate_rr not in rr_matrix import: {import_lines}"
        )

    def test_old_inline_rr_epsilon_removed(self):
        """Old inline RR_EPSILON = 0.001 check must not exist in the planner."""
        assert "RR_EPSILON" not in PLANNER_SRC, (
            "Old inline RR_EPSILON logic still present in planner_service.py — "
            "the planner must delegate to validate_rr() instead"
        )

    def test_validate_rr_called_in_planner(self):
        """planner_service.py must call validate_rr(...)."""
        assert "validate_rr(" in PLANNER_SRC, (
            "validate_rr() not called in planner_service.py — wiring is missing"
        )

    def test_validate_rr_signature_compatible(self):
        """validate_rr() must accept the keyword args the planner passes."""
        from backend.shared.config.rr_matrix import validate_rr
        sig = inspect.signature(validate_rr)
        required_params = {"plan_type", "risk_reward", "mode_profile",
                           "confluence_score", "trade_type", "min_rr_override"}
        actual_params = set(sig.parameters.keys())
        missing = required_params - actual_params
        assert not missing, (
            f"validate_rr() missing expected params: {missing} — "
            "planner call would fail at runtime"
        )

    def test_tp1_clamped_override_path_present(self):
        """The _tp1_clamped / _min_rr_override block must be present in planner."""
        assert "_tp1_clamped" in PLANNER_SRC, (
            "_tp1_clamped not found — reachability-clamp logic may have been dropped"
        )
        assert "_min_rr_override" in PLANNER_SRC, (
            "_min_rr_override not found — TP1 clamp → validate_rr bridge is missing"
        )
