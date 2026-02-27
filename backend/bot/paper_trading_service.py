"""
Paper Trading Service

Orchestrates the full paper trading workflow:
- Scanner integration (using Orchestrator)
- Paper order execution
- Position management with SL/TP monitoring
- Trade lifecycle tracking

This service ties together the scanner logic with paper execution,
allowing users to test trading strategies without real capital.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
import asyncio
import logging
import uuid

from backend.bot.executor.paper_executor import PaperExecutor, OrderStatus
from backend.bot.executor.position_manager import PositionManager, PositionStatus
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.scanner_modes import get_mode, ScannerMode
from backend.shared.config.defaults import ScanConfig
from backend.shared.models.planner import TradePlan
from backend.data.adapters.phemex import PhemexAdapter

logger = logging.getLogger(__name__)


class PaperBotStatus(Enum):
    """Paper trading bot status."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PaperTradingConfig:
    """
    Configuration for paper trading session.

    Attributes:
        exchange: Exchange profile for pricing
        sniper_mode: Bot strategy mode (stealth, surgical, strike, overwatch)
        initial_balance: Starting paper money (USDT)
        risk_per_trade: % of balance to risk per trade (0-100)
        max_positions: Maximum concurrent open positions
        leverage: Leverage multiplier
        duration_hours: Auto-stop after X hours (0 = manual)
        scan_interval_minutes: How often to run scanner
        trailing_stop: Enable trailing stops
        trailing_activation: R-multiple to activate trailing
        breakeven_after_target: Move SL to entry after Nth target
        min_confluence: Minimum confluence score to take trade (None = use mode default)
        symbols: Specific pairs to trade (empty = use scanner defaults)
        exclude_symbols: Pairs to exclude
        slippage_bps: Simulated slippage (basis points)
        fee_rate: Simulated trading fee (decimal, e.g., 0.001 = 0.1%)
    """

    exchange: str = "phemex"
    sniper_mode: str = "stealth"
    initial_balance: float = 10000.0
    risk_per_trade: float = 2.0
    max_positions: int = 3
    leverage: int = 1
    duration_hours: int = 24
    scan_interval_minutes: int = 5
    trailing_stop: bool = True
    trailing_activation: float = 1.5
    breakeven_after_target: int = 1
    min_confluence: Optional[float] = None
    symbols: List[str] = field(default_factory=list)
    exclude_symbols: List[str] = field(default_factory=list)
    slippage_bps: float = 5.0
    fee_rate: float = 0.001

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperTradingConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CompletedTrade:
    """
    Record of a completed paper trade.

    Attributes:
        trade_id: Unique trade identifier
        symbol: Trading pair
        direction: LONG or SHORT
        entry_price: Average entry price
        exit_price: Average exit price (or current if still open)
        quantity: Position size
        entry_time: When position was opened
        exit_time: When position was closed
        pnl: Profit/loss in USDT
        pnl_pct: Profit/loss percentage
        exit_reason: Why the trade was closed (target, stop, manual)
        targets_hit: List of targets that were hit
        max_favorable: Maximum favorable excursion (MFE)
        max_adverse: Maximum adverse excursion (MAE)
    """

    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl: float
    pnl_pct: float
    exit_reason: str
    targets_hit: List[int] = field(default_factory=list)
    max_favorable: float = 0.0
    max_adverse: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "exit_reason": self.exit_reason,
            "targets_hit": self.targets_hit,
            "max_favorable": self.max_favorable,
            "max_adverse": self.max_adverse,
        }


