"""
Live Trading Service

Orchestrates real order execution on Phemex via LiveExecutor.
Mirrors PaperTradingService structure — same scan/monitor loops,
same PositionManager callbacks, same signal processing.
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
import time

from backend.bot.executor.live_executor import LiveExecutor
from backend.bot.executor.paper_executor import OrderStatus, OrderType
from backend.bot.executor.position_manager import PositionManager, PositionStatus
from backend.bot.paper_trading_service import (
    CompletedTrade,
    PaperTradingStats,
    _PENDING_TTL_MINUTES,
    _SENSITIVITY_PRESETS,
)
from backend.bot.trade_journal import get_trade_journal
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.live_trading_config import LiveTradingConfig, load_phemex_credentials
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.defaults import ScanConfig
from backend.shared.models.planner import TradePlan
from backend.data.adapters.phemex import PhemexAdapter
from backend.shared.utils.math_utils import round_to_lot

logger = logging.getLogger(__name__)


class LiveBotStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    KILL_SWITCHED = "kill_switched"


class LiveTradingService:
    """
    Live trading service using real Phemex orders via LiveExecutor.

    Drop-in API equivalent of PaperTradingService — same status schema,
    same endpoints, same PositionManager risk management.
    """

    def __init__(self):
        self.config: Optional[LiveTradingConfig] = None
        self.status: LiveBotStatus = LiveBotStatus.IDLE
        self.session_id: Optional[str] = None

        self.executor: Optional[LiveExecutor] = None
        self.position_manager: Optional[PositionManager] = None
        self.orchestrator: Optional[Orchestrator] = None
        self.adapter: Optional[PhemexAdapter] = None

        self.completed_trades: List[CompletedTrade] = []
        self._completed_trade_ids: set = set()
        self.activity_log: List[Dict[str, Any]] = []
        self.stats: PaperTradingStats = PaperTradingStats()
        self._peak_equity: float = 0.0

        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        self.last_scan_at: Optional[datetime] = None
        self.current_scan: Optional[Dict] = None

        self._scan_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

        self._price_cache: Dict[str, float] = {}
        self._price_cache_refreshed_at: Optional[datetime] = None
        self._pending_plans: Dict[str, TradePlan] = {}
        self._pending_placed_at: Dict[str, datetime] = {}
        self._pending_placed_price: Dict[str, float] = {}
        self._pending_extended: set = set()

        self._current_regime_composite: str = "unknown"
        self._current_regime_score: float = 50.0
        self._last_reconcile_at: float = 0.0

        self.signal_log: List[Dict[str, Any]] = []

        # Session log directory (set on start, used for persistent output)
        self._session_log_dir: Optional[Path] = None

        # Symbols with exchange-side positions/orders that pre-date this session.
        # Populated by _startup_reconcile() so _has_position() blocks double-entry.
        self._orphaned_symbols: set = set()

        # Exchange-native stop order tracking (position_id → internal order_id / level)
        self._exchange_stop_orders: Dict[str, str] = {}
        self._exchange_stop_levels: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start(self, config: LiveTradingConfig) -> Dict[str, Any]:
        if self.status == LiveBotStatus.RUNNING:
            raise ValueError("Live trading already running")

        self.config = config
        self.session_id = str(uuid.uuid4())[:8]

        # Load credentials
        api_key, api_secret = load_phemex_credentials()
        if not api_key and not config.dry_run:
            raise ValueError(
                "PHEMEX_API_KEY not set. Add it to your .env file."
            )

        # Build authenticated adapter
        self.adapter = PhemexAdapter(
            testnet=config.testnet,
            api_key=api_key,
            api_secret=api_secret,
        )

        # Create executor
        self.executor = LiveExecutor(
            adapter=self.adapter,
            fee_rate=config.fee_rate,
            max_position_size_usd=config.max_position_size_usd,
            max_total_exposure_usd=config.max_total_exposure_usd,
            min_balance_usd=config.min_balance_usd,
            dry_run=config.dry_run,
        )

        # Preflight
        preflight = self.executor.preflight_check()
        if not preflight["ok"] and not config.dry_run:
            issues = "; ".join(preflight.get("issues", []))
            raise ValueError(f"Preflight failed: {issues}")

        self._peak_equity = self.executor.get_balance()

        # Position manager — identical callbacks as paper service
        self.position_manager = PositionManager(
            price_fetcher=self._get_price,
            order_executor=self._execute_exit_order,
            check_interval=1.0,
            breakeven_after_target=config.breakeven_after_target,
            trailing_stop_activation=config.trailing_activation,
            trailing_stop_distance=0.75,
            max_hours_open=config.max_hours_open,
        )

        # Orchestrator (same as paper)
        mode = get_mode("stealth")
        if not mode:
            raise ValueError("Failed to load stealth mode")

        _preset = (config.sensitivity_preset or "balanced").lower()
        if _preset in _SENSITIVITY_PRESETS:
            _gate = _SENSITIVITY_PRESETS[_preset]["gate"]
            _floor = _SENSITIVITY_PRESETS[_preset]["floor"]
            _min_conf = config.min_confluence if config.min_confluence is not None else _gate
            _soft_floor = _floor
        else:
            _min_conf = config.min_confluence if config.min_confluence is not None else 65.0
            _soft_floor = config.confluence_soft_floor if config.confluence_soft_floor is not None else max(0.0, _min_conf - 10.0)

        scan_config = ScanConfig(
            profile=mode.profile,
            timeframes=tuple(mode.timeframes),
            min_confluence_score=_min_conf,
            confluence_soft_floor=_soft_floor,
            sensitivity_preset=_preset,
            min_rr_ratio=1.0,
            max_symbols=20,
        )
        scan_config.enable_fusion = True

        self.orchestrator = Orchestrator(config=scan_config, exchange_adapter=self.adapter)

        # Reset tracking
        self.completed_trades = []
        self._completed_trade_ids = set()
        self.activity_log = []
        self.stats = PaperTradingStats()
        self.signal_log = []
        self._session_log_dir = None
        self._orphaned_symbols = set()
        self._price_cache = {}
        self._pending_plans = {}
        self._pending_placed_at = {}
        self._pending_placed_price = {}
        self._pending_extended = set()
        self._last_reconcile_at = 0.0
        self._exchange_stop_orders = {}
        self._exchange_stop_levels = {}

        self.started_at = datetime.now(timezone.utc)
        self.stopped_at = None
        self._running = True
        self.status = LiveBotStatus.RUNNING

        # Create session log directory
        project_root = Path(__file__).parent.parent.parent
        self._session_log_dir = project_root / "logs" / "live_trading" / f"session_{self.session_id}"
        self._session_log_dir.mkdir(parents=True, exist_ok=True)

        mode_label = "DRY RUN" if config.dry_run else ("TESTNET" if config.testnet else "LIVE — REAL MONEY")
        logger.warning(f"Live trading started: session={self.session_id} mode={mode_label}")
        self._log_activity("session_started", {"session_id": self.session_id, "mode": mode_label})

        # Write session_info.json
        try:
            session_info = {
                "session_id": self.session_id,
                "started_at": self.started_at.isoformat(),
                "mode": mode_label,
                "config": config.to_dict(),
            }
            with open(self._session_log_dir / "session_info.json", "w", encoding="utf-8") as f:
                json.dump(session_info, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to write session_info.json: {e}")

        # Reconcile exchange state before first scan to prevent double-entry
        await self._startup_reconcile()

        self._scan_task = asyncio.create_task(self._scan_loop(), name=f"live_scan_{self.session_id}")
        self._scan_task.add_done_callback(self._task_done_callback)
        self._monitor_task = asyncio.create_task(self._monitor_loop(), name=f"live_monitor_{self.session_id}")
        self._monitor_task.add_done_callback(self._task_done_callback)

        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "trading_mode": mode_label,
            "balance": self.executor.get_balance(),
            "preflight": preflight,
        }

    async def stop(self) -> Dict[str, Any]:
        if self.status not in (LiveBotStatus.RUNNING, LiveBotStatus.KILL_SWITCHED):
            return {"status": self.status.value, "message": "Not running"}

        self._running = False
        self.status = LiveBotStatus.STOPPED
        self.stopped_at = datetime.now(timezone.utc)

        for task in (self._scan_task, self._monitor_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await self._close_all_positions("session_stopped")
        self._log_activity("session_stopped", {"session_id": self.session_id})
        logger.info(f"Live trading stopped: session={self.session_id}")

        # Write final session report
        if self._session_log_dir:
            try:
                with open(self._session_log_dir / "stats.json", "w", encoding="utf-8") as f:
                    json.dump(self.stats.to_dict(), f, indent=2, default=str)
                if self.config:
                    with open(self._session_log_dir / "config.json", "w", encoding="utf-8") as f:
                        json.dump(self.config.to_dict(), f, indent=2, default=str)
                stopped_at = self.stopped_at or datetime.now(timezone.utc)
                with open(self._session_log_dir / "session_info.json", "r+", encoding="utf-8") as f:
                    info = json.load(f)
                    info["stopped_at"] = stopped_at.isoformat()
                    info["duration_seconds"] = self._get_uptime_seconds()
                    f.seek(0)
                    json.dump(info, f, indent=2, default=str)
                    f.truncate()
            except Exception as e:
                logger.warning(f"Failed to write session report: {e}")

        return self.get_status()

    async def kill_switch(self) -> Dict[str, Any]:
        """Emergency stop — cancel all orders and close all positions immediately."""
        logger.critical(f"KILL SWITCH ACTIVATED — session={self.session_id}")
        self._log_activity("kill_switch_activated", {"session_id": self.session_id})

        self._running = False
        self.status = LiveBotStatus.KILL_SWITCHED

        for task in (self._scan_task, self._monitor_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Cancel all open orders on exchange
        if self.executor:
            for order in self.executor.get_open_orders():
                try:
                    self.executor.cancel_order(order.order_id)
                except Exception as e:
                    logger.error(f"Failed to cancel order {order.order_id}: {e}")

        # Close all positions
        if self.position_manager:
            self.position_manager.emergency_close_all("KILL_SWITCH")

        self.stopped_at = datetime.now(timezone.utc)
        return self.get_status()

    def reset(self) -> Dict[str, Any]:
        if self.status == LiveBotStatus.RUNNING:
            raise ValueError("Cannot reset while running. Stop first.")

        self.config = None
        self.session_id = None
        self.executor = None
        self.position_manager = None
        self.orchestrator = None
        self.adapter = None
        self.completed_trades = []
        self._completed_trade_ids = set()
        self.activity_log = []
        self.stats = PaperTradingStats()
        self.signal_log = []
        self._price_cache = {}
        self._pending_plans = {}
        self.started_at = None
        self.stopped_at = None
        self.status = LiveBotStatus.IDLE
        return {"status": "reset", "message": "Live trading reset"}

    # ------------------------------------------------------------------
    # Status / query
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        next_scan_in = None
        if self.status == LiveBotStatus.RUNNING and self.config and self.last_scan_at:
            nxt = self.last_scan_at + timedelta(seconds=self.config.scan_interval_minutes * 60)
            next_scan_in = max(0, (nxt - datetime.now(timezone.utc)).total_seconds())

        config = self.config
        trading_mode = "idle"
        if config:
            if config.dry_run:
                trading_mode = "dry_run"
            elif config.testnet:
                trading_mode = "testnet"
            else:
                trading_mode = "live"

        result: Dict[str, Any] = {
            "status": self.status.value,
            "trading_mode": trading_mode,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "uptime_seconds": self._get_uptime_seconds(),
            "config": config.to_dict() if config else None,
            "last_scan_at": self.last_scan_at.isoformat() if self.last_scan_at else None,
            "next_scan_in_seconds": next_scan_in,
            "current_scan": self.current_scan,
            "regime": {"composite": self._current_regime_composite, "score": self._current_regime_score},
        }

        active_positions = self._get_active_positions()
        result["positions"] = active_positions

        if self.executor:
            current = self.executor.get_balance()
            initial = self.executor._initial_balance
            unrealized = sum(
                pos.unrealized_pnl
                for pos in self.position_manager.positions.values()
                if pos.status in (PositionStatus.OPEN, PositionStatus.PARTIAL)
            ) if self.position_manager else 0.0
            equity = current + unrealized
            result["balance"] = {
                "initial": initial,
                "current": current,
                "equity": equity,
                "pnl": equity - initial,
                "pnl_pct": ((equity - initial) / initial * 100) if initial > 0 else 0,
            }
        else:
            result["balance"] = {"initial": 0, "current": 0, "equity": 0, "pnl": 0, "pnl_pct": 0}

        result["statistics"] = self.stats.to_dict()
        result["recent_activity"] = self.activity_log[-50:]
        result["signal_log"] = self.signal_log[-100:]
        result["pending_orders"] = []
        if self.executor:
            for order_id, plan in self._pending_plans.items():
                order = self.executor.get_order(order_id)
                if order and order.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                    result["pending_orders"].append({
                        "order_id": order_id,
                        "symbol": order.symbol,
                        "direction": plan.direction,
                        "limit_price": order.price,
                        "quantity": order.quantity,
                        "status": order.status.value,
                    })
        return result

    def get_positions(self) -> List[Dict[str, Any]]:
        return self._get_active_positions()

    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        trades = sorted(
            self.completed_trades,
            key=lambda t: t.exit_time or t.entry_time,
            reverse=True,
        )[:limit]
        return [t.to_dict() for t in trades]

    def get_activity_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.activity_log[-limit:]

    # ------------------------------------------------------------------
    # Startup reconciliation
    # ------------------------------------------------------------------

    async def _startup_reconcile(self):
        """
        Sync exchange state on session start to prevent double-entry after restart.

        Two cases handled:
        1. Orphaned limit orders — we lost the TradePlan on restart so we cannot
           manage a fill correctly. Cancel them and let the next scan re-evaluate.
        2. Orphaned open positions — register their symbols in _orphaned_symbols so
           _has_position() blocks new entries. The exchange-native stop still protects
           the position; the bot won't trail/target it but won't add to it either.
        """
        if not self.adapter or not self.executor or (self.config and self.config.dry_run):
            return

        loop = asyncio.get_running_loop()

        # ── 1. Cancel orphaned limit orders ──────────────────────────────────
        try:
            raw_orders = await loop.run_in_executor(
                None, lambda: self.adapter.exchange.fetch_open_orders()
            )
            for o in raw_orders:
                if o.get("type", "").lower() not in ("limit", "stop_market", "stop"):
                    continue
                symbol = o.get("symbol", "")
                oid = str(o.get("id", ""))
                try:
                    await loop.run_in_executor(
                        None, lambda s=symbol, i=oid: self.adapter.cancel_order(i, s)
                    )
                    logger.warning(f"Startup reconcile: cancelled orphaned order {oid} {symbol}")
                    self._log_activity("orphaned_order_cancelled", {"order_id": oid, "symbol": symbol})
                except Exception as e:
                    logger.error(f"Startup reconcile: could not cancel {oid} {symbol}: {e}")
        except Exception as e:
            logger.warning(f"Startup reconcile: could not fetch open orders: {e}")

        # ── 2. Block new entries on symbols with existing positions ───────────
        try:
            positions = await loop.run_in_executor(None, self.adapter.fetch_positions)
            for pos in positions:
                qty = float(pos.get("contracts", 0) or 0)
                if abs(qty) < 1e-6:
                    continue
                symbol = pos.get("symbol", "")
                side = pos.get("side", "long")
                entry_price = float(pos.get("entryPrice", 0) or 0)
                self._orphaned_symbols.add(symbol)
                logger.warning(
                    f"Startup reconcile: orphaned position detected — {symbol} "
                    f"{side.upper()} qty={qty:.4f} @ {entry_price:.4f}. "
                    f"Exchange-native stop still active. Bot will not add to this position."
                )
                self._log_activity("orphaned_position_detected", {
                    "symbol": symbol,
                    "side": side,
                    "quantity": qty,
                    "entry_price": entry_price,
                    "note": "Exchange stop active. No new entries will be placed.",
                })
        except Exception as e:
            logger.warning(f"Startup reconcile: could not fetch positions: {e}")

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    async def _scan_loop(self):
        while self._running:
            config = self.config
            if not config:
                await asyncio.sleep(5)
                continue

            interval = (config.scan_interval_minutes or 2) * 60

            try:
                await self._run_scan()
            except Exception as e:
                logger.error(f"Live scan error: {e}")
                self._log_activity("scan_error", {"error": str(e)})

            # Duration limit
            if config.duration_hours > 0:
                elapsed = self._get_uptime_seconds()
                if elapsed >= config.duration_hours * 3600:
                    logger.info("Live session duration limit reached")
                    asyncio.create_task(self.stop())
                    break

            # Max drawdown kill switch
            if config.max_drawdown_pct is not None and self.stats.max_drawdown >= config.max_drawdown_pct:
                logger.warning(f"Max drawdown kill switch: {self.stats.max_drawdown:.1f}%")
                asyncio.create_task(self.kill_switch())
                break

            await asyncio.sleep(interval)

    async def _monitor_loop(self):
        while self._running:
            try:
                if self.position_manager:
                    await self._refresh_price_cache()

                    executor = self.executor
                    if executor:
                        # Poll open orders for fills
                        for order in executor.get_open_orders():
                            if order.order_type == OrderType.LIMIT:
                                price = self._price_cache.get(order.symbol)
                                if price:
                                    fill = executor.execute_limit_order(order.order_id, price)
                                    if fill and order.order_id in self._pending_plans:
                                        plan = self._pending_plans[order.order_id]
                                        active_count = len(self._get_active_positions())
                                        cap = self.config.max_positions if self.config else 3
                                        if active_count >= cap:
                                            executor.cancel_order(order.order_id)
                                            self._pending_plans.pop(order.order_id, None)
                                        else:
                                            pos_id = self.position_manager.open_position(
                                                trade_plan=plan,
                                                entry_price=fill.price,
                                                quantity=fill.quantity,
                                                entry_order_id=order.order_id,
                                            )
                                            self.stats.signals_taken += 1
                                            self._pending_plans.pop(order.order_id, None)
                                            self._pending_placed_at.pop(order.order_id, None)
                                            # Place exchange-native stop immediately after entry fills
                                            await self._place_exchange_stop(pos_id, plan, fill.price, fill.quantity)
                                            self._log_activity("trade_opened", {
                                                "position_id": pos_id,
                                                "symbol": plan.symbol,
                                                "direction": plan.direction,
                                                "entry_price": fill.price,
                                            })

                        # Expire stale pending orders
                        if self._pending_plans and self.config:
                            now = datetime.now(timezone.utc)
                            for order_id in list(self._pending_plans.keys()):
                                placed_at = self._pending_placed_at.get(order_id)
                                if not placed_at:
                                    continue
                                plan = self._pending_plans[order_id]
                                trade_type = getattr(plan, "trade_type", "intraday") or "intraday"
                                ttl = timedelta(minutes=_PENDING_TTL_MINUTES.get(trade_type, 10.0))
                                if (now - placed_at) > ttl:
                                    try:
                                        executor.cancel_order(order_id)
                                    except Exception:
                                        pass
                                    self._pending_plans.pop(order_id, None)
                                    self._pending_placed_at.pop(order_id, None)
                                    logger.info(f"Pending order expired: {order_id} {plan.symbol}")

                    # Run position monitoring
                    await self.position_manager.monitor_all_positions()
                    await self._sync_exchange_stops()
                    await self._sync_closed_positions()

                    # Periodic balance reconciliation
                    if self.executor and self.config:
                        now_ts = time.monotonic()
                        if now_ts - self._last_reconcile_at >= self.config.balance_reconcile_interval:
                            self.executor.reconcile_balance()
                            self.executor.reconcile_positions()
                            self._last_reconcile_at = now_ts

                            # Auto kill switch on low balance
                            if (
                                self.config.kill_switch_enabled
                                and self.executor.get_balance() < self.config.min_balance_usd
                            ):
                                logger.critical("Balance below minimum — activating kill switch")
                                asyncio.create_task(self.kill_switch())

            except Exception as e:
                logger.error(f"Live monitor error: {e}")

            await asyncio.sleep(1.0)

    # ------------------------------------------------------------------
    # Scanning / signal processing
    # ------------------------------------------------------------------

    async def _run_scan(self):
        if not self.orchestrator or not self.config:
            return

        self.last_scan_at = datetime.now(timezone.utc)
        self.stats.scans_completed += 1
        self._log_activity("scan_started", {"scan_number": self.stats.scans_completed})

        # Build symbol list (same logic as paper trading service)
        config = self.config
        if config.symbols:
            scan_symbols = list(config.symbols)
        else:
            try:
                from backend.analysis.pair_selection import select_symbols
                limit = getattr(config, "universe_size", 20)
                scan_symbols = select_symbols(
                    adapter=self.orchestrator.exchange_adapter,
                    limit=limit,
                    majors=getattr(config, "majors", True),
                    altcoins=getattr(config, "altcoins", False),
                    meme_mode=getattr(config, "meme_mode", False),
                    leverage=config.leverage,
                )
            except Exception as e:
                logger.warning(f"Pair selection failed ({e}), using default majors")
                scan_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]

        if getattr(config, "exclude_symbols", None):
            scan_symbols = [s for s in scan_symbols if s not in config.exclude_symbols]

        self.current_scan = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed": 0,
            "total": len(scan_symbols),
            "passed": 0,
            "rejected": 0,
            "progress_pct": 0,
            "current_symbol": None,
            "recent_symbols": [],
        }

        def _progress_callback(completed: int, total: int, symbol: str, passed: bool, _extra=None):
            if self.current_scan:
                self.current_scan["completed"] = completed
                self.current_scan["current_symbol"] = symbol
                self.current_scan["progress_pct"] = (completed / total * 100) if total > 0 else 0
                if passed:
                    self.current_scan["passed"] = self.current_scan.get("passed", 0) + 1
                else:
                    self.current_scan["rejected"] = self.current_scan.get("rejected", 0) + 1
                recent = self.current_scan.get("recent_symbols", [])
                recent.append({"symbol": symbol, "passed": passed})
                self.current_scan["recent_symbols"] = recent[-12:]

        try:
            loop = asyncio.get_running_loop()
            trade_plans, rejection_summary = await loop.run_in_executor(
                None,
                lambda: self.orchestrator.scan(
                    symbols=scan_symbols,
                    progress_callback=_progress_callback,
                ),
            )
        except Exception as e:
            logger.error(f"Orchestrator scan failed: {e}")
            if self.current_scan:
                self.current_scan["status"] = "error"
            return

        # Update regime from scan result
        if isinstance(rejection_summary, dict):
            regime = (rejection_summary.get("regime") or {})
            self._current_regime_composite = regime.get("composite", "unknown")
            self._current_regime_score = regime.get("score", 50.0)

            # Log orchestrator-level rejections into signal_log (feeds Gauntlet panel)
            rejections_details = rejection_summary.get("details", {})
            for reason_type, items in rejections_details.items():
                for item in items:
                    from types import SimpleNamespace
                    mock_plan = SimpleNamespace(
                        symbol=item.get("symbol", "Unknown"),
                        direction=item.get("direction", "LONG"),
                        confidence_score=item.get("score", 0.0),
                        setup_type="filtered",
                        trade_type=item.get("trade_type", "unknown"),
                        primary_timeframe=None,
                        entry_zone=SimpleNamespace(near_entry=item.get("entry_price", 0.0) or item.get("current_price", 0.0)),
                        stop_loss=SimpleNamespace(level=item.get("stop_loss", 0.0)),
                        risk_reward=0.0,
                        conviction_class="B",
                        plan_type="SMC",
                    )
                    self._log_signal(
                        mock_plan,
                        result="filtered",
                        reason=item.get("reason", f"Scanner Filter: {reason_type}"),
                        reason_type=reason_type,
                        threshold=item.get("threshold"),
                        setup_state=item.get("setup_state", "NOISE"),
                        convergence_score=item.get("convergence_score", 0),
                        convergence_critical_count=item.get("convergence_critical_count", 0),
                        convergence_critical_total=item.get("convergence_critical_total"),
                        convergence_missing=item.get("convergence_missing"),
                        conflict_conditions=item.get("conflict_conditions", []),
                        conflict_count=item.get("conflict_count"),
                        veto_blocked=item.get("veto_blocked", False),
                        active_vetoes=item.get("active_vetoes", []),
                    )

            if self.current_scan:
                _by_reason = rejection_summary.get("by_reason", {})
                self.current_scan["rejection_funnel"] = {k: v for k, v in _by_reason.items() if isinstance(v, (int, float))}
                self.current_scan["total_scanned"] = len(scan_symbols)
                self.current_scan["total_passed"] = len(trade_plans)

        if self.current_scan:
            self.current_scan["status"] = "complete"
            self.current_scan["progress_pct"] = 100

        self.stats.signals_generated += len(trade_plans)
        logger.info(f"Live scan complete: {len(trade_plans)} signals from {len(scan_symbols)} symbols")

        for plan in trade_plans:
            try:
                await self._process_signal(plan)
            except Exception as e:
                logger.error(f"Signal processing error for {getattr(plan, 'symbol', '?')}: {e}")

    async def _process_signal(self, plan: TradePlan):
        config = self.config
        if not config or not self.executor or not self.position_manager:
            return

        symbol = plan.symbol
        score = getattr(plan, "confidence_score", 0.0)

        # Position cap
        active_count = len(self._get_active_positions())
        if active_count >= config.max_positions:
            self._log_signal(plan, "filtered", f"Max positions reached ({config.max_positions})", reason_type="max_positions")
            return

        # No duplicate positions
        if self._has_position(symbol):
            self._log_signal(plan, "filtered", f"Already have position on {symbol}", reason_type="has_position")
            return

        # No duplicate pending orders for same symbol
        for pending_plan in self._pending_plans.values():
            if pending_plan.symbol == symbol:
                self._log_signal(plan, "filtered", f"Pending order already exists for {symbol}", reason_type="pending_order")
                return

        # Confluence gate
        _preset = (config.sensitivity_preset or "balanced").lower()
        if _preset in _SENSITIVITY_PRESETS:
            gate = config.min_confluence if config.min_confluence is not None else _SENSITIVITY_PRESETS[_preset]["gate"]
        else:
            gate = config.min_confluence if config.min_confluence is not None else 65.0

        if score < gate:
            self._log_signal(plan, "filtered", f"Confluence {score:.1f} < gate {gate:.1f}", reason_type="confluence", threshold=gate)
            return

        # Position sizing — use current equity
        current_price = self._price_cache.get(symbol)
        if not current_price:
            try:
                current_price = await self._fetch_price(symbol)
                self._price_cache[symbol] = current_price
            except Exception:
                self._log_signal(plan, "filtered", f"Could not fetch price for {symbol}", reason_type="price_fetch")
                return

        sl_obj = getattr(plan, "stop_loss", None)
        stop_level = getattr(sl_obj, "level", None) if sl_obj is not None else None
        if not stop_level or stop_level <= 0:
            self._log_signal(plan, "filtered", "Invalid stop loss level", reason_type="risk_validation")
            return

        stop_distance = abs(current_price - stop_level)
        if stop_distance <= 0:
            self._log_signal(plan, "filtered", "Zero stop distance", reason_type="risk_validation")
            return

        equity = self.executor.get_equity(self._price_cache)
        risk_amount = equity * (config.risk_per_trade / 100.0)
        quantity = risk_amount / stop_distance

        # Apply lot rounding if available
        try:
            market_info = self.adapter.get_market_info(symbol) if self.adapter else {}
            lot_size = market_info.get("lot_size", 0.0)
            if lot_size > 0:
                quantity = round_to_lot(quantity, lot_size)
        except Exception:
            pass

        if quantity <= 0:
            self._log_signal(plan, "filtered", "Position size rounds to zero", reason_type="position_size")
            return

        # Check position size cap
        if hasattr(config, "max_position_size_usd") and config.max_position_size_usd:
            position_value = quantity * current_price
            if position_value > config.max_position_size_usd:
                self._log_signal(
                    plan, "filtered",
                    f"Position size ${position_value:.2f} exceeds cap ${config.max_position_size_usd:.2f}",
                    reason_type="position_size",
                )
                return

        # Entry price — use OB near_entry or current price
        ez_obj = getattr(plan, "entry_zone", None)
        near = getattr(ez_obj, "near_entry", None)
        far = getattr(ez_obj, "far_entry", None)
        if near and far:
            entry_price = (near + far) / 2
        elif near:
            entry_price = near
        else:
            entry_price = current_price

        # Stale-entry guard: if the OB entry zone has already been passed by price,
        # a limit order at entry_price would be below market (SHORT) or above market
        # (LONG) and get rejected by Phemex. Skip these — the setup has already fired.
        is_long = plan.direction == "LONG"
        if is_long and entry_price < current_price * 0.985:
            self._log_signal(plan, "filtered",
                f"Entry {entry_price:.4f} is >1.5% below market {current_price:.4f} — OB already passed",
                reason_type="risk_validation")
            return
        if not is_long and entry_price > current_price * 1.015:
            self._log_signal(plan, "filtered",
                f"Entry {entry_price:.4f} is >1.5% above market {current_price:.4f} — OB already passed",
                reason_type="risk_validation")
            return

        order = self.executor.place_order(
            symbol=symbol,
            side="BUY" if is_long else "SELL",
            order_type="LIMIT",
            quantity=quantity,
            price=entry_price,
        )

        if order.status.value in ("REJECTED",):
            logger.warning(f"Order rejected for {symbol}: {order.status}")
            self._log_signal(plan, "filtered", f"Order rejected by exchange: {order.status.value}", reason_type="errors")
            return

        self._pending_plans[order.order_id] = plan
        self._pending_placed_at[order.order_id] = datetime.now(timezone.utc)
        self._pending_placed_price[order.order_id] = current_price

        self._log_signal(plan, "pending", f"Waiting for limit fill @ {entry_price:.4f}", reason_type="pending_fill")
        self._log_activity("signal_taken", {
            "symbol": symbol,
            "direction": plan.direction,
            "score": score,
            "entry": entry_price,
            "stop": stop_level,
            "quantity": quantity,
            "order_id": order.order_id,
        })

    # ------------------------------------------------------------------
    # Signal logging (mirrors PaperTradingService._log_signal)
    # ------------------------------------------------------------------

    def _log_signal(self, plan: Any, result: str, reason: str, **extra):
        from backend.strategy.smc.sessions import get_current_kill_zone
        _now = datetime.now(timezone.utc)
        try:
            _kz_raw = get_current_kill_zone(_now)
            _kz = (_kz_raw.value if hasattr(_kz_raw, "value") else str(_kz_raw)) if _kz_raw else "no_session"
        except Exception:
            _kz = "no_session"

        ez_obj = getattr(plan, "entry_zone", None)
        sl_obj = getattr(plan, "stop_loss", None)
        entry_val = getattr(ez_obj, "near_entry", 0.0) or 0.0
        stop_val = getattr(sl_obj, "level", 0.0) or 0.0

        entry = {
            "timestamp": _now.isoformat(),
            "scan_number": self.stats.scans_completed,
            "symbol": getattr(plan, "symbol", "Unknown"),
            "direction": getattr(plan, "direction", "LONG"),
            "confluence": round(float(getattr(plan, "confidence_score", 0.0)), 1),
            "setup_type": getattr(plan, "setup_type", "unknown"),
            "trade_type": getattr(plan, "trade_type", "unknown"),
            "timeframe": getattr(plan, "primary_timeframe", None) or getattr(plan, "signal_timeframe", None),
            "entry_zone": round(float(entry_val), 6),
            "stop_loss": round(float(stop_val), 6),
            "rr": round(float(getattr(plan, "risk_reward", 0.0) or 0.0), 2),
            "result": result,
            "reason": reason,
            "conviction_class": getattr(plan, "conviction_class", "B"),
            "plan_type": getattr(plan, "plan_type", "SMC"),
            "regime": self._current_regime_composite,
            "pullback_probability": 0.0,
            "kill_zone": _kz,
        }
        entry.update(extra)
        self.signal_log.append(entry)
        if len(self.signal_log) > 200:
            self.signal_log = self.signal_log[-200:]
        if self._session_log_dir:
            try:
                with open(self._session_log_dir / "signals.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_price(self, symbol: str) -> float:
        return self._price_cache.get(symbol, 0.0)

    async def _fetch_price(self, symbol: str) -> float:
        if not self.orchestrator or not hasattr(self.orchestrator, "exchange_adapter"):
            raise ValueError("No exchange adapter")
        ticker = self.orchestrator.exchange_adapter.fetch_ticker(symbol)
        price = ticker.get("last", ticker.get("close", 0.0))
        if price and price > 0:
            return float(price)
        raise ValueError(f"Could not get price for {symbol}")

    async def _execute_exit_order(self, symbol: str, side: str, quantity: float, price: float) -> bool:
        if not self.executor:
            return False
        if quantity <= 0 or price <= 0:
            return False

        # Cancel exchange-native stop before firing software market exit to avoid double-close
        if self.position_manager:
            for pos in self.position_manager.get_open_positions():
                if pos.symbol == symbol:
                    await self._cancel_exchange_stop(pos.position_id)
                    break

        try:
            order = self.executor.place_order(symbol=symbol, side=side, order_type="MARKET", quantity=quantity, price=price)
            if order is None:
                return False
            fill = self.executor.execute_market_order(order.order_id, price)
            return fill is not None
        except Exception as e:
            logger.exception(f"Exit order failed for {symbol}: {e}")
            return False

    async def _place_exchange_stop(
        self, position_id: str, plan: "TradePlan", entry_price: float, quantity: float
    ):
        """Place a native stop-market on Phemex immediately after an entry fills."""
        if not self.executor:
            return
        sl_obj = getattr(plan, "stop_loss", None)
        stop_level = getattr(sl_obj, "level", None) if sl_obj is not None else None
        if not stop_level or stop_level <= 0:
            return
        stop_side = "SELL" if plan.direction == "LONG" else "BUY"
        order = self.executor.place_stop_order(
            symbol=plan.symbol,
            side=stop_side,
            quantity=quantity,
            stop_price=stop_level,
        )
        if order.status.value != "REJECTED":
            self._exchange_stop_orders[position_id] = order.order_id
            self._exchange_stop_levels[position_id] = stop_level
            self._log_activity("exchange_stop_placed", {
                "position_id": position_id,
                "symbol": plan.symbol,
                "stop_price": stop_level,
                "direction": plan.direction,
            })

    async def _sync_exchange_stops(self):
        """Detect stop level changes from PositionManager and update Phemex stop orders."""
        if not self.position_manager or not self.executor:
            return
        for pos in self.position_manager.get_open_positions():
            pid = pos.position_id
            current_stop = pos.stop_loss
            if not current_stop or current_stop <= 0:
                continue
            last_stop = self._exchange_stop_levels.get(pid)
            if last_stop is None or abs(current_stop - last_stop) < 1e-8:
                continue
            # Stop level moved — cancel old exchange order and place new one
            old_order_id = self._exchange_stop_orders.get(pid)
            if old_order_id:
                try:
                    self.executor.cancel_order(old_order_id)
                except Exception as e:
                    logger.warning(f"Could not cancel old exchange stop {old_order_id}: {e}")
            stop_side = "SELL" if pos.direction == "LONG" else "BUY"
            qty = getattr(pos, "remaining_quantity", None) or pos.quantity
            order = self.executor.place_stop_order(
                symbol=pos.symbol,
                side=stop_side,
                quantity=qty,
                stop_price=current_stop,
            )
            if order.status.value != "REJECTED":
                self._exchange_stop_orders[pid] = order.order_id
                self._exchange_stop_levels[pid] = current_stop
                logger.info(
                    f"Exchange stop updated: {pos.symbol} {last_stop:.5f} → {current_stop:.5f} "
                    f"(pos={pid})"
                )
                self._log_activity("exchange_stop_updated", {
                    "position_id": pid,
                    "symbol": pos.symbol,
                    "old_stop": last_stop,
                    "new_stop": current_stop,
                })

    async def _cancel_exchange_stop(self, position_id: str):
        """Cancel Phemex native stop for a position — called before software exits."""
        order_id = self._exchange_stop_orders.pop(position_id, None)
        self._exchange_stop_levels.pop(position_id, None)
        if not order_id or not self.executor:
            return
        try:
            self.executor.cancel_order(order_id)
            logger.info(f"Exchange stop cancelled before software exit: pos={position_id}")
        except Exception as e:
            logger.warning(f"Could not cancel exchange stop {order_id} (may have already fired): {e}")

    async def _refresh_price_cache(self):
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
            except Exception:
                pass
        if symbols:
            self._price_cache_refreshed_at = datetime.now(timezone.utc)

    def _has_position(self, symbol: str) -> bool:
        # Also block entry on symbols with pre-session exchange positions/orders
        if symbol in self._orphaned_symbols:
            return True
        if not self.position_manager:
            return False
        for pos in self.position_manager.positions.values():
            if pos.symbol == symbol and pos.status in (PositionStatus.OPEN, PositionStatus.PARTIAL):
                return True
        return False

    def _get_active_positions(self) -> List[Dict[str, Any]]:
        if not self.position_manager:
            return []
        positions = []
        for pos in self.position_manager.positions.values():
            if pos.status not in (PositionStatus.OPEN, PositionStatus.PARTIAL):
                continue
            current_price = self._price_cache.get(pos.symbol, pos.entry_price)
            pos.update_unrealized_pnl(current_price)
            remaining_targets = sorted(pos.targets, key=lambda t: t.level) if pos.direction == "LONG" else sorted(pos.targets, key=lambda t: t.level, reverse=True)
            tp1 = remaining_targets[0].level if len(remaining_targets) > 0 else None
            tp2 = remaining_targets[1].level if len(remaining_targets) > 1 else None
            tp_final = remaining_targets[-1].level if len(remaining_targets) > 1 else None
            positions.append({
                "position_id": pos.position_id,
                "symbol": pos.symbol,
                "direction": pos.direction,
                "entry_price": pos.entry_price,
                "current_price": current_price,
                "quantity": pos.quantity,
                "stop_loss": pos.stop_loss,
                "initial_stop_loss": pos.initial_stop_loss,
                "unrealized_pnl": pos.unrealized_pnl,
                "unrealized_pnl_pct": pos.pnl_percentage,
                "breakeven_active": pos.breakeven_active,
                "trailing_active": pos.trailing_active,
                "opened_at": pos.created_at.isoformat(),
                "trade_type": getattr(pos, "trade_type", "intraday"),
                "tp1": tp1,
                "tp2": tp2,
                "tp_final": tp_final,
                "target_pnl": pos.target_pnl,
                "risk_pnl": pos.risk_pnl,
                "targets_hit": len(pos.targets_hit),
                "targets_remaining": len(pos.targets),
            })
        return positions

    async def _sync_closed_positions(self):
        if not self.position_manager:
            return
        for pos in list(self.position_manager.positions.values()):
            if pos.status not in (PositionStatus.CLOSED, PositionStatus.STOPPED_OUT, PositionStatus.EMERGENCY_EXIT):
                continue
            if pos.position_id in self._completed_trade_ids:
                continue

            # Clean up any remaining exchange stop (e.g. fired natively or was never cancelled)
            self._exchange_stop_orders.pop(pos.position_id, None)
            self._exchange_stop_levels.pop(pos.position_id, None)

            exit_reason = pos.exit_reason or ("target" if pos.status == PositionStatus.CLOSED else "stop_loss")
            if pos.status == PositionStatus.EMERGENCY_EXIT:
                exit_reason = "emergency"

            _entry = pos.entry_price
            _high = pos.highest_price or _entry
            _low = pos.lowest_price or _entry
            if pos.direction == "LONG":
                _mfe = max(0.0, (_high - _entry) / _entry * 100) if _entry else 0.0
                _mae = max(0.0, (_entry - _low) / _entry * 100) if _entry else 0.0
            else:
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
                confidence_score=getattr(pos, "confidence_score", 0.0),
                conviction_class=getattr(pos, "conviction_class", "B"),
                plan_type=getattr(pos, "plan_type", "SMC"),
                risk_reward_ratio=getattr(pos, "risk_reward_ratio", 0.0),
                stop_distance_atr=getattr(pos, "stop_distance_atr", 0.0),
                timeframe=getattr(pos, "timeframe", "1h"),
                regime=getattr(pos, "regime", "unknown"),
                pullback_probability=getattr(pos, "pullback_probability", 0.0),
                kill_zone=getattr(pos, "kill_zone", "no_session"),
            )

            self.completed_trades.append(trade)
            self._completed_trade_ids.add(trade.trade_id)
            self._update_stats(trade)
            if self._session_log_dir:
                try:
                    with open(self._session_log_dir / "trades.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps(trade.to_dict(), default=str) + "\n")
                except Exception:
                    pass
            self._log_activity("trade_closed", {
                "position_id": pos.position_id,
                "symbol": pos.symbol,
                "pnl": pos.total_pnl,
                "exit_reason": exit_reason,
            })

            # Write to journal
            try:
                get_trade_journal().append(trade.to_dict(), self.session_id or "live")
            except Exception as e:
                logger.warning(f"Failed to write live trade to journal: {e}")

    async def _close_all_positions(self, reason: str):
        if not self.position_manager:
            return
        for pos in self.position_manager.get_open_positions():
            try:
                self.position_manager.close_position(pos.position_id, reason)
            except Exception as e:
                logger.error(f"Failed to close position {pos.position_id}: {e}")

    def _update_stats(self, trade: CompletedTrade):
        self.stats.total_trades += 1
        if trade.pnl > 0:
            self.stats.winning_trades += 1
            self.stats.current_streak = max(1, self.stats.current_streak + 1) if self.stats.current_streak >= 0 else 1
            self.stats.avg_win = (self.stats.avg_win * (self.stats.winning_trades - 1) + trade.pnl) / self.stats.winning_trades
            self.stats.best_trade = max(self.stats.best_trade, trade.pnl)
        else:
            self.stats.losing_trades += 1
            self.stats.current_streak = min(-1, self.stats.current_streak - 1) if self.stats.current_streak <= 0 else -1
            self.stats.avg_loss = (self.stats.avg_loss * (self.stats.losing_trades - 1) + trade.pnl) / self.stats.losing_trades
            self.stats.worst_trade = min(self.stats.worst_trade, trade.pnl)

        self.stats.total_pnl += trade.pnl
        initial = self.executor._initial_balance if self.executor else 1
        self.stats.total_pnl_pct = (self.stats.total_pnl / initial * 100) if initial > 0 else 0
        if self.stats.total_trades > 0:
            self.stats.win_rate = self.stats.winning_trades / self.stats.total_trades * 100
        if self.stats.avg_loss != 0:
            self.stats.avg_rr = abs(self.stats.avg_win / self.stats.avg_loss)

        reason = trade.exit_reason or "unknown"
        self.stats.exit_reasons[reason] = self.stats.exit_reasons.get(reason, 0) + 1

        # Update max drawdown
        if self.executor:
            equity = self.executor.get_equity(self._price_cache)
            self._peak_equity = max(self._peak_equity, equity)
            if self._peak_equity > 0:
                drawdown = (self._peak_equity - equity) / self._peak_equity * 100
                self.stats.max_drawdown = max(self.stats.max_drawdown, drawdown)

    def _log_activity(self, event_type: str, data: Dict[str, Any]):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": data,
        }
        self.activity_log.append(entry)
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-500:]
        if self._session_log_dir:
            try:
                with open(self._session_log_dir / "activity.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception:
                pass

    def _get_uptime_seconds(self) -> int:
        if not self.started_at:
            return 0
        end = self.stopped_at or datetime.now(timezone.utc)
        return int((end - self.started_at).total_seconds())

    def _task_done_callback(self, task: asyncio.Task):
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"Live trading task {task.get_name()} crashed: {exc}")
            self.status = LiveBotStatus.ERROR


# Global singleton
_live_trading_service: Optional[LiveTradingService] = None


def get_live_trading_service() -> LiveTradingService:
    global _live_trading_service
    if _live_trading_service is None:
        _live_trading_service = LiveTradingService()
    return _live_trading_service
