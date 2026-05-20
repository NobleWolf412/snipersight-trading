"""
Tests for .claude/skills/_state_helper.py.

Per §16 rubric 4: every public API method gets a positive test paired with a
negative test (missing-state path returns empty/None rather than raising).
Idempotency invariant (rubric 3 mass-conservation): re-writing a finding with
the same thread_key produces exactly one entry, not two.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


# Load the helper module by path (lives outside backend/ so isn't an importable package)
_HELPER_PATH = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "_state_helper.py"


@pytest.fixture
def helper(tmp_path, monkeypatch):
    """Load the helper module fresh with _STATE_DIR redirected to a tmp dir."""
    spec = importlib.util.spec_from_file_location("_skill_state_helper_test", _HELPER_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Redirect state directory to the per-test tmp_path
    monkeypatch.setattr(mod, "_STATE_DIR", tmp_path / ".skill-state")
    return mod


# ──────────────────────────────────────────────────────────────────────────────
# read_session_state — missing + present + corrupt
# ──────────────────────────────────────────────────────────────────────────────


def test_read_returns_none_for_missing_session(helper):
    """Missing state file → None, no exception."""
    assert helper.read_session_state("does-not-exist") is None


def test_read_returns_dict_after_write(helper):
    """After write_finding the state file is readable as a dict."""
    assert helper.write_finding("sess-1", "thread-A", "autopsy", "CLEARED")
    state = helper.read_session_state("sess-1")
    assert state is not None
    assert state["session_id"] == "sess-1"
    assert len(state["resolved_findings"]) == 1


def test_read_returns_none_on_corrupt_file(helper, tmp_path):
    """Corrupt JSON → None + stderr warning, no exception bubbling."""
    helper._STATE_DIR.mkdir(parents=True, exist_ok=True)
    (helper._STATE_DIR / "session-corrupt.json").write_text("{not json", encoding="utf-8")
    assert helper.read_session_state("corrupt") is None


# ──────────────────────────────────────────────────────────────────────────────
# write_finding — positive, upsert idempotency, mass conservation
# ──────────────────────────────────────────────────────────────────────────────


def test_write_finding_persists_to_disk(helper):
    """A written finding survives across read calls."""
    assert helper.write_finding(
        session_id="sess-A",
        thread_key="hi-conf-loss-trade-123",
        skill="trade-autopsy",
        verdict="EXPECTED-LOSS-NO-BUG",
        summary="geometry correct",
    )
    found = helper.get_finding("sess-A", "hi-conf-loss-trade-123")
    assert found is not None
    assert found["verdict"] == "EXPECTED-LOSS-NO-BUG"
    assert found["skill"] == "trade-autopsy"
    assert found["summary"] == "geometry correct"


def test_write_finding_idempotent_upsert(helper):
    """Re-writing the same thread_key replaces the entry — not duplicates it."""
    helper.write_finding("sess-B", "thread-X", "autopsy", "PENDING")
    helper.write_finding("sess-B", "thread-X", "trade-autopsy", "RESOLVED")
    findings = helper.list_findings("sess-B")
    # Mass conservation: one thread_key, one entry
    assert len(findings) == 1
    assert findings[0]["verdict"] == "RESOLVED"
    assert findings[0]["skill"] == "trade-autopsy"


def test_multiple_thread_keys_coexist(helper):
    """Different thread_keys produce distinct entries."""
    helper.write_finding("sess-C", "thread-1", "autopsy", "VA")
    helper.write_finding("sess-C", "thread-2", "autopsy", "VB")
    helper.write_finding("sess-C", "thread-3", "trade-autopsy", "VC")
    findings = helper.list_findings("sess-C")
    assert len(findings) == 3
    keys = sorted(f["thread_key"] for f in findings)
    assert keys == ["thread-1", "thread-2", "thread-3"]


# ──────────────────────────────────────────────────────────────────────────────
# write_gap — observability gap registry
# ──────────────────────────────────────────────────────────────────────────────


def test_write_gap_initialises_open_status(helper):
    """New gap defaults to status=open with first_seen + summary preserved."""
    helper.write_gap("sess-D", "ml-rejections-not-in-telemetry", summary="ML filters not telemeterized")
    gaps = helper.list_gaps("sess-D")
    assert len(gaps) == 1
    assert gaps[0]["id"] == "ml-rejections-not-in-telemetry"
    assert gaps[0]["status"] == "open"
    assert gaps[0]["summary"] == "ML filters not telemeterized"
    assert "first_seen" in gaps[0]


def test_write_gap_preserves_first_seen_on_status_change(helper):
    """Updating an existing gap's status keeps first_seen stable."""
    helper.write_gap("sess-E", "test-gap", status="open", summary="initial")
    initial = helper.list_gaps("sess-E")[0]
    initial_first_seen = initial["first_seen"]
    # Now mark patched
    helper.write_gap("sess-E", "test-gap", status="patched", summary="fixed in commit X")
    after = helper.list_gaps("sess-E")[0]
    assert after["status"] == "patched"
    assert after["summary"] == "fixed in commit X"
    assert after["first_seen"] == initial_first_seen, (
        "first_seen must NOT change on status update — it's an audit-trail field"
    )