@dataclass
class PaperTradingStats:
    """
    Statistics for paper trading session.

    Attributes:
        total_trades: Number of completed trades
        winning_trades: Number of profitable trades
        losing_trades: Number of losing trades
        win_rate: Winning percentage
        total_pnl: Total profit/loss
        total_pnl_pct: Total P&L as percentage of initial balance
        avg_win: Average winning trade P&L
        avg_loss: Average losing trade P&L
        avg_rr: Average risk-reward ratio achieved
        best_trade: Largest winning trade P&L
        worst_trade: Largest losing trade P&L
        max_drawdown: Maximum drawdown experienced
        current_streak: Current win/loss streak
        scans_completed: Number of scanner runs
        signals_generated: Total signals from scanner
        signals_taken: Signals that passed filters and were executed
    """

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_rr: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    max_drawdown: float = 0.0
    current_streak: int = 0
    scans_completed: int = 0
    signals_generated: int = 0
    signals_taken: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PaperTradingService:
    """
    Main paper trading orchestration service.

    Integrates:
    - Orchestrator for signal generation
    - PaperExecutor for order simulation
    - PositionManager for SL/TP management

    Usage:
        service = PaperTradingService()
        await service.start(config)

        # Check status
        status = service.get_status()

        # Stop
        await service.stop()
    """

    def __init__(self):
        """Initialize paper trading service."""
        self.config: Optional[PaperTradingConfig] = None
        self.status: PaperBotStatus = PaperBotStatus.IDLE
        self.session_id: Optional[str] = None

        # Core components (initialized on start)
        self.executor: Optional[PaperExecutor] = None
        self.position_manager: Optional[PositionManager] = None
        self.orchestrator: Optional[Orchestrator] = None
        self.mode: Optional[ScannerMode] = None

        # Tracking
        self.completed_trades: List[CompletedTrade] = []
        self.activity_log: List[Dict[str, Any]] = []
        self.stats: PaperTradingStats = PaperTradingStats()

        # Session timing
        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        self.last_scan_at: Optional[datetime] = None

        # Background task
        self._scan_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # Price cache for P&L calculations
        self._price_cache: Dict[str, float] = {}

        logger.info("PaperTradingService initialized")

    async def start(self, config: PaperTradingConfig) -> Dict[str, Any]:
        """
        Start paper trading session.

        Args:
            config: Paper trading configuration

        Returns:
            Session info including session_id
        """
        if self.status == PaperBotStatus.RUNNING:
            raise ValueError("Paper trading already running")

        self.config = config
        self.session_id = str(uuid.uuid4())[:8]

        # Load scanner mode
        self.mode = get_mode(config.sniper_mode)
        if not self.mode:
            raise ValueError(f"Invalid sniper mode: {config.sniper_mode}")

        # Initialize paper executor
        self.executor = PaperExecutor(
            initial_balance=config.initial_balance,
            fee_rate=config.fee_rate,
            slippage_bps=config.slippage_bps,
            enable_partial_fills=False,  # Simplify for paper trading
        )

        # Initialize position manager
        self.position_manager = PositionManager(
            price_fetcher=self._get_price,
            order_executor=self._execute_exit_order,
            check_interval=1.0,
            breakeven_after_target=config.breakeven_after_target,
            trailing_stop_activation=config.trailing_activation,
            trailing_stop_distance=0.5,
        )

        # Initialize orchestrator with exchange adapter
        try:
            adapter = PhemexAdapter()  # Default to Phemex

            # Get min_rr from mode overrides or use default
            min_rr = 1.0  # Default
            if self.mode.overrides and "min_rr_ratio" in self.mode.overrides:
                min_rr = self.mode.overrides["min_rr_ratio"]

            # Create ScanConfig from paper trading config
            scan_config = ScanConfig(
                profile=config.sniper_mode,
                timeframes=tuple(self.mode.timeframes),
                min_confluence_score=config.min_confluence or self.mode.min_confluence_score,
                min_rr_ratio=min_rr,
                max_symbols=20,
            )

            self.orchestrator = Orchestrator(config=scan_config, exchange_adapter=adapter)
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            raise ValueError(f"Failed to initialize scanner: {e}")

        # Reset tracking
        self.completed_trades = []
        self.activity_log = []
        self.stats = PaperTradingStats()
        self._price_cache = {}

        # Start session
        self.started_at = datetime.now(timezone.utc)
        self.stopped_at = None
        self.status = PaperBotStatus.RUNNING
        self._running = True

        # Log activity
        self._log_activity(
            "session_started", {"session_id": self.session_id, "config": config.to_dict()}
        )

        # Start background tasks
        self._scan_task = asyncio.create_task(self._scan_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info(f"Paper trading started: session={self.session_id}, mode={config.sniper_mode}")

        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "config": config.to_dict(),
        }

    async def stop(self) -> Dict[str, Any]:
        """
        Stop paper trading session.

        Returns:
            Final session statistics
        """
        if self.status != PaperBotStatus.RUNNING:
            return {"status": self.status.value, "message": "Not running"}

        self._running = False
        self.status = PaperBotStatus.STOPPED
        self.stopped_at = datetime.now(timezone.utc)

        # Cancel background tasks
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Close all open positions
        await self._close_all_positions("session_stopped")

        # Log activity
        self._log_activity(
            "session_stopped", {"session_id": self.session_id, "final_stats": self.stats.to_dict()}
        )

        logger.info(f"Paper trading stopped: session={self.session_id}")

        return self.get_status()

    def reset(self) -> Dict[str, Any]:
        """
        Reset paper trading to fresh state.

        Returns:
            Reset confirmation
        """
        if self.status == PaperBotStatus.RUNNING:
            raise ValueError("Cannot reset while running. Stop first.")

        self.config = None
        self.session_id = None
        self.executor = None
        self.position_manager = None
        self.orchestrator = None
        self.mode = None

        self.completed_trades = []
        self.activity_log = []
        self.stats = PaperTradingStats()
        self._price_cache = {}

        self.started_at = None
        self.stopped_at = None
        self.status = PaperBotStatus.IDLE

        logger.info("Paper trading reset")

        return {"status": "reset", "message": "Paper trading reset to initial state"}

    def get_status(self) -> Dict[str, Any]:
        """
        Get current paper trading status.

        Returns:
            Comprehensive status including balance, positions, stats
        """
        # Calculate next scan time
        next_scan_in = None
        if self.status == PaperBotStatus.RUNNING and self.config and self.last_scan_at:
            interval_seconds = self.config.scan_interval_minutes * 60
            next_scan_at = self.last_scan_at + timedelta(seconds=interval_seconds)
            next_scan_in = max(0, (next_scan_at - datetime.now(timezone.utc)).total_seconds())

        # Basic status
        result = {
            "status": self.status.value,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "uptime_seconds": self._get_uptime_seconds(),
            "config": self.config.to_dict() if self.config else None,
            "last_scan_at": self.last_scan_at.isoformat() if self.last_scan_at else None,
            "next_scan_in_seconds": next_scan_in,
        }

        # Balance info
        if self.executor:
            initial = self.config.initial_balance if self.config else 0
            current = self.executor.get_balance()
            equity = self.executor.get_equity(self._price_cache)

            result["balance"] = {
                "initial": initial,
                "current": current,
                "equity": equity,
                "pnl": equity - initial,
                "pnl_pct": ((equity - initial) / initial * 100) if initial > 0 else 0,
            }
        else:
            result["balance"] = None

        # Active positions
        result["positions"] = self._get_active_positions()

        # Statistics
        result["statistics"] = self.stats.to_dict()

        # Recent activity (last 20)
        result["recent_activity"] = self.activity_log[-20:]

        # OHLCV cache stats (for monitoring efficiency)
        try:
            from backend.data.ohlcv_cache import get_ohlcv_cache

            cache = get_ohlcv_cache()
            cache_stats = cache.get_stats()
            result["cache_stats"] = {
                "hit_rate_pct": cache_stats["hit_rate_pct"],
                "entries": cache_stats["entries"],
                "candles_cached": cache_stats["total_candles_cached"],
            }
        except Exception:
            result["cache_stats"] = None

        return result

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get active positions with real-time P&L."""
        return self._get_active_positions()

    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get completed trade history.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of completed trades (newest first)
        """
        trades = sorted(
            self.completed_trades, key=lambda t: t.exit_time or t.entry_time, reverse=True
        )[:limit]

        return [t.to_dict() for t in trades]

    def get_activity_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get activity log.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of activity events (newest first)
        """
        return list(reversed(self.activity_log[-limit:]))

    # -------------------- Private Methods --------------------

    async def _scan_loop(self):
        """Background loop for running scanner at intervals."""
        interval = (self.config.scan_interval_minutes or 5) * 60

        while self._running:
            try:
                await self._run_scan()
            except Exception as e:
                logger.error(f"Scan error: {e}")
                self._log_activity("scan_error", {"error": str(e)})

            # Check duration limit
            if self.config and self.config.duration_hours > 0:
                elapsed = self._get_uptime_seconds()
                if elapsed >= self.config.duration_hours * 3600:
                    logger.info("Duration limit reached, stopping")
                    await self.stop()
                    break

            # Wait for next interval
            await asyncio.sleep(interval)

    async def _monitor_loop(self):
        """Background loop for monitoring positions."""
        while self._running:
            try:
                if self.position_manager:
                    await self.position_manager.monitor_all_positions()

                    # Check for closed positions
                    await self._sync_closed_positions()

            except Exception as e:
                logger.error(f"Monitor error: {e}")

            await asyncio.sleep(1)  # Check every second

    async def _run_scan(self):
        """Run a single scanner iteration."""
        if not self.orchestrator or not self.config or not self.mode:
            return

        self.last_scan_at = datetime.now(timezone.utc)
        self._log_activity("scan_started", {"mode": self.config.sniper_mode})
        self.stats.scans_completed += 1

        try:
            # Build symbol list - use config symbols or default top pairs
            if self.config.symbols:
                symbols = self.config.symbols
            else:
                # Default to fewer pairs for faster scanning
                # Full list available but reduces to 5 for performance
                symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]

            # Filter out excluded symbols
            if self.config.exclude_symbols:
                symbols = [s for s in symbols if s not in self.config.exclude_symbols]

            logger.info(f"Starting scan: {len(symbols)} symbols, mode={self.config.sniper_mode}")

            # Run scanner - use self.mode (ScannerMode object), not config.sniper_mode (string)
            self.orchestrator.apply_mode(self.mode)
            trade_plans, rejections = self.orchestrator.scan(symbols=symbols)

            self.stats.signals_generated += len(trade_plans)

            self._log_activity(
                "scan_completed",
                {
                    "signals_found": len(trade_plans),
                    "symbols_scanned": len(symbols),
                    "rejections": len(rejections) if isinstance(rejections, dict) else 0,
                },
            )

            # Process each signal
            for plan in trade_plans:
                await self._process_signal(plan)

        except Exception as e:
            import traceback

            error_details = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Scanner error: {error_details}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._log_activity("scan_error", {"error": error_details})

    async def _process_signal(self, plan: TradePlan):
        """
        Process a trade signal and potentially execute it.

        Args:
            plan: Trade plan from scanner
        """
        if not self.config or not self.executor or not self.position_manager:
            return

        # Check if we can take more positions
        active_count = len(self._get_active_positions())
        if active_count >= self.config.max_positions:
            logger.debug(f"Max positions reached ({active_count}), skipping {plan.symbol}")
            self._log_activity(
                "signal_filtered",
                {
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "confluence": plan.confidence_score,
                    "reason": f"Max positions reached ({active_count}/{self.config.max_positions})",
                },
            )
            return

        # Check if already in position for this symbol
        if self._has_position(plan.symbol):
            logger.debug(f"Already in position for {plan.symbol}, skipping")
            self._log_activity(
                "signal_filtered",
                {
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "confluence": plan.confidence_score,
                    "reason": "Already in position for symbol",
                },
            )
            return

        # Check confluence threshold
        min_score = self.config.min_confluence or (
            self.mode.min_confluence_score if self.mode else 60
        )
        if plan.confidence_score < min_score:
            logger.debug(
                f"Confluence {plan.confidence_score} below min {min_score}, skipping {plan.symbol}"
            )
            self._log_activity(
                "signal_filtered",
                {
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "confluence": plan.confidence_score,
                    "reason": f"Confluence {plan.confidence_score:.0f}% below min {min_score:.0f}%",
                },
            )
            return

        # Calculate position size
        position_size = self._calculate_position_size(plan)
        if position_size <= 0:
            logger.debug(f"Invalid position size for {plan.symbol}")
            return

        # Get current price
        try:
            current_price = await self._fetch_price(plan.symbol)
            self._price_cache[plan.symbol] = current_price
        except Exception as e:
            logger.error(f"Failed to get price for {plan.symbol}: {e}")
            return

        # Execute entry
        try:
            side = "BUY" if plan.direction == "LONG" else "SELL"

            order = self.executor.place_order(
                symbol=plan.symbol,
                side=side,
                order_type="MARKET",
                quantity=position_size,
                price=current_price,
            )

            fill = self.executor.execute_market_order(order.order_id, current_price)

            if fill and order.status == OrderStatus.FILLED:
                # Open position in manager
                position_id = self.position_manager.open_position(
                    trade_plan=plan, entry_price=fill.price, quantity=fill.quantity
                )

                self.stats.signals_taken += 1

                self._log_activity(
                    "trade_opened",
                    {
                        "position_id": position_id,
                        "symbol": plan.symbol,
                        "direction": plan.direction,
                        "entry_price": fill.price,
                        "quantity": fill.quantity,
                        "stop_loss": plan.stop_loss.level,
                        "targets": [t.level for t in plan.targets],
                        "confluence": plan.confidence_score,
                    },
                )

                logger.info(f"Trade opened: {plan.symbol} {plan.direction} @ {fill.price}")

        except Exception as e:
            logger.error(f"Failed to execute trade for {plan.symbol}: {e}")
            self._log_activity("trade_error", {"symbol": plan.symbol, "error": str(e)})

    def _calculate_position_size(self, plan: TradePlan) -> float:
        """
        Calculate position size based on risk parameters.

        Args:
            plan: Trade plan with stop loss

        Returns:
            Position size in base currency
        """
        if not self.config or not self.executor:
            return 0.0

        balance = self.executor.get_balance()
        risk_amount = balance * (self.config.risk_per_trade / 100)

        # Calculate risk per unit
        # EntryZone is a dataclass with near_entry and far_entry attributes
        # Use near_entry as the primary entry price (aggressive entry)
        entry = plan.entry_zone.near_entry
        stop = plan.stop_loss.level

        if entry == 0 or stop == 0:
            return 0.0

        risk_per_unit = abs(entry - stop)
        if risk_per_unit == 0:
            return 0.0

        # Base position size
        position_size = risk_amount / risk_per_unit

        # Apply leverage
        position_size *= self.config.leverage

        # Ensure we don't exceed available balance
        max_position_value = balance * 0.5  # Max 50% of balance per position
        max_size = max_position_value / entry if entry > 0 else 0

        return min(position_size, max_size)

    def _has_position(self, symbol: str) -> bool:
        """Check if already in position for symbol."""
        if not self.position_manager:
            return False

        for pos in self.position_manager.positions.values():
            if pos.symbol == symbol and pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]:
                return True

        return False

    def _get_active_positions(self) -> List[Dict[str, Any]]:
        """Get list of active positions with current P&L."""
        if not self.position_manager:
            return []

        positions = []
        for pos in self.position_manager.positions.values():
            if pos.status not in [PositionStatus.OPEN, PositionStatus.PARTIAL]:
                continue

            current_price = self._price_cache.get(pos.symbol, pos.entry_price)
            pos.update_unrealized_pnl(current_price)

            positions.append(
                {
                    "position_id": pos.position_id,
                    "symbol": pos.symbol,
                    "direction": pos.direction,
                    "entry_price": pos.entry_price,
                    "current_price": current_price,
                    "quantity": pos.quantity,
                    "remaining_quantity": pos.remaining_quantity,
                    "stop_loss": pos.stop_loss,
                    "targets_remaining": len(pos.targets),
                    "targets_hit": len(pos.targets_hit),
                    "unrealized_pnl": pos.unrealized_pnl,
                    "unrealized_pnl_pct": pos.pnl_percentage,
                    "breakeven_active": pos.breakeven_active,
                    "trailing_active": pos.trailing_active,
                    "opened_at": pos.created_at.isoformat(),
                }
            )

        return positions

    async def _sync_closed_positions(self):
        """Check for positions that have been closed and record them."""
        if not self.position_manager:
            return

        for pos in list(self.position_manager.positions.values()):
            if pos.status in [
                PositionStatus.CLOSED,
                PositionStatus.STOPPED_OUT,
                PositionStatus.EMERGENCY_EXIT,
            ]:
                # Check if already recorded
                existing = [t for t in self.completed_trades if t.trade_id == pos.position_id]
                if existing:
                    continue

                # Record completed trade
                exit_reason = "target" if pos.status == PositionStatus.CLOSED else "stop_loss"
                if pos.status == PositionStatus.EMERGENCY_EXIT:
                    exit_reason = "emergency"

                trade = CompletedTrade(
                    trade_id=pos.position_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    entry_price=pos.entry_price,
                    exit_price=self._price_cache.get(pos.symbol, pos.entry_price),
                    quantity=pos.quantity,
                    entry_time=pos.created_at,
                    exit_time=pos.updated_at,
                    pnl=pos.total_pnl,
                    pnl_pct=pos.pnl_percentage,
                    exit_reason=exit_reason,
                    targets_hit=[i for i, _ in enumerate(pos.targets_hit)],
                    max_favorable=0.0,  # Would track during position
                    max_adverse=0.0,
                )

                self.completed_trades.append(trade)
                self._update_stats(trade)

                self._log_activity(
                    "trade_closed",
                    {
                        "position_id": pos.position_id,
                        "symbol": pos.symbol,
                        "direction": pos.direction,
                        "entry_price": pos.entry_price,
                        "exit_price": trade.exit_price,
                        "pnl": trade.pnl,
                        "pnl_pct": trade.pnl_pct,
                        "exit_reason": exit_reason,
                    },
                )

    async def _close_all_positions(self, reason: str):
        """Close all open positions."""
        if not self.position_manager:
            return

        for pos in list(self.position_manager.positions.values()):
            if pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]:
                current_price = self._price_cache.get(pos.symbol, pos.entry_price)
                self.position_manager.close_position(pos.position_id, reason, current_price)

        # Sync to completed trades
        await self._sync_closed_positions()

    def _update_stats(self, trade: CompletedTrade):
        """Update statistics after a trade completes."""
        self.stats.total_trades += 1

        if trade.pnl > 0:
            self.stats.winning_trades += 1
            self.stats.current_streak = (
                max(1, self.stats.current_streak + 1) if self.stats.current_streak >= 0 else 1
            )

            if self.stats.winning_trades > 0:
                self.stats.avg_win = (
                    self.stats.avg_win * (self.stats.winning_trades - 1) + trade.pnl
                ) / self.stats.winning_trades

            if trade.pnl > self.stats.best_trade:
                self.stats.best_trade = trade.pnl
        else:
            self.stats.losing_trades += 1
            self.stats.current_streak = (
                min(-1, self.stats.current_streak - 1) if self.stats.current_streak <= 0 else -1
            )

            if self.stats.losing_trades > 0:
                self.stats.avg_loss = (
                    self.stats.avg_loss * (self.stats.losing_trades - 1) + trade.pnl
                ) / self.stats.losing_trades

            if trade.pnl < self.stats.worst_trade:
                self.stats.worst_trade = trade.pnl

        self.stats.total_pnl += trade.pnl

        if self.config:
            self.stats.total_pnl_pct = (self.stats.total_pnl / self.config.initial_balance) * 100

        if self.stats.total_trades > 0:
            self.stats.win_rate = (self.stats.winning_trades / self.stats.total_trades) * 100

        if self.stats.avg_loss != 0:
            self.stats.avg_rr = abs(self.stats.avg_win / self.stats.avg_loss)

    def _log_activity(self, event_type: str, data: Dict[str, Any]):
        """Add event to activity log."""
        self.activity_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "data": data,
            }
        )

        # Keep log manageable
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-500:]

    def _get_uptime_seconds(self) -> int:
        """Get session uptime in seconds."""
        if not self.started_at:
            return 0

        end_time = self.stopped_at or datetime.now(timezone.utc)
        return int((end_time - self.started_at).total_seconds())

    def _get_price(self, symbol: str) -> float:
        """Synchronous price fetcher for position manager."""
        return self._price_cache.get(symbol, 0.0)

    async def _fetch_price(self, symbol: str) -> float:
        """Fetch current price from exchange adapter."""
        if not self.orchestrator or not self.orchestrator.adapter:
            raise ValueError("No exchange adapter available")

        try:
            ticker = self.orchestrator.adapter.get_ticker(symbol)
            return ticker.get("last", ticker.get("close", 0.0))
        except Exception as e:
            logger.error(f"Failed to fetch price for {symbol}: {e}")
            raise

    async def _execute_exit_order(self, symbol: str, side: str, quantity: float, price: float):
        """Execute exit order (called by position manager)."""
        if not self.executor:
            return

        order = self.executor.place_order(
            symbol=symbol, side=side, order_type="MARKET", quantity=quantity, price=price
        )

        self.executor.execute_market_order(order.order_id, price)


# Global instance for API endpoints
_paper_trading_service: Optional[PaperTradingService] = None


def get_paper_trading_service() -> PaperTradingService:
    """Get or create global paper trading service instance."""
    global _paper_trading_service
    if _paper_trading_service is None:
        _paper_trading_service = PaperTradingService()
    return _paper_trading_service
