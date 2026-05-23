"""
Tests for the executor-side `_check_target_hit` structural-validity guard's
telemetry emission and the `PositionState.targets_stripped_count` counter.

Bug-class context — see `test_target_structural_validity.py` for the full
fill-drift story (May 2026 INJ session #fcfeffd6 — 45/67 instant-target
losses). That test file covers BEHAVIOR (strip happens, position stays open,
warning fires); this file covers OBSERVABILITY (structured telemetry event,
lifetime stripped-count counter, journal-row diagnostic field).

Trade-autopsy currently cannot distinguish "stagnation because the market
didn't move" from "stagnation because all targets were stripped at runtime
and no TP exit was reachable." These telemetry + diagnostic-counter
additions close that gap.

Per CLAUDE.md §11 (silent-bug surfacing), §14 rubric 4 (negative pair),
§16 rubric 12 (bull/bear symmetry).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List
from unittest.mock import patch, MagicMock

import pytest

from backend.bot.executor.position_manager import (
    PositionManager,
    PositionState,
    PositionStatus,
)
from backend.shared.models.planner import Target


def _dummy_price_fetcher(symbol: str) -> float:
    return 100.0


@pytest.fixture
def manager() -> PositionManager:
    return PositionManager(
        price_fetcher=_dummy_price_fetcher,
        order_executor=lambda *a, **kw: None,
    )


def _make_target(level: float, percentage: float = 50.0, label: str = "TP") -> Target:
    return Target(
        level=level,
        rationale="test target",
        percentage=percentage,
        label=label,
        rr_ratio=1.5,
        weight=1.0,
    )


def _make_position(
    direction: str,
    entry_price: float,
    target_levels: List[float],
) -> PositionState:
    return PositionState(
        position_id="test-position",
        symbol="TEST/USDT",
        direction=direction,
        entry_price=entry_price,
        quantity=100.0,
        remaining_quantity=100.0,
        stop_loss=entry_price * 0.99 if direction == "LONG" else entry_price * 1.01,
        targets=[_make_target(lvl) for lvl in target_levels],
        created_at=datetime.now(timezone.utc) - timedelta(hours=24),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Telemetry — positive LONG: event fires with correct payload
# ──────────────────────────────────────────────────────────────────────────────


def test_strip_emits_executor_telemetry_long(manager):
    """LONG with one wrong-side target (below entry): structured telemetry
    event fires with kind=executor_target_strip, direction=LONG, accurate
    entry_price, stripped_count, total_before, remaining_after, and the
    stripped target's level."""
    pos = _make_position("LONG", entry_price=5.113, target_levels=[5.027, 5.250])
    mock_logger = MagicMock()
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=mock_logger,
    ):
        manager._check_targets_hit(pos, current_price=5.020)

    # Behavior unchanged: invalid stripped, valid retained
    assert len(pos.targets) == 1
    assert pos.targets[0].level == 5.250
    assert pos.targets_stripped_count == 1

    # Telemetry: exactly one event, with the right shape
    assert mock_logger.log_event.called
    event = mock_logger.log_event.call_args[0][0]
    assert event.event_type.value == "warning_issued"
    assert event.symbol == "TEST/USDT"
    assert event.data["kind"] == "executor_target_strip"
    assert event.data["direction"] == "LONG"
    assert event.data["entry_price"] == 5.113
    assert event.data["stripped_count"] == 1
    assert event.data["total_before"] == 2
    assert event.data["remaining_after"] == 1
    assert 5.027 in event.data["stripped_levels"]


# ──────────────────────────────────────────────────────────────────────────────
# Telemetry — SHORT mirror (§16 rubric 12 bull/bear pair)
# ──────────────────────────────────────────────────────────────────────────────


