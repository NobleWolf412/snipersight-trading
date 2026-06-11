"""
Headless Session Autopsy.

Per CLAUDE.md §12: produces the post-run triage report the `/autopsy` skill
generates, but as a standalone CLI/programmatic invocation. Same data sources
(`backend/cache/telemetry.db` + `backend/cache/trade_journal.jsonl`), same
paste-friendly output format (short summary first, structured detail second,
raw data last), same anomaly-detection rules.

Why this is NOT the /autopsy skill:
  - The skill is the interactive Claude-driven version. It reasons across
    multiple data sources, follows up on threads, escalates to other skills.
  - This diagnostic is the headless version. It runs in ~5 seconds, writes
    a report to disk, exits with a status code, and stays out of the way.
  - Both share the same forensic logic; they differ only in invocation surface.

Typical invocations:
  python -m backend.diagnostics.autopsy_report                          # most recent session
  python -m backend.diagnostics.autopsy_report --session 3544b1b6       # specific session
  python -m backend.diagnostics.autopsy_report --since 2026-05-20T00Z   # cycles since
  python -m backend.diagnostics.autopsy_report --quiet                  # file-only, no stdout

Wire it into the bot lifecycle (suggested patterns):
  # In start-sniper.bat or any wrapper:
  REM Run autopsy after bot exits, regardless of exit code:
  python -m backend.diagnostics.autopsy_report

  # Or wrap the bot:
  python -m backend.bot.paper_trading_service ; python -m backend.diagnostics.autopsy_report

Output:
  stdout:                          paste-friendly report (unless --quiet)
  .claude/autopsy-reports/<utc>.md  the same report as a dated file
  exit code:                       0=CLEAN, 1=NOTABLE, 2=INVESTIGATE,
                                   3=DATA-UNAVAILABLE (no telemetry/journal),
                                   4=INTERNAL-ERROR

Read-only. No mutation of telemetry, journal, or cache. Idempotent on re-runs.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DB = _REPO_ROOT / "backend" / "cache" / "telemetry.db"
_DEFAULT_JOURNAL = _REPO_ROOT / "backend" / "cache" / "trade_journal.jsonl"
_REPORTS_DIR = _REPO_ROOT / ".claude" / "autopsy-reports"


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class Thread:
    """A finding worth pulling on, with the skill/agent that owns drilldown."""

    severity: str   # NOTABLE | INVESTIGATE | URGENT
    title: str
    evidence: str
    delegate: str   # e.g. "/trade-autopsy <id>" or "rejection-forensics on <SYM>"


@dataclass
class AutopsyReport:
    session_id: Optional[str]
    window_start: Optional[str]
    window_end: Optional[str]
    source: str                # how the session was resolved ("journal" | "scan_cluster" | "user")
    mode: Optional[str]
    profile: Optional[str]
    verdict: str               # CLEAN | NOTABLE | INVESTIGATE

    scans_started: int = 0
    scans_completed: int = 0
    signals_generated: int = 0
    signals_rejected: int = 0
    symmetry_long: int = 0
    symmetry_short: int = 0
    trades_closed: int = 0
    pnl_total: float = 0.0
    wins: int = 0
    losses: int = 0
    errors: int = 0
    warnings: int = 0

    threads: List[Thread] = field(default_factory=list)
    exit_reasons: Dict[str, int] = field(default_factory=dict)
    top_rejections: List[Tuple[str, int]] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)
    run_ids: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Session resolution
# ──────────────────────────────────────────────────────────────────────────────


def _resolve_session_from_journal(journal: Path, target_sid: Optional[str]) -> Optional[Dict[str, Any]]:
    """Resolve session by latest session_id (or target_sid). Returns dict with rows + window."""
    if not journal.exists():
        return None
    try:
        # context-manager ensures the file handle closes on any exception during parse
        with journal.open() as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    except Exception:
        return None
    if not rows:
        return None
    sid = target_sid or rows[-1].get("session_id")
    if not sid:
        return None
    in_session = [r for r in rows if r.get("session_id") == sid]
    if not in_session:
        return None
    return {
        "session_id": sid,
        "rows": in_session,
        "start": in_session[0].get("entry_time"),
        "end": in_session[-1].get("exit_time"),
        "source": "journal",
    }


def _resolve_session_from_scan_cluster(db_path: Path, gap_minutes: int = 30) -> Optional[Dict[str, Any]]:
    """Fall back: latest contiguous cluster of scan_started events."""
    from datetime import timedelta
    if not db_path.exists():
        return None
    try:
        # contextlib.closing guarantees conn.close() even if cur.execute() raises —
        # closes the rubric-7 silent-failure gap (audit round 1, item #5).
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            cur = conn.execute(
                "SELECT timestamp FROM telemetry_events "
                "WHERE event_type='scan_started' ORDER BY timestamp DESC LIMIT 500"
            )
            timestamps = [r[0] for r in cur.fetchall()]
    except Exception:
        return None
    if not timestamps:
        return None
    cluster = [timestamps[0]]
    gap = timedelta(minutes=gap_minutes)
    for t in timestamps[1:]:
        try:
            prev = datetime.fromisoformat(cluster[-1])
            cur_ts = datetime.fromisoformat(t)
        except Exception:
            break
        if (prev - cur_ts) > gap:
            break
        cluster.append(t)
    return {
        "session_id": None,
        "rows": [],
        "start": cluster[-1],
        "end": cluster[0],
        "source": "scan_cluster",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Telemetry queries (window-scoped)
# ──────────────────────────────────────────────────────────────────────────────


def _collect_telemetry(db_path: Path, start: str, end: str) -> Dict[str, Any]:
    """Pull all the session vitals from telemetry.db inside the window."""
    out: Dict[str, Any] = {
        "scans_started": 0,
        "scans_completed": 0,
        "signals_generated": 0,
        "signals_rejected": 0,
        "symmetry": {"LONG": 0, "SHORT": 0},
        "errors": 0,
        "warnings": 0,
        "position_events": {},
        "top_rejections": [],
        "run_ids": [],
        "scan_profiles": {},
        "telemetry_available": False,
    }
    if not db_path.exists():
        return out
    try:
        # contextlib.closing guarantees conn.close() even if any cur.execute() raises
        # mid-query — closes the rubric-7 silent-failure gap (audit round 1, item #5).
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            cur = conn.cursor()

            def count(ev: str) -> int:
                cur.execute(
                    "SELECT COUNT(*) FROM telemetry_events "
                    "WHERE event_type=? AND timestamp BETWEEN ? AND ?",
                    (ev, start, end),
                )
                return cur.fetchone()[0]

            out["scans_started"] = count("scan_started")
            out["scans_completed"] = count("scan_completed")
            out["signals_generated"] = count("signal_generated")
            out["signals_rejected"] = count("signal_rejected")
            out["errors"] = count("error_occurred")
            out["warnings"] = count("warning_issued")

            cur.execute(
                "SELECT json_extract(data_json,'$.direction') AS d, COUNT(*) "
                "FROM telemetry_events WHERE event_type='signal_generated' "
                "AND timestamp BETWEEN ? AND ? GROUP BY d",
                (start, end),
            )
            for d, n in cur.fetchall():
                if d in ("LONG", "SHORT"):
                    out["symmetry"][d] = n

            cur.execute(
                "SELECT json_extract(data_json,'$.reason') AS reason, "
                "       json_extract(data_json,'$.gate_name') AS gate, COUNT(*) AS n "
                "FROM telemetry_events WHERE event_type='signal_rejected' "
                "AND timestamp BETWEEN ? AND ? GROUP BY reason, gate ORDER BY n DESC LIMIT 5",
                (start, end),
            )
            out["top_rejections"] = [(reason, gate, n) for reason, gate, n in cur.fetchall()]

            cur.execute(
                "SELECT event_type, COUNT(*) FROM telemetry_events "
                "WHERE event_type IN ('position_opened','position_closed','stop_loss_hit',"
                "                     'partial_taken','risk_limit_hit','daily_loss_limit_hit',"
                "                     'alt_stop_suggested') "
                "AND timestamp BETWEEN ? AND ? GROUP BY event_type",
                (start, end),
            )
            out["position_events"] = dict(cur.fetchall())

            cur.execute(
                "SELECT DISTINCT run_id FROM telemetry_events "
                "WHERE event_type='scan_completed' AND timestamp BETWEEN ? AND ? "
                "ORDER BY timestamp DESC LIMIT 5",
                (start, end),
            )
            out["run_ids"] = [r[0] for r in cur.fetchall() if r[0]]

            cur.execute(
                "SELECT json_extract(data_json,'$.profile') AS p, COUNT(*) "
                "FROM telemetry_events WHERE event_type='scan_started' "
                "AND timestamp BETWEEN ? AND ? GROUP BY p",
                (start, end),
            )
            out["scan_profiles"] = {p: n for p, n in cur.fetchall() if p}

            out["telemetry_available"] = True
    except Exception as exc:
        # Fix audit round 1 item #1: the caveats field is a list on AutopsyReport,
        # but this dict used a singular "caveat" key — silently dropped at the
        # build_report pickup. Use a list under the matching plural key so the
        # consumer's caveats.extend(...) call below catches it.
        out["caveats_pending"] = [f"telemetry query failed: {type(exc).__name__}: {exc}"]
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Anomaly checklist
# ──────────────────────────────────────────────────────────────────────────────


def _build_threads(report: AutopsyReport, trades: List[Dict[str, Any]]) -> List[Thread]:
    """Apply the same anomaly checklist /autopsy uses."""
    threads: List[Thread] = []

    # Symmetry leak (LONG/SHORT count grossly skewed; only fires at N>=20)
    L, S = report.symmetry_long, report.symmetry_short
    if (L + S) >= 20:
        if S > 0 and (L / max(S, 1)) > 3:
            threads.append(Thread(
                severity="NOTABLE",
                title="Symmetry leak — LONG/SHORT ratio > 3:1",
                evidence=f"LONG {L} / SHORT {S} = {L/max(S,1):.1f}:1",
                delegate="run symmetry-guard",
            ))
        elif L > 0 and (S / max(L, 1)) > 3:
            threads.append(Thread(
                severity="NOTABLE",
                title="Symmetry leak — SHORT/LONG ratio > 3:1",
                evidence=f"LONG {L} / SHORT {S} = 1:{S/max(L,1):.1f}",
                delegate="run symmetry-guard",
            ))

    # Single rejection reason dominates
    if report.signals_rejected and report.top_rejections:
        top_reason, top_n = report.top_rejections[0]
        share = top_n / max(report.signals_rejected, 1)
        if share > 0.50:
            threads.append(Thread(
                severity="NOTABLE",
                title=f"Single rejection reason dominates ({share*100:.0f}%)",
                evidence=f"{(top_reason or '<null>')[:60]} ({top_n}/{report.signals_rejected})",
                delegate="run /rejection-survey 50",
            ))

    # High-confidence loss
    hi_conf_losses = [
        t for t in trades
        if (t.get("pnl", 0) or 0) < 0 and (t.get("confidence_score", 0) or 0) >= 80
    ]
    for t in hi_conf_losses:
        threads.append(Thread(
            severity="NOTABLE",
            title=f"High-confidence loss — {t.get('symbol','?')} conf={t.get('confidence_score',0):.1f}",
            evidence=f"pnl={t.get('pnl',0):.2f} exit={t.get('exit_reason','?')}",
            delegate=f"run /trade-autopsy {t.get('trade_id')}",
        ))

    # Weird exits — orphan / stagnation / target_strip / EMERGENCY
    weird = [
        t for t in trades
        if t.get("exit_reason") in ("orphan_price_feed_failure", "stagnation", "target_strip")
        or str(t.get("exit_reason", "")).startswith("EMERGENCY")
    ]
    for t in weird:
        threads.append(Thread(
            severity="URGENT" if str(t.get("exit_reason", "")).startswith("EMERGENCY") else "NOTABLE",
            title=f"Suspect exit — {t.get('symbol','?')} {t.get('exit_reason')}",
            evidence=f"trade_id={t.get('trade_id')}",
            delegate=f"run /trade-autopsy {t.get('trade_id')}",
        ))

    # Errors in window
    if report.errors > 0:
        threads.append(Thread(
            severity="NOTABLE",
            title=f"{report.errors} error_occurred event(s) in window",
            evidence="see telemetry.db error_occurred rows",
            delegate="inspect inline; do not delegate",
        ))

    # Bot-mode mismatch — STEALTH is the only sanctioned bot mode per §15
    profiles = list((getattr(report, "_scan_profiles", {}) or {}).keys())
    non_stealth = [p for p in profiles if p and p not in ("stealth_balanced", "stealth")]
    if non_stealth:
        threads.append(Thread(
            severity="URGENT",
            title=f"Bot mode mismatch — non-STEALTH profile detected: {non_stealth}",
            evidence="CLAUDE.md §15: bot production mode is STEALTH",
            delegate="halt + verify botConfig.sniperMode source",
        ))

    return threads[:3]  # top 3 only, like /autopsy


# ──────────────────────────────────────────────────────────────────────────────
# Report builder
# ──────────────────────────────────────────────────────────────────────────────


def build_report(
    db_path: Optional[Path] = None,
    journal_path: Optional[Path] = None,
    session_id: Optional[str] = None,
    since: Optional[str] = None,
) -> AutopsyReport:
    """Construct an AutopsyReport from the live data sources.

    Mirrors the /autopsy skill's protocol:
      1. Resolve session window (journal → scan_cluster fallback → user-named)
      2. Pull session-level vitals from telemetry
      3. Run anomaly checklist
      4. Pick top-3 threads
      5. Compose verdict
    """
    db_path = db_path or _DEFAULT_DB
    journal_path = journal_path or _DEFAULT_JOURNAL

    # Step 1: session resolution
    sess = _resolve_session_from_journal(journal_path, session_id)
    if sess is None:
        sess = _resolve_session_from_scan_cluster(db_path)
    if sess is None:
        # Neither source available — emit a minimal report
        return AutopsyReport(
            session_id=None,
            window_start=None,
            window_end=None,
            source="none",
            mode=None,
            profile=None,
            verdict="DATA-UNAVAILABLE",
            caveats=[
                f"trade_journal.jsonl not found or empty at {journal_path}",
                f"telemetry.db not found or empty at {db_path}",
            ],
        )

    start = since or sess["start"]
    end = sess["end"]

    # Step 2: telemetry vitals
    tel = _collect_telemetry(db_path, start, end)

    # Step 2b: trade-side aggregates from journal rows
    trades = sess.get("rows") or []
    pnl_total = sum((t.get("pnl") or 0) for t in trades)
    wins = sum(1 for t in trades if (t.get("pnl") or 0) > 0)
    losses = sum(1 for t in trades if (t.get("pnl") or 0) <= 0)
    # Mass-conservation runtime check (§14 rubric 3 — audit round 1 item #3).
    # pnl>0 → wins, pnl<=0 → losses (break-even bucketed into losses by design;
    # documented assumption). Every trade must land in exactly one bucket.
    assert wins + losses == len(trades), (
        f"autopsy_report trade-bucket mass leak: "
        f"wins={wins} losses={losses} total={len(trades)}"
    )
    exit_dist = collections.Counter((t.get("exit_reason") or "unknown") for t in trades)

    # Compose report
    profile = next(iter(tel.get("scan_profiles", {}).keys()), None)
    mode = None
    if profile:
        mode_map = {
            "macro_surveillance": "OVERWATCH",
            "intraday_aggressive": "STRIKE",
            "precision": "SURGICAL",
            "stealth_balanced": "STEALTH",
            "stealth": "STEALTH",
        }
        mode = mode_map.get(profile, profile.upper())

    report = AutopsyReport(
        session_id=sess.get("session_id"),
        window_start=start,
        window_end=end,
        source=sess.get("source", "unknown"),
        mode=mode,
        profile=profile,
        verdict="CLEAN",  # tentative — adjusted below
        scans_started=tel["scans_started"],
        scans_completed=tel["scans_completed"],
        signals_generated=tel["signals_generated"],
        signals_rejected=tel["signals_rejected"],
        symmetry_long=tel["symmetry"]["LONG"],
        symmetry_short=tel["symmetry"]["SHORT"],
        trades_closed=len(trades),
        pnl_total=pnl_total,
        wins=wins,
        losses=losses,
        errors=tel["errors"],
        warnings=tel["warnings"],
        exit_reasons=dict(exit_dist),
        top_rejections=[(r, n) for r, _g, n in tel["top_rejections"]],
        run_ids=tel["run_ids"],
    )
    # tuck scan_profiles in for the threads checker (without exposing on the dataclass)
    report._scan_profiles = tel.get("scan_profiles", {})  # type: ignore[attr-defined]

    # Caveats
    if not tel.get("telemetry_available"):
        report.caveats.append(f"telemetry.db not queryable — partial report")
    if sess.get("source") == "scan_cluster":
        report.caveats.append("session resolved via scan_started cluster (no trades in journal)")
    # Pick up any caveats the telemetry-collection step queued (e.g. query-mid-flow
    # exceptions). Fix audit round 1 item #1 — the old singular "caveat" key was
    # silently dropped; now the plural "caveats_pending" list propagates correctly.
    for c in tel.get("caveats_pending", []) or []:
        report.caveats.append(c)

    # Step 3+4: threads
    report.threads = _build_threads(report, trades)

    # Step 5: verdict
    if not report.threads:
        report.verdict = "CLEAN"
    elif any(t.severity == "URGENT" for t in report.threads):
        report.verdict = "INVESTIGATE"
    else:
        report.verdict = "NOTABLE"
    return report


# ──────────────────────────────────────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────────────────────────────────────


def format_report(report: AutopsyReport) -> str:
    """Paste-friendly markdown, mirroring /autopsy skill output format."""
    lines: List[str] = []
    sid = report.session_id or "(no session_id)"
    lines.append(f"SESSION AUTOPSY — {sid}")
    lines.append("=" * 60)
    lines.append(f"Window: {report.window_start} -> {report.window_end}")
    lines.append(f"Source: {report.source}  Mode: {report.mode or '?'}  Profile: {report.profile or '?'}")
    lines.append(f"Verdict: {report.verdict}")
    lines.append("")

    # Headline
    lines.append("Headline")
    lines.append("--------")
    if report.verdict == "CLEAN":
        lines.append("No threads. Session looks clean.")
    elif report.verdict == "INVESTIGATE":
        lines.append("URGENT thread present — see Top Threads below.")
    else:
        lines.append("Notable threads present — review below.")
    lines.append("")

    # Vitals
    accept_pct = (
        report.signals_generated / max(report.signals_generated + report.signals_rejected, 1) * 100
    )
    L, S = report.symmetry_long, report.symmetry_short
    if S > 0:
        ratio = f"{L/S:.2f}:1" if L >= S else f"1:{S/max(L,1):.2f}"
    elif L > 0:
        ratio = "inf:1"
    else:
        ratio = "—"
    win_rate = report.wins / max(report.wins + report.losses, 1) * 100

    lines.append("Vitals")
    lines.append("------")
    lines.append(f"Scans: {report.scans_started}/{report.scans_completed}")
    lines.append(
        f"Signals: {report.signals_generated} gen / {report.signals_rejected} rej ({accept_pct:.2f}%)"
    )
    lines.append(f"Symmetry: LONG {L}  SHORT {S}  ratio {ratio}")
    lines.append(f"Trades: {report.trades_closed} closed   PnL: {report.pnl_total:.2f}   {report.wins}W/{report.losses}L ({win_rate:.0f}%)")
    lines.append(f"Errors: {report.errors}   Warnings: {report.warnings}")
    lines.append("")

    # Top threads
    lines.append("Top 3 Threads")
    lines.append("-------------")
    if not report.threads:
        lines.append("None.")
    else:
        for i, t in enumerate(report.threads, 1):
            lines.append(f"{i}. [{t.severity}] {t.title}")
            lines.append(f"   evidence: {t.evidence}")
            lines.append(f"   -> {t.delegate}")
    lines.append("")

    # Exit-reason distribution
    if report.exit_reasons:
        lines.append("Exit-Reason Distribution")
        lines.append("------------------------")
        total = sum(report.exit_reasons.values()) or 1
        for reason, n in sorted(report.exit_reasons.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {reason}: {n} ({n/total*100:.0f}%)")
        lines.append("")

    # Top rejection reasons
    if report.top_rejections:
        lines.append("Top Rejection Reasons (top 5)")
        lines.append("-----------------------------")
        total = report.signals_rejected or 1
        for reason, n in report.top_rejections:
            lines.append(f"  {(reason or '<null>')[:55]}: {n} ({n/total*100:.0f}%)")
        lines.append("")

    # Caveats
    if report.caveats:
        lines.append("Caveats")
        lines.append("-------")
        for c in report.caveats:
            lines.append(f"  - {c}")
        lines.append("")

    # Raw evidence
    lines.append("Raw Evidence")
    lines.append("------------")
    lines.append(f"Run IDs in window: {report.run_ids[:5]}")
    if report.session_id:
        lines.append(f"Session resolution: trade_journal.jsonl session_id={report.session_id}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────────────────


def write_report_file(report_text: str, reports_dir: Optional[Path] = None) -> Path:
    """Write the report to .claude/autopsy-reports/<utc>__<pid>.md and return the path.

    Filename includes pid suffix so two invocations in the same wall-clock second
    (e.g. CI loop, bot-restart-then-autopsy, parallel hook) don't silently
    overwrite each other. Fix audit round 1 item #2.
    """
    reports_dir = reports_dir or _REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    path = reports_dir / f"{ts}__pid{os.getpid()}.md"
    # Last-resort guard: if the pid+ts combo somehow collides (extremely unlikely),
    # bump a counter so we don't overwrite an existing report silently.
    counter = 1
    while path.exists():
        path = reports_dir / f"{ts}__pid{os.getpid()}__{counter}.md"
        counter += 1
    path.write_text(report_text, encoding="utf-8")
    return path


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


_EXIT_CLEAN = 0
_EXIT_NOTABLE = 1
_EXIT_INVESTIGATE = 2
_EXIT_DATA_UNAVAILABLE = 3
_EXIT_INTERNAL_ERROR = 4


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Headless session autopsy. Same data sources as the /autopsy skill, "
            "different invocation surface. Writes a paste-friendly report to "
            ".claude/autopsy-reports/<utc>.md and stdout."
        )
    )
    parser.add_argument("--session", help="specific session_id to autopsy (default: latest)")
    parser.add_argument("--since", help="ISO-8601 lower bound override")
    parser.add_argument("--db", help=f"path to telemetry.db (default: {_DEFAULT_DB})")
    parser.add_argument("--journal", help=f"path to trade_journal.jsonl (default: {_DEFAULT_JOURNAL})")
    parser.add_argument("--reports-dir", help=f"directory for report file (default: {_REPORTS_DIR})")
    parser.add_argument("--quiet", action="store_true", help="suppress stdout, file-only")
    parser.add_argument("--no-file", action="store_true", help="suppress file write, stdout-only")
    args = parser.parse_args()

    try:
        report = build_report(
            db_path=Path(args.db) if args.db else None,
            journal_path=Path(args.journal) if args.journal else None,
            session_id=args.session,
            since=args.since,
        )
    except Exception as exc:
        if not args.quiet:
            print(f"AUTOPSY FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return _EXIT_INTERNAL_ERROR

    text = format_report(report)

    if not args.quiet:
        print(text)
    if not args.no_file:
        path = write_report_file(
            text,
            reports_dir=Path(args.reports_dir) if args.reports_dir else None,
        )
        if not args.quiet:
            print(f"\n[report written: {path}]", file=sys.stderr)

    if report.verdict == "CLEAN":
        return _EXIT_CLEAN
    if report.verdict == "INVESTIGATE":
        return _EXIT_INVESTIGATE
    if report.verdict == "DATA-UNAVAILABLE":
        return _EXIT_DATA_UNAVAILABLE
    return _EXIT_NOTABLE


if __name__ == "__main__":
    sys.exit(_main())
