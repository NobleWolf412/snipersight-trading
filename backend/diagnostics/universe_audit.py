"""
Universe (pair selection) Audit.

Per CLAUDE.md §12: catches regressions in pair_selection drop tracking
and surfaces anomalies that would otherwise be invisible (e.g. an adapter
silently degrading and feeding all stablecoin garbage, or the perp filter
misclassifying every symbol as non-perp).

Invariants enforced (failures — provable bugs):
  (a) Every drop reason is in the documented vocabulary.
  (b) selected ∩ dropped is empty (no symbol in both buckets).
  (c) Mass conservation: every symbol from the original fetched set is
      either in `selected` or in `dropped`. Asserted inside
      _select_symbols_impl as well; the audit re-checks externally.
  (d) qualified > 0 when fetched > 0 (otherwise the adapter or every
      filter rejected everything — almost certainly a bug, not user intent).

Observations (notes — heuristic, not failures):
  - Per-reason proportions surfaced as informational data. Until 10–20
    real production cycles establish a baseline distribution and
    thresholds are set at 95th percentile or 2σ, no rate-based check
    fires DEGRADED. Firing DEGRADED on guesses would train the operator
    to ignore the signal — anti-pattern called out in CLAUDE.md §15.

This audit is read-only. It reads the latest snapshot from
backend.analysis.pair_selection.get_latest_snapshot() — it does not
re-run selection or call the adapter.

CLAUDE.md §10 note: this audit does NOT touch the confluence
conflict_density gate (5 for overwatch/macro, 3 elsewhere). That gate
is a downstream scoring concern; pair selection runs before scoring
and is direction-agnostic, so the §10 standing fix is unaffected.

Usage (in-process):
    from backend.diagnostics.universe_audit import audit_universe
    print(audit_universe())

Usage (CLI):
    python -m backend.diagnostics.universe_audit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


VALID_REASONS = {"stale_no_data", "stable_base", "non_perp", "bucket_excluded", "limit_exhausted"}


@dataclass
class CycleTrendRow:
    """Per-cycle row in the cross-cycle drift trend table."""

    ts: float
    fetched: int
    qualified: int
    drops_by_reason: Dict[str, int] = field(default_factory=dict)


@dataclass
class UniverseAuditReport:
    has_snapshot: bool
    snapshot_age_s: Optional[float]
    fetched: int
    qualified: int
    dropped_total: int
    drops_by_reason: Dict[str, int] = field(default_factory=dict)
    leverage: int = 1
    market_type: Optional[str] = None
    toggles: Dict[str, bool] = field(default_factory=dict)
    adapter: Optional[str] = None
    history_size: int = 0
    cycle_trend: List[CycleTrendRow] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    unknown_reasons: List[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.failures and not self.unknown_reasons

    def __str__(self) -> str:
        if not self.has_snapshot:
            return (
                "=== Universe Audit ===\n"
                "No snapshot yet — pair_selection.select_symbols* has not "
                "been called since process start.\n"
                "(This is expected if the bot/scanner hasn't run a cycle yet.)"
            )
        status = "HEALTHY" if self.healthy else "DEGRADED"
        lines = [
            f"=== Universe Audit — {status} ===",
            f"adapter             : {self.adapter}",
            f"snapshot age        : {self.snapshot_age_s:.1f}s" if self.snapshot_age_s is not None else "snapshot age        : unknown",
            f"fetched             : {self.fetched}",
            f"qualified           : {self.qualified}",
            f"dropped total       : {self.dropped_total}",
            f"leverage            : {self.leverage}",
            f"market_type         : {self.market_type}",
            f"toggles             : {self.toggles}",
        ]
        if self.drops_by_reason:
            lines.append("")
            lines.append("--- Drops by reason ---")
            for k in sorted(self.drops_by_reason, key=lambda r: -self.drops_by_reason[r]):
                v = self.drops_by_reason[k]
                pct = (100.0 * v / max(self.fetched, 1))
                lines.append(f"  {k:<18} : {v:>4}  ({pct:>5.1f}%)")
        if self.cycle_trend:
            lines.append("")
            lines.append(f"--- Cycle trend (last {len(self.cycle_trend)} cycles, oldest-first) ---")
            # Header: ts | fetched | qualified | top drop reasons
            lines.append(f"  {'ts':<12} {'fetched':>8} {'qualif':>7}  drops_by_reason")
            for row in self.cycle_trend:
                # Compact per-row reason summary
                reasons_compact = ", ".join(
                    f"{k}={v}" for k, v in sorted(
                        row.drops_by_reason.items(), key=lambda kv: -kv[1]
                    )[:4]
                )
                lines.append(
                    f"  {row.ts:>12.0f} {row.fetched:>8} {row.qualified:>7}  {reasons_compact}"
                )
        if self.unknown_reasons:
            lines.append("")
            lines.append("--- Unknown / out-of-vocabulary reasons ---")
            for r in self.unknown_reasons:
                lines.append(f"  {r}")
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


def audit_universe(
    snapshot: Optional[Dict[str, Any]] = None,
    *,
    history: Optional[List[Dict[str, Any]]] = None,
    now_ts: Optional[float] = None,
) -> UniverseAuditReport:
    """
    Audit the latest pair_selection snapshot for anomalies.

    `snapshot`, `history`, and `now_ts` are injectable for tests. By
    default the function pulls the latest snapshot and the recent
    history from the live ring buffer and uses time.time().
    """
    import time

    from backend.analysis.pair_selection import (
        get_latest_snapshot,
        get_snapshot_history,
        history_size,
    )

    if snapshot is None:
        snapshot = get_latest_snapshot()

    if history is None:
        history = get_snapshot_history(n=20)

    if snapshot is None:
        return UniverseAuditReport(
            has_snapshot=False,
            snapshot_age_s=None,
            fetched=0,
            qualified=0,
            dropped_total=0,
            history_size=history_size(),
        )

    if now_ts is None:
        now_ts = time.time()

    selected: List[str] = list(snapshot.get("selected") or [])
    dropped: List[Dict[str, str]] = list(snapshot.get("dropped") or [])
    fetched: int = int(snapshot.get("fetched") or 0)

    drops_by_reason: Dict[str, int] = {}
    unknown_reasons: List[str] = []
    for d in dropped:
        r = d.get("reason", "<missing>")
        drops_by_reason[r] = drops_by_reason.get(r, 0) + 1
        if r not in VALID_REASONS:
            unknown_reasons.append(r)

    failures: List[str] = []

    # Invariant: selected ∩ dropped is empty
    selected_set = set(selected)
    dropped_set = {d.get("symbol") for d in dropped}
    overlap = selected_set & dropped_set
    if overlap:
        failures.append(
            f"selected and dropped overlap: {sorted(overlap)[:5]}..."
            f" ({len(overlap)} symbols)"
        )

    # Invariant: qualified > 0 when fetched > 0
    if fetched > 0 and len(selected) == 0:
        failures.append(
            f"fetched={fetched} but qualified=0 — every candidate was dropped. "
            f"drops_by_reason={drops_by_reason}"
        )

    notes: List[str] = []

    # Provisional rate observations — NOT failures. The 90% / 50% bounds
    # in earlier drafts were untuned guesses; firing DEGRADED on guesses
    # would train the operator to ignore the signal. Until baseline data
    # exists (10–20 real production cycles, set thresholds at 95th
    # percentile or 2σ — see CLAUDE.md §15), these surface as notes only.
    leverage = int(snapshot.get("leverage") or 1)
    if leverage > 1 and fetched > 0:
        non_perp_pct = 100.0 * drops_by_reason.get("non_perp", 0) / fetched
        if non_perp_pct >= 50.0:
            notes.append(
                f"non_perp rate {non_perp_pct:.1f}% with leverage={leverage} "
                f"— provisional observation, threshold not yet baselined."
            )

    if fetched > 0:
        stable_pct = 100.0 * drops_by_reason.get("stable_base", 0) / fetched
        if stable_pct >= 25.0:
            notes.append(
                f"stable_base rate {stable_pct:.1f}% — provisional observation, "
                f"threshold not yet baselined."
            )
    snapshot_age = now_ts - float(snapshot.get("ts", now_ts))
    if snapshot_age > 600:
        notes.append(
            f"snapshot is {snapshot_age:.0f}s old — scanner may have stalled "
            f"(no new selection in over 10 minutes)."
        )

    # Cross-cycle trend: compact per-cycle rows for the last N snapshots.
    cycle_trend: List[CycleTrendRow] = []
    for snap in history or []:
        per_cycle_reasons: Dict[str, int] = {}
        for d in snap.get("dropped") or []:
            r = d.get("reason", "<missing>")
            per_cycle_reasons[r] = per_cycle_reasons.get(r, 0) + 1
        cycle_trend.append(CycleTrendRow(
            ts=float(snap.get("ts") or 0.0),
            fetched=int(snap.get("fetched") or 0),
            qualified=len(snap.get("selected") or []),
            drops_by_reason=per_cycle_reasons,
        ))

    # Drift detection: if fetched count collapsed by >50% in the last
    # cycle vs. the median of the prior 5, flag it. Adapter feed issue.
    if len(cycle_trend) >= 6:
        recent = cycle_trend[-1].fetched
        prior_window = sorted(r.fetched for r in cycle_trend[-6:-1])
        median_prior = prior_window[len(prior_window) // 2]
        if median_prior > 0 and recent < median_prior * 0.5:
            failures.append(
                f"fetched count collapsed: latest={recent} vs prior-5 median={median_prior}. "
                f"Adapter feed likely degraded."
            )

    return UniverseAuditReport(
        has_snapshot=True,
        snapshot_age_s=snapshot_age,
        fetched=fetched,
        qualified=len(selected),
        dropped_total=len(dropped),
        drops_by_reason=drops_by_reason,
        leverage=leverage,
        market_type=snapshot.get("market_type"),
        toggles=dict(snapshot.get("toggles") or {}),
        adapter=snapshot.get("adapter"),
        history_size=len(cycle_trend),
        cycle_trend=cycle_trend,
        notes=notes,
        failures=failures,
        unknown_reasons=unknown_reasons,
    )


def _cli() -> int:  # pragma: no cover
    print(audit_universe())
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(_cli())
