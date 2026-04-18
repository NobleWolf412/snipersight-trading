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
        self._price_cache = {}
        self._pending_plans = {}
        self._pending_placed_at = {}
        self._pending_placed_price = {}
        self._pending_extended = set()
        self._last_reconcile_at = 0.0

        self.started_at = datetime.now(timezone.utc)
        self.stopped_at = None
        self._running = True
        self.status = LiveBotStatus.RUNNING

        mode_label = "DRY RUN" if config.dry_run else ("TESTNET" if config.testnet else "LIVE — REAL MONEY")
        logger.warning(f"Live trading started: session={self.session_id} mode={mode_label}")
        self._log_activity("session_started", {"session_id": self.session_id, "mode": mode_label})

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

        try:
            results = await asyncio.get_event_loop().run_in_executor(
                None, self.orchestrator.run_scan
            )
        except Exception as e:
            logger.error(f"Orchestrator scan failed: {e}")
            return

        if not results:
            return

        signals = results if isinstance(results, list) else results.get("signals", [])
        self.stats.signals_generated += len(signals)

        for plan in signals:
            try:
                await self._process_signal(plan)
            except Exception as e:
                logger.error(f"Signal processing error for {getattr(plan, 'symbol', '?')}: {e}")

    async def _process_signal(self, plan: TradePlan):
        config = self.config
        if not config or not self.executor or not self.position_manager:
            return

        symbol = plan.symbol

        # Position cap
        active_count = len(self._get_active_positions())
        if active_count >= config.max_positions:
            return

        # No duplicate positions
        if self._has_position(symbol):
            return

        # No duplicate pending orders for same symbol
        for pending_plan in self._pending_plans.values():
            if pending_plan.symbol == symbol:
                return

        # Confluence gate
        score = getattr(plan, "confidence_score", 0.0)
        _preset = (config.sensitivity_preset or "balanced").lower()
        if _preset in _SENSITIVITY_PRESETS:
            gate = config.min_confluence if config.min_confluence is not None else _SENSITIVITY_PRESETS[_preset]["gate"]
        else:
            gate = config.min_confluence if config.min_confluence is not None else 65.0

        if score < gate:
            return

        # Position sizing — use current equity
        current_price = self._price_cache.get(symbol)
        if not current_price:
            try:
                current_price = await self._fetch_price(symbol)
                self._price_cache[symbol] = current_price
            except Exception:
                return

        stop_loss = getattr(plan, "stop_loss", None)
        if not stop_loss or stop_loss <= 0:
            return

        stop_distance = abs(current_price - stop_loss)
        if stop_distance <= 0:
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
            return

        # Entry price — use OB zone midpoint or current price
        entry_targets = getattr(plan, "entry_zone", None)
        if entry_targets and len(entry_targets) >= 2:
            entry_price = (entry_targets[0] + entry_targets[1]) / 2
        else:
            entry_price = current_price

        order = self.executor.place_order(
            symbol=symbol,
            side="BUY" if plan.direction == "LONG" else "SELL",
            order_type="LIMIT",
            quantity=quantity,
            price=entry_price,
        )

        if order.status.value in ("REJECTED",):
            logger.warning(f"Order rejected for {symbol}: {order.status}")
            return

        self._pending_plans[order.order_id] = plan
        self._pending_placed_at[order.order_id] = datetime.now(timezone.utc)
        self._pending_placed_price[order.order_id] = current_price

        self._log_activity("signal_taken", {
            "symbol": symbol,
            "direction": plan.direction,
            "score": score,
            "entry": entry_price,
            "stop": stop_loss,
            "quantity": quantity,
            "order_id": order.order_id,
        })

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
        try:
            order = self.executor.place_order(symbol=symbol, side=side, order_type="MARKET", quantity=quantity, price=price)
            if order is None:
                return False
            fill = self.executor.execute_market_order(order.order_id, price)
            return fill is not None
        except Exception as e:
            logger.exception(f"Exit order failed for {symbol}: {e}")
            return False

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
            positions.append({
                "position_id": pos.position_id,
                "symbol": pos.symbol,
                "direction": pos.direction,
                "entry_price": pos.entry_price,
                "current_price": current_price,
                "quantity": pos.quantity,
                "stop_loss": pos.stop_loss,
                "unrealized_pnl": pos.unrealized_pnl,
                "unrealized_pnl_pct": pos.pnl_percentage,
                "breakeven_active": pos.breakeven_active,
                "trailing_active": pos.trailing_active,
                "opened_at": pos.created_at.isoformat(),
                "trade_type": getattr(pos, "trade_type", "intraday"),
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