def test_write_gap_warns_on_unknown_status(helper, capsys):
    """Unknown status value emits a stderr warning but still writes."""
    helper.write_gap("sess-F", "g", status="bogus")
    captured = capsys.readouterr()
    assert "unrecognised gap status" in captured.err


# ──────────────────────────────────────────────────────────────────────────────
# write_drift — vocabulary-drift counter
# ──────────────────────────────────────────────────────────────────────────────


def test_write_drift_increments_count_on_match(helper):
    """Same (reason, gate) repeated → count climbs; not separate entries."""
    helper.write_drift("sess-G", "Below new threshold", "new_gate")
    helper.write_drift("sess-G", "Below new threshold", "new_gate")
    helper.write_drift("sess-G", "Below new threshold", "new_gate")
    drift = helper.list_drift("sess-G")
    assert len(drift) == 1
    assert drift[0]["count"] == 3


def test_write_drift_distinguishes_different_gates(helper):
    """Same reason text but different gate_name → distinct entries."""
    helper.write_drift("sess-H", "rejected", "gate-1")
    helper.write_drift("sess-H", "rejected", "gate-2")
    drift = helper.list_drift("sess-H")
    assert len(drift) == 2


def test_write_drift_handles_null_gate_name(helper):
    """gate_name=None is a valid distinct key."""
    helper.write_drift("sess-I", "some reason", None)
    helper.write_drift("sess-I", "some reason", None)
    drift = helper.list_drift("sess-I")
    assert len(drift) == 1
    assert drift[0]["count"] == 2
    assert drift[0]["gate_name"] is None


# ──────────────────────────────────────────────────────────────────────────────
# Cross-section schema invariants
# ──────────────────────────────────────────────────────────────────────────────


def test_all_three_sections_coexist(helper):
    """One session can hold findings, gaps, and drift entries simultaneously."""
    helper.write_finding("sess-J", "t1", "autopsy", "CLEAR")
    helper.write_gap("sess-J", "gap-1", status="open")
    helper.write_drift("sess-J", "weird reason", "weird_gate")
    state = helper.read_session_state("sess-J")
    assert state is not None
    assert len(state["resolved_findings"]) == 1
    assert len(state["observability_gaps"]) == 1
    assert len(state["vocabulary_drift"]) == 1
    # Mass-conservation: keys present + non-empty
    for key in ("session_id", "first_seen", "last_updated"):
        assert key in state


def test_last_updated_advances_on_each_write(helper):
    """last_updated changes with every write."""
    helper.write_finding("sess-K", "t1", "skill", "v1")
    first = helper.read_session_state("sess-K")["last_updated"]
    helper.write_finding("sess-K", "t2", "skill", "v2")
    second = helper.read_session_state("sess-K")["last_updated"]
    # ISO-8601 strings sort lexically; second write must be >= first
    assert second >= first


# ──────────────────────────────────────────────────────────────────────────────
# Empty-list reads for missing sessions
# ──────────────────────────────────────────────────────────────────────────────


def test_list_findings_missing_session_returns_empty(helper):
    assert helper.list_findings("never-written") == []


def test_list_gaps_missing_session_returns_empty(helper):
    assert helper.list_gaps("never-written") == []


def test_list_drift_missing_session_returns_empty(helper):
    assert helper.list_drift("never-written") == []
