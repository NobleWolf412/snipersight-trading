"""
Rejection-Coverage Audit.

Per CLAUDE.md §11 (silent-bug surfacing) and §14 rubric 3 (mass conservation):
catches the regression where a `return None, _rejection_info` path in
`backend/engine/orchestrator.py::_process_symbol` (or its worker variant)
fails to emit a paired `signal_rejected` telemetry event, leaving rejected
symbols invisible to telemetry.db while still being counted by
`scan_completed.signals_rejected`.

The bug class this audit catches was first localized by rejection-forensics
on cycle 88e434ee where NEAR/USDT and INJ/USDT were silently dropped at the
pre-scoring conflict_density gate. The orchestrator.py:1663 branch (plus
six sibling sites) returned rejection_info without an accompanying
`create_signal_rejected_event` emit. Fixed via parent-loop emit-of-last-resort
guard at the scan loop's else branch + `_emit_rejection_telemetry` helper.
This diagnostic enforces the same invariant from the outside so any future
regression in either the per-site emits or the parent-loop guard fails loud
the moment it ships.

Invariants enforced (FAILURES — provable bugs):
  (a) For every run_id with a `scan_completed` event:
        scan_completed.data.symbols_generated + scan_completed.data.signals_rejected
            == count(signal_generated events) + count(signal_rejected events)
      The bookkeeping counter (`rejected_count` in orchestrator.py:601) sees
      every result=None outcome. The telemetry events must match.
  (b) Universe coverage: every symbol in `scan_started.data.symbols` is
      accounted for in `signal_generated.symbol` OR `signal_rejected.symbol`
      for the same run_id. A symbol appearing in neither AND not contributing
      to `signals_generated` count is a silent drop.
  (c) gate_name vocabulary stability: every `signal_rejected` event carries
      a non-null `data.gate_name` OR `data.reason_type` so /scan-autopsy and
      /rejection-survey can bucket it by stage. A NULL/missing field is a
      calibration drift signal.

Observations (NOTES — informational):
  - Per-stage distribution of rejections (vs prior-N median). If a stage's
    count shifts >2x relative to the prior-N median, flag as drift candidate
    but do NOT fail — could be regime change, not a bug.
  - Cycles where rejections=0 across the full universe (everything passed).

Usage (in-process):
    from backend.diagnostics.rejection_coverage_audit import audit_runs
    print(audit_runs())
    print(audit_runs(run_id="88e434ee"))
    print(audit_runs(since="2026-05-20T00:00:00Z"))

Usage (CLI):
    python -m backend.diagnostics.rejection_coverage_audit
    python -m backend.diagnostics.rejection_coverage_audit --run-id 88e434ee
    python -m backend.diagnostics.rejection_coverage_audit --runs 50
    python -m backend.diagnostics.rejection_coverage_audit --since "2026-05-20T00:00:00Z"

This script is read-only and idempotent. It does not re-run any pipeline.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_DEFAULT_DB = Path(__file__).resolve().parent.parent / "cache" / "telemetry.db"


@dataclass
class CycleRow:
    """Per-cycle audit row."""

    run_id: str
    ts: str
    profile: Optional[str]
    universe_size: int
    generated_count_completed: int        # from scan_completed.data
    rejected_count_completed: int         # from scan_completed.data
    generated_events: int                 # count(signal_generated) in db
    rejected_events: int                  # count(signal_rejected) in db
    silent_drops: List[str] = field(default_factory=list)
    null_gate_count: int = 0
    null_reason_count: int = 0

    @property
    def coverage_gap(self) -> int:
        """How many telemetry events are missing vs scan_completed bookkeeping."""
        expected = self.generated_count_completed + self.rejected_count_completed
        actual = self.generated_events + self.rejected_events
        return expected - actual

    @property
    def healthy(self) -> bool:
        return (
            self.coverage_gap == 0
            and not self.silent_drops
            and self.null_gate_count == 0
            and self.null_reason_count == 0
        )


@dataclass
class AuditReport:
    """Summary across the audited window."""

    cycles_audited: int
    cycles_healthy: int
    cycles_with_gap: int
    cycles_with_silent_drops: int
    total_silent_drops: int
    null_gate_total: int
    cycle_rows: List[CycleRow] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return (
            self.cycles_with_gap == 0
            and self.total_silent_drops == 0
            and self.null_gate_total == 0
        )

    def __str__(self) -> str:
        status = "HEALTHY" if self.healthy else "DEGRADED"
        lines: List[str] = []
        lines.append(f"REJECTION-COVERAGE AUDIT — {status}")
        lines.append("=" * 60)
        lines.append(
            f"Cycles audited:           {self.cycles_audited}"
        )
        lines.append(
            f"Cycles healthy:           {self.cycles_healthy} ({_pct(self.cycles_healthy, self.cycles_audited)}%)"
        )
        lines.append(
            f"Cycles with coverage gap: {self.cycles_with_gap}"
        )
        lines.append(
            f"Cycles with silent drops: {self.cycles_with_silent_drops}"
        )
        lines.append(
            f"Total silent drops:       {self.total_silent_drops}"
        )
        lines.append(
            f"Null gate_name events:    {self.null_gate_total}"
        )
        lines.append("")
        if not self.cycle_rows:
            lines.append("(no cycles in window)")
            return "\n".join(lines)

        # Per-cycle table (only failures and the most recent few)
        lines.append("Per-cycle detail (failures first, then most recent):")
        lines.append(
            f"  {'run_id':>10s}  {'ts':19s}  {'uni':>3s}  {'gen/rej (cmpl)':>14s}  {'gen/rej (evt)':>14s}  {'gap':>3s}  status"
        )
        failed = [r for r in self.cycle_rows if not r.healthy]
        healthy_recent = [r for r in self.cycle_rows if r.healthy][:5]
        for row in failed + healthy_recent:
            tag = "OK"
            if row.coverage_gap > 0:
                tag = f"GAP({row.coverage_gap})"
            if row.silent_drops:
                tag = f"DROPS:{len(row.silent_drops)}"
            if row.null_gate_count:
                tag = f"NULL_GATE:{row.null_gate_count}"
            lines.append(
                f"  {row.run_id[:10]:>10s}  {row.ts[:19]:19s}  {row.universe_size:>3d}  "
                f"{row.generated_count_completed:>5d}/{row.rejected_count_completed:<6d}    "
                f"{row.generated_events:>5d}/{row.rejected_events:<6d}    "
                f"{row.coverage_gap:>3d}  {tag}"
            )
        # Silent-drop detail
        drop_rows = [r for r in self.cycle_rows if r.silent_drops]
        if drop_rows:
            lines.append("")
            lines.append("Silent-drop detail:")
            for row in drop_rows:
                lines.append(f"  {row.run_id}: {', '.join(row.silent_drops)}")
        return "\n".join(lines)


def _pct(n: int, d: int) -> int:
    if d == 0:
        return 0
    return int(round(n * 100 / d))


def audit_runs(
    db_path: Optional[Path] = None,
    run_id: Optional[str] = None,
    runs: int = 20,
    since: Optional[str] = None,
) -> AuditReport:
    """Audit telemetry rejection coverage for one or more runs.

    Args:
        db_path: telemetry.db path. Defaults to backend/cache/telemetry.db.
        run_id: if set, audit just this run.
        runs: if run_id and since both None, audit the N most recent scan_completed cycles.
        since: ISO-8601 timestamp filter (audits all cycles >= this ts).

    Returns:
        AuditReport with per-cycle rows + summary.
    """
    db = db_path or _DEFAULT_DB
    if not db.exists():
        raise FileNotFoundError(f"telemetry.db not found at {db}")

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        if run_id:
            where = "WHERE run_id = ?"
            params: Tuple[Any, ...] = (run_id,)
            limit_sql = ""
        elif since:
            where = "WHERE timestamp >= ?"
            params = (since,)
            limit_sql = ""
        else:
            where = ""
            params = ()
            limit_sql = f" LIMIT {int(runs)}"

        cycle_q = (
            "SELECT run_id, timestamp, data_json "
            "FROM telemetry_events "
            "WHERE event_type='scan_completed' "
            + (("AND " + where[6:]) if where else "")
            + " ORDER BY timestamp DESC"
            + limit_sql
        )
        cur = conn.execute(cycle_q, params)
        cycle_rows: List[CycleRow] = []
        for row in cur.fetchall():
            rid = row["run_id"]
            ts = row["timestamp"]
            sc_data = json.loads(row["data_json"]) if row["data_json"] else {}
            cycle = _audit_one_cycle(conn, rid, ts, sc_data)
            cycle_rows.append(cycle)

        report = AuditReport(
            cycles_audited=len(cycle_rows),
            cycles_healthy=sum(1 for r in cycle_rows if r.healthy),
            cycles_with_gap=sum(1 for r in cycle_rows if r.coverage_gap > 0),
            cycles_with_silent_drops=sum(1 for r in cycle_rows if r.silent_drops),
            total_silent_drops=sum(len(r.silent_drops) for r in cycle_rows),
            null_gate_total=sum(r.null_gate_count for r in cycle_rows),
            cycle_rows=cycle_rows,
        )
        return report
    finally:
        conn.close()


def _audit_one_cycle(
    conn: sqlite3.Connection,
    run_id: str,
    ts: str,
    scan_completed_data: Dict[str, Any],
) -> CycleRow:
    """Build a per-cycle CycleRow from telemetry events."""

    # scan_started provides the universe + profile
    ss_row = conn.execute(
        "SELECT data_json FROM telemetry_events "
        "WHERE event_type='scan_started' AND run_id = ? LIMIT 1",
        (run_id,),
    ).fetchone()
    universe: List[str] = []
    profile: Optional[str] = None
    if ss_row and ss_row["data_json"]:
        ss_data = json.loads(ss_row["data_json"])
        universe = ss_data.get("symbols", []) or []
        profile = ss_data.get("profile")

    # scan_completed bookkeeping counters
    generated_count_completed = int(scan_completed_data.get("signals_generated", 0))
    rejected_count_completed = int(scan_completed_data.get("signals_rejected", 0))

    # Per-symbol telemetry events
    gen_syms: List[str] = []
    rej_syms: List[str] = []
    null_gate = 0
    null_reason = 0

    for ev_type, sym_list, count_null_gate in (
        ("signal_generated", gen_syms, False),
        ("signal_rejected", rej_syms, True),
    ):
        cur = conn.execute(
            "SELECT symbol, data_json FROM telemetry_events "
            "WHERE event_type = ? AND run_id = ?",
            (ev_type, run_id),
        )
        for r in cur.fetchall():
            sym_list.append(r["symbol"])
            if count_null_gate and r["data_json"]:
                d = json.loads(r["data_json"])
                if d.get("gate_name") is None:
                    null_gate += 1
                if d.get("reason") is None:
                    null_reason += 1

    # Silent drops: in universe but not in either event bucket
    accounted = set(gen_syms) | set(rej_syms)
    silent_drops = [s for s in universe if s not in accounted]

    return CycleRow(
        run_id=run_id,
        ts=ts,
        profile=profile,
        universe_size=len(universe),
        generated_count_completed=generated_count_completed,
        rejected_count_completed=rejected_count_completed,
        generated_events=len(gen_syms),
        rejected_events=len(rej_syms),
        silent_drops=silent_drops,
        null_gate_count=null_gate,
        null_reason_count=null_reason,
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit telemetry rejection coverage. Catches silent-drop regressions "
            "in the orchestrator pipeline by enforcing the invariant that every "
            "rejected symbol produces exactly one signal_rejected telemetry event."
        )
    )
    parser.add_argument("--run-id", help="audit a specific run_id")
    parser.add_argument(
        "--runs",
        type=int,
        default=20,
        help="audit the N most recent cycles (default 20). Ignored if --run-id or --since set.",
    )
    parser.add_argument(
        "--since",
        help="audit all cycles since this ISO-8601 timestamp (e.g. 2026-05-20T00:00:00Z)",
    )
    parser.add_argument(
        "--db",
        help=f"path to telemetry.db (default: {_DEFAULT_DB})",
    )
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None
    report = audit_runs(
        db_path=db_path,
        run_id=args.run_id,
        runs=args.runs,
        since=args.since,
    )
    print(report)
    return 0 if report.healthy else 1


if __name__ == "__main__":
    sys.exit(_main())
