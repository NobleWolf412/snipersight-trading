"""
Persist the CALCULATED stop/target geometry on the trade journal (2026-06-02).

Before this change the journal stored stop_distance_atr + risk_reward_ratio but NOT
the actual SL/TP prices, so a closed trade's planned levels weren't auditable. These
tests pin:
  - PositionState snapshots the original stop + TP levels at open (initial_stop_loss /
    initial_target_levels), before any target is hit/stripped.
  - CompletedTrade.to_dict() (the journal record) carries the 5 new keys.
  - open_position captures stop_loss_rationale / tp1_clamped from the TradePlan
    (source-pin so the wiring can't be silently removed).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from backend.bot.executor.position_manager import PositionState
from backend.bot.paper_trading_service import CompletedTrade
from backend.shared.models.planner import Target


def test_positionstate_snapshots_original_levels():
    """initial_stop_loss + initial_target_levels are captured at open from the plan,
    independent of the live (mutable) stop_loss / targets that trail and strip."""
    ps = PositionState(
        position_id="t1", symbol="X/USDT", direction="LONG",
        entry_price=100.0, quantity=1.0, remaining_quantity=1.0,
        stop_loss=98.0,
        targets=[Target(level=103.0, rationale="tp1"), Target(level=106.0, rationale="tp2")],
    )
    assert ps.initial_stop_loss == 98.0, "original SL must be anchored at open"
    assert ps.initial_target_levels == [103.0, 106.0], "original TP ladder must be snapshotted at open"
    # New provenance fields exist with safe defaults.
    assert ps.stop_loss_rationale == ""
    assert ps.tp1_clamped is False
    assert ps.tp1_realized_rr == 0.0


def test_positionstate_target_snapshot_survives_target_mutation():
    """If the live targets list is later stripped/popped, initial_target_levels is unchanged
    — that's the whole point (the journal records the PLANNED ladder, not the survivors)."""
    ps = PositionState(
        position_id="t2", symbol="X/USDT", direction="SHORT",
        entry_price=100.0, quantity=1.0, remaining_quantity=1.0,
        stop_loss=102.0, targets=[Target(level=97.0, rationale="tp1")],
    )
    ps.targets.clear()  # simulate runtime strip / all targets hit
    assert ps.initial_target_levels == [97.0], "snapshot must survive live-targets mutation"


def test_positionstate_handles_no_targets():
    """Empty targets → empty snapshot, no crash (ATR-fallback / no-TP plans)."""
    ps = PositionState(
        position_id="t3", symbol="X/USDT", direction="LONG",
        entry_price=100.0, quantity=1.0, remaining_quantity=1.0,
        stop_loss=98.0, targets=[],
    )
    assert ps.initial_target_levels == []


def test_completed_trade_journal_carries_calc_levels():
    """The journal record (to_dict) must include the 5 calc-geometry keys with values."""
    now = datetime.now(timezone.utc)
    ct = CompletedTrade(
        trade_id="t4", symbol="X/USDT", direction="LONG",
        entry_price=100.0, exit_price=103.0, quantity=1.0,
        entry_time=now, exit_time=now, pnl=3.0, pnl_pct=3.0, exit_reason="target",
        stop_loss_level=98.0, target_levels=[103.0, 106.0],
        stop_loss_rationale="Stop below 15m entry structure invalidation point",
        tp1_clamped=True, tp1_realized_rr=1.3,
    )
    d = ct.to_dict()
    assert d["stop_loss_level"] == 98.0
    assert d["target_levels"] == [103.0, 106.0]
    assert d["stop_loss_rationale"] == "Stop below 15m entry structure invalidation point"
    assert d["tp1_clamped"] is True
    assert d["tp1_realized_rr"] == 1.3


def test_completed_trade_defaults_are_journal_safe():
    """Defaults serialize cleanly (older/ATR-fallback trades with no extra metadata)."""
    now = datetime.now(timezone.utc)
    ct = CompletedTrade(
        trade_id="t5", symbol="X/USDT", direction="SHORT",
        entry_price=100.0, exit_price=100.0, quantity=1.0,
        entry_time=now, exit_time=now, pnl=0.0, pnl_pct=0.0, exit_reason="session_stopped",
    )
    d = ct.to_dict()
    assert d["stop_loss_level"] == 0.0 and d["target_levels"] == []
    assert d["tp1_clamped"] is False and d["tp1_realized_rr"] == 0.0


def test_open_position_captures_provenance_source_pin():
    """Source-pin: open_position wires stop_loss_rationale + tp1_clamped + tp1_realized_rr
    from the TradePlan into the PositionState. Catches silent removal of the capture."""
    src = (
        Path(__file__).resolve().parents[2] / "bot" / "executor" / "position_manager.py"
    ).read_text(encoding="utf-8")
    assert 'stop_loss_rationale=str(getattr(trade_plan.stop_loss, "rationale"' in src, (
        "open_position must capture the stop rationale from the plan"
    )
    assert '.get("tp1_clamped"' in src and '.get("tp1_realized_rr"' in src, (
        "open_position must capture tp1_clamped / tp1_realized_rr from plan.metadata"
    )
    # And __post_init__ snapshots the original target ladder.
    assert "self.initial_target_levels = [float(t.level) for t in self.targets" in src
