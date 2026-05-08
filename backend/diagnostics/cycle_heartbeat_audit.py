"""
Cycle Heartbeat Audit.

Per CLAUDE.md §12: catches regressions in scan-cycle instrumentation
and surfaces drift across cycles, not just the current cycle in
isolation. Mirrors the pattern of breakdown_cache_audit and
universe_audit — every long-lived ring buffer in this codebase has
a sibling diagnostic that walks it.

Invariants enforced (FAILURES — provable bugs):
  (a) Mass conservation per cycle:
        plans_emitted + sum(signals_per_stage.values()) == symbols_scanned
      Already asserted at record time, but the audit re-checks
      historical snapshots to catch a regression that bypassed record().
  (b) `failed=True` cycles must carry an exception_class.

Drift detectors (FAILURES — relative, not absolute thresholds):
  - plans_emitted collapsed > 50% vs prior-5 median
  - wall_ms > 2× prior-5 median (latency regression)
  - failed_cycles_total ratio over the window > 30% (5-of-15+)

Drift observations (NOTES — informational, not failures):
  - bottleneck_stage changed in last cycle vs prior-5 mode
    (drives "switch mode" or "tune threshold" suggestions in the UI)
  - Total wall_ms > 180s with zero plans
    ("scan stalled or universe is unscoreable")

Per-mode filtering:
  Different modes have different baselines (overwatch's wall_ms is
  naturally longer than surgical's, plans_emitted distributions
  differ). The audit accepts a `mode` filter and computes drift
  detectors against same-mode history only.

Usage (in-process):
    from backend.diagnostics.cycle_heartbeat_audit import audit_cycles
    print(audit_cycles())                 # all modes, full window
    print(audit_cycles(mode="stealth"))   # filter to stealth only

Usage (CLI):
    python -m backend.diagnostics.cycle_heartbeat_audit
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CycleRow:
    """Compact per-cycle row in the trend table."""

    ts_start: float
    run_id: str
    mode: Optional[str]
    wall_ms: Optional[int]
    symbols_scanned: int
    plans_emitted: int
    bottleneck_stage: Optional[str]
    failed: bool
    signals_per_stage: Dict[str, int] = field(default_factory=dict)


@dataclass
class CycleAuditReport:
    has_history: bool
    history_size: int
    mode_filter: Optional[str]
    failed_cycles: int
    healthy_cycles: int
    rows: List[CycleRow] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.failures

    def __str__(self) -> str:
        if not self.has_history:
            return (
                "=== Cycle Heartbeat Audit ===\n"
                "No cycles recorded yet. Either the orchestrator hasn't run "
                "scan_with_heartbeat() since process start, or the buffer "
                "was cleared."
            )
        status = "HEALTHY" if self.healthy else "DEGRADED"
        lines = [
            f"=== Cycle Heartbeat Audit — {status} ===",
            f"mode filter        : {self.mode_filter or '(all)'}",
            f"history size       : {self.history_size}",
            f"healthy cycles     : {self.healthy_cycles}",
            f"failed cycles      : {self.failed_cycles}",
        ]
        if self.rows:
            lines.append("")
            lines.append(f"--- Cycle trend (last {len(self.rows)}, oldest-first) ---")
            lines.append(
                f"  {'ts':>10}  {'run_id':<10} {'mode':<10} {'wall':>6} "
                f"{'scan':>5} {'emit':>5}  {'bottleneck':<18} stages"
            )
            for r in self.rows:
                tag = "✗" if r.failed else " "
                wall = f"{r.wall_ms}ms" if r.wall_ms is not None else "?"
                # Compact per-row stage summary
                stages_compact = ", ".join(
                    f"{k}={v}" for k, v in sorted(
                        r.signals_per_stage.items(), key=lambda kv: -kv[1]
                    )[:4]
                )
                lines.append(
                    f"{tag} {r.ts_start:>10.0f}  {r.run_id:<10} "
                    f"{(r.mode or '?'):<10} {wall:>6} "
                    f"{r.symbols_scanned:>5} {r.plans_emitted:>5}  "
                    f"{(r.bottleneck_stage or '-'):<18} {stages_compact}"
                )
        if self.failures:
            lines.append("")
            lines.append("--- Failures ---")
            for f in self.failures:
                lines.append(f"  {f}")
        if self.notes:
            lines.append("")
            for n in self.notes:
                lines.append(f"NOTE: {n}")
        return "\n".join(lines)


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return float(s[len(s) // 2])


def audit_cycles(
    snapshots: Optional[List[Dict[str, Any]]] = None,
    *,
    mode: Optional[str] = None,
) -> CycleAuditReport:
    """
    Audit recent cycle heartbeats for drift and invariant breaches.

    `snapshots` is injectable for tests. By default, pulls from the
    live ring buffer via cycle_heartbeat.recent() (or filter_by_mode
    when `mode` is set).
    """
    from backend.engine import cycle_heartbeat as hb

    if snapshots is None:
        snapshots = hb.filter_by_mode(mode) if mode else hb.recent()

    if not snapshots:
        return CycleAuditReport(
            has_history=False,
            history_size=0,
            mode_filter=mode,
            failed_cycles=0,
            healthy_cycles=0,
        )

    failures: List[str] = []
    notes: List[str] = []
    rows: List[CycleRow] = []
    failed_total = 0

    for snap in snapshots:
        is_failed = bool(snap.get("failed"))
        if is_failed:
            failed_total += 1
        rows.append(CycleRow(
            ts_start=float(snap.get("ts_start") or 0.0),
            run_id=str(snap.get("run_id") or "?"),
            mode=snap.get("mode"),
            wall_ms=snap.get("wall_ms"),
            symbols_scanned=int(snap.get("symbols_scanned") or 0),
            plans_emitted=int(snap.get("plans_emitted") or 0),
            bottleneck_stage=snap.get("bottleneck_stage"),
            failed=is_failed,
            signals_per_stage=dict(snap.get("signals_per_stage") or {}),
        ))

    # Invariant (a): mass conservation re-check.
    for r in rows:
        if r.failed:
            continue  # partial counts allowed for failed cycles
        per_stage_sum = sum(r.signals_per_stage.values())
        if r.plans_emitted + per_stage_sum != r.symbols_scanned:
            failures.append(
                f"mass conservation breach in run_id={r.run_id}: "
                f"plans_emitted={r.plans_emitted} + per_stage={per_stage_sum} "
                f"!= symbols_scanned={r.symbols_scanned}"
            )

    # Invariant (b): failed cycles must carry an exception_class.
    for snap in snapshots:
        if snap.get("failed") and not snap.get("exception_class"):
            failures.append(
                f"failed cycle missing exception_class: run_id={snap.get('run_id')}"
            )

    # Drift detectors operate on healthy cycles only — failed cycles
    # would skew baselines.
    healthy_rows = [r for r in rows if not r.failed]

    if len(healthy_rows) >= 6:
        # plans_emitted collapse: latest vs prior-5 median, > 50% drop
        latest = healthy_rows[-1]
        prior5 = healthy_rows[-6:-1]
        median_emit = _median([float(p.plans_emitted) for p in prior5])
        if median_emit > 0 and latest.plans_emitted < median_emit * 0.5:
            failures.append(
                f"plans_emitted collapsed: latest={latest.plans_emitted} "
                f"vs prior-5 median={median_emit:.0f}. Scoring or planner regression."
            )

        # wall_ms latency regression: latest vs prior-5 median, > 2× spike
        prior5_walls = [float(p.wall_ms) for p in prior5 if p.wall_ms is not None]
        if latest.wall_ms is not None and prior5_walls:
            median_wall = _median(prior5_walls)
            if median_wall > 0 and latest.wall_ms > median_wall * 2.0:
                failures.append(
                    f"wall_ms doubled: latest={latest.wall_ms}ms vs prior-5 "
                    f"median={median_wall:.0f}ms. Latency regression."
                )

        # bottleneck mode-change: NOTE only (informational)
        prior5_bottlenecks = [p.bottleneck_stage for p in prior5 if p.bottleneck_stage]
        if prior5_bottlenecks and latest.bottleneck_stage:
            mode_count = Counter(prior5_bottlenecks)
            prior_mode = mode_count.most_common(1)[0][0]
            if latest.bottleneck_stage != prior_mode:
                notes.append(
                    f"bottleneck shifted: prior-5 mode '{prior_mode}' → "
                    f"latest '{latest.bottleneck_stage}'. Tune the new gate "
                    f"or switch scanner mode."
                )

    # Failure-rate over the window
    if len(rows) >= 15:
        recent_window = rows[-15:]
        recent_failed = sum(1 for r in recent_window if r.failed)
        if recent_failed / 15.0 > 0.30:
            failures.append(
                f"failure ratio {recent_failed}/15 = {100.0 * recent_failed / 15.0:.0f}% "
                f"in last 15 cycles. Scanner is unstable."
            )

    # NOTE: stalled scan
    if rows:
        latest = rows[-1]
        if (latest.wall_ms or 0) > 180_000 and latest.plans_emitted == 0:
            notes.append(
                f"scan stalled — run_id={latest.run_id} took "
                f"{latest.wall_ms}ms with zero plans. Universe may be unscoreable."
            )

    return CycleAuditReport(
        has_history=True,
        history_size=len(rows),
        mode_filter=mode,
        failed_cycles=failed_total,
        healthy_cycles=len(rows) - failed_total,
        rows=rows,
        failures=failures,
        notes=notes,
    )


def _cli() -> int:  # pragma: no cover
    print(audit_cycles())
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(_cli())
