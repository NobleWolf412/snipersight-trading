"""Honest outcome fields for a settled trade.

WHY THIS EXISTS

`exit_reason` is the engine's account of how a trade ended, and for 306 of 460
trades before 2026-05-20 it was wrong in the one direction that flatters:
`target` recorded against a negative P&L. The cause was entry-zone drift putting
a "target" on the unfavourable side of the actual fill, so it registered as hit
the instant the position opened. That specific defect was fixed at the source
(`position_manager._check_targets_hit`, commit 9a9a7c9, 2026-05-20) and the
journal has been clean since — zero bad target exits in the 82 recorded after.

The fix below is not that fix. It closes the *class* of failure rather than the
instance:

  1. A win is decided by MONEY, never by a label. `outcome` is computed from
     `pnl` and cannot disagree with the account, whatever any engine claims. The
     guard fixed one call site; six other paths write `exit_reason` and no future
     one is obliged to be honest.

  2. The disagreement is RECORDED, not suppressed. `label_conflict` marks a row
     whose engine reason contradicts its money, so a corrupted stretch of history
     is findable instead of silently averaged into a win rate.

  3. A trade is never dropped for being mislabelled. It happened; refusing to
     write it would trade one kind of lie for a worse one. The record is written
     and flagged.

WHAT A "SCRATCH" IS

A trade whose absolute P&L is inside the round-trip cost of opening and closing
it did not win or lose — it paid the venue and went home. Counting those as wins
is how a 37% strategy shows a 50% win rate. They get their own bucket rather
than being forced to a side.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Round-trip cost as a fraction of notional. 0.1% per side, taken twice. A P&L
# inside this band is noise against the fees, not a result.
DEFAULT_FEE_RATE = 0.001
SCRATCH_BAND = DEFAULT_FEE_RATE * 2

#: Engine reason -> the family it belongs to. The raw string is always kept;
#: this is for grouping, so "why did trades end" is answerable without a
#: `set()` over free text that grows a new spelling every release.
EXIT_PATHS: Dict[str, str] = {
    "target": "TARGET",
    "stop_loss": "STOP",
    "trailing_stop": "TRAIL",
    "trail_stop": "TRAIL",
    "breakeven_stop": "BREAKEVEN",
    "stagnation": "STAGNATION",
    "partial_stagnation": "STAGNATION",
    "max_hours_open": "TIMEOUT",
    "direction_flip": "FLIP",
    "session_stopped": "OPERATOR",
    "manual_close": "OPERATOR",
    "emergency": "EMERGENCY",
    "orphan_price_feed_failure": "FAULT",
}

#: A family is expected to end on this side of zero. Only families with a real
#: expectation appear — a stagnation or an operator close can honestly land
#: either way, and asserting otherwise would manufacture false conflicts.
EXPECTED_SIGN: Dict[str, str] = {
    "TARGET": "WIN",
    "STOP": "LOSS",
}


def _f(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def notional_of(record: Dict[str, Any]) -> Optional[float]:
    qty, entry = _f(record.get("quantity")), _f(record.get("entry_price"))
    if qty is None or entry is None:
        return None
    return abs(qty * entry)


def realized_r(record: Dict[str, Any]) -> Optional[float]:
    """P&L as a multiple of the risk actually taken at entry.

    Reconstructed from `stop_distance_atr` only when the ATR is recoverable from
    the row itself. Returns None rather than guessing — an R value derived from
    an assumed ATR is worse than no R value, because it looks like a measurement.
    """
    pnl = _f(record.get("pnl"))
    qty = _f(record.get("quantity"))
    entry = _f(record.get("entry_price"))
    stop = _f(record.get("stop_price")) or _f(record.get("stop_loss"))
    if None in (pnl, qty, entry) or stop is None or qty == 0:
        return None
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return None
    risk_total = risk_per_unit * abs(qty)
    if risk_total <= 0:
        return None
    return pnl / risk_total


def classify(record: Dict[str, Any], fee_rate: float = DEFAULT_FEE_RATE) -> Dict[str, Any]:
    """Derive the honest fields. Never mutates `record`.

    Returns a dict to merge onto the row:
      exit_path      — normalised family of `exit_reason` (str)
      outcome        — WIN / LOSS / SCRATCH / UNKNOWN, decided by money
      realized_r     — P&L in units of risk taken, or None if not reconstructable
      label_conflict — True when the engine's reason contradicts the money
      conflict_note  — human sentence naming the contradiction, else None
    """
    reason = (record.get("exit_reason") or "").strip().lower()
    path = EXIT_PATHS.get(reason, "UNKNOWN" if reason else "MISSING")

    pnl = _f(record.get("pnl"))
    if pnl is None:
        return {"exit_path": path, "outcome": "UNKNOWN", "realized_r": None,
                "label_conflict": False, "conflict_note": None}

    notional = notional_of(record)
    band = (notional * fee_rate * 2) if notional else 0.0
    if abs(pnl) <= band:
        outcome = "SCRATCH"
    elif pnl > 0:
        outcome = "WIN"
    else:
        outcome = "LOSS"

    expected = EXPECTED_SIGN.get(path)
    conflict, note = False, None
    if expected and outcome != expected:
        # A trailed stop closing green is not a conflict — it is the trail doing
        # its job — but it arrives labelled TRAIL, not STOP, so it never lands here.
        #
        # SCRATCH COUNTS AS A CONFLICT HERE, and that is the whole point. The 306
        # bad rows were not large losses wearing a win's label; they were moves of
        # about zero — the XRP case is entry 1.4369215, exit 1.4366, −$0.77 on a
        # $2,292 position. A "target" means price travelled to a level chosen in
        # advance; if it travelled less than the cost of trading, the target was
        # at or behind the fill and the label is describing something that did not
        # happen. A detector that waved those through would miss every instance of
        # the defect it exists to catch.
        conflict = True
        if outcome == "SCRATCH":
            note = (f"exit_reason={reason!r} implies {expected.lower()} but the trade "
                    f"moved less than its own round-trip cost ({pnl:+.4f}) — the "
                    f"bracket was at or behind the fill")
        else:
            note = (f"exit_reason={reason!r} implies {expected.lower()} but the trade "
                    f"{'made' if pnl > 0 else 'lost'} {abs(pnl):.4f}")

    return {"exit_path": path, "outcome": outcome,
            "realized_r": realized_r(record),
            "label_conflict": conflict, "conflict_note": note}


def enrich(record: Dict[str, Any], fee_rate: float = DEFAULT_FEE_RATE) -> Dict[str, Any]:
    """`record` plus its honest fields. The original keys are left untouched —
    `exit_reason` stays exactly as the engine wrote it, because provenance is
    what makes a later forensic possible."""
    return {**record, **classify(record, fee_rate)}
