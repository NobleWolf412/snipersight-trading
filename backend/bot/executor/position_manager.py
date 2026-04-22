"""
Position Manager Module

Real-time position monitoring and management for live trading.
Handles stop loss, take profit, breakeven, and trailing stop logic.

This is the critical missing component for production trading - it continuously
monitors open positions and executes risk management actions in real-time.

Features:
- Real-time SL/TP monitoring
- Breakeven stop logic (move SL to entry after first target)
- Trailing stop implementation
- Position state tracking
- Emergency exit handling
- Market data integration for accurate price checks
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import asyncio
import logging
from threading import Lock

from backend.shared.models.planner import TradePlan, Target
from backend.strategy.smc.sessions import get_current_kill_zone

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Position lifecycle states."""

    PENDING = "PENDING"  # Order placed but not filled
    OPEN = "OPEN"  # Position active
    PARTIAL = "PARTIAL"  # Some targets hit
    CLOSED = "CLOSED"  # All targets hit or stopped out
    STOPPED_OUT = "STOPPED_OUT"  # Hit stop loss
    EMERGENCY_EXIT = "EMERGENCY_EXIT"  # Emergency closure


@dataclass
class PositionState:
    """
    Real-time position state tracking.

    Tracks position lifecycle from entry through partial exits to final closure.

    Attributes:
        position_id: Unique position identifier
        symbol: Trading pair
        direction: LONG or SHORT
        entry_price: Actual fill price
        quantity: Initial position size
        remaining_quantity: Current position size (reduced as targets hit)
        stop_loss: Current stop loss level (can trail)
        targets: List of remaining targets
        targets_hit: List of targets already hit
        status: Current position status
        unrealized_pnl: Current P&L
        realized_pnl: P&L from partial exits
        created_at: Position entry timestamp
        updated_at: Last update timestamp
        breakeven_active: Whether stop has moved to breakeven
        trailing_active: Whether trailing stop is active
        highest_price: Highest price seen (for trailing longs)
        lowest_price: Lowest price seen (for trailing shorts)
        entry_order_id: The order ID that opened this position (optional)
    """

    position_id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    quantity: float
    remaining_quantity: float
    stop_loss: float
    targets: List[Target]
    targets_hit: List[Target] = field(default_factory=list)
    status: PositionStatus = PositionStatus.OPEN
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    breakeven_active: bool = False
    trailing_active: bool = False
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None
    initial_stop_loss: float = 0.0
    initial_entry_price: float = 0.0
    entry_order_id: Optional[str] = None
    exit_reason: Optional[str] = None
    exit_price: Optional[float] = None

    # Trade-type and regime context for adaptive stagnation
    trade_type: str = "intraday"  # "scalp", "intraday", "swing" — from TradePlan
    regime_volatility: str = "normal"  # "compressed", "normal", "elevated", "chaotic"
    regime_trend: str = "sideways"  # "strong_up", "up", "sideways", "down", "strong_down"

    # ML feature snapshot — captured at open time from TradePlan, used for model training
    confidence_score: float = 0.0
    conviction_class: str = "B"       # "A", "B", "C"
    plan_type: str = "SMC"            # "SMC", "ATR_FALLBACK", "HYBRID"
    risk_reward_ratio: float = 0.0
    stop_distance_atr: float = 0.0
    timeframe: str = "1h"
    regime: str = "unknown"           # symbol_regime from plan metadata
    pullback_probability: float = 0.0
    kill_zone: str = "no_session"     # active kill zone at entry time

    # Price history for progress detection (sampled every 30 minutes)
    _price_samples: List[float] = field(default_factory=list)
    _last_sample_time: Optional[datetime] = field(default=None)

    # Stagnation strike counter — consecutive monitor cycles where stagnation
    # conditions are met. Exit only fires when this reaches _STAGNATION_EXIT_THRESHOLD.
    # Prevents a single flat candle from triggering premature exit.
    _stagnation_strikes: int = field(default=0)

    # Separate timestamp used ONLY for orphan detection.
    # updated_at is reset every monitor cycle (via update_unrealized_pnl),
    # so it cannot measure true staleness. _last_monitored_at is set only when
    # the price feed successfully returns a price for this position.
    _last_monitored_at: Optional[datetime] = field(default=None)

    def __post_init__(self):
        """Initialize price tracking and anchor initial stop loss."""
        # Track BOTH extremes from the start so MAE is available regardless of direction.
        self.highest_price = self.entry_price
        self.lowest_price = self.entry_price

        # Anchor the original stop loss and entry price forever to ensure
        # risk and stagnation calculations remain based on the initial thesis.
        self.initial_stop_loss = self.stop_loss
        self.initial_entry_price = self.entry_price

    def update_unrealized_pnl(self, current_price: float):
        """Calculate unrealized P&L based on current price."""
        if self.direction == "LONG":
            pnl_per_unit = current_price - self.entry_price
        else:  # SHORT
            pnl_per_unit = self.entry_price - current_price

        self.unrealized_pnl = pnl_per_unit * self.remaining_quantity
        self.updated_at = datetime.now(timezone.utc)

    def update_price_extremes(self, current_price: float):
        """Track highest/lowest prices for trailing stops and MFE/MAE."""
        if self.highest_price is None or current_price > self.highest_price:
            self.highest_price = current_price
        if self.lowest_price is None or current_price < self.lowest_price:
            self.lowest_price = current_price

    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def pnl_percentage(self) -> float:
        """P&L as percentage of entry value."""
        entry_value = self.entry_price * self.quantity
        if entry_value == 0:
            return 0.0
        return (self.total_pnl / entry_value) * 100

    @property
    def target_pnl(self) -> float:
        """Calculate total estimated P&L if all remaining targets are hit."""
        potential_total = self.realized_pnl
        for target in self.targets:
            qty_at_level = (target.percentage / 100) * self.quantity
            if self.direction == "LONG":
                target_profit = (target.level - self.entry_price) * qty_at_level
            else:
                target_profit = (self.entry_price - target.level) * qty_at_level
            potential_total += target_profit
        return potential_total

    @property
    def risk_pnl(self) -> float:
        """Calculate P&L if stopped out at CURRENT stop loss level."""
        if self.direction == "LONG":
            stop_profit = (self.stop_loss - self.entry_price) * self.remaining_quantity
        else:
            stop_profit = (self.entry_price - self.stop_loss) * self.remaining_quantity
        return self.realized_pnl + stop_profit