def test_strip_emits_executor_telemetry_short(manager):
    """SHORT mirror: target above entry is the wrong side and must trigger
    the same telemetry event with direction=SHORT."""
    pos = _make_position("SHORT", entry_price=4.986, target_levels=[5.027, 4.800])
    mock_logger = MagicMock()
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=mock_logger,
    ):
        manager._check_targets_hit(pos, current_price=5.030)

    assert len(pos.targets) == 1
    assert pos.targets[0].level == 4.800
    assert pos.targets_stripped_count == 1

    assert mock_logger.log_event.called
    event = mock_logger.log_event.call_args[0][0]
    assert event.event_type.value == "warning_issued"
    assert event.data["kind"] == "executor_target_strip"
    assert event.data["direction"] == "SHORT"
    assert event.data["entry_price"] == 4.986
    assert event.data["stripped_count"] == 1
    assert event.data["total_before"] == 2
    assert event.data["remaining_after"] == 1
    assert 5.027 in event.data["stripped_levels"]


# ──────────────────────────────────────────────────────────────────────────────
# Telemetry — negative: no event when all targets are valid
# ──────────────────────────────────────────────────────────────────────────────


def test_strip_no_telemetry_when_all_targets_valid_long(manager):
    """Negative pair — when no targets need stripping, telemetry must NOT
    fire. Without this, the strip event becomes blanket-spammy on every
    polling tick."""
    pos = _make_position("LONG", entry_price=100.0, target_levels=[103.0, 105.0])
    mock_logger = MagicMock()
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=mock_logger,
    ):
        manager._check_targets_hit(pos, current_price=101.0)

    assert len(pos.targets) == 2
    assert pos.targets_stripped_count == 0
    assert not mock_logger.log_event.called


def test_strip_no_telemetry_when_all_targets_valid_short(manager):
    """SHORT mirror of the negative pair."""
    pos = _make_position("SHORT", entry_price=100.0, target_levels=[97.0, 95.0])
    mock_logger = MagicMock()
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=mock_logger,
    ):
        manager._check_targets_hit(pos, current_price=99.0)

    assert len(pos.targets) == 2
    assert pos.targets_stripped_count == 0
    assert not mock_logger.log_event.called


# ──────────────────────────────────────────────────────────────────────────────
# Lifetime counter — accumulates across multiple strip events
# ──────────────────────────────────────────────────────────────────────────────


def test_targets_stripped_count_accumulates_across_multiple_invocations(manager):
    """The counter is lifetime-cumulative. If a second batch of invalid
    targets ever lands on a position (e.g. dynamic stop / breakeven push),
    the count should keep growing. Mass-conservation invariant: counter ==
    total targets removed during the position's lifetime."""
    pos = _make_position("LONG", entry_price=100.0, target_levels=[97.0, 95.0, 103.0])
    # First strip: 2 invalid (97, 95)
    manager._check_targets_hit(pos, current_price=98.0)
    assert pos.targets_stripped_count == 2
    assert len(pos.targets) == 1

    # Simulate a stale invalid target being re-attached (real-world cause:
    # never happens in current code, but this exercises the counter's
    # cumulative property without depending on actual code paths).
    pos.targets.append(_make_target(99.0))
    manager._check_targets_hit(pos, current_price=98.5)
    assert pos.targets_stripped_count == 3  # 2 from first call + 1 from second
    assert len(pos.targets) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Idempotency — second call on cleaned position emits no telemetry
# ──────────────────────────────────────────────────────────────────────────────


def test_second_call_after_strip_is_silent(manager):
    """Once invalid targets are removed, subsequent _check_targets_hit
    calls should NOT re-emit telemetry. Critical because the executor
    polls this function continuously."""
    pos = _make_position("LONG", entry_price=5.113, target_levels=[5.027, 5.250])
    mock_logger = MagicMock()
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=mock_logger,
    ):
        # First call — emits
        manager._check_targets_hit(pos, current_price=5.020)
        first_call_count = mock_logger.log_event.call_count
        assert first_call_count == 1

        # Second call — must NOT re-emit
        manager._check_targets_hit(pos, current_price=5.021)
        assert mock_logger.log_event.call_count == first_call_count
