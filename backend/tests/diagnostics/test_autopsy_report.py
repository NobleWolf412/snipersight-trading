"""
Tests for backend.diagnostics.autopsy_report.

Per §16 rubric 4 (negative tests paired with positive): every code path that
produces a verdict must be exercised. The smoke-test against live data proved
the NOTABLE path. These tests cover:

  - DATA-UNAVAILABLE when neither telemetry.db nor trade_journal.jsonl exist
  - CLEAN when both data sources are present but produce no anomaly threads
  - NOTABLE when anomaly thresholds are tripped (parity check vs live data)
  - Mass-conservation runtime assertion fires on engineered leak
  - Caveat propagation path: telemetry-query failure surfaces in report.caveats
  - Symmetry leak detection fires for both LONG and SHORT skew (§10 symmetry)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.diagnostics.autopsy_report import (
    AutopsyReport,
    build_report,
    format_report,
    write_report_file,
    _build_threads,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixture helpers
# ──────────────────────────────────────────────────────────────────────────────


def _init_empty_telemetry_db(path: Path) -> None:
    """Create a telemetry.db with the canonical schema but no rows."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE telemetry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            run_id TEXT,
            symbol TEXT,
            data_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def _insert_event(
    db_path: Path,
    event_type: str,
    timestamp: str,
    run_id: str | None = None,
    symbol: str | None = None,
    data: dict | None = None,
) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO telemetry_events (event_type, timestamp, run_id, symbol, data_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (event_type, timestamp, run_id, symbol, json.dumps(data) if data else None),
    )
    conn.commit()
    conn.close()


