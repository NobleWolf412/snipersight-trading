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
        self._path = Path(path) if path else _JOURNAL_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.info("Trade journal: %s", self._path)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, trade_dict: Dict[str, Any], session_id: str) -> None:
        """Persist a completed trade.  trade_dict is the output of CompletedTrade.to_dict()."""
        record = {**trade_dict, "session_id": session_id}
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")

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
        """Compute summary stats over the entire journal."""
        trades = self._load_all()
        if not trades:
            return self._empty_aggregate()

        total = len(trades)
        wins = [t for t in trades if (t.get("pnl") or 0) > 0]
        losses = [t for t in trades if (t.get("pnl") or 0) <= 0]
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
            "win_rate": round(len(wins) / total * 100, 1) if total else 0,
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
