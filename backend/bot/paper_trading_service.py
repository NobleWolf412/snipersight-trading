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
from pathlib import Path
import asyncio
import json
import logging
import uuid
from pathlib import Path
import time

from backend.bot.executor.paper_executor import PaperExecutor, OrderStatus, OrderType
from backend.bot.executor.position_manager import PositionManager, PositionStatus
from backend.bot.telemetry.storage import TelemetryStorage
from backend.bot.telemetry.events import TelemetryEvent, EventType
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.scanner_modes import get_mode, ScannerMode
from backend.shared.config.defaults import ScanConfig
from backend.shared.models.planner import TradePlan
from backend.data.adapters.phemex import PhemexAdapter
from backend.analysis.regime_policies import get_regime_policy
from backend.shared.utils.math_utils import round_to_lot
from backend.diagnostics.logger import DiagnosticLogger, ProbeCategory, Severity
from backend.diagnostics.report import ReportGenerator, ModeStats

logger = logging.getLogger(__name__)

# Pending order TTL by trade type. Swing limit orders targeting HTF demand zones
# may not get retested for hours; the old flat 10-min TTL was silently killing them.
_PENDING_TTL_MINUTES: Dict[str, float] = {
    "swing": 240.0,    # 4 hours
    "intraday": 60.0,  # 1 hour
    "scalp": 10.0,     # 2 scan cycles
}



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
    sniper_mode: str = "stealth"  # Fixed: stealth mode is the optimal balance for paper trading (adaptive scalp/swing)
    initial_balance: float = 10000.0
    risk_per_trade: float = 1.0  # Reduced from 2.0%: safer for automated trading (3 positions * 1% = 3% max risk)
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
    majors: bool = True
    altcoins: bool = False
    meme_mode: bool = False
    slippage_bps: float = 15.0  # Realistic for alt-crypto limit fills (was 5.0)
    fee_rate: float = 0.001
    max_hours_open: float = 72.0
    max_pending_scans: int = 2  # Cancel pending limit orders after this many scan cycles
    max_drawdown_pct: Optional[float] = 10.0  # Kill switch: stop session if peak-to-trough drawdown exceeds X%

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
    trade_type: str = "intraday"  # "scalp", "intraday", "swing"

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
            "trade_type": self.trade_type,
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
        current_streak: Current win/loss streak (positive=wins, negative=losses)
        scans_completed: Number of scanner runs
        signals_generated: Total signals from scanner
        signals_taken: Signals that passed filters and were executed
        exit_reasons: Count of trades by exit reason (target/stop_loss/stagnation/etc.)
        by_trade_type: Per-type breakdown (scalp/intraday/swing) with wins, losses,
                       win_rate, total_pnl, avg_win, avg_loss
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
    exit_reasons: Dict[str, int] = field(default_factory=dict)
    by_trade_type: Dict[str, Dict[str, Any]] = field(default_factory=dict)

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
        self.active_mode: str = "stealth"  # Current adaptive mode (e.g. overwatch)
        self.active_profile: str = "stealth"  # Current logic fusion profile (e.g. surgical)

        # Tracking
        self.completed_trades: List[CompletedTrade] = []
        self._completed_trade_ids: set = set()  # O(1) dedup for _sync_closed_positions
        self.activity_log: List[Dict[str, Any]] = []
        self.stats: PaperTradingStats = PaperTradingStats()
        self._peak_equity: float = 0.0
        self._last_drawdown_check: datetime = datetime.now(timezone.utc)

        # Session timing
        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        self.last_scan_at: Optional[datetime] = None
        self.current_scan: Optional[Dict[str, Any]] = None

        # Background task
        self._scan_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # Price cache for P&L calculations
        self._price_cache: Dict[str, float] = {}
        self._price_cache_refreshed_at: Optional[datetime] = None
        # Detailed signal processing log (every signal, not just recent activity)
        self.signal_log: List[Dict[str, Any]] = []

        # Regime state (updated each scan cycle for position sizing adjustments)
        self._current_regime_composite: str = "unknown"
        self._current_regime_score: float = 50.0
        self._current_regime_policy = None
        self._current_regime_trend: str = "sideways"
        self._current_regime_volatility: str = "normal"

        # Session log directory for persistent diagnostic output
        self._session_log_dir: Optional[Path] = None

        # Track limit orders that are waiting to fill
        self._pending_plans: Dict[str, TradePlan] = {}
        self._pending_placed_at: Dict[str, datetime] = {}

        # Diagnostics
        self.diagnostic_logger: Optional[DiagnosticLogger] = None

        # Telemetry persistence (initialized on start)
        self.telemetry_storage: Optional[TelemetryStorage] = None

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

        # Paper trading always uses stealth mode — it's the optimal balance:
        # - Covers D→5m timeframes (full range)
        # - Allows all trade types (scalp, intraday, swing) adaptively
        # - Requires solid 1.5 R:R minimum
        # - Can trade both directions (long + short)
        # If the caller requested a different mode, log it so the user knows it was overridden.
        if config.sniper_mode != "stealth":
            logger.info(
                f"Paper trading overrides sniper_mode '{config.sniper_mode}' → 'stealth'. "
                "Stealth is the only supported mode for paper trading (adaptive scalp/intraday/swing)."
            )
        config.sniper_mode = "stealth"
        self.mode = get_mode("stealth")
        if not self.mode:
            raise ValueError("Failed to load stealth mode")

        # Initialize paper executor
        self.executor = PaperExecutor(
            initial_balance=config.initial_balance,
            fee_rate=config.fee_rate,
            slippage_bps=config.slippage_bps,
            enable_partial_fills=True,  # Step 5: Enable realistic partial fills
            partial_fill_prob=0.3,      # 30% chance of a partial fill
            min_fill_pct=0.3,           # Min 30% fill
            max_fill_pct=0.7,           # Max 70% fill
        )

        # Initialize position manager
        self.position_manager = PositionManager(
            price_fetcher=self._get_price,
            order_executor=self._execute_exit_order,
            check_interval=1.0,
            breakeven_after_target=config.breakeven_after_target,
            trailing_stop_activation=config.trailing_activation,
            trailing_stop_distance=0.75,  # WAS 0.5 - increased to 0.75 to give trade more room to breathe
            max_hours_open=config.max_hours_open,
        )

        # Initialize orchestrator with exchange adapter
        try:
            adapter = PhemexAdapter()  # Default to Phemex

            # Get min_rr from mode overrides or use default
            min_rr = 1.0  # Default
            if self.mode.overrides and "min_rr_ratio" in self.mode.overrides:
                min_rr = self.mode.overrides["min_rr_ratio"]

            # Paper trading should be able to tune planner behavior without affecting
            # the main scanner. We attach a session-local PlannerConfig to this ScanConfig.
            from backend.shared.config.planner_config import PlannerConfig

            planner_cfg = PlannerConfig.defaults_for_mode("stealth")
            # Training Ground tuning:
            # - don't hard-reject on PD (use confluence + structure instead)
            # - widen stop buffers to reduce noise stop-outs
            planner_cfg.pd_compliance_required = False
            planner_cfg.stop_buffer_by_regime = {
                "calm": 0.35,
                "normal": 0.45,
                "elevated": 0.55,
                "explosive": 0.65,
            }

            # Create ScanConfig from paper trading config.
            # NOTE: use explicit None-check instead of ``or`` — a legitimate
            # override of ``min_confluence=0`` (used when forcing raw signals
            # through for diagnostics) is falsy and would otherwise silently
            # fall back to the mode default.
            _min_conf = (
                config.min_confluence
                if config.min_confluence is not None
                else self.mode.min_confluence_score
            )
            scan_config = ScanConfig(
                profile=self.mode.profile,
                timeframes=tuple(self.mode.timeframes),
                min_confluence_score=_min_conf,
                min_rr_ratio=min_rr,
                max_symbols=20,
            )
            scan_config.planner = planner_cfg
            scan_config.enable_fusion = True  # Bot uses Dynamic Logic Fusion — scanner stays on pure Stealth weights


            self.orchestrator = Orchestrator(config=scan_config, exchange_adapter=adapter)
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            raise ValueError(f"Failed to initialize scanner: {e}")

        # Reset tracking
        self.completed_trades = []
        self._completed_trade_ids = set()
        self.activity_log = []
        self.signal_log = []
        self.stats = PaperTradingStats()
        self._pending_plans = {}
        self._pending_placed_at = {}
        self._price_cache = {}
        self._peak_equity = config.initial_balance

        # Create session log directory for persistent output
        project_root = Path(__file__).parent.parent.parent
        self._session_log_dir = project_root / "logs" / "paper_trading" / f"session_{self.session_id}"
        self._session_log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize telemetry DB persistence
        try:
            self.telemetry_storage = TelemetryStorage()  # default: backend/cache/telemetry.db
        except Exception as e:
            logger.error(f"Failed to initialize telemetry storage: {e}")
            self.telemetry_storage = None

        # Start session
        self.started_at = datetime.now(timezone.utc)
        self.stopped_at = None
        self.status = PaperBotStatus.RUNNING
        self.active_mode = "stealth"
        self.active_profile = "stealth"
        self._running = True

        # Initialize diagnostics
        try:
            diagnostic_path = Path("logs/paper_trading") / f"session_{self.session_id}"
            self.diagnostic_logger = DiagnosticLogger(output_dir=diagnostic_path)
            self.diagnostic_logger.set_context(mode=config.sniper_mode)
            logger.info(f"Diagnostic logging initialized at {diagnostic_path}")
        except Exception as e:
            logger.error(f"Failed to initialize diagnostic logger: {e}")

        # Log activity
        self._log_activity(
            "session_started", {"session_id": self.session_id, "config": config.to_dict()}
        )

        # Start background tasks. Both tasks run for the lifetime of the
        # session; attach a done-callback so exceptions surface immediately
        # instead of being swallowed by the event loop.
        self._scan_task = asyncio.create_task(
            self._scan_loop(), name=f"paper_scan_loop_{self.session_id}"
        )
        self._scan_task.add_done_callback(self._task_done_callback)
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(), name=f"paper_monitor_loop_{self.session_id}"
        )
        self._monitor_task.add_done_callback(self._task_done_callback)

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

        # Generate diagnostic report
        if self.diagnostic_logger:
            try:
                diag_stats = self.diagnostic_logger.get_stats()
                mode_name = self.config.sniper_mode if self.config else "unknown"
                
                mode_stats = {
                    mode_name: ModeStats(
                        mode=mode_name,
                        trades=self.stats.total_trades,
                        wins=self.stats.winning_trades,
                        losses=self.stats.losing_trades,
                        win_rate=self.stats.win_rate,
                        avg_rr=self.stats.avg_rr,
                        total_pnl_pct=self.stats.total_pnl_pct,
                        issues_found=diag_stats["counts"]["total"],
                        critical_issues=diag_stats["counts"]["critical"],
                        warnings=diag_stats["counts"]["warning"]
                    )
                }
                
                report_gen = ReportGenerator(
                    output_dir=self.diagnostic_logger.output_dir,
                    logger=self.diagnostic_logger
                )
                
                report_path = report_gen.generate(
                    mode_stats=mode_stats,
                    regime_stats={},
                    config=self.config.to_dict() if self.config else {},
                    start_time=self.started_at or self.stopped_at,
                    end_time=self.stopped_at
                )
                
                logger.info(f"Diagnostic report generated at: {report_path}")
                self._log_activity("diagnostic_report_generated", {"path": str(report_path)})
            except Exception as e:
                logger.error(f"Failed to generate diagnostic report: {e}")

        # Log activity
        self._log_activity(
            "session_stopped", {"session_id": self.session_id, "final_stats": self.stats.to_dict()}
        )

        # Final state checkpoint before session report (captures last balance/stats)
        self._save_state()

        # Generate comprehensive session report on disk
        report_path = self._generate_session_report()
        if report_path:
            logger.info(f"Session report: {report_path}")

        logger.info(f"Paper trading stopped: session={self.session_id}")

        status = self.get_status()
        if report_path:
            status["report_path"] = str(report_path)
        return status

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
        self._completed_trade_ids = set()
        self.activity_log = []
        self.signal_log = []
        self.stats = PaperTradingStats()
        self._price_cache = {}
        self._pending_plans = {}
        self._pending_placed_at = {}

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
            "current_scan": self.current_scan,
            "active_mode": self.active_mode,
            "active_profile": self.active_profile,
            "regime": {
                "composite": self._current_regime_composite,
                "score": self._current_regime_score,
                "trend": self._current_regime_trend,
                "volatility": self._current_regime_volatility,
            },
        }

        # Active positions — must be computed first so unrealized_pnl on each
        # PositionState is refreshed from the price cache before equity is summed.
        # Previously equity was summed from pos.unrealized_pnl (set by the last
        # monitor tick) while the positions list was built from a newer cache read
        # — the two could reflect different price snapshots.
        active_positions = self._get_active_positions()
        result["positions"] = active_positions

        # Balance info
        if self.executor:
            initial = self.config.initial_balance if self.config else 0

            # Pure cash balance (executor handles fees and ALL realized PnL)
            current = self.executor.get_balance()

            # Sum unrealized PnL from PositionState — already refreshed by
            # _get_active_positions() above, so equity and positions are consistent.
            unrealized_pnl = 0.0
            if self.position_manager:
                unrealized_pnl = sum(
                    pos.unrealized_pnl
                    for pos in self.position_manager.positions.values()
                    if pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
                )

            equity = current + unrealized_pnl

            prices_age_seconds = None
            if self._price_cache_refreshed_at:
                prices_age_seconds = round(
                    (datetime.now(timezone.utc) - self._price_cache_refreshed_at).total_seconds(), 1
                )

            result["balance"] = {
                "initial": initial,
                "current": current,
                "equity": equity,
                "pnl": equity - initial,
                "pnl_pct": ((equity - initial) / initial * 100) if initial > 0 else 0,
                "prices_age_seconds": prices_age_seconds,
            }
        else:
            # Return a fully-populated schema instead of ``None`` so the
            # frontend can always read ``status.balance.equity`` without
            # null-guarding every field. Values all default to zero when
            # the bot is not running / executor is not initialized.
            initial = self.config.initial_balance if self.config else 0
            result["balance"] = {
                "initial": initial,
                "current": initial,
                "equity": initial,
                "pnl": 0.0,
                "pnl_pct": 0.0,
                "prices_age_seconds": None,
            }

        # Statistics
        result["statistics"] = self.stats.to_dict()

        # Recent activity (last 50 for better visibility)
        result["recent_activity"] = self.activity_log[-50:]

        # Pending limit orders
        result["pending_orders"] = []
        if self.executor:
            for order_id, plan in self._pending_plans.items():
                order = self.executor.get_order(order_id)
                if order and order.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
                    result["pending_orders"].append({
                        "order_id": order_id,
                        "symbol": order.symbol,
                        "direction": plan.direction,
                        "limit_price": order.price,
                        "quantity": order.quantity,
                        "filled_qty": order.filled_quantity,
                        "status": order.status.value,
                        "confluence": plan.confidence_score,
                        "trade_type": getattr(plan, "trade_type", "intraday"),
                    })

        # Signal processing log (every signal with full details)
        result["signal_log"] = self.signal_log[-100:]

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
        while self._running:
            # Re-read config each iteration so mid-session changes take effect
            config = self.config
            if not config:
                await asyncio.sleep(5)
                continue

            interval = (config.scan_interval_minutes or 5) * 60

            try:
                await self._run_scan()
            except Exception as e:
                logger.error(f"Scan error: {e}")
                self._log_activity("scan_error", {"error": str(e)})

            # Check duration limit
            if config.duration_hours > 0:
                elapsed = self._get_uptime_seconds()
                if elapsed >= config.duration_hours * 3600:
                    logger.info("Duration limit reached, stopping")
                    _stop_task = asyncio.create_task(
                        self.stop(), name="paper_stop_duration_limit"
                    )
                    _stop_task.add_done_callback(self._task_done_callback)
                    break

            # Max drawdown kill switch — use peak-to-trough (same metric as monitor loop)
            if config.max_drawdown_pct is not None:
                self._update_drawdown()  # ensure stats are fresh after each scan cycle
                if self.stats.max_drawdown >= config.max_drawdown_pct:
                    logger.warning(
                        f"Max drawdown kill switch triggered (scan loop): "
                        f"{self.stats.max_drawdown:.1f}% >= {config.max_drawdown_pct}% limit"
                    )
                    self._log_activity("session_stopped", {
                        "reason": "max_drawdown_kill_switch",
                        "drawdown_pct": round(self.stats.max_drawdown, 2),
                        "limit_pct": config.max_drawdown_pct,
                    })
                    _stop_task = asyncio.create_task(
                        self.stop(), name="paper_stop_max_drawdown_scan"
                    )
                    _stop_task.add_done_callback(self._task_done_callback)
                    break

            # Wait for next interval
            await asyncio.sleep(interval)

    async def _monitor_loop(self):
        """Background loop for monitoring positions."""
        while self._running:
            try:
                if self.position_manager:
                    # Refresh prices for all open positions before monitoring
                    await self._refresh_price_cache()

                    # Process open limit orders
                    executor = self.executor
                    if executor:
                        open_orders = executor.get_open_orders()
                        for order in open_orders:
                            if order.order_type == OrderType.LIMIT:
                                current_price = self._price_cache.get(order.symbol)
                                if current_price:
                                    fill = executor.execute_limit_order(order.order_id, current_price)
                                    if fill:
                                        # Check if this order is linked to an existing position
                                        position = self.position_manager.find_position_by_order_id(order.order_id)
                                        if position:
                                            # Add volume to existing position
                                            self.position_manager.add_position_volume(
                                                position.position_id, fill.price, fill.quantity
                                            )
                                            logger.info(
                                                f"PARTIAL FILL SYNCED: {position.symbol} +{fill.quantity:.6f} "
                                                f"| New Size: {position.quantity:.6f}"
                                            )
                                        # Handle filled orders that were waiting in _pending_plans
                                        elif order.order_id in self._pending_plans and order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                                            plan = self._pending_plans.get(order.order_id)
                                            if plan:
                                                # Re-check position cap at fill time. Multiple pending orders
                                                # can fill in the same monitor tick, bypassing the cap that
                                                # was checked when the signal was originally processed.
                                                active_count_now = len(self._get_active_positions())
                                                cap = self.config.max_positions if self.config else 3
                                                if active_count_now >= cap:
                                                    executor.cancel_order(order.order_id)
                                                    self._pending_plans.pop(order.order_id, None)
                                                    self._pending_placed_at.pop(order.order_id, None)
                                                    logger.info(
                                                        f"PENDING FILL BLOCKED (cap): {plan.symbol} "
                                                        f"| active={active_count_now}/{cap} — order cancelled"
                                                    )
                                                    self._log_activity("pending_fill_blocked", {
                                                        "order_id": order.order_id,
                                                        "symbol": plan.symbol,
                                                        "direction": plan.direction,
                                                        "reason": "max_positions_reached_at_fill",
                                                        "active_count": active_count_now,
                                                        "cap": cap,
                                                    })
                                                else:
                                                    position_id = self.position_manager.open_position(
                                                        trade_plan=plan,
                                                        entry_price=fill.price,
                                                        quantity=fill.quantity,
                                                        entry_order_id=order.order_id
                                                    )

                                                    self.stats.signals_taken += 1
                                                    logger.info(
                                                        f"PENDING ORDER FILLED: {plan.symbol} @ {fill.price:.2f} "
                                                        f"| Opening position {position_id}"
                                                    )

                                                    # Position opened — remove from pending tracking
                                                    self._pending_plans.pop(order.order_id, None)
                                                    self._pending_placed_at.pop(order.order_id, None)

                                                    self._log_activity("trade_opened", {
                                                        "position_id": position_id,
                                                        "symbol": plan.symbol,
                                                        "direction": plan.direction,
                                                        "entry_price": fill.price,
                                                        "quantity": fill.quantity,
                                                        "status": "pending_filled"
                                                    })
                                        elif not self._has_position(order.symbol) and order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                                            # This case handles orders that filled but haven't opened a position yet
                                            # (though _process_signal should handle most of these)
                                            pass

                        # Expire stale pending orders that have outlived their per-type TTL.
                        if self._pending_plans and self.config:
                            now = datetime.now(timezone.utc)
                            for order_id in list(self._pending_plans.keys()):
                                placed_at = self._pending_placed_at.get(order_id)
                                if not placed_at:
                                    continue
                                plan = self._pending_plans[order_id]
                                trade_type = getattr(plan, "trade_type", "intraday") or "intraday"
                                ttl_minutes = _PENDING_TTL_MINUTES.get(
                                    trade_type,
                                    self.config.scan_interval_minutes * self.config.max_pending_scans,
                                )
                                max_age = timedelta(minutes=ttl_minutes)
                                if (now - placed_at) > max_age:
                                    executor.cancel_order(order_id)
                                    self._pending_plans.pop(order_id, None)
                                    self._pending_placed_at.pop(order_id, None)

                                    # Ghost-position cleanup: if this order was PARTIALLY_FILLED
                                    # before expiry, the executor still holds the partial in its
                                    # positions dict. Zero it out so equity calculations don't
                                    # include an unmanaged phantom position.
                                    expired_order = executor.get_order(order_id)
                                    if (
                                        expired_order is not None
                                        and expired_order.filled_quantity > 0
                                    ):
                                        ghost_qty = executor.positions.get(plan.symbol, 0.0)
                                        if abs(ghost_qty) > 1e-9:
                                            ghost_price = self._price_cache.get(plan.symbol, 0.0)
                                            logger.warning(
                                                f"GHOST POSITION CLEANUP: {plan.symbol} "
                                                f"| partial fill {expired_order.filled_quantity:.6f} "
                                                f"from expired order {order_id} "
                                                f"| zeroing executor position {ghost_qty:.6f} "
                                                f"@ {ghost_price:.4f}"
                                            )
                                            # Settle the ghost at current market price
                                            # so balance reflects the real outcome.
                                            if ghost_price > 0:
                                                close_side = "SELL" if ghost_qty > 0 else "BUY"
                                                close_order = executor.place_order(
                                                    symbol=plan.symbol,
                                                    side=close_side,
                                                    order_type="MARKET",
                                                    quantity=abs(ghost_qty),
                                                    price=ghost_price,
                                                )
                                                executor.execute_market_order(
                                                    close_order.order_id, ghost_price
                                                )
                                            else:
                                                # No price available — force zero directly
                                                executor.positions[plan.symbol] = 0.0
                                                executor.position_avg_price[plan.symbol] = 0.0

                                    logger.info(
                                        f"PENDING ORDER EXPIRED: {plan.symbol} [{trade_type}] | "
                                        f"age={(now - placed_at).total_seconds() / 60:.1f}min "
                                        f"(ttl={ttl_minutes:.0f}min)"
                                    )
                                    self._log_activity("pending_order_expired", {
                                        "order_id": order_id,
                                        "symbol": plan.symbol,
                                        "direction": plan.direction,
                                        "trade_type": trade_type,
                                        "confluence": plan.confidence_score,
                                        "age_minutes": (now - placed_at).total_seconds() / 60,
                                        "ttl_minutes": ttl_minutes,
                                    })

                    await self.position_manager.monitor_all_positions()

                    # Check for closed positions
                    await self._sync_closed_positions()

                    # Update drawdown in real-time (every 10s) to capture open-position
                    # underwater equity, not only at trade-close time.
                    _now = datetime.now(timezone.utc)
                    if (_now - self._last_drawdown_check).total_seconds() >= 10:
                        self._update_drawdown()
                        self._last_drawdown_check = _now

                        # Check for drawdown limit
                        if (self.config
                                and self.config.max_drawdown_pct is not None
                                and self.stats.max_drawdown >= self.config.max_drawdown_pct):
                            logger.warning(
                                f"🛑 MAX DRAWDOWN LIMIT REACHED ({self.stats.max_drawdown:.2f}% >= {self.config.max_drawdown_pct}%)"
                            )
                            self._log_activity("drawdown_limit_reached", {
                                "drawdown": self.stats.max_drawdown,
                                "limit": self.config.max_drawdown_pct
                            })
                            _stop_task = asyncio.create_task(
                                self.stop(), name="paper_stop_max_drawdown_monitor"
                            )
                            _stop_task.add_done_callback(self._task_done_callback)
                            break

            except Exception as e:
                logger.error(f"Monitor error: {e}")

            await asyncio.sleep(1)  # Check every second

    async def _refresh_price_cache(self):
        """Fetch current prices for all open positions and pending orders, update the cache."""
        if not self.position_manager:
            return

        open_positions = self.position_manager.get_open_positions()
        pending_symbols = {plan.symbol for plan in self._pending_plans.values()}
        symbols = {pos.symbol for pos in open_positions} | pending_symbols

        for symbol in symbols:
            try:
                price = await self._fetch_price(symbol)
                if price > 0:
                    self._price_cache[symbol] = price
            except Exception as e:
                logger.debug(f"Price refresh failed for {symbol}: {e}")

        if symbols:
            self._price_cache_refreshed_at = datetime.now(timezone.utc)

    async def _run_scan(self):
        """Run a single scanner iteration."""
        if not self.orchestrator or not self.config or not self.mode:
            return

        conf = self.config
        assert conf is not None  # For type checker
        
        self.last_scan_at = datetime.now(timezone.utc)
        
        # Check for dynamic mode adaptation if base mode is "stealth"
        actual_scan_mode = getattr(conf, "sniper_mode", "stealth")
        if actual_scan_mode == "stealth":
            try:
                from backend.analysis.regime_detector import get_regime_detector  # type: ignore
                from backend.strategy.planner.regime_engine import get_mode_recommendation  # type: ignore
                
                detector = get_regime_detector("stealth_balanced")
                global_regime = detector.get_confirmed_regime()
                
                if global_regime and global_regime.composite != "unknown":
                    rec = get_mode_recommendation(
                        global_regime.trend, 
                        global_regime.volatility, 
                        global_regime.risk_appetite
                    )
                    recommended_mode = rec.get("mode", "stealth")
                    if recommended_mode != "stealth":
                        logger.info(
                            f"🧠 ADAPTIVE MODE: Regime is {global_regime.composite}. "
                            f"Adapting scan mode from stealth → {recommended_mode} ({rec.get('reason')})"
                        )
                        # NOTE: For paper trading, execution stays locked to STEALTH to avoid
                        # accidentally switching into stricter modes (e.g., Overwatch 78% gate)
                        # which can starve trade frequency.  actual_scan_mode is only used for
                        # display/logging — the orchestrator always scans with self.mode (stealth).
                        actual_scan_mode = recommended_mode
                        self.active_mode = actual_scan_mode
                        
                        # Set active profile for fusion visibility
                        # If recommended is Strike/Surgical, use that; otherwise stealth
                        if recommended_mode in ["strike", "surgical"]:
                           self.active_profile = recommended_mode
                        else:
                           self.active_profile = "stealth"

                        # Log the recommendation to the UI Activity Feed.
                        # Explicitly note the scan remains in stealth to avoid misleading users.
                        self._log_activity("system_update", {
                            "message": (
                                f"Regime Advisory: {recommended_mode.upper()} conditions detected "
                                f"(scan stays in STEALTH)."
                            ),
                            "details": rec.get("reason", "")
                        })
            except Exception as e:
                logger.error(f"Failed to calculate adaptive regime mode: {e}")

        self._log_activity("scan_started", {"mode": actual_scan_mode})
        self.stats.scans_completed += 1


        try:
            # Build symbol list — single code path (fixes dual-path bug)
            # Priority: user-specified symbols > category selection > defaults
            if self.config.symbols:
                # User specified exact pairs to trade (pair-of-choice feature)
                scan_symbols = list(self.config.symbols)
                logger.info(f"Using user-specified pairs: {scan_symbols}")
            else:
                # Auto-select from exchange using category toggles
                try:
                    from backend.analysis.pair_selection import select_symbols
                    limit = self.config.max_positions * 4  # Scan 4x max positions
                    scan_symbols = select_symbols(
                        adapter=self.orchestrator.exchange_adapter,
                        limit=limit,
                        majors=getattr(self.config, "majors", True),
                        altcoins=getattr(self.config, "altcoins", False),
                        meme_mode=getattr(self.config, "meme_mode", False),
                        leverage=self.config.leverage,
                        market_type=self.orchestrator.config.market_type if hasattr(self.orchestrator.config, "market_type") else "perp"
                    )
                except Exception as e:
                    logger.warning(f"Pair selection failed ({e}), using default majors")
                    scan_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]

            # Filter out excluded symbols
            if self.config.exclude_symbols:
                scan_symbols = [s for s in scan_symbols if s not in self.config.exclude_symbols]

            logger.info(f"Starting scan: {len(scan_symbols)} symbols, mode={self.config.sniper_mode}")

            self.current_scan = {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "actual_mode": actual_scan_mode,
                "completed": 0,
                "total": len(scan_symbols),
                "current_symbol": None,
                "progress_pct": 0,
                "passed": 0,
                "rejected": 0,
                "recent_symbols": []
            }

            def _progress_callback(completed: int, total: int, sym: str, passed: bool, rejection_info: Optional[Dict[str, Any]]):
                if self.current_scan is None:
                    return
                from typing import cast
                cs = cast(Dict[str, Any], self.current_scan)
                cs["completed"] = completed
                cs["total"] = total
                cs["current_symbol"] = sym
                cs["progress_pct"] = int((completed / total) * 100) if total > 0 else 0
                if passed:
                    cs["passed"] += 1
                else:
                    cs["rejected"] += 1

                # Keep last 5 symbols for the UI ticker
                status_obj = {
                    "symbol": sym,
                    "passed": passed,
                    "reason": rejection_info.get("reason", "Unknown") if rejection_info else None
                }
                
                # Log to diagnostics
                if self.diagnostic_logger:
                    category = ProbeCategory.CONF_BREAKDOWN_MISMATCH
                    if rejection_info:
                        rtype = rejection_info.get("reason_type")
                        if rtype == "low_confluence":
                            category = ProbeCategory.CONF_BREAKDOWN_MISMATCH
                        elif rtype == "risk_validation":
                            category = ProbeCategory.RISK_REJECTION_UNCLEAR
                        elif rtype == "no_data":
                            category = ProbeCategory.DATA_MISSING
                        elif rtype == "missing_critical_tf":
                            category = ProbeCategory.MTF_MISSING_CRITICAL
                    
                    if passed:
                        # Only log passed if you want verbose logs, info level
                        pass
                    else:
                        reason = rejection_info.get("reason", "Unknown") if rejection_info else "Unknown"
                        if self.diagnostic_logger:
                            from backend.diagnostics.logger import Severity
                            self.diagnostic_logger.log(
                                probe_id="SCAN_002", 
                                category=category, 
                                severity=Severity.WARNING,
                                message=f"Rejected: {sym} | {reason}", 
                                context=rejection_info,
                                symbol=sym
                            )

                recent = cs.setdefault("recent_symbols", [])  # pyre-ignore
                recent.insert(0, status_obj)
                cs["recent_symbols"] = recent[:5]  # pyre-ignore

            # Run scanner
            orch = self.orchestrator
            assert orch is not None
            orch.apply_mode(self.mode)
            
            # Apply user's custom min confluence override if specified
            if getattr(conf, "min_confluence", None) is not None:
                orch.config.min_confluence_score = conf.min_confluence
                
            loop = asyncio.get_running_loop()
            trade_plans, rejection_summary = await loop.run_in_executor(
                None,
                lambda: self.orchestrator.scan(
                    symbols=scan_symbols,
                    progress_callback=_progress_callback,
                ),
            )

            # Graduated regime filtering using RegimePolicy system
            # Instead of a nuclear veto that kills ALL signals, apply per-mode
            # policies that adjust position sizing and filter only truly chaotic regimes.
            # Use `or {}` rather than a default arg: the orchestrator explicitly packs
            # "regime": None when BTC data fails, so .get("regime", {}) would still
            # return None (key exists). `or {}` handles the None case correctly.
            regime = (rejection_summary.get("regime") if isinstance(rejection_summary, dict) else None) or {}
            regime_composite = regime.get("composite", "unknown")
            regime_score = regime.get("score", 0)

            try:
                score_val = float(regime_score)
            except (ValueError, TypeError):
                score_val = 0.0

            # Get the regime policy for current mode (defines min_score, adjustments)
            regime_policy = get_regime_policy(self.config.sniper_mode)

            # Only veto in truly extreme conditions (chaotic + very low score)
            is_extreme = regime_composite in ["chaotic_volatile"] and score_val < 20

            if is_extreme and len(trade_plans) > 0:
                logger.info(
                    f"REGIME VETO (extreme only): Market is {regime_composite} "
                    f"(Score: {regime_score}). Vetoing {len(trade_plans)} signals."
                )
                veto_reason = f"Extreme Regime Veto: {regime_composite} ({regime_score}/100)"
                for plan in trade_plans:
                    self._log_signal(plan, "filtered", veto_reason)
                trade_plans = []
            elif score_val < regime_policy.min_regime_score and len(trade_plans) > 0:
                # Below mode's minimum: log warning but DON'T veto — let position
                # sizing adjustments handle the risk reduction instead
                logger.info(
                    f"REGIME WARNING: Score {score_val:.0f} below mode min "
                    f"{regime_policy.min_regime_score:.0f} for {self.config.sniper_mode}. "
                    f"Position sizes will be reduced. Keeping {len(trade_plans)} signals."
                )

            # Store regime context for position sizing adjustments in _process_signal
            self._current_regime_composite = regime_composite
            self._current_regime_score = score_val
            self._current_regime_policy = regime_policy
            self._current_regime_trend = regime.get("trend", "sideways") if regime else "sideways"
            self._current_regime_volatility = regime.get("volatility", "normal") if regime else "normal"

            # Update open positions with latest regime data so adaptive
            # stagnation adjusts to current market conditions, not just entry-time
            self._update_position_regimes()
            
            self.stats.signals_generated += len(trade_plans)
            
            if self.current_scan:
                self.current_scan["status"] = "completed"

            # Log rejections
            rejections_details = rejection_summary.get("details", {}) if isinstance(rejection_summary, dict) else {}
            for reason_type, items in rejections_details.items():
                for item in items:
                    # Convert rejection_info to a format _log_signal understands
                    # Create unique nested objects per item to avoid shared-state corruption
                    from types import SimpleNamespace
                    
                    entry_zone = SimpleNamespace(
                        near_entry=item.get('entry_price', 0.0) or item.get('current_price', 0.0),
                        far_entry=0.0
                    )
                    
                    stop_loss = SimpleNamespace(
                        level=item.get('stop_loss', 0.0)
                    )
                    
                    mock_plan = SimpleNamespace(
                        symbol=item.get('symbol', 'Unknown'),
                        direction=item.get('direction', 'LONG'),
                        confidence_score=item.get('score', 0.0),
                        setup_type='filtered',
                        entry_zone=entry_zone,
                        stop_loss=stop_loss,
                        risk_reward=0.0
                    )
                    
                    self._log_signal(
                        mock_plan,
                        result="filtered",
                        reason=item.get('reason', f"Scanner Filter: {reason_type}"),
                        # Gate category — surfaces as badge in Signal Intelligence panel
                        reason_type=reason_type,
                        # Score vs threshold — lets the UI draw a gap bar
                        threshold=item.get('threshold'),
                        # Critical factor convergence — surface DEVELOPING/WATCHING in UI
                        setup_state=item.get('setup_state', 'NOISE'),
                        convergence_score=item.get('convergence_score', 0),
                        convergence_critical_count=item.get('convergence_critical_count', 0),
                        convergence_critical_total=item.get('convergence_critical_total', 9),
                        convergence_missing=item.get('convergence_missing', []),
                        veto_blocked=item.get('veto_blocked', False),
                        active_vetoes=item.get('active_vetoes', []),
                        # Crash traceback hint — non-empty only for 'errors' reason_type
                        traceback_hint=item.get('traceback_hint', ''),
                    )

            self._log_activity(
                "scan_completed",
                {
                    "signals_found": len(trade_plans),
                    "symbols_scanned": len(scan_symbols),
                    "rejections": len(rejections_details),
                },
            )

            # Process valid signal plans
            for plan in trade_plans:
                await self._process_signal(plan)

        except Exception as e:
            import traceback

            error_details = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Scanner error: {error_details}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._log_activity("scan_error", {"error": error_details})

    def _log_signal(self, plan: TradePlan, result: str, reason: str, **extra):
        """Record every signal's processing result for the Signal Intelligence panel."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scan_number": self.stats.scans_completed,
            "symbol": plan.symbol,
            "direction": plan.direction,
            "confluence": round(plan.confidence_score, 1),
            "setup_type": getattr(plan, "setup_type", "unknown"),
            "trade_type": getattr(plan, "trade_type", "unknown"),
            "timeframe": getattr(plan, "primary_timeframe", None) or getattr(plan, "signal_timeframe", None),
            "entry_zone": round(plan.entry_zone.near_entry, 2),
            "stop_loss": round(plan.stop_loss.level, 2),
            "rr": round(plan.risk_reward, 2) if hasattr(plan, "risk_reward") else None,
            "result": result,  # "executed", "filtered", "error"
            "reason": reason,
        }
        entry.update(extra)
        self.signal_log.append(entry)
        # Keep last 200 entries in memory for UI
        if len(self.signal_log) > 200:
            self.signal_log = self.signal_log[-200:]
        # Persist every signal to disk so nothing is lost on long runs
        if self._session_log_dir:
            try:
                with open(self._session_log_dir / "signals.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception:
                pass  # Don't let logging failure crash the bot

        # Log to diagnostics
        if self.diagnostic_logger:
            diag_sev = Severity.INFO if result == "executed" else Severity.WARNING
            # FIX: was using PLAN_RR_LOW for ALL non-executed results (including "filtered"),
            # which spammed anomalies.jsonl with 440+ false plan-quality warnings.
            # Now: executed→EXEC_SUCCESS, filtered→SIGNAL_FILTERED, other (bad R:R)→PLAN_RR_LOW
            if result == "executed":
                diag_cat = ProbeCategory.EXEC_SUCCESS
            elif result == "filtered":
                diag_cat = ProbeCategory.SIGNAL_FILTERED
            else:
                diag_cat = ProbeCategory.PLAN_RR_LOW

            self.diagnostic_logger.log(
                probe_id="SIG_001",
                category=diag_cat,
                severity=diag_sev,
                message=f"Signal {result}: {plan.symbol} ({plan.direction}) | Reason: {reason}",
                context={"plan": str(plan), "result": result, "reason": reason},
                symbol=plan.symbol
            )

    async def _process_signal(self, plan: TradePlan):
        """
        Process a trade signal and potentially execute it.

        Args:
            plan: Trade plan from scanner
        """
        # Capture core components locally for the duration of this method to prevent
        # AttributeErrors if the session is stopped/reset while processing.
        config = self.config
        executor = self.executor
        position_manager = self.position_manager

        if not config or not executor or not position_manager:
            return

        # Explicitly assert for the linter (though None-check above already covers it)
        assert executor is not None
        assert config is not None
        assert position_manager is not None



        # Check if we can take more positions.
        # Only count ACTIVE (filled) positions against the cap — pending limit orders
        # hold no capital and are already deduplicated per-symbol by Gate 3.
        # Counting pending here caused valid signals to be blocked whenever the book
        # was full of stale unfilled limits, even with zero actual exposure.
        active_count = len(self._get_active_positions())
        if active_count >= config.max_positions:
            reason = f"Max positions reached ({active_count}/{config.max_positions})"
            logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
            self._log_signal(plan, "filtered", reason)
            self._log_activity("signal_filtered", {
                "symbol": plan.symbol, "direction": plan.direction,
                "confluence": plan.confidence_score, "reason": reason,
            })
            return

        # Check if already in position for this symbol.
        # If the new signal is in the OPPOSITE direction, market structure has flipped —
        # close the active position at the current market price and fall through to take
        # the new signal. Same-direction signals are dropped (no pyramid on paper).
        if self._has_position(plan.symbol):
            existing_pos = next(
                (p for p in self.position_manager.positions.values()
                 if p.symbol == plan.symbol
                 and p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]),
                None,
            )
            existing_direction = getattr(existing_pos, "direction", None) if existing_pos else None
            direction_flipped = existing_direction is not None and existing_direction != plan.direction

            if direction_flipped and existing_pos is not None:
                # Fetch price for the close; fall back to cached price so we always have a value.
                try:
                    close_price = await self._fetch_price(plan.symbol)
                    self._price_cache[plan.symbol] = close_price
                except Exception:
                    close_price = self._price_cache.get(plan.symbol)

                # IMPORTANT: fire the exit order through the executor BEFORE
                # closing in the PositionManager so the executor's positions dict
                # and balance accounting are reconciled with the close.
                if executor and existing_pos.remaining_quantity > 0 and close_price:
                    close_side = "SELL" if existing_direction == "LONG" else "BUY"
                    try:
                        await self._execute_exit_order(
                            symbol=plan.symbol,
                            side=close_side,
                            quantity=existing_pos.remaining_quantity,
                            price=close_price,
                        )
                    except Exception as _ex:
                        logger.warning(
                            f"DIRECTION FLIP: executor close failed for {plan.symbol}: {_ex} — "
                            f"continuing with PositionManager close"
                        )

                self.position_manager.close_position(
                    existing_pos.position_id,
                    reason="direction_flip",
                    current_price=close_price,
                )
                logger.info(
                    f"DIRECTION FLIP (active): {plan.symbol} | closed {existing_direction} position "
                    f"{existing_pos.position_id} @ {close_price} | taking new {plan.direction} signal"
                )
                self._log_activity("position_closed_direction_flip", {
                    "position_id": existing_pos.position_id,
                    "symbol": plan.symbol,
                    "closed_direction": existing_direction,
                    "new_direction": plan.direction,
                    "close_price": close_price,
                    "new_confluence": plan.confidence_score,
                })
                # Fall through — continue to execute the new signal below.
            else:
                reason = "Already in position for symbol"
                logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
                self._log_signal(plan, "filtered", reason)
                self._log_activity("signal_filtered", {
                    "symbol": plan.symbol, "direction": plan.direction,
                    "confluence": plan.confidence_score, "reason": reason,
                })
                return

        # Check for existing pending orders for this symbol
        existing_order_id = next(
            (oid for oid, p in self._pending_plans.items() if p.symbol == plan.symbol), None
        )
        if existing_order_id:
            existing_plan = self._pending_plans[existing_order_id]
            direction_flipped = existing_plan.direction != plan.direction

            if direction_flipped:
                # Market structure has flipped — always cancel the stale opposite-direction
                # pending and take the new signal regardless of confluence comparison.
                logger.info(
                    f"DIRECTION FLIP: {plan.symbol} | cancelling stale {existing_plan.direction} "
                    f"pending ({existing_plan.confidence_score:.1f}%), taking {plan.direction} "
                    f"({plan.confidence_score:.1f}%)"
                )
                executor.cancel_order(existing_order_id)
                self._pending_plans.pop(existing_order_id, None)
                self._pending_placed_at.pop(existing_order_id, None)
                self._log_activity("pending_order_replaced", {
                    "symbol": plan.symbol,
                    "reason": "direction_flip",
                    "old_direction": existing_plan.direction,
                    "new_direction": plan.direction,
                    "old_confluence": existing_plan.confidence_score,
                    "new_confluence": plan.confidence_score,
                    "limit_price": plan.entry_zone.near_entry,
                })
            elif plan.confidence_score <= existing_plan.confidence_score:
                # Same direction, equal or lower confluence — keep existing
                reason = (
                    f"Pending order already exists with equal/higher confluence "
                    f"({existing_plan.confidence_score:.1f}% >= {plan.confidence_score:.1f}%)"
                )
                logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
                self._log_signal(plan, "filtered", reason)
                return
            else:
                # Same direction, better confluence — replace
                logger.info(
                    f"REPLACING PENDING ORDER: {plan.symbol} | "
                    f"old confluence={existing_plan.confidence_score:.1f}% → "
                    f"new confluence={plan.confidence_score:.1f}%"
                )
                executor.cancel_order(existing_order_id)
                self._pending_plans.pop(existing_order_id, None)
                self._pending_placed_at.pop(existing_order_id, None)
                self._log_activity("pending_order_replaced", {
                    "symbol": plan.symbol,
                    "reason": "higher_confluence",
                    "old_confluence": existing_plan.confidence_score,
                    "new_confluence": plan.confidence_score,
                    "limit_price": plan.entry_zone.near_entry,
                })

        # Check confluence threshold - use same rounding as scanner to avoid asymmetry.
        # Explicit None-check: a caller may legitimately set min_confluence=0 to
        # capture every signal for diagnostics; ``or`` would swallow that.
        min_score = (
            config.min_confluence
            if config.min_confluence is not None
            else (self.mode.min_confluence_score if self.mode else 60)
        )
        if round(plan.confidence_score, 1) < round(min_score, 1):
            reason = f"Confluence {plan.confidence_score:.1f}% below min {min_score:.0f}%"
            logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
            self._log_signal(
                plan, "filtered", reason,
                reason_type="low_confluence",
                threshold=round(min_score, 1),
            )
            self._log_activity("signal_filtered", {
                "symbol": plan.symbol, "direction": plan.direction,
                "confluence": plan.confidence_score, "reason": reason,
            })
            return

        # Calculate position size
        balance = executor.get_balance()
        position_size = self._calculate_position_size(plan)
        if position_size <= 0:
            reason = (
                f"Invalid position size (balance={balance:.2f}, "
                f"entry={plan.entry_zone.near_entry:.2f}, "
                f"stop={plan.stop_loss.level:.2f})"
            )
            # WARNING not INFO — zero size means a valid setup was silently skipped.
            # Common cause: lot_size rounding floors a small quantity to 0.
            # Operator needs to know this is happening to diagnose sizing constraints.
            logger.warning(f"⚠️ SIGNAL SKIPPED (zero size): {plan.symbol} {plan.direction} | {reason}")
            self._log_signal(plan, "filtered", reason, balance=balance)
            self._log_activity("signal_filtered", {
                "symbol": plan.symbol, "direction": plan.direction,
                "confluence": plan.confidence_score, "reason": reason,
            })
            return


        # Get current price
        try:
            current_price = await self._fetch_price(plan.symbol)
            self._price_cache[plan.symbol] = current_price
            if current_price <= 0:
                raise ValueError("Price is zero or negative")
        except Exception as e:
            reason = f"Price fetch failed: {e}"
            logger.error(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
            self._log_signal(plan, "filtered", reason)
            self._log_activity("signal_filtered", {
                "symbol": plan.symbol, "direction": plan.direction,
                "confluence": plan.confidence_score, "reason": reason,
            })
            return

        # If entry is far from price and unlikely to be reached, don't clog the book with
        # low-probability pending limits. This directly improves trade frequency/quality:
        # - fewer “12h → 1 pending that never fills”
        # - frees slots for intraday/scalp setups that are actually reachable
        try:
            # Note: TradePlan.metadata defaults to ``{}`` (empty dict, falsy),
            # so a truthy check silently skips lookups on plans that simply
            # happen to carry no metadata yet. Use an explicit isinstance
            # check so an empty dict is still probed (and returns None
            # naturally via .get).
            pullback_prob = None
            _meta = getattr(plan, "metadata", None)
            if isinstance(_meta, dict):
                pullback_prob = _meta.get("pullback_probability")
            if pullback_prob is None:
                # Backward compat: some plans may carry it on the entry_zone
                pullback_prob = getattr(plan.entry_zone, "pullback_probability", None)

            # Determine if the placed limit would be fillable right now.
            side = "BUY" if plan.direction == "LONG" else "SELL"
            limit_price = float(plan.entry_zone.near_entry)
            would_fill_now = (current_price <= limit_price) if side == "BUY" else (current_price >= limit_price)

            # If it won't fill now and probability is low, skip instead of placing.
            if not would_fill_now and pullback_prob is not None:
                try:
                    pb = float(pullback_prob)
                except (TypeError, ValueError):
                    pb = None

                if pb is not None and pb < 0.45:
                    reason = f"Low pullback probability ({pb:.2f}) for limit entry @ {limit_price:.4f} (price={current_price:.4f})"
                    logger.info(f"SIGNAL FILTERED: {plan.symbol} {plan.direction} | {reason}")
                    self._log_signal(plan, "filtered", reason)
                    self._log_activity("signal_filtered", {
                        "symbol": plan.symbol,
                        "direction": plan.direction,
                        "confluence": plan.confidence_score,
                        "reason": reason,
                    })
                    return
        except Exception as _e:
            # Never let heuristics block execution; fall back to original behavior.
            pass

        # Execute entry
        try:
            side = "BUY" if plan.direction == "LONG" else "SELL"

            # Use LIMIT to allow the executor to simulate realistic partial fills
            order = executor.place_order(
                symbol=plan.symbol,
                side=side,
                order_type="LIMIT",
                quantity=position_size,
                price=plan.entry_zone.near_entry,
            )


            # Because the EntryEngine caps near_entry to current_price, this will immediately evaluate
            fill = executor.execute_limit_order(order.order_id, current_price)

            if fill and order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                # Open position in manager using the ACTUALLY filled quantity
                position_id = position_manager.open_position(
                    trade_plan=plan, 
                    entry_price=fill.price, 
                    quantity=fill.quantity,
                    entry_order_id=order.order_id
                )


                self.stats.signals_taken += 1
                
                # ... already handled by immediate fill logic ...

                logger.info(
                    f"TRADE OPENED: {plan.symbol} {plan.direction} @ {fill.price:.2f} "
                    f"| qty={fill.quantity:.6f} (Requested: {position_size:.6f}) | SL={plan.stop_loss.level:.2f} "
                    f"| confluence={plan.confidence_score:.1f}%"
                )
                self._log_signal(
                    plan, "executed", "Trade opened successfully",
                    fill_price=fill.price, fill_qty=fill.quantity,
                    position_id=position_id,
                )
                self._log_activity("trade_opened", {
                    "position_id": position_id,
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "entry_price": fill.price,
                    "quantity": fill.quantity,
                    "stop_loss": plan.stop_loss.level,
                    "targets": [t.level for t in plan.targets],
                    "confluence": plan.confidence_score,
                    "trade_type": getattr(plan, "trade_type", "unknown"),
                })
                self._save_state()
            else:
                order_status = order.status.value if order.status else "unknown"
                reason = (
                    f"Waiting for limit fill (price={current_price:.2f}, "
                    f"limit={plan.entry_zone.near_entry:.2f})"
                )
                logger.info(
                    f"PENDING ORDER: {plan.symbol} {plan.direction} | {reason}"
                )
                self._log_signal(plan, "pending", reason, order_status=order_status)
                self._log_activity("pending_order_placed", {
                    "order_id": order.order_id,
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "confluence": plan.confidence_score,
                    "limit_price": plan.entry_zone.near_entry,
                    "current_price": current_price,
                })

                # Keep the plan so _monitor_loop can pick it up if it fills later
                self._pending_plans[order.order_id] = plan
                self._pending_placed_at[order.order_id] = datetime.now(timezone.utc)

        except Exception as e:
            import traceback
            reason = f"Execution error: {type(e).__name__}: {e}"
            logger.error(f"SIGNAL ERROR: {plan.symbol} {plan.direction} | {reason}")
            logger.error(traceback.format_exc())
            self._log_signal(plan, "error", reason)
            self._log_activity("trade_error", {"symbol": plan.symbol, "error": str(e)})

    def _update_position_regimes(self):
        """
        Update open positions with the latest regime data.

        This ensures adaptive stagnation uses current market conditions,
        not just the regime at position entry time. A trade entered during
        a trend that later becomes choppy should have its patience reduced.
        """
        if not self.position_manager:
            return

        open_positions = self.position_manager.get_open_positions()
        for pos in open_positions:
            pos.regime_trend = self._current_regime_trend
            pos.regime_volatility = self._current_regime_volatility

    def _calculate_position_size(self, plan: TradePlan) -> float:
        """
        Calculate position size based on risk parameters with regime-aware adjustment.

        Risk is calculated correctly for leveraged positions:
        - risk_amount = balance * risk_pct (e.g., 1% of $10,000 = $100)
        - position_size = risk_amount / risk_per_unit (how many units to risk $100)
        - Leverage only affects MARGIN required, NOT risk amount
        - Regime policy adjusts position size up/down based on market conditions

        Args:
            plan: Trade plan with stop loss

        Returns:
            Position size in base currency
        """
        config = self.config
        executor = self.executor
        if not config or not executor:
            return 0.0

        balance = executor.get_balance()
        # Include unrealized P&L so we don't oversize into an existing drawdown
        if self.position_manager:
            balance += sum(
                pos.unrealized_pnl
                for pos in self.position_manager.get_open_positions()
            )
        balance = max(balance, 0.0)  # Never size off negative effective equity

        # Apply streak-based risk adaptation
        effective_risk_pct = self._get_adapted_risk_pct()
        risk_amount = balance * (effective_risk_pct / 100)

        # Calculate risk per unit
        entry = plan.entry_zone.near_entry
        stop = plan.stop_loss.level

        if entry == 0 or stop == 0:
            return 0.0

        risk_per_unit = abs(entry - stop)
        if risk_per_unit == 0:
            return 0.0

        # Base position size from risk calculation
        position_size = risk_amount / risk_per_unit

        # FIX: Leverage affects MARGIN required, not position size.
        # With 5x leverage, you need 1/5th margin but risk stays the same.
        # Do NOT multiply position_size by leverage — that was causing
        # actual risk to be leverage * intended_risk (e.g., 5x * 2% = 10%).
        # The position_size already represents the correct number of units
        # to risk exactly risk_amount dollars.

        # Apply regime-aware position size adjustment (Fix #7)
        regime_multiplier = self._get_regime_size_multiplier()
        position_size *= regime_multiplier

        # Ensure we don't exceed available balance (accounting for leverage on margin)
        # With leverage, margin required = position_value / leverage
        margin_factor = max(1, config.leverage)

        max_position_value = balance * 0.5 * margin_factor  # 50% of balance * leverage
        max_size = max_position_value / entry if entry > 0 else 0

        final_size = min(position_size, max_size)
        
        # Apply lot size rounding to align with exchange requirements
        if hasattr(plan, 'lot_size') and plan.lot_size > 0:
            final_size = round_to_lot(final_size, plan.lot_size)

        if regime_multiplier != 1.0:
            logger.info(
                f"Position sized: {plan.symbol} | risk={effective_risk_pct:.1f}% "
                f"| regime_mult={regime_multiplier:.2f} | size={final_size:.6f}"
            )

        return final_size

    def _get_adapted_risk_pct(self) -> float:
        """
        Get risk percentage adapted by recent win/loss streak.

        Reduces risk after consecutive losses, increases slightly after wins.
        This prevents the bot from bleeding out during drawdowns.

        Returns:
            Adjusted risk percentage
        """
        if not self.config:
            return 1.0

        base_risk = self.config.risk_per_trade
        streak = self.stats.current_streak

        if streak <= -3:
            # 3+ consecutive losses: cut risk to 50%
            adapted = base_risk * 0.5
            logger.info(f"RISK ADAPTED: Losing streak {streak}, risk reduced {base_risk:.1f}% → {adapted:.1f}%")
            return adapted
        elif streak <= -2:
            # 2 consecutive losses: cut risk to 75%
            adapted = base_risk * 0.75
            return adapted
        # NOTE: Winning streak risk increase removed.
        # Crypto winning streaks often precede mean-reversion / regime flips.
        # Sizing up into a hot streak adds correlated exposure at the worst time.

        return base_risk

    def _get_regime_size_multiplier(self) -> float:
        """
        Get position size multiplier based on current regime and mode policy.

        Uses the RegimePolicy system to adjust position sizes:
        - Strong trends aligned with trade: size up
        - Choppy/sideways: size down
        - Chaotic: minimal size

        Returns:
            Multiplier (0.3 to 1.3, where 1.0 = no adjustment)
        """
        policy = getattr(self, '_current_regime_policy', None)
        composite = getattr(self, '_current_regime_composite', 'unknown')
        score = getattr(self, '_current_regime_score', 50.0)

        if not policy or not policy.position_size_adjustment:
            return 1.0

        # Try exact composite match first
        multiplier = policy.position_size_adjustment.get(composite)

        if multiplier is None:
            # Try trend-level match (extract trend from composite like "bullish_risk_on" → "up")
            trend_map = {
                "strong_up": "strong_up", "bullish": "up", "up": "up",
                "sideways": "sideways", "neutral": "sideways", "range": "sideways",
                "bearish": "down", "down": "down",
                "strong_down": "strong_down", "chaotic": "sideways",
            }
            for key, trend_key in trend_map.items():
                if key in composite.lower():
                    multiplier = policy.position_size_adjustment.get(trend_key)
                    if multiplier is not None:
                        break

        if multiplier is None:
            # Low score fallback: reduce size proportionally
            if score < 40:
                multiplier = 0.5
            elif score < 50:
                multiplier = 0.75
            else:
                multiplier = 1.0

        # Clamp to safe range
        return max(0.3, min(1.3, multiplier))

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
                    "target_pnl": pos.target_pnl,
                    "risk_pnl": pos.risk_pnl,
                    "breakeven_active": pos.breakeven_active,
                    "trailing_active": pos.trailing_active,
                    "opened_at": pos.created_at.isoformat(),
                    "tp1": pos.targets[0].level if pos.targets else (pos.targets_hit[-1].level if pos.targets_hit else 0.0),
                    "tp_final": pos.targets[-1].level if pos.targets else (pos.targets_hit[-1].level if pos.targets_hit else 0.0),
                    "trade_type": getattr(pos, "trade_type", "intraday"),
                    "initial_stop_loss": getattr(pos, "initial_stop_loss", pos.stop_loss),
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
                # Check if already recorded (O(1) set lookup)
                if pos.position_id in self._completed_trade_ids:
                    continue

                # Record completed trade
                exit_reason = pos.exit_reason or ("target" if pos.status == PositionStatus.CLOSED else "stop_loss")
                if pos.status == PositionStatus.EMERGENCY_EXIT:
                    exit_reason = "emergency"

                # MFE/MAE as % of entry price.
                # highest_price and lowest_price are now tracked for all directions
                # (both initialized to entry_price in __post_init__).
                _entry = pos.entry_price
                _high = pos.highest_price or _entry
                _low = pos.lowest_price or _entry
                if pos.direction == "LONG":
                    _mfe = max(0.0, (_high - _entry) / _entry * 100) if _entry else 0.0
                    _mae = max(0.0, (_entry - _low) / _entry * 100) if _entry else 0.0
                else:  # SHORT
                    _mfe = max(0.0, (_entry - _low) / _entry * 100) if _entry else 0.0
                    _mae = max(0.0, (_high - _entry) / _entry * 100) if _entry else 0.0

                trade = CompletedTrade(
                    trade_id=pos.position_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    entry_price=pos.entry_price,
                    exit_price=pos.exit_price or self._price_cache.get(pos.symbol, pos.entry_price),
                    quantity=pos.quantity,
                    entry_time=pos.created_at,
                    exit_time=pos.updated_at,
                    pnl=pos.total_pnl,
                    pnl_pct=pos.pnl_percentage,
                    exit_reason=exit_reason,
                    targets_hit=[i for i, _ in enumerate(pos.targets_hit)],
                    max_favorable=_mfe,
                    max_adverse=_mae,
                    trade_type=getattr(pos, "trade_type", "intraday"),
                )

                self.completed_trades.append(trade)
                self._completed_trade_ids.add(trade.trade_id)

                # Persist trade to telemetry DB for queryable historical data
                if self.telemetry_storage:
                    try:
                        _evt_type = (
                            EventType.STOP_LOSS_HIT
                            if exit_reason == "stop_loss"
                            else EventType.POSITION_CLOSED
                        )
                        self.telemetry_storage.store_event(TelemetryEvent(
                            event_type=_evt_type,
                            timestamp=trade.exit_time or datetime.now(timezone.utc),
                            run_id=self.session_id,
                            symbol=trade.symbol,
                            data={
                                "trade_id": trade.trade_id,
                                "direction": trade.direction,
                                "entry_price": trade.entry_price,
                                "exit_price": trade.exit_price,
                                "quantity": trade.quantity,
                                "pnl": trade.pnl,
                                "pnl_pct": trade.pnl_pct,
                                "exit_reason": trade.exit_reason,
                                "trade_type": trade.trade_type,
                                "targets_hit": trade.targets_hit,
                                "max_favorable": trade.max_favorable,
                                "max_adverse": trade.max_adverse,
                            },
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to persist trade to telemetry DB: {e}")

                # CRITICAL: Remove from position manager to prevent "Zombie" active
                # positions and memory leaks. The trade is now in completed_trades.
                # Use the public, lock-guarded helper instead of mutating the
                # underlying dict directly — otherwise this races with the
                # monitor loop's iteration over get_open_positions().
                self.position_manager.remove_position(pos.position_id)
                logger.info(f"💾 Trade {pos.position_id} archived and removed from active tracking")
                self._update_stats(trade)

                # Register stop-loss cooldown in orchestrator so the symbol is
                # locked out of re-entry for _cooldown_hours. Without this call the
                # orchestrator's CooldownManager never learns about runtime stop-outs
                # (which are fired by the position_manager, not the orchestrator itself),
                # so the same broken level can be re-entered seconds later.
                if exit_reason == "stop_loss" and self.orchestrator:
                    try:
                        self.orchestrator.register_stop_out(
                            symbol=pos.symbol,
                            direction=pos.direction,
                            price=trade.exit_price or pos.entry_price,
                        )
                    except Exception as _e:
                        logger.warning(
                            f"Failed to register stop-out cooldown for {pos.symbol}: {_e}"
                        )

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
                        "trade_type": getattr(pos, "trade_type", "unknown"),
                        "regime_at_close": {
                            "trend": getattr(pos, "regime_trend", "unknown"),
                            "volatility": getattr(pos, "regime_volatility", "unknown"),
                        },
                    },
                )
                self._save_state()

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

        # --- Exit reason breakdown ---
        reason = trade.exit_reason or "unknown"
        self.stats.exit_reasons[reason] = self.stats.exit_reasons.get(reason, 0) + 1

        # --- Per-trade-type breakdown ---
        tt = trade.trade_type or "unknown"
        if tt not in self.stats.by_trade_type:
            self.stats.by_trade_type[tt] = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
            }
        bucket = self.stats.by_trade_type[tt]
        bucket["trades"] += 1
        bucket["total_pnl"] += trade.pnl
        if trade.pnl > 0:
            bucket["wins"] += 1
            bucket["avg_win"] = (
                bucket["avg_win"] * (bucket["wins"] - 1) + trade.pnl
            ) / bucket["wins"]
        else:
            bucket["losses"] += 1
            bucket["avg_loss"] = (
                bucket["avg_loss"] * (bucket["losses"] - 1) + trade.pnl
            ) / bucket["losses"]
        bucket["win_rate"] = (bucket["wins"] / bucket["trades"]) * 100

        # Update max drawdown on each trade close
        self._update_drawdown()

    def _save_state(self) -> None:
        """Write a crash-recovery checkpoint to state.json in the session log dir.

        Called after every position open/close and on session stop so that a server
        restart can show what was happening. Uses an atomic write (tmp → rename) to
        avoid a corrupt checkpoint if the process dies mid-write.

        Restoring from this file is a manual/future operation — it does not
        automatically resume the session, but it gives enough context to reconstruct
        what happened and what the final balance / open exposure was.
        """
        if not self._session_log_dir:
            return
        try:
            # Serialize open/partial positions
            positions_data = []
            if self.position_manager:
                for pos in self.position_manager.positions.values():
                    if pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]:
                        positions_data.append(asdict(pos))

            # Serialize pending orders — simplified (no full TradePlan graph needed)
            pending_data = []
            for order_id, plan in self._pending_plans.items():
                placed_at = self._pending_placed_at.get(order_id)
                pending_data.append({
                    "order_id": order_id,
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "limit_price": getattr(plan.entry_zone, "near_entry", None),
                    "stop_loss": getattr(plan.stop_loss, "level", None),
                    "targets": [
                        {"level": t.level, "percentage": t.percentage, "label": getattr(t, "label", "")}
                        for t in (plan.targets or [])
                    ],
                    "trade_type": getattr(plan, "trade_type", "intraday"),
                    "confluence": getattr(plan, "confidence_score", None),
                    "placed_at": placed_at.isoformat() if placed_at else None,
                })

            state = {
                "session_id": self.session_id,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "config": self.config.to_dict() if self.config else None,
                "balance": self.executor.get_balance() if self.executor else None,
                "stats": self.stats.to_dict(),
                "positions": positions_data,
                "pending_orders": pending_data,
            }

            state_path = self._session_log_dir / "state.json"
            tmp_path = state_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
            tmp_path.rename(state_path)

        except Exception as e:
            logger.warning(f"State checkpoint save failed: {e}")

    def _update_drawdown(self) -> None:
        """Recompute peak equity and max drawdown from current balance + unrealized PnL.

        Called both on trade close (via _update_stats) and on every monitor loop tick
        so that drawdown is captured in real-time, not only when positions close.
        """
        if not self.executor or not self.config:
            return
        # Equity = realized balance + all unrealized PnL on open/partial positions
        current_equity = self.executor.get_balance()
        if self.position_manager:
            current_equity += sum(
                pos.unrealized_pnl
                for pos in self.position_manager.positions.values()
                if pos.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
            )
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity
        elif self._peak_equity > 0:
            drawdown = (self._peak_equity - current_equity) / self._peak_equity * 100
            if drawdown > self.stats.max_drawdown:
                self.stats.max_drawdown = drawdown

    def _task_done_callback(self, task: "asyncio.Task") -> None:
        """
        Done-callback for fire-and-forget ``asyncio.create_task`` jobs.

        Without this, exceptions raised by background tasks (scan loop,
        monitor loop, self-stop triggers) are swallowed by the event loop
        and only emitted at GC time as ``Task exception was never retrieved``.
        This makes real failures invisible in the activity log / UI.
        """
        try:
            if task.cancelled():
                return
            exc = task.exception()
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.exception(f"Error reading background task result: {e}")
            return

        if exc is not None:
            task_name = getattr(task, "get_name", lambda: "<task>")()
            logger.exception(
                f"Background task {task_name!r} failed: {exc}",
                exc_info=exc,
            )
            try:
                self._log_activity(
                    "background_task_error",
                    {"task_name": task_name, "error": str(exc)},
                )
            except Exception:
                # _log_activity must never re-raise from inside a callback
                pass

    def _log_activity(self, event_type: str, data: Dict[str, Any]):
        """Add event to activity log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": data,
        }
        self.activity_log.append(entry)

        # Keep log manageable in memory
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-500:]

        # Persist to disk so nothing is lost
        if self._session_log_dir:
            try:
                with open(self._session_log_dir / "activity.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception:
                pass

    def _generate_session_report(self) -> Optional[Path]:
        """
        Generate a comprehensive diagnostic report from the live session data.

        Writes a markdown report + raw JSONL data to the session log directory.
        Designed to be AI-readable for automated investigation and fixes.
        """
        if not self._session_log_dir:
            return None

        log_dir = self._session_log_dir
        report_path = log_dir / "diagnostic_report.md"

        # --- Persist raw data files ---
        try:
            # Completed trades
            with open(log_dir / "trades.jsonl", "w", encoding="utf-8") as f:
                for trade in self.completed_trades:
                    f.write(json.dumps(trade.to_dict(), default=str) + "\n")

            # Full signal log from disk (already written incrementally)
            # signals.jsonl is already populated by _log_signal

            # Stats snapshot
            with open(log_dir / "stats.json", "w", encoding="utf-8") as f:
                json.dump(self.stats.to_dict(), f, indent=2)

            # Config
            if self.config:
                with open(log_dir / "config.json", "w", encoding="utf-8") as f:
                    json.dump(self.config.to_dict(), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to persist raw session data: {e}")

        # --- Build the markdown report ---
        try:
            lines = []
            now = datetime.now(timezone.utc)
            started = self.started_at or now
            stopped = self.stopped_at or now
            duration_h = (stopped - started).total_seconds() / 3600

            lines.append("# SniperSight Paper Trading Session Report\n")
            lines.append(f"*Session:* `{self.session_id}`  ")
            lines.append(f"*Generated:* {now.isoformat()}Z  ")
            lines.append(f"*Duration:* {duration_h:.1f} hours  ")
            lines.append(f"*Mode:* {self.config.sniper_mode if self.config else 'unknown'}\n")

            # --- Executive Summary ---
            lines.append("\n## Executive Summary\n")
            s = self.stats
            initial = self.config.initial_balance if self.config else 0
            final_equity = initial  # fallback
            if self.executor:
                unrealized = 0.0
                if self.position_manager:
                    unrealized = sum(
                        p.unrealized_pnl for p in self.position_manager.positions.values()
                        if p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
                    )
                final_equity = self.executor.get_balance() + unrealized

            pnl = final_equity - initial
            pnl_pct = (pnl / initial * 100) if initial > 0 else 0

            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Starting Balance | ${initial:,.2f} |")
            lines.append(f"| Final Equity | ${final_equity:,.2f} |")
            lines.append(f"| Net P&L | ${pnl:,.2f} ({pnl_pct:+.2f}%) |")
            lines.append(f"| Total Trades | {s.total_trades} |")
            lines.append(f"| Win Rate | {s.win_rate:.1f}% ({s.winning_trades}W / {s.losing_trades}L) |")
            lines.append(f"| Avg R:R | {s.avg_rr:.2f} |")
            lines.append(f"| Best Trade | ${s.best_trade:,.2f} |")
            lines.append(f"| Worst Trade | ${s.worst_trade:,.2f} |")
            lines.append(f"| Max Drawdown | {s.max_drawdown:.2f}% |")
            lines.append(f"| Scans Completed | {s.scans_completed} |")
            lines.append(f"| Signals Generated | {s.signals_generated} |")
            lines.append(f"| Signals Taken | {s.signals_taken} |")
            lines.append(f"| Signal Pass Rate | {(s.signals_taken / s.signals_generated * 100) if s.signals_generated > 0 else 0:.1f}% |")
            lines.append("")

            # --- Trade Log ---
            lines.append("\n## Completed Trades\n")
            if self.completed_trades:
                lines.append("| # | Symbol | Dir | Entry | Exit | P&L % | Exit Reason | Type | Duration |")
                lines.append("|---|--------|-----|-------|------|-------|-------------|------|----------|")
                for i, t in enumerate(self.completed_trades, 1):
                    dur = ""
                    if t.entry_time and t.exit_time:
                        dur_h = (t.exit_time - t.entry_time).total_seconds() / 3600
                        dur = f"{dur_h:.1f}h"
                    icon = "+" if t.pnl >= 0 else ""
                    lines.append(
                        f"| {i} | {t.symbol} | {t.direction} | "
                        f"${t.entry_price:.2f} | ${t.exit_price:.2f} | "
                        f"{icon}{t.pnl_pct:.2f}% | {t.exit_reason} | {t.trade_type} | {dur} |"
                    )
                lines.append("")
            else:
                lines.append("*No completed trades this session.*\n")

            # --- Signal Rejection Analysis ---
            lines.append("\n## Signal Rejection Analysis\n")
            # Read the full signal log from disk (not the truncated in-memory version)
            all_signals = []
            signals_file = log_dir / "signals.jsonl"
            if signals_file.exists():
                with open(signals_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            all_signals.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

            if all_signals:
                total_signals = len(all_signals)
                executed = [s for s in all_signals if s.get("result") == "executed"]
                filtered = [s for s in all_signals if s.get("result") == "filtered"]
                pending = [s for s in all_signals if s.get("result") == "pending"]

                lines.append(f"**Total signals processed:** {total_signals}  ")
                lines.append(f"**Executed:** {len(executed)} | **Filtered:** {len(filtered)} | **Pending:** {len(pending)}\n")

                # Rejection reasons breakdown
                reason_counts: Dict[str, int] = {}
                for sig in filtered:
                    reason = sig.get("reason", "unknown")
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1

                if reason_counts:
                    lines.append("### Filter Reasons\n")
                    lines.append("| Reason | Count | % of Filtered |")
                    lines.append("|--------|-------|---------------|")
                    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
                        pct = count / len(filtered) * 100 if filtered else 0
                        lines.append(f"| {reason} | {count} | {pct:.1f}% |")
                    lines.append("")

                # Rejected signals by symbol
                symbol_rejected: Dict[str, int] = {}
                for sig in filtered:
                    sym = sig.get("symbol", "?")
                    symbol_rejected[sym] = symbol_rejected.get(sym, 0) + 1
                if symbol_rejected:
                    lines.append("### Rejections by Symbol\n")
                    lines.append("| Symbol | Rejected | Executed |")
                    lines.append("|--------|----------|----------|")
                    all_symbols = set(s.get("symbol") for s in all_signals)
                    for sym in sorted(all_symbols):
                        rej = symbol_rejected.get(sym, 0)
                        exe = len([s for s in executed if s.get("symbol") == sym])
                        lines.append(f"| {sym} | {rej} | {exe} |")
                    lines.append("")
            else:
                lines.append("*No signal data recorded.*\n")

            # --- Issues & Anomalies ---
            lines.append("\n## Issues Detected During Session\n")
            # Scan activity log for errors/warnings
            activity_file = log_dir / "activity.jsonl"
            errors = []
            if activity_file.exists():
                with open(activity_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            evt = json.loads(line)
                            if evt.get("event_type") in ("scan_error", "monitor_error"):
                                errors.append(evt)
                        except json.JSONDecodeError:
                            pass

            if errors:
                lines.append(f"**{len(errors)} error events recorded:**\n")
                for err in errors[:20]:
                    ts = err.get("timestamp", "?")
                    msg = err.get("data", {}).get("error", str(err.get("data", "")))
                    lines.append(f"- `{ts}` {msg}")
                if len(errors) > 20:
                    lines.append(f"\n*... and {len(errors) - 20} more in `activity.jsonl`*")
                lines.append("")
            else:
                lines.append("No errors detected during this session.\n")

            # --- Positions Still Open at Stop ---
            lines.append("\n## Positions at Session End\n")
            if self.position_manager:
                still_open = [
                    p for p in self.position_manager.positions.values()
                    if p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
                ]
                if still_open:
                    lines.append(f"**{len(still_open)} positions were force-closed on stop:**\n")
                    for p in still_open:
                        lines.append(
                            f"- {p.symbol} {p.direction} | Entry: ${p.entry_price:.2f} | "
                            f"P&L: {p.pnl_percentage:.2f}% | Status: {p.status.value}"
                        )
                    lines.append("")
                else:
                    lines.append("All positions were closed before session end.\n")

            # --- AI Recommendations Section ---
            lines.append("\n## Recommendations for AI Investigation\n")
            lines.append(
                "Use the raw data files alongside this report for deeper analysis:\n"
            )
            lines.append(f"- `{log_dir / 'signals.jsonl'}` — Every signal processed (full history, not truncated)")
            lines.append(f"- `{log_dir / 'activity.jsonl'}` — Every lifecycle event (scans, fills, closes, errors)")
            lines.append(f"- `{log_dir / 'trades.jsonl'}` — Completed trade details with P&L")
            lines.append(f"- `{log_dir / 'stats.json'}` — Final session statistics")
            lines.append(f"- `{log_dir / 'config.json'}` — Configuration used\n")

            recs = []
            if s.total_trades == 0 and s.signals_generated > 0:
                recs.append(
                    "**Zero trades executed despite signals** — Check confluence thresholds, "
                    "risk sizing, and position limit gates. Review `signals.jsonl` for "
                    "the `reason` field on filtered signals."
                )
            if s.win_rate < 40 and s.total_trades >= 5:
                recs.append(
                    f"**Low win rate ({s.win_rate:.1f}%)** — Review entry zone quality, "
                    "stop placement, and whether trades are being opened against the trend."
                )
            if s.max_drawdown > 10:
                recs.append(
                    f"**High drawdown ({s.max_drawdown:.1f}%)** — Consider reducing risk_per_trade "
                    "or tightening position limits."
                )
            if s.signals_generated > 0 and s.signals_taken / s.signals_generated < 0.05:
                recs.append(
                    f"**Very low signal pass rate ({s.signals_taken}/{s.signals_generated})** — "
                    "Filters may be too aggressive. Check confluence gate, R:R minimum, and "
                    "trade type restrictions in `signals.jsonl`."
                )

            # Check for specific rejection patterns
            if all_signals:
                confluence_fails = len([s for s in all_signals if "confluence" in s.get("reason", "").lower()])
                if confluence_fails > len(all_signals) * 0.5:
                    recs.append(
                        f"**{confluence_fails}/{len(all_signals)} signals failed confluence** — "
                        "The min_confluence_score threshold may be too high for current market conditions."
                    )

            if recs:
                for i, rec in enumerate(recs, 1):
                    lines.append(f"{i}. {rec}")
            else:
                lines.append("No critical recommendations — session performed within expected parameters.")
            lines.append("")

            # --- Write report ---
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            logger.info(f"Session report saved: {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"Failed to generate session report: {e}")
            return None

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
        """Fetch current price from exchange adapter, falling back to OHLCV cache."""
        if not self.orchestrator or not hasattr(self.orchestrator, 'exchange_adapter'):
            raise ValueError("No exchange adapter available")

        # Primary: live ticker from exchange
        try:
            ticker = self.orchestrator.exchange_adapter.fetch_ticker(symbol)
            price = ticker.get("last", ticker.get("close", 0.0))
            if price and price > 0:
                return float(price)
        except Exception as e:
            logger.warning(f"Live ticker failed for {symbol}, trying OHLCV cache: {e}")

        # Fallback: use latest close from the OHLCV cache populated during scan
        try:
            from backend.data.ohlcv_cache import get_ohlcv_cache
            cache = get_ohlcv_cache()
            for tf in ("1m", "5m", "15m", "1h"):
                df = cache.get(symbol, tf)
                if df is not None and not df.empty:
                    price = float(df["close"].iloc[-1])
                    if price > 0:
                        logger.info(f"Using OHLCV cache price for {symbol} ({tf}): {price:.4f}")
                        return price
        except Exception as e:
            logger.warning(f"OHLCV cache fallback failed for {symbol}: {e}")

        raise ValueError(f"Could not get price for {symbol} from ticker or OHLCV cache")

    async def _execute_exit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> bool:
        """
        Execute exit order (called by position manager).

        Returns True on successful fill, False on any failure. The position
        manager checks the return value to decide whether to clear the
        position state — swallowing exceptions silently here previously
        left positions in a "half-closed" state where internal bookkeeping
        thought the exit had executed but the paper executor never filled.
        """
        if not self.executor:
            logger.error(
                f"_execute_exit_order: no executor configured for {symbol} "
                f"{side} qty={quantity} price={price}"
            )
            return False

        if quantity <= 0 or price <= 0:
            logger.error(
                f"_execute_exit_order: invalid args for {symbol} "
                f"side={side} qty={quantity} price={price}"
            )
            return False

        try:
            order = self.executor.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                price=price,
            )
            if order is None:
                logger.error(
                    f"_execute_exit_order: place_order returned None for {symbol} "
                    f"side={side} qty={quantity} price={price}"
                )
                return False

            fill = self.executor.execute_market_order(order.order_id, price)
            if not fill:
                logger.error(
                    f"_execute_exit_order: execute_market_order returned falsy fill "
                    f"for {symbol} order_id={order.order_id} price={price}"
                )
                return False

            logger.info(
                f"✅ Exit order filled: {symbol} {side} qty={quantity} @ {price:.6f} "
                f"order_id={order.order_id}"
            )
            return True
        except Exception as e:
            logger.exception(
                f"_execute_exit_order failed for {symbol} side={side} "
                f"qty={quantity} price={price}: {e}"
            )
            return False


# Global instance for API endpoints
_paper_trading_service: Optional[PaperTradingService] = None


def get_paper_trading_service() -> PaperTradingService:
    """Get or create global paper trading service instance."""
    global _paper_trading_service
    if _paper_trading_service is None:
        _paper_trading_service = PaperTradingService()
    return _paper_trading_service