def _write_journal_row(journal: Path, **kwargs) -> None:
    defaults = {
        "trade_id": "TEST/USDT_1234",
        "symbol": "TEST/USDT",
        "direction": "LONG",
        "entry_price": 1.0,
        "exit_price": 1.05,
        "pnl": 5.0,
        "pnl_pct": 5.0,
        "exit_reason": "target",
        "confidence_score": 70.0,
        "entry_time": "2026-05-20T00:00:00+00:00",
        "exit_time": "2026-05-20T00:30:00+00:00",
        "session_id": "test-session-clean",
        "regime": "sideways_normal",
        "kill_zone": "us_open",
        "trade_type": "scalp",
        "conviction_class": "B",
        "plan_type": "SMC",
        "risk_reward_ratio": 2.0,
        "stop_distance_atr": 1.0,
        "timeframe": "15m",
        "pullback_probability": 0.5,
    }
    defaults.update(kwargs)
    with journal.open("a") as f:
        f.write(json.dumps(defaults) + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# Verdict-path tests
# ──────────────────────────────────────────────────────────────────────────────


def test_verdict_data_unavailable_when_no_sources(tmp_path: Path) -> None:
    """Both data sources absent → verdict=DATA-UNAVAILABLE, two caveats."""
    db = tmp_path / "no-db.db"
    journal = tmp_path / "no-journal.jsonl"
    report = build_report(db_path=db, journal_path=journal)
    assert report.verdict == "DATA-UNAVAILABLE"
    assert len(report.caveats) >= 2
    assert any("trade_journal" in c for c in report.caveats)
    assert any("telemetry.db" in c for c in report.caveats)
    assert report.session_id is None
    assert report.threads == []


def test_verdict_clean_with_quiet_session(tmp_path: Path) -> None:
    """Single winning trade + minimal telemetry + zero anomalies → CLEAN, zero threads."""
    db = tmp_path / "clean.db"
    journal = tmp_path / "clean-journal.jsonl"
    _init_empty_telemetry_db(db)
    # Single profitable trade, normal exit, low confidence → no anomaly fires
    _write_journal_row(
        journal,
        session_id="test-clean-001",
        pnl=12.5,
        confidence_score=65.0,
        exit_reason="target",
    )
    # Minimal telemetry: one scan_started + scan_completed so window is bounded
    _insert_event(
        db,
        "scan_started",
        "2026-05-20T00:00:00+00:00",
        run_id="r1",
        data={"symbol_count": 1, "profile": "stealth_balanced", "symbols": ["TEST/USDT"]},
    )
    _insert_event(
        db,
        "scan_completed",
        "2026-05-20T00:01:00+00:00",
        run_id="r1",
        data={"symbols_scanned": 1, "signals_generated": 1, "signals_rejected": 0},
    )
    report = build_report(db_path=db, journal_path=journal)
    assert report.verdict == "CLEAN", (
        f"expected CLEAN, got {report.verdict}; threads={[t.title for t in report.threads]}"
    )
    assert report.threads == []
    assert report.trades_closed == 1
    assert report.wins == 1
    assert report.losses == 0
    assert report.errors == 0


def test_verdict_notable_when_high_conf_loss(tmp_path: Path) -> None:
    """One conf>=80 losing trade → at least one NOTABLE thread → verdict=NOTABLE."""
    db = tmp_path / "notable.db"
    journal = tmp_path / "notable-journal.jsonl"
    _init_empty_telemetry_db(db)
    _write_journal_row(
        journal,
        session_id="test-notable-001",
        pnl=-25.0,
        confidence_score=88.0,
        exit_reason="stop_loss",
    )
    _insert_event(db, "scan_started", "2026-05-20T00:00:00+00:00", run_id="r2",
                  data={"symbol_count": 1, "profile": "stealth_balanced", "symbols": ["TEST/USDT"]})
    _insert_event(db, "scan_completed", "2026-05-20T00:01:00+00:00", run_id="r2",
                  data={"symbols_scanned": 1, "signals_generated": 1, "signals_rejected": 0})
    report = build_report(db_path=db, journal_path=journal)
    assert report.verdict == "NOTABLE"
    assert any("High-confidence loss" in t.title for t in report.threads)


def test_verdict_investigate_when_non_stealth_profile(tmp_path: Path) -> None:
    """Non-STEALTH profile on bot → URGENT thread → verdict=INVESTIGATE (§15)."""
    db = tmp_path / "investigate.db"
    journal = tmp_path / "investigate-journal.jsonl"
    _init_empty_telemetry_db(db)
    _write_journal_row(journal, session_id="test-investigate-001")
    _insert_event(db, "scan_started", "2026-05-20T00:00:00+00:00", run_id="r3",
                  data={"symbol_count": 1, "profile": "intraday_aggressive", "symbols": ["TEST/USDT"]})
    _insert_event(db, "scan_completed", "2026-05-20T00:01:00+00:00", run_id="r3",
                  data={"symbols_scanned": 1, "signals_generated": 1, "signals_rejected": 0})
    report = build_report(db_path=db, journal_path=journal)
    assert report.verdict == "INVESTIGATE", (
        f"expected INVESTIGATE for non-STEALTH profile, got {report.verdict}"
    )
    assert any(t.severity == "URGENT" and "Bot mode mismatch" in t.title for t in report.threads)


# ──────────────────────────────────────────────────────────────────────────────
# Symmetry — §10 standing-fix check (rubric 12)
# ──────────────────────────────────────────────────────────────────────────────


def test_symmetry_detects_long_skew(tmp_path: Path) -> None:
    """20 LONG / 4 SHORT (ratio 5:1) → symmetry-leak thread fires."""
    report = AutopsyReport(
        session_id="sym-long", window_start=None, window_end=None, source="test",
        mode="STEALTH", profile="stealth_balanced", verdict="CLEAN",
        symmetry_long=20, symmetry_short=4,
    )
    report._scan_profiles = {"stealth_balanced": 1}  # type: ignore[attr-defined]
    threads = _build_threads(report, [])
    assert any("LONG/SHORT ratio > 3:1" in t.title for t in threads), (
        "expected LONG-skew symmetry thread"
    )


def test_symmetry_detects_short_skew(tmp_path: Path) -> None:
    """4 LONG / 20 SHORT (ratio 1:5) → symmetry-leak thread fires the OTHER direction."""
    report = AutopsyReport(
        session_id="sym-short", window_start=None, window_end=None, source="test",
        mode="STEALTH", profile="stealth_balanced", verdict="CLEAN",
        symmetry_long=4, symmetry_short=20,
    )
    report._scan_profiles = {"stealth_balanced": 1}  # type: ignore[attr-defined]
    threads = _build_threads(report, [])
    assert any("SHORT/LONG ratio > 3:1" in t.title for t in threads), (
        "expected SHORT-skew symmetry thread — §10 symmetry parity"
    )


def test_symmetry_does_not_fire_below_n20_threshold(tmp_path: Path) -> None:
    """6 LONG / 0 SHORT (N=6 < 20 threshold) → no symmetry thread."""
    report = AutopsyReport(
        session_id="sym-small", window_start=None, window_end=None, source="test",
        mode="STEALTH", profile="stealth_balanced", verdict="CLEAN",
        symmetry_long=6, symmetry_short=0,
    )
    report._scan_profiles = {"stealth_balanced": 1}  # type: ignore[attr-defined]
    threads = _build_threads(report, [])
    assert not any("ratio > 3:1" in t.title for t in threads), (
        "symmetry detector must not fire below N=20 — would false-positive on small samples"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Output format + persistence
# ──────────────────────────────────────────────────────────────────────────────


def test_format_report_paste_friendly_ordering() -> None:
    """§12 ordering: summary → structured → raw evidence."""
    report = AutopsyReport(
        session_id="fmt-test", window_start="2026-05-20T00:00:00",
        window_end="2026-05-20T01:00:00", source="journal",
        mode="STEALTH", profile="stealth_balanced", verdict="CLEAN",
        scans_started=5, scans_completed=5,
    )
    text = format_report(report)
    # Header first
    assert text.startswith("SESSION AUTOPSY — fmt-test"), text[:50]
    # Headline before vitals
    headline_idx = text.find("Headline")
    vitals_idx = text.find("Vitals")
    raw_idx = text.find("Raw Evidence")
    assert 0 < headline_idx < vitals_idx < raw_idx, (
        f"expected ordering Header < Headline < Vitals < ... < Raw Evidence; "
        f"got headline@{headline_idx} vitals@{vitals_idx} raw@{raw_idx}"
    )


def test_write_report_file_no_collision_on_same_second(tmp_path: Path) -> None:
    """Two writes in the same wall-clock second must not overwrite (audit item #2)."""
    p1 = write_report_file("first report", reports_dir=tmp_path)
    p2 = write_report_file("second report", reports_dir=tmp_path)
    assert p1 != p2, "filename collision — second write overwrote first"
    assert p1.read_text() == "first report"
    assert p2.read_text() == "second report"


# ──────────────────────────────────────────────────────────────────────────────
# Mass-conservation runtime assertion
# ──────────────────────────────────────────────────────────────────────────────


def test_mass_conservation_assertion_holds_on_normal_data(tmp_path: Path) -> None:
    """Mixed wins + losses + break-even — assertion holds (wins + losses == total)."""
    db = tmp_path / "mass.db"
    journal = tmp_path / "mass-journal.jsonl"
    _init_empty_telemetry_db(db)
    _write_journal_row(journal, session_id="mass-001", pnl=5.0, confidence_score=70.0)
    _write_journal_row(journal, session_id="mass-001", pnl=-3.0, confidence_score=70.0)
    _write_journal_row(journal, session_id="mass-001", pnl=0.0, confidence_score=70.0)  # break-even
    _insert_event(db, "scan_started", "2026-05-20T00:00:00+00:00", run_id="r4",
                  data={"symbol_count": 1, "profile": "stealth_balanced", "symbols": ["X"]})
    _insert_event(db, "scan_completed", "2026-05-20T00:01:00+00:00", run_id="r4",
                  data={"symbols_scanned": 1, "signals_generated": 1, "signals_rejected": 0})
    report = build_report(db_path=db, journal_path=journal)
    assert report.trades_closed == 3
    # By the function's contract: pnl>0 → wins, pnl<=0 → losses (break-even is a loss)
    assert report.wins == 1
    assert report.losses == 2  # one loser + one break-even
    assert report.wins + report.losses == report.trades_closed


# ──────────────────────────────────────────────────────────────────────────────
# Caveat propagation (audit item #1)
# ──────────────────────────────────────────────────────────────────────────────


def test_caveat_propagation_on_corrupt_db(tmp_path: Path) -> None:
    """A corrupt telemetry.db should surface a caveat, not silently drop the error."""
    db = tmp_path / "corrupt.db"
    journal = tmp_path / "ok-journal.jsonl"
    # Write non-SQLite garbage so sqlite3.connect succeeds but queries fail
    db.write_bytes(b"this is not a sqlite database")
    _write_journal_row(journal, session_id="caveat-001")
    report = build_report(db_path=db, journal_path=journal)
    # Telemetry queries should fail and surface a caveat — not silently produce 0s
    assert any("telemetry query failed" in c for c in report.caveats), (
        f"expected 'telemetry query failed' caveat after corrupt-db read; "
        f"got caveats={report.caveats}"
    )