class PositionManager:
    """
    Real-time position management and monitoring.

    This is the critical component that was missing from the system review.
    It continuously monitors positions and executes risk management logic.

    Usage:
        manager = PositionManager(price_fetcher=get_current_price)
        position_id = manager.open_position(trade_plan, entry_price, quantity)

        # In main loop:
        await manager.monitor_all_positions()
    """

    # --- Adaptive Stagnation Configuration ---
    # Base hold times by trade type (hours). These represent how long a trade
    # should be allowed to develop before we start checking for stagnation.
    # PARTIAL trades (where at least one target has been hit) get a 2x bonus
    # to the timer to allow the "runner" portion of the trade to develop.
    #
    # Scalp raised 3h→5h: crypto scalp setups at SMC levels routinely need
    # 4-6 hours to play out, especially at HTF demand zones where accumulation
    # is slow. 3h was causing exits on trades that broke out at hour 4-6.
    # Intraday raised 10h→14h: covers full 24h crypto session with room for
    # overnight continuation without needing swing classification.
    TRADE_TYPE_BASE_HOURS = {
        "scalp": 5.0,       # was 3.0 — crypto scalps need 4-6h to resolve
        "intraday": 14.0,   # was 10.0 — covers full 24h session
        "swing": 48.0,      # unchanged
    }

    # Minimum P&L threshold (%) before stagnation exit is considered.
    # Below this AND past the time limit = stagnation exit.
    TRADE_TYPE_STAGNATION_PNL = {
        "scalp": 0.2,       # Scalps: tight threshold
        "intraday": 0.5,    # Intraday: moderate
        "swing": 1.5,       # Swings: need room to breathe
    }

    # Stagnation should NOT close trades that are already deeply underwater.
    # Fraction of the trade's stop distance used as the stagnation loss floor.
    # If the current loss is > STAGNATION_FLOOR_RATIO × stop_distance, defer to stop loss.
    # Using stop distance (not fixed %) makes this adaptive: a trade with a 0.3% stop has
    # a tighter floor than one with a 2% stop, which is structurally correct.
    STAGNATION_FLOOR_RATIO = 0.5

    # Regime-based multipliers on the base hold time.
    # Trending markets deserve more patience; choppy markets less.
    REGIME_TREND_MULTIPLIER = {
        "strong_up": 1.5,   # Strong trend = let it ride
        "up": 1.3,
        "sideways": 0.8,    # Ranging = cut sooner
        "down": 1.3,        # Downtrend (for shorts) = let it ride
        "strong_down": 1.5,
    }

    REGIME_VOLATILITY_MULTIPLIER = {
        "compressed": 0.7,  # Nothing moving = close sooner
        "normal": 1.0,
        "elevated": 1.2,    # Big swings need time to resolve
        "chaotic": 1.0,     # Chaotic = neutral (stop loss handles the risk)
    }

    def __init__(
        self,
        price_fetcher: Callable[[str], float],
        order_executor: Optional[Callable] = None,
        check_interval: float = 1.0,
        breakeven_after_target: int = 1,
        trailing_stop_activation: float = 1.5,  # Activate after 1.5R profit
        trailing_stop_distance: float = 0.5,  # Trail 0.5R behind
        max_hours_open: float = 6.0,  # Legacy fallback — used only if trade_type unknown
    ):
        """
        Initialize Position Manager.

        Args:
            price_fetcher: Function to fetch current price for symbol
            order_executor: Function to execute orders (market sell/buy)
            check_interval: How often to check positions (seconds)
            breakeven_after_target: Move to breakeven after Nth target
            trailing_stop_activation: R multiple to activate trailing
            trailing_stop_distance: R multiple to trail behind
            max_hours_open: Fallback max hours (overridden by adaptive logic per position)
        """
        self.price_fetcher = price_fetcher
        self.order_executor = order_executor
        self.check_interval = check_interval
        self.breakeven_after_target = breakeven_after_target
        self.trailing_stop_activation = trailing_stop_activation
        self.trailing_stop_distance = trailing_stop_distance
        self.max_hours_open = max_hours_open  # Legacy fallback

        self.positions: Dict[str, PositionState] = {}
        self._lock = Lock()
        self._running = False

        logger.info(
            f"PositionManager initialized: check_interval={check_interval}s, "
            f"breakeven_after_target={breakeven_after_target}, "
            f"trailing_activation={trailing_stop_activation}R"
        )

    def open_position(
        self,
        trade_plan: TradePlan,
        entry_price: float,
        quantity: float,
        entry_order_id: Optional[str] = None
    ) -> str:
        """
        Open new position from trade plan.

        Args:
            trade_plan: Trade plan with stops/targets
            entry_price: Actual entry fill price
            quantity: Position size
            entry_order_id: Unique identifier for the order that opened the position

        Returns:
            position_id: Unique position identifier
        """
        position_id = f"{trade_plan.symbol}_{datetime.now(timezone.utc).timestamp()}"

        # Extract regime context from the trade plan metadata
        _meta = getattr(trade_plan, "metadata", {}) or {}
        global_regime = _meta.get("global_regime", {})
        regime_volatility = global_regime.get("volatility", "normal")
        regime_trend = global_regime.get("trend", "sideways")

        # Extract trade type from the planner's derivation
        trade_type = getattr(trade_plan, "trade_type", "intraday") or "intraday"

        # ML feature snapshot — pinned at open time so the model always trains on
        # the conditions that were present when the decision was made.
        _kz = get_current_kill_zone(datetime.now(timezone.utc))
        _ml_kill_zone = _kz.name if _kz else "no_session"
        _ml_regime = str(_meta.get("symbol_regime", "unknown"))
        _ml_pb_prob = float(_meta.get("pullback_probability", 0.0) or 0.0)

        position = PositionState(
            position_id=position_id,
            symbol=trade_plan.symbol,
            direction=trade_plan.direction,
            entry_price=entry_price,
            quantity=quantity,
            remaining_quantity=quantity,
            stop_loss=trade_plan.stop_loss.level,
            targets=sorted(
                trade_plan.targets.copy(),
                key=lambda t: t.level if trade_plan.direction == "LONG" else -t.level,
            ),
            status=PositionStatus.OPEN,
            entry_order_id=entry_order_id,
            trade_type=trade_type,
            regime_volatility=regime_volatility,
            regime_trend=regime_trend,
            confidence_score=float(getattr(trade_plan, "confidence_score", 0.0) or 0.0),
            conviction_class=str(getattr(trade_plan, "conviction_class", "B") or "B"),
            plan_type=str(getattr(trade_plan, "plan_type", "SMC") or "SMC"),
            risk_reward_ratio=float(getattr(trade_plan, "risk_reward_ratio", 0.0) or 0.0),
            stop_distance_atr=float(getattr(trade_plan.stop_loss, "distance_atr", 0.0) or 0.0),
            timeframe=str(getattr(trade_plan, "timeframe", "1h") or "1h"),
            regime=_ml_regime,
            pullback_probability=_ml_pb_prob,
            kill_zone=_ml_kill_zone,
        )

        # Calculate the adaptive stagnation deadline for logging
        adaptive_hours = self._get_adaptive_stagnation_hours(position)
        adaptive_pnl = self._get_adaptive_stagnation_pnl(position)

        with self._lock:
            self.positions[position_id] = position

        logger.info(
            f"Position opened: {position_id} | {trade_plan.symbol} {trade_plan.direction} "
            f"| Entry: {entry_price} | Qty: {quantity} | SL: {trade_plan.stop_loss.level} "
            f"| Type: {trade_type} | Stagnation: {adaptive_hours:.1f}h / {adaptive_pnl:.2f}% "
            f"(regime: trend={regime_trend}, vol={regime_volatility})"
        )

        return position_id

    def add_position_volume(self, position_id: str, fill_price: float, fill_qty: float):
        """
        Add volume to an existing position (for subsequent entry fills).
        Updates average entry price and total quantity.
        """
        with self._lock:
            if position_id not in self.positions:
                logger.warning(f"Position {position_id} not found for volume update")
                return

            pos = self.positions[position_id]
            
            # Recalculate average entry price
            total_qty = pos.quantity + fill_qty
            new_avg = (pos.entry_price * pos.quantity + fill_price * fill_qty) / total_qty
            
            pos.entry_price = new_avg
            pos.quantity = total_qty
            pos.remaining_quantity += fill_qty
            pos.updated_at = datetime.now(timezone.utc)
            
            # Re-init price tracking for new average
            if pos.direction == "LONG":
                pos.highest_price = max(pos.highest_price or 0, new_avg)
            else:
                pos.lowest_price = min(pos.lowest_price or 999999, new_avg)

        logger.info(
            f"Position volume added: {position_id} | Added: {fill_qty} @ {fill_price} "
            f"| New Size: {pos.quantity} | Avg: {pos.entry_price:.2f}"
        )

    def close_position(self, position_id: str, reason: str, current_price: Optional[float] = None):
        """
        Close position completely.

        Args:
            position_id: Position to close
            reason: Reason for closure
            current_price: Price at closure (for P&L calculation)
        """
        with self._lock:
            if position_id not in self.positions:
                logger.warning(f"Position {position_id} not found for closure")
                return

            position = self.positions[position_id]

            # Calculate final P&L if price provided
            if current_price is not None:
                position.update_unrealized_pnl(current_price)
                position.realized_pnl += position.unrealized_pnl
                position.unrealized_pnl = 0.0

            position.remaining_quantity = 0.0
            position.status = PositionStatus.CLOSED
            position.exit_reason = reason
            position.exit_price = current_price
            position.updated_at = datetime.now(timezone.utc)

        logger.info(
            f"Position closed: {position_id} | Reason: {reason} | "
            f"Total P&L: {position.total_pnl:.2f} ({position.pnl_percentage:.2f}%)"
        )

    async def monitor_all_positions(self):
        """
        Monitor all open positions and execute risk management.

        This is the main monitoring loop - should run continuously.
        Checks each position for:
        - Stop loss hit
        - Target hit
        - Breakeven conditions
        - Trailing stop activation
        """
        with self._lock:
            open_positions = [
                p
                for p in self.positions.values()
                if p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
            ]

        if not open_positions:
            return

        logger.debug(f"Monitoring {len(open_positions)} positions")

        for position in open_positions:
            try:
                await self._monitor_position(position)
            except Exception as e:
                logger.error(f"Error monitoring position {position.position_id}: {e}")

        # Orphan detection: if a position's price feed has been silent for more than
        # 2x its adaptive stagnation budget, force-close at last known price.
        # Uses _last_monitored_at (set only on successful price-feed delivery) rather
        # than updated_at (which is reset every cycle by update_unrealized_pnl and
        # therefore can never measure real staleness).
        now = datetime.now(timezone.utc)
        for position in open_positions:
            try:
                stagnation_hours = self._get_adaptive_stagnation_hours(position)
                staleness_limit = timedelta(hours=stagnation_hours * 2)
                # Use _last_monitored_at; fall back to created_at for brand-new positions
                # that haven't received their first successful price tick yet.
                _last_seen = position._last_monitored_at or position.created_at
                if (now - _last_seen) > staleness_limit:
                    try:
                        last_price = self.price_fetcher(position.symbol)
                    except Exception:
                        last_price = position.entry_price
                    _stale_hours = (now - _last_seen).total_seconds() / 3600
                    logger.error(
                        f"ORPHAN DETECTED: {position.position_id} | {position.symbol} | "
                        f"No price feed for {_stale_hours:.1f}h "
                        f"(limit: {stagnation_hours*2:.1f}h). Force-closing at {last_price}."
                    )
                    with self._lock:
                        position.update_unrealized_pnl(last_price)
                        position.realized_pnl += position.unrealized_pnl
                        position.unrealized_pnl = 0.0
                        position.status = PositionStatus.EMERGENCY_EXIT
                        position.exit_reason = "orphan_price_feed_failure"
                        position.exit_price = last_price
                        position.remaining_quantity = 0.0
                        position.updated_at = now
            except Exception as e:
                logger.error(f"Orphan check failed for {position.position_id}: {e}")

    async def _monitor_position(self, position: PositionState):
        """
        Monitor single position and execute risk management logic.

        Order of checks (stop loss FIRST to ensure correct exit classification):
        1. Stop loss hit (immediate exit)
        2. Adaptive stagnation check
        3. Target hit (partial exit)
        4. Breakeven logic
        5. Trailing stop update
        """
        # Fetch current price
        try:
            current_price = self.price_fetcher(position.symbol)
        except Exception as e:
            logger.error(f"Failed to fetch price for {position.symbol}: {e}")
            return

        if current_price <= 0:
            logger.warning(
                f"Skipping monitor cycle for {position.symbol}: "
                f"invalid price {current_price} (cache miss or feed error)"
            )
            return

        # Update P&L and price extremes
        position.update_unrealized_pnl(current_price)
        position.update_price_extremes(current_price)

        # Stamp successful price-feed delivery for orphan detection.
        # updated_at is reset every cycle by update_unrealized_pnl so it cannot
        # measure staleness. _last_monitored_at is only set here — if the price_fetcher
        # throws before reaching this line, the stamp never updates, triggering orphan.
        position._last_monitored_at = datetime.now(timezone.utc)

        # --- Check Stop Loss FIRST ---
        # Must run before stagnation to ensure stop-level exits are classified
        # as "stop_loss" and not "stagnation" when both conditions are true.
        if self._check_stop_hit(position, current_price):
            logger.warning(
                f"STOP HIT: {position.position_id} | {position.symbol} | "
                f"Price: {current_price} | SL: {position.stop_loss} | "
                f"P&L: {position.total_pnl:.2f}"
            )

            if self.order_executor:
                # Execute market close
                success = await self._execute_exit(position, current_price, "STOP_LOSS")
                if not success:
                    return  # Critical: don't settle position if order failed

            # Apply stop-loss slippage: stops fill slightly worse than the trigger price
            # in real execution (0.05% is conservative for crypto; reality can be 0.1-0.5%).
            _STOP_SLIPPAGE_PCT = 0.0005
            if position.direction == "LONG":
                settlement_price = current_price * (1 - _STOP_SLIPPAGE_PCT)
            else:
                settlement_price = current_price * (1 + _STOP_SLIPPAGE_PCT)

            with self._lock:
                # Settle P&L before zeroing remaining_quantity
                position.update_unrealized_pnl(settlement_price)
                position.realized_pnl += position.unrealized_pnl
                position.unrealized_pnl = 0.0
                position.status = PositionStatus.STOPPED_OUT
                position.exit_reason = "stop_loss"
                position.exit_price = settlement_price
                position.remaining_quantity = 0.0

            return  # Position closed, no further checks

        # --- Adaptive Stagnation Check ---
        # Uses trade type + regime to determine how long to hold before cutting.
        # Also checks whether price is making progress toward targets.
        hours_open = (datetime.now(timezone.utc) - position.created_at).total_seconds() / 3600.0

        # --- Hard max_hours_open cap ---
        # Enforced BEFORE adaptive stagnation so the user's configured cap is
        # always respected regardless of progress/stagnation state.
        # adaptive stagnation can be more lenient for trending regimes (1.5× base),
        # which would silently exceed a user-set max_hours_open without this check.
        if self.max_hours_open and hours_open >= self.max_hours_open:
            logger.warning(
                f"MAX_HOURS_OPEN: {position.position_id} | {position.symbol} "
                f"open {hours_open:.1f}h >= hard cap {self.max_hours_open:.1f}h | "
                f"P&L: {position.pnl_percentage:.2f}% | type={position.trade_type}"
            )
            if self.order_executor:
                success = await self._execute_exit(position, current_price, "MAX_HOURS_OPEN")
                if not success:
                    return  # Retry next tick
            with self._lock:
                position.update_unrealized_pnl(current_price)
                position.realized_pnl += position.unrealized_pnl
                position.unrealized_pnl = 0.0
                position.status = PositionStatus.CLOSED
                position.exit_reason = "max_hours_open"
                position.exit_price = current_price
                position.remaining_quantity = 0.0
            return

        # Sample price hourly for progress detection
        self._record_price_sample(position, current_price)

        adaptive_hours = self._get_adaptive_stagnation_hours(position)
        adaptive_pnl = self._get_adaptive_stagnation_pnl(position)

        # For PARTIAL positions (TP1 already hit), use 2x the adaptive timer.
        # They've already locked in profit, so give the runner more room.
        is_partial = position.status == PositionStatus.PARTIAL
        stagnation_hours = adaptive_hours * 2.0 if is_partial else adaptive_hours

        if hours_open >= stagnation_hours and position.status in (
            PositionStatus.OPEN,
            PositionStatus.PARTIAL,
        ):
            # Check if price is making progress toward next target
            making_progress = self._is_making_progress(position, current_price)

            if position.pnl_percentage <= adaptive_pnl and not making_progress:
                # If the position is already deeply underwater, stagnation closing it
                # at a loss makes the R:R distribution worse than a clean stop-out.
                # Defer to the stop loss — stagnation exits should be near-flat, not large losses.
                # ATR-adaptive stagnation floor: if the loss has already exceeded
                # STAGNATION_FLOOR_RATIO of the original stop distance, the trade is too
                # far in the red for a stagnation exit to make sense — the stop is closer
                # to the right exit level. This scales with each trade's actual risk size.
                _stop_pct = (
                    abs(position.initial_entry_price - position.initial_stop_loss)
                    / position.initial_entry_price * 100
                    if position.initial_entry_price > 0 else 0.30
                )
                loss_floor = -(_stop_pct * self.STAGNATION_FLOOR_RATIO)
                if position.pnl_percentage < loss_floor:
                    logger.info(
                        f"STAGNATION DEFERRED (loss floor): {position.position_id} | "
                        f"{position.symbol} | P&L {position.pnl_percentage:.2f}% < floor "
                        f"{loss_floor:.2f}% (={self.STAGNATION_FLOOR_RATIO:.0%} of "
                        f"{_stop_pct:.2f}% stop) — deferring to stop loss"
                    )
                    return

                # Increment strike counter — require 2 consecutive failures before
                # closing. A single flat/poor candle at the stagnation boundary is
                # not sufficient evidence; crypto often consolidates briefly before
                # continuing. Two consecutive failures means the move has genuinely stalled.
                position._stagnation_strikes += 1
                _STAGNATION_EXIT_THRESHOLD = 2

                stagnation_label = "PARTIAL_STAGNATION" if is_partial else "STAGNATION"
                if position._stagnation_strikes < _STAGNATION_EXIT_THRESHOLD:
                    logger.info(
                        f"{stagnation_label} WARNING ({position._stagnation_strikes}/{_STAGNATION_EXIT_THRESHOLD}): "
                        f"{position.position_id} | {position.symbol} | "
                        f"open {hours_open:.1f}h | P&L: {position.pnl_percentage:.2f}% | "
                        f"waiting for confirmation ({_STAGNATION_EXIT_THRESHOLD - position._stagnation_strikes} more)"
                    )
                    return  # Hold — wait for next cycle to confirm

                logger.warning(
                    f"{stagnation_label} EXIT: {position.position_id} | {position.symbol} "
                    f"open {hours_open:.1f}h (limit: {stagnation_hours:.1f}h) | "
                    f"P&L: {position.pnl_percentage:.2f}% (threshold: {adaptive_pnl:.2f}%) | "
                    f"Type: {position.trade_type} | Progress: {making_progress} | "
                    f"Regime: trend={position.regime_trend}, vol={position.regime_volatility} | "
                    f"Strikes: {position._stagnation_strikes}/{_STAGNATION_EXIT_THRESHOLD}"
                )
                if self.order_executor:
                    success = await self._execute_exit(position, current_price, "TIME_STAGNATION")
                    if not success:
                        return  # Persistent retry on next monitor cycle

                with self._lock:
                    # Settle P&L before zeroing remaining_quantity
                    position.update_unrealized_pnl(current_price)
                    position.realized_pnl += position.unrealized_pnl
                    position.unrealized_pnl = 0.0
                    position.status = PositionStatus.CLOSED
                    position.exit_reason = "stagnation"
                    position.exit_price = current_price
                    position.remaining_quantity = 0.0
                return
            elif making_progress:
                logger.info(
                    f"STAGNATION SPARED: {position.position_id} | {position.symbol} "
                    f"past {stagnation_hours:.1f}h limit but making progress toward target | "
                    f"P&L: {position.pnl_percentage:.2f}%"
                )
            else:
                # Progress detected or P&L above threshold — reset strike counter
                # so recovery after a brief stall doesn't carry over stale strikes.
                position._stagnation_strikes = 0

        # --- Check Targets ---
        target_hit = self._check_targets_hit(position, current_price)
        if target_hit:
            logger.info(
                f"TARGET HIT: {position.position_id} | {position.symbol} | "
                f"Level: {target_hit.level} | Closing {target_hit.percentage}%"
            )

            # Calculate quantity to close
            close_qty = (target_hit.percentage / 100) * position.quantity

            if close_qty <= 0:
                logger.error(
                    f"TARGET HIT but close_qty=0 for {position.position_id} | "
                    f"{position.symbol} | target.percentage={target_hit.percentage} | "
                    f"quantity={position.quantity} — skipping partial exit, "
                    f"removing broken target to prevent infinite loop"
                )
                with self._lock:
                    position.targets.remove(target_hit)
                    position.targets_hit.append(target_hit)
                return

            if self.order_executor:
                success = await self._execute_partial_exit(position, current_price, close_qty)
                if not success:
                    return  # Target stays active for next cycle

            with self._lock:
                # Update position state
                position.remaining_quantity -= close_qty
                position.targets.remove(target_hit)
                position.targets_hit.append(target_hit)

                # Update realized P&L
                if position.direction == "LONG":
                    partial_pnl = (current_price - position.entry_price) * close_qty
                else:
                    partial_pnl = (position.entry_price - current_price) * close_qty
                position.realized_pnl += partial_pnl

                # Update status
                if position.remaining_quantity < 1e-9 or not position.targets:  # All targets hit or no targets left
                    position.status = PositionStatus.CLOSED
                    position.exit_reason = "target"
                    position.remaining_quantity = 0.0  # Zero out any residue
                else:
                    position.status = PositionStatus.PARTIAL

            # Check if should move to breakeven
            if len(position.targets_hit) >= self.breakeven_after_target:
                self._move_to_breakeven(position)

        # --- Update Trailing Stop ---
        if position.trailing_active:
            self._update_trailing_stop(position)
        else:
            # Check if should activate trailing
            self._check_trailing_activation(position, current_price)

    # --- Adaptive Stagnation Helpers ---

    def _get_adaptive_stagnation_hours(self, position: PositionState) -> float:
        """
        Calculate adaptive stagnation time limit based on trade type and regime.

        Instead of a flat timer, this scales the hold time:
        - Trade type sets the base (scalp=3h, intraday=10h, swing=48h)
        - Trending regimes extend the timer (price is moving, give it room)
        - Compressed volatility shortens it (nothing's happening)
        - PARTIAL status (runners) doubles the final result (applied in caller)

        Falls back to self.max_hours_open if trade type is unknown.
        """
        base_hours = self.TRADE_TYPE_BASE_HOURS.get(position.trade_type)

        if base_hours is None:
            # Unknown trade type — use legacy flat timer
            return self.max_hours_open

        # Apply regime multipliers
        trend_mult = self.REGIME_TREND_MULTIPLIER.get(position.regime_trend, 1.0)

        # For trend multiplier, check directional alignment:
        # A LONG in a downtrend shouldn't get extra patience, nor a SHORT in an uptrend.
        if position.direction == "LONG" and position.regime_trend in ("down", "strong_down"):
            trend_mult = 0.7  # Counter-trend long — cut sooner
        elif position.direction == "SHORT" and position.regime_trend in ("up", "strong_up"):
            trend_mult = 0.7  # Counter-trend short — cut sooner

        vol_mult = self.REGIME_VOLATILITY_MULTIPLIER.get(position.regime_volatility, 1.0)

        adaptive = base_hours * trend_mult * vol_mult

        # Clamp to reasonable bounds
        return max(1.0, min(adaptive, 120.0))

    def _get_adaptive_stagnation_pnl(self, position: PositionState) -> float:
        """
        Get the minimum P&L threshold for stagnation exit based on trade type.

        Scalps use tight thresholds (0.2%), swings use wide ones (1.5%).
        """
        return self.TRADE_TYPE_STAGNATION_PNL.get(position.trade_type, 0.5)

    def _record_price_sample(self, position: PositionState, current_price: float):
        """Record hourly price samples for progress detection."""
        now = datetime.now(timezone.utc)

        last_time = position._last_sample_time
        if last_time is None:
            # First sample
            position._price_samples.append(current_price)
            position._last_sample_time = now
            return

        # Explicitly ensure last_time is not None for the linter
        assert last_time is not None
        elapsed = (now - last_time).total_seconds()
        
        if elapsed >= 1800:  # Sample every 30 minutes
            position._price_samples.append(current_price)
            position._last_sample_time = now

            # Keep last 24 samples (12 hours of data)
            if len(position._price_samples) > 24:
                # Use list comprehension as a workaround for linter slice issues
                n = len(position._price_samples)
                position._price_samples = [position._price_samples[i] for i in range(n - 24, n)]

    def _is_making_progress(self, position: PositionState, current_price: float) -> bool:
        """
        Determine if price is trending toward TP1, even if P&L is still low.

        Checks if the recent price samples show a directional trend toward
        the first target. This prevents killing trades that are slowly but
        steadily moving in the right direction.

        Uses simple higher-lows (for longs) / lower-highs (for shorts) detection
        over the last several samples.
        """
        samples = position._price_samples
        if len(samples) < 4:
            return False  # Not enough data to judge

        # Get the first unfilled target
        if not position.targets:
            return False

        tp1 = position.targets[0].level

        # Use last 6 samples (or all if fewer)
        # Using list comprehension workaround for linter slice issues
        n_samples = len(samples)
        n_to_take = min(6, n_samples)
        recent = [samples[i] for i in range(n_samples - n_to_take, n_samples)]

        if position.direction == "LONG":
            # For longs, check if price is making higher lows toward TP1
            # Split recent samples into two halves and compare
            mid = len(recent) // 2
            first_half = [recent[i] for i in range(0, mid)]
            second_half = [recent[i] for i in range(mid, len(recent))]
            
            first_half_min = min(first_half)
            second_half_min = min(second_half)
            latest = recent[-1]

            # Progress = recent lows are higher than earlier lows
            # AND latest price is closer to target than the ORIGINAL entry
            # AND at least 10% of the entry-to-target distance has been covered
            # (prevents micro-oscillations within noise from deferring stagnation exit)
            lows_rising = second_half_min > first_half_min
            closer_to_target = abs(tp1 - latest) < abs(tp1 - position.initial_entry_price)
            initial_distance = abs(tp1 - position.initial_entry_price)
            current_distance = abs(tp1 - latest)
            meaningful_progress = (
                initial_distance > 0
                and current_distance < initial_distance * 0.90
            )

            return lows_rising and closer_to_target and meaningful_progress

        else:  # SHORT
            # Split recent samples into two halves and compare
            mid = len(recent) // 2
            first_half = [recent[i] for i in range(0, mid)]
            second_half = [recent[i] for i in range(mid, len(recent))]

            first_half_max = max(first_half)
            second_half_max = max(second_half)
            latest = recent[-1]

            highs_falling = second_half_max < first_half_max
            closer_to_target = abs(tp1 - latest) < abs(tp1 - position.initial_entry_price)
            initial_distance = abs(tp1 - position.initial_entry_price)
            current_distance = abs(tp1 - latest)
            meaningful_progress = (
                initial_distance > 0
                and current_distance < initial_distance * 0.90
            )

            return highs_falling and closer_to_target and meaningful_progress

    def _check_stop_hit(self, position: PositionState, current_price: float) -> bool:
        """Check if stop loss was hit."""
        if position.direction == "LONG":
            return current_price <= position.stop_loss
        else:  # SHORT
            return current_price >= position.stop_loss

    def _check_targets_hit(self, position: PositionState, current_price: float) -> Optional[Target]:
        """
        Check if any targets were hit.

        Returns first target hit (closest to entry).
        """
        if not position.targets:
            return None

        for target in position.targets:
            if position.direction == "LONG":
                if current_price >= target.level:
                    return target
            else:  # SHORT
                if current_price <= target.level:
                    return target

        return None

    def _move_to_breakeven(self, position: PositionState):
        """Move stop loss to breakeven plus a 0.1R buffer to absorb spread/wick noise."""
        if position.breakeven_active:
            return  # Already at breakeven

        old_stop = position.stop_loss

        # Add 0.1R buffer above/below entry so crypto spread/wick noise doesn't produce
        # a zero-P&L (or negative-after-fees) stop-out on the runner.
        risk = abs(position.initial_entry_price - position.initial_stop_loss)
        buffer = risk * 0.1
        if position.direction == "LONG":
            position.stop_loss = position.entry_price + buffer
        else:
            position.stop_loss = position.entry_price - buffer

        position.breakeven_active = True

        logger.info(
            f"BREAKEVEN: {position.position_id} | {position.symbol} | "
            f"Stop moved: {old_stop:.6f} -> {position.stop_loss:.6f} (entry + 0.1R buffer: {buffer:.6f})"
        )

    def protect_alt_shorts_on_btc_pump(self, price_cache: dict) -> list:
        """
        Called when global BTC regime transitions to strong_up/up.
        For every open SHORT position on a non-BTC symbol, move the stop
        to breakeven if it's currently below entry. If already profitable,
        tighten the trailing stop to within 0.25R of current price.

        Returns list of (symbol, position_id, action) tuples for activity logging.
        """
        actions = []
        with self._lock:
            for pos_id, pos in self.positions.items():
                if pos.status not in (PositionStatus.OPEN, PositionStatus.PARTIAL):
                    continue
                if pos.direction != "SHORT":
                    continue
                if "BTC" in pos.symbol.upper():
                    continue

                current_price = price_cache.get(pos.symbol)
                if not current_price:
                    continue

                risk = abs(pos.initial_entry_price - pos.initial_stop_loss)
                if risk == 0:
                    continue

                if not pos.breakeven_active:
                    # Mirror _move_to_breakeven convention: SHORT breakeven stop is
                    # entry - buffer (slightly below entry). Stop triggers when
                    # current_price >= stop_loss, so this fires if price rises back
                    # near entry, locking in a small profit on the runner.
                    old_stop = pos.stop_loss
                    buffer = risk * 0.1
                    new_stop = pos.entry_price - buffer
                    if new_stop < pos.stop_loss:
                        # New stop is tighter (lower) than current — only tighten, never loosen
                        pos.stop_loss = new_stop
                        pos.breakeven_active = True
                        actions.append((pos.symbol, pos_id, f"breakeven {old_stop:.4f}→{new_stop:.4f}"))
                        logger.info(
                            f"BTC_PUMP_PROTECT: {pos.symbol} SHORT {pos_id} | "
                            f"stop tightened to breakeven {old_stop:.4f} → {new_stop:.4f}"
                        )
                else:
                    # Already at breakeven — tighten trailing to 0.25R from current price
                    profit_r = (pos.entry_price - current_price) / risk
                    if profit_r > 0:
                        trail_stop = current_price + risk * 0.25
                        if trail_stop < pos.stop_loss:
                            old_stop = pos.stop_loss
                            pos.stop_loss = trail_stop
                            pos.trailing_active = True
                            actions.append((pos.symbol, pos_id, f"trail {old_stop:.4f}→{trail_stop:.4f}"))
                            logger.info(
                                f"BTC_PUMP_PROTECT: {pos.symbol} SHORT {pos_id} | "
                                f"trailing tightened {old_stop:.4f} → {trail_stop:.4f} (0.25R)"
                            )
        return actions

    def _check_trailing_activation(self, position: PositionState, current_price: float):
        """Check if trailing stop should be activated."""
        if position.trailing_active:
            return

        # Calculate profit in R multiples
        # FIX: Anchor risk to initial_stop_loss
        risk = abs(position.entry_price - position.initial_stop_loss)
        if risk == 0:
            return

        if position.direction == "LONG":
            profit = current_price - position.entry_price
        else:
            profit = position.entry_price - current_price

        profit_r = profit / risk

        if profit_r >= self.trailing_stop_activation:
            position.trailing_active = True
            logger.info(
                f"TRAILING ACTIVATED: {position.position_id} | {position.symbol} | "
                f"Profit: {profit_r:.2f}R"
            )
            self._update_trailing_stop(position)

    def _update_trailing_stop(self, position: PositionState):
        """Update trailing stop based on price movement."""
        if not position.trailing_active:
            return

        # Calculate trail distance scaled by trade type — scalps need tight trails,
        # swings need room to breathe during normal retracements.
        _TRAIL_DISTANCE_BY_TYPE = {"scalp": 0.3, "intraday": 0.5, "swing": 1.0}
        risk = abs(position.entry_price - position.initial_stop_loss)
        type_distance = _TRAIL_DISTANCE_BY_TYPE.get(position.trade_type, self.trailing_stop_distance)
        trail_distance = risk * type_distance
        
        if position.direction == "LONG":
            highest = position.highest_price
            if highest is None:
                return
            new_stop = highest - trail_distance
            # Only trail up, never down
            if new_stop > position.stop_loss:
                old_stop = position.stop_loss
                position.stop_loss = new_stop
                logger.debug(
                    f"TRAIL UPDATE: {position.position_id} | "
                    f"Stop: {old_stop:.2f} -> {new_stop:.2f}"
                )
        else:  # SHORT
            lowest = position.lowest_price
            if lowest is None:
                return
            new_stop = lowest + trail_distance
            # Only trail down, never up
            if new_stop < position.stop_loss:
                old_stop = position.stop_loss
                position.stop_loss = new_stop
                logger.debug(
                    f"TRAIL UPDATE: {position.position_id} | "
                    f"Stop: {old_stop:.2f} -> {new_stop:.2f}"
                )

    async def _execute_exit(self, position: PositionState, price: float, reason: str) -> bool:
        """Execute full position exit."""
        executor = self.order_executor
        if not executor:
            logger.warning("No order executor configured - simulating exit")
            return True

        try:
            # Execute market order to close
            order_side = "SELL" if position.direction == "LONG" else "BUY"
            await executor(
                symbol=position.symbol,
                side=order_side,
                quantity=position.remaining_quantity,
                price=price,
            )
            logger.info(
                f"Exit executed: {position.position_id} | {reason} | "
                f"Qty: {position.remaining_quantity} @ {price}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to execute exit for {position.position_id}: {e}")
            return False

    async def _execute_partial_exit(self, position: PositionState, price: float, quantity: float) -> bool:
        """Execute partial position exit at target."""
        executor = self.order_executor
        if not executor:
            logger.warning("No order executor configured - simulating partial exit")
            return True

        try:
            order_side = "SELL" if position.direction == "LONG" else "BUY"
            await executor(
                symbol=position.symbol, side=order_side, quantity=quantity, price=price
            )
            logger.info(
                f"Partial exit executed: {position.position_id} | " f"Qty: {quantity} @ {price}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to execute partial exit for {position.position_id}: {e}")
            return False

    def get_position(self, position_id: str) -> Optional[PositionState]:
        """Get position state by ID."""
        with self._lock:
            return self.positions.get(position_id)

    def get_all_positions(self) -> List[PositionState]:
        """Get all positions."""
        with self._lock:
            return list(self.positions.values())

    def get_open_positions(self) -> List[PositionState]:
        """Get only open/partial positions."""
        with self._lock:
            return [
                p
                for p in self.positions.values()
                if p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
            ]

    def remove_position(self, position_id: str) -> Optional[PositionState]:
        """
        Atomically remove a position from the tracking dict.

        Used after a trade has been archived to ``completed_trades`` so the
        caller never reaches into ``self.positions`` directly. Returns the
        removed :class:`PositionState` (or ``None`` if it had already been
        removed). Acquiring ``self._lock`` guarantees this cannot race with
        the monitor loop's iteration over ``get_open_positions``.
        """
        with self._lock:
            return self.positions.pop(position_id, None)

    def emergency_close_all(self, reason: str = "EMERGENCY"):
        """
        Emergency close all open positions.

        Calls order_executor for each position so the executor's position dict
        and balance are correctly updated — without this, the executor's margin
        accounting would still show open positions after an emergency shutdown.

        Use in case of system shutdown, critical error, or risk event.
        """
        logger.critical(f"EMERGENCY CLOSE ALL: {reason}")

        open_positions = self.get_open_positions()

        for position in open_positions:
            try:
                current_price = self.price_fetcher(position.symbol)

                # Fire exit order through executor BEFORE settling the PositionState
                # so the executor's positions dict and balance reflect the close.
                if self.order_executor and position.remaining_quantity > 0 and current_price > 0:
                    import asyncio
                    order_side = "SELL" if position.direction == "LONG" else "BUY"
                    try:
                        # order_executor is async; emergency_close_all may be
                        # called from either an async context (shutdown hook)
                        # or a sync thread (signal handler / tests).
                        #
                        # ``asyncio.get_event_loop()`` is deprecated in 3.12+
                        # when there is no running loop: prefer
                        # ``get_running_loop`` (which raises cleanly if none
                        # exists) and fall back to creating a fresh loop only
                        # as a last resort.
                        try:
                            running_loop = asyncio.get_running_loop()
                        except RuntimeError:
                            running_loop = None

                        if running_loop is not None:
                            asyncio.ensure_future(
                                self.order_executor(
                                    symbol=position.symbol,
                                    side=order_side,
                                    quantity=position.remaining_quantity,
                                    price=current_price,
                                ),
                                loop=running_loop,
                            )
                        else:
                            # No running loop — create a throwaway one so the
                            # executor coroutine runs to completion before we
                            # settle the position. Closed explicitly to avoid
                            # ResourceWarning.
                            _tmp_loop = asyncio.new_event_loop()
                            try:
                                _tmp_loop.run_until_complete(
                                    self.order_executor(
                                        symbol=position.symbol,
                                        side=order_side,
                                        quantity=position.remaining_quantity,
                                        price=current_price,
                                    )
                                )
                            finally:
                                _tmp_loop.close()
                    except Exception as exec_err:
                        logger.warning(
                            f"Emergency executor close failed for {position.position_id}: {exec_err}"
                        )

                # Set EMERGENCY_EXIT status BEFORE settling so _sync_closed_positions
                # can distinguish this from a normal CLOSED status.
                with self._lock:
                    position.status = PositionStatus.EMERGENCY_EXIT
                    position.exit_reason = f"EMERGENCY: {reason}"

                # Calculate final P&L and zero out remaining quantity
                if current_price is not None:
                    position.update_unrealized_pnl(current_price)
                    position.realized_pnl += position.unrealized_pnl
                    position.unrealized_pnl = 0.0
                position.remaining_quantity = 0.0
                position.exit_price = current_price
                position.updated_at = datetime.now(timezone.utc)

                logger.info(
                    f"Emergency closed: {position.position_id} | "
                    f"Total P&L: {position.total_pnl:.2f} ({position.pnl_percentage:.2f}%)"
                )
            except Exception as e:
                logger.error(f"Failed to emergency close {position.position_id}: {e}")

    def find_position_by_order_id(self, order_id: str) -> Optional[PositionState]:
        """Find an open/partial position linked to a specific entry order ID."""
        with self._lock:
            for pos in self.positions.values():
                if pos.entry_order_id == order_id and pos.status in [
                    PositionStatus.OPEN,
                    PositionStatus.PARTIAL,
                ]:
                    return pos
        return None

    async def start_monitoring(self):
        """
        Start continuous position monitoring loop.

        Run this in background task/thread.
        """
        self._running = True
        logger.info("Position monitoring started")

        while self._running:
            try:
                await self.monitor_all_positions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)

    def stop_monitoring(self):
        """Stop monitoring loop."""
        self._running = False
        logger.info("Position monitoring stopped")
