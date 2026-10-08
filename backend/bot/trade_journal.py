"""
Trade Journal

Persistent cross-session trade history stored as newline-delimited JSON.
Survives bot restarts and accumulates across all sessions so the UI can
show a running tally and the ML layer can train on real outcomes.
"""

import json
import csv
import io
import logging
import threading
import os
import tempfile
from contextlib import contextmanager

from .exit_classification import enrich
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_JOURNAL_PATH = Path(__file__).parent.parent / "cache" / "trade_journal.jsonl"


class TradeJournalService:
    """
    Append-only JSONL trade journal shared across all paper trading sessions.

    Thread-safe: a single file-level lock serialises all writes.
    Reads scan the full file each time — acceptable until we have tens of
    thousands of trades, at which point a SQLite migration is trivial.
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = (Path(path) if path else _JOURNAL_PATH).resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.info("Trade journal: %s", self._path)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, trade_dict: Dict[str, Any], session_id: str) -> None:
        """Persist a completed trade.  trade_dict is the output of CompletedTrade.to_dict().

        Every row is classified on the way in (see `exit_classification`), so
        `outcome` — the field every win rate should read — is arithmetic on the
        P&L rather than a restatement of whatever `exit_reason` claims. Before
        2026-05-20, 306 of 460 `target` rows carried a negative P&L. That source
        defect is fixed; a journal that can only be trusted while every writer
        behaves is still not a record, it is an assumption.

        A contradictory row is written and FLAGGED, never dropped. The trade
        happened; discarding it would swap an overstated win rate for a missing
        trade, which is the worse of the two lies.
        """
        record = self._classified(trade_dict, session_id)
        with self._write_guard():
            original, _ = self._read_for_write()
            self._publish_record(original, record)

    def upsert(self, trade_dict: Dict[str, Any], session_id: str) -> bool:
        """
        Append the trade only if no existing row shares the same trade_id.

        Returns True after durable publication, False for an identical retry.
        Reusing an identity with different data raises instead of hiding a conflict.
        """
        trade_id = trade_dict.get("trade_id")
        if not trade_id:
            # No id → fall back to plain append; better to risk a duplicate than drop.
            self.append(trade_dict, session_id)
            return True
        record = self._classified(trade_dict, session_id)
        # Compare the same JSON representation that readers receive.
        canonical = json.loads(json.dumps(record, default=str, allow_nan=False))
        with self._write_guard():
            original, records = self._read_for_write()
            matches = [r for r in records if r.get('trade_id') == trade_id]
            if matches:
                if any(r != canonical for r in matches):
                    raise ValueError(f'TRADE_ID_CONFLICT: {trade_id}')
                # A preceding call may have replaced the file but failed while
                # confirming durability. Retry that confirmation before success.
                with self._path.open('r+b') as handle:
                    os.fsync(handle.fileno())
                self._sync_directory()
                return False
            self._publish_record(original, canonical)
            return True

    @contextmanager
    def _write_guard(self):
        """Serialize all cooperating writers; unavailable ownership is retryable."""
        with self._lock:
            with self._path.with_suffix(self._path.suffix + '.lock').open('a+b') as handle:
                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b'\0')
                    handle.flush()
                handle.seek(0)
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    raise OSError('TRADE_JOURNAL_WRITER_BUSY') from exc
                yield

    def _read_for_write(self):
        """Never append into a torn row or silently discard damaged evidence."""
        original = self._path.read_bytes() if self._path.exists() else b''
        records = []
        def invalid_constant(value):
            raise ValueError(f'Non-finite JSON constant: {value}')
        try:
            for line in original.decode('utf-8').splitlines():
                if not line.strip():
                    continue
                record = json.loads(line, parse_constant=invalid_constant)
                if not isinstance(record, dict):
                    raise ValueError('Trade row must be an object')
                records.append(record)
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f'TRADE_JOURNAL_CORRUPT: {exc}') from exc
        return original, records

    def _publish_record(self, original, record):
        """Publish old bytes plus one row atomically; no in-place history repair."""
        row = (json.dumps(record, default=str, allow_nan=False) + '\n').encode('utf-8')
        separator = b'\n' if original and not original.endswith(b'\n') else b''
        fd, name = tempfile.mkstemp(prefix='.' + self._path.name + '.', suffix='.tmp', dir=self._path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(original)
                handle.write(separator)
                handle.write(row)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
            self._sync_directory()
        finally:
            temporary.unlink(missing_ok=True)

    def _sync_directory(self):
        if os.name != 'nt':
            directory = os.open(self._path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

    def _classified(self, trade_dict: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Stamp the honest fields, and say so out loud when they disagree with
        the engine. Both write paths go through here — a second writer that
        skipped the classification is exactly how the original defect stayed
        invisible for a month."""
        record = enrich({**trade_dict, "session_id": session_id})
        if record.get("label_conflict"):
            logger.warning(
                "EXIT_LABEL_CONFLICT %s %s: %s (trade_id=%s session=%s)",
                record.get("symbol"), record.get("trade_type"),
                record.get("conflict_note"), record.get("trade_id"), session_id)
        return record

    def _existing_trade_ids_unlocked(self) -> set:
        """Return the set of trade_ids currently in the journal. Caller holds the lock."""
        ids: set = set()
        if not self._path.exists():
            return ids
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tid = rec.get("trade_id")
                if tid:
                    ids.add(tid)
        return ids

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(
        self,
        symbol: Optional[str] = None,
        trade_type: Optional[str] = None,
        exit_reason: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return trades matching the given filters, newest-first."""
        trades = self._load_all()

        if symbol:
            trades = [t for t in trades if t.get("symbol") == symbol]
        if trade_type:
            trades = [t for t in trades if t.get("trade_type") == trade_type]
        if exit_reason:
            trades = [t for t in trades if t.get("exit_reason") == exit_reason]
        if session_id:
            trades = [t for t in trades if t.get("session_id") == session_id]
        if start_date:
            trades = [t for t in trades if (t.get("exit_time") or t.get("entry_time") or "") >= start_date]
        if end_date:
            trades = [t for t in trades if (t.get("exit_time") or t.get("entry_time") or "") <= end_date]

        trades.sort(key=lambda t: t.get("exit_time") or t.get("entry_time") or "", reverse=True)
        return trades[offset : offset + limit]

    def aggregate(self) -> Dict[str, Any]:
        """Compute summary stats over the entire journal.

        Rows written before the classifier existed carry no `outcome`, so it is
        derived on read for those. Two numbers are surfaced that were not here
        before, and both exist because this journal was believed for a month
        while it was wrong:

          `scratches`      — trades whose P&L is inside the round-trip fee. They
                             were counted as wins whenever they closed a cent up,
                             which is most of how a 37% strategy showed 50%.
          `label_conflicts` — rows whose exit_reason contradicts their money. A
                             non-zero count here means a stretch of this history
                             cannot be trusted, and the operator should be told
                             rather than shown an average over it.
        """
        trades = [t if "outcome" in t else enrich(t) for t in self._load_all()]
        if not trades:
            return self._empty_aggregate()

        total = len(trades)
        wins = [t for t in trades if t.get("outcome") == "WIN"]
        losses = [t for t in trades if t.get("outcome") == "LOSS"]
        scratches = [t for t in trades if t.get("outcome") == "SCRATCH"]
        conflicts = [t for t in trades if t.get("label_conflict")]
        pnls = [t.get("pnl", 0) for t in trades]
        win_pnls = [t.get("pnl", 0) for t in wins]
        loss_pnls = [t.get("pnl", 0) for t in losses]

        # Cumulative P&L series for chart (oldest-first)
        sorted_trades = sorted(
            trades,
            key=lambda t: t.get("exit_time") or t.get("entry_time") or "",
        )
        running = 0.0
        equity_curve = []
        for t in sorted_trades:
            running += t.get("pnl", 0)
            equity_curve.append(
                {
                    "time": t.get("exit_time") or t.get("entry_time"),
                    "value": round(running, 2),
                }
            )

        # Max drawdown
        peak = 0.0
        max_dd = 0.0
        for point in equity_curve:
            v = point["value"]
            if v > peak:
                peak = v
            dd = peak - v
            if dd > max_dd:
                max_dd = dd

        # Per-symbol breakdown
        by_symbol: Dict[str, Any] = {}
        for t in trades:
            sym = t.get("symbol", "?")
            b = by_symbol.setdefault(sym, {"trades": 0, "wins": 0, "pnl": 0.0})
            b["trades"] += 1
            if (t.get("pnl") or 0) > 0:
                b["wins"] += 1
            b["pnl"] = round(b["pnl"] + (t.get("pnl") or 0), 2)
        for sym, b in by_symbol.items():
            b["win_rate"] = round(b["wins"] / b["trades"] * 100, 1) if b["trades"] else 0

        # Per-type breakdown
        by_type: Dict[str, Any] = {}
        for t in trades:
            tt = t.get("trade_type", "unknown")
            b = by_type.setdefault(tt, {"trades": 0, "wins": 0, "pnl": 0.0})
            b["trades"] += 1
            if (t.get("pnl") or 0) > 0:
                b["wins"] += 1
            b["pnl"] = round(b["pnl"] + (t.get("pnl") or 0), 2)
        for tt, b in by_type.items():
            b["win_rate"] = round(b["wins"] / b["trades"] * 100, 1) if b["trades"] else 0

        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
        avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0

        return {
            "total_trades": total,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "scratches": len(scratches),
            "label_conflicts": len(conflicts),
            # Denominator excludes scratches: a trade that paid the fee and went
            # home is not a coin that landed. Reported as `decided_trades` so the
            # figure can never be read against the wrong base.
            "decided_trades": len(wins) + len(losses),
            "win_rate": round(len(wins) / (len(wins) + len(losses)) * 100, 1)
                        if (wins or losses) else 0,
            "total_pnl": round(sum(pnls), 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "avg_rr": round(abs(avg_win / avg_loss), 2) if avg_loss else 0,
            "best_trade": round(max(pnls), 2) if pnls else 0,
            "worst_trade": round(min(pnls), 2) if pnls else 0,
            "max_drawdown": round(max_dd, 2),
            "equity_curve": equity_curve,
            "by_symbol": by_symbol,
            "by_type": by_type,
        }

    def export_csv(self, **filters) -> str:
        """Return journal as a CSV string."""
        trades = self.query(**filters, limit=10_000)
        if not trades:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(trades[0].keys()))
        writer.writeheader()
        writer.writerows(trades)
        return output.getvalue()

    def count(self) -> int:
        return len(self._load_all())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        records = []
        with self._lock:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    @staticmethod
    def _empty_aggregate() -> Dict[str, Any]:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "scratches": 0,
            "label_conflicts": 0,
            "decided_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "avg_rr": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "max_drawdown": 0,
            "equity_curve": [],
            "by_symbol": {},
            "by_type": {},
        }


# Singleton
_journal_instance: Optional[TradeJournalService] = None


def get_trade_journal() -> TradeJournalService:
    global _journal_instance
    if _journal_instance is None:
        _journal_instance = TradeJournalService()
    return _journal_instance
