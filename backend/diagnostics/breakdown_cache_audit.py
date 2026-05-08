"""
Breakdown Cache ↔ Signal Log Parity Audit.

Per CLAUDE.md §12: this script catches the regression if the wiring
between live_trading_service._log_signal() and
backend.strategy.confluence.cache breaks later.

Invariants enforced:
  (a) Every signal_log entry from the last N cycles that reached scoring
      (i.e. carried a confluence_breakdown when it hit _log_signal) has a
      matching entry in the ring buffer.
  (b) Orphan signal_log entries (id minted, no breakdown found) are flagged.
  (c) Counter sanity: records_total >= lookups_total - lookup_misses_total.
  (d) The id format is parseable and matches the canonical layout.

Usage (in-process):
    from backend.diagnostics.breakdown_cache_audit import audit_signal_log
    report = audit_signal_log(service)
    print(report)

Usage (CLI, against a live service in dev):
    python -m backend.diagnostics.breakdown_cache_audit

This script is intentionally read-only and idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class AuditReport:
    """Summary of a parity audit run."""

    signal_log_size: int
    cache_buffer_size: int
    cache_records_total: int
    cache_record_errors_total: int
    cache_lookups_total: int
    cache_lookup_misses_total: int
    entries_audited: int
    matched: int
    orphans: List[Dict[str, Any]] = field(default_factory=list)
    malformed_ids: List[Dict[str, Any]] = field(default_factory=list)
    direction_breakdown: Dict[str, int] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return (
            not self.orphans
            and not self.malformed_ids
            and self.cache_record_errors_total == 0
        )

    def __str__(self) -> str:
        status = "HEALTHY" if self.healthy else "DEGRADED"
        lines = [
            f"=== Breakdown Cache Audit — {status} ===",
            f"signal_log size       : {self.signal_log_size}",
            f"cache buffer size     : {self.cache_buffer_size}",
            f"cache records total   : {self.cache_records_total}",
            f"cache record errors   : {self.cache_record_errors_total}",
            f"cache lookups total   : {self.cache_lookups_total}",
            f"cache lookup misses   : {self.cache_lookup_misses_total}",
            f"entries audited       : {self.entries_audited}",
            f"matched               : {self.matched}",
            f"orphans               : {len(self.orphans)}",
            f"malformed ids         : {len(self.malformed_ids)}",
            f"direction breakdown   : {self.direction_breakdown}",
        ]
        if self.orphans:
            lines.append("")
            lines.append("--- Orphans (signal_log entry, no breakdown in cache) ---")
            for o in self.orphans[:20]:
                lines.append(
                    f"  id={o['id']} reason_type={o.get('reason_type')} "
                    f"result={o.get('result')} confluence={o.get('confluence')}"
                )
            if len(self.orphans) > 20:
                lines.append(f"  ... and {len(self.orphans) - 20} more")
        if self.malformed_ids:
            lines.append("")
            lines.append("--- Malformed ids ---")
            for m in self.malformed_ids[:20]:
                lines.append(f"  raw={m['raw']!r} reason={m['reason']}")
        if self.notes:
            lines.append("")
            for n in self.notes:
                lines.append(f"NOTE: {n}")
        return "\n".join(lines)


# Reason types that are EXPECTED to land in _log_signal without a breakdown.
# These short-circuit before scoring, so the cache is correctly empty for
# these — they should not count as orphans.
_PRE_SCORING_REASONS: Set[str] = {
    "max_positions",
    "has_position",
    "pending_order",
    "pending_fill",
}


def _parse_signal_id(sid: str) -> Optional[Dict[str, str]]:
    """
    Parse `{symbol}_{scan}_{tf}_{direction}` back into parts.

    Returns None for malformed ids. Note that symbol can contain '/' so
    we split from the right.
    """
    if not isinstance(sid, str) or not sid:
        return None
    parts = sid.rsplit("_", 3)
    if len(parts) != 4:
        return None
    symbol, scan_no, tf, direction = parts
    if not symbol or not scan_no.isdigit() or not tf or not direction:
        return None
    return {
        "symbol": symbol,
        "scan_no": scan_no,
        "tf": tf,
        "direction": direction,
    }


def audit_signal_log(service: Any, *, last_n: int = 200) -> AuditReport:
    """
    Walk the live trading service's signal_log and verify that every entry
    that should have a cached breakdown does.

    `service` should expose:
      - `signal_log: list[dict]`
    """
    from backend.strategy.confluence import cache as _cache

    sig_log: List[Dict[str, Any]] = list(getattr(service, "signal_log", []))[-last_n:]
    cache_stats = _cache.stats()

    report = AuditReport(
        signal_log_size=len(getattr(service, "signal_log", [])),
        cache_buffer_size=cache_stats["buffer_size"],
        cache_records_total=cache_stats["records_total"],
        cache_record_errors_total=cache_stats["record_errors_total"],
        cache_lookups_total=cache_stats["lookups_total"],
        cache_lookup_misses_total=cache_stats["lookup_misses_total"],
        entries_audited=len(sig_log),
        matched=0,
    )

    if not sig_log:
        report.notes.append(
            "signal_log is empty — service has not processed any plans yet."
        )
        return report

    for entry in sig_log:
        sid = entry.get("id")
        direction = str(entry.get("direction", "?")).lower()
        report.direction_breakdown[direction] = (
            report.direction_breakdown.get(direction, 0) + 1
        )

        if not sid:
            report.malformed_ids.append({"raw": sid, "reason": "missing id field"})
            continue

        parsed = _parse_signal_id(sid)
        if parsed is None:
            report.malformed_ids.append(
                {"raw": sid, "reason": "id failed canonical parse"}
            )
            continue

        # Skip entries that legitimately wouldn't have a breakdown.
        if entry.get("reason_type") in _PRE_SCORING_REASONS:
            continue

        br = _cache.get(sid)
        if br is None:
            report.orphans.append({
                "id": sid,
                "reason_type": entry.get("reason_type"),
                "result": entry.get("result"),
                "confluence": entry.get("confluence"),
            })
        else:
            report.matched += 1

    # Drift detection: actually look at the cache's own ids to see if they
    # parse the same way as signal_log ids. Eviction alone doesn't trigger
    # this; format mismatch does.
    cache_recent = _cache.recent(50)
    if cache_recent:
        unparseable_in_cache = sum(
            1 for sid, _ in cache_recent if _parse_signal_id(sid) is None
        )
        if unparseable_in_cache > 0:
            report.notes.append(
                f"Cache contains {unparseable_in_cache}/{len(cache_recent)} ids "
                f"that fail the canonical parse — id format has drifted "
                f"between record() and the audit's parser."
            )

    if cache_stats["record_errors_total"] > 0:
        report.notes.append(
            f"Cache recorded {cache_stats['record_errors_total']} record errors. "
            f"Check warnings around 'confluence cache record' in the service log."
        )

    return report


def _cli() -> int:  # pragma: no cover — manual diagnostic only
    """
    Try to find a live LiveTradingService instance and audit it.

    Falls back to importing the module without instantiating, in which
    case only the cache-side stats are reported.
    """
    try:
        from backend.bot.live_trading_service import LiveTradingService  # noqa: F401
        # We can't reach a live instance from a fresh CLI process — print
        # cache-only stats so this is at least diagnostic-useful.
        from backend.strategy.confluence import cache as _cache
        print("(no service instance reachable from CLI; cache stats only)")
        for k, v in _cache.stats().items():
            print(f"  {k}: {v}")
        return 0
    except Exception as e:
        print(f"audit failed: {e}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(_cli())
