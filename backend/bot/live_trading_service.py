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
from decimal import Decimal
from pathlib import Path
import asyncio
import json
import logging
import math
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
    _MAX_LIMIT_DISTANCE_PCT,
)
from backend.bot.trade_journal import get_trade_journal
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.live_trading_config import LiveTradingConfig, load_phemex_credentials
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.defaults import ScanConfig
from backend.shared.models.planner import TradePlan
from backend.data.adapters.phemex import PhemexAdapter
from backend.data.adapters.phemex_ws import PhemexWebSocketClient
from backend.shared.utils.math_utils import round_to_lot

logger = logging.getLogger(__name__)


class LiveBotStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    KILL_SWITCHED = "kill_switched"


class LifecycleConflict(ValueError):
    """A lifecycle command would discard execution ownership or recovery."""


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
        self._ws_task: Optional[asyncio.Task] = None
        self._backfill_task: Optional[asyncio.Task] = None
        self._ws_client: Optional[PhemexWebSocketClient] = None
        self._running = False
        self._lifecycle_busy = False
        self._phase = "idle"
        self._generation = 0
        self._shutdown_task: Optional[asyncio.Task] = None
        self._shutdown_step_task: Optional[asyncio.Task] = None
        self._shutdown_reason: Optional[str] = None
        self._account_state = "unknown"
        self._account_observed_at = None
        self._account_revision = None
        self._account_observed_monotonic = 0.0
        self._account_orders = []
        self._unmanaged_symbols = []
        self._recovery_error = None

        # Phemex fill backfill state — persisted between sessions so a restart
        # does not re-scan history from epoch.
        self._last_trade_sync_ts: Optional[int] = None
        self._backfill_metrics: Dict[str, Any] = {
            "runs_total": 0,
            "errors_total": 0,
            "rows_seen_total": 0,
            "rows_new_total": 0,
            "last_run_ts": None,
            "last_error_ts": None,
            "last_error_msg": None,
        }
        self._fills_log_path: Optional[Path] = None

        self._price_cache: Dict[str, float] = {}
        self._price_cache_observed_at: Dict[str, float] = {}
        self._price_cache_refreshed_at: Optional[datetime] = None
        self._pending_plans: Dict[str, TradePlan] = {}
        self._pending_exit_orders = {}
        self._pending_stop_orders = {}
        self._pending_placed_at: Dict[str, datetime] = {}
        self._pending_placed_price: Dict[str, float] = {}
        self._pending_extended: set = set()

        self._current_regime_composite: str = "unknown"
        self._current_regime_score: float = 50.0
        self._last_reconcile_at: float = 0.0
        self._exchange_state_known = False
        self._startup_reconciled = False

        self.signal_log: List[Dict[str, Any]] = []

        # Session log directory (set on start, used for persistent output)
        self._session_log_dir: Optional[Path] = None

        # Symbols with exchange-side positions/orders that pre-date this session.
        # Populated by _startup_reconcile() so _has_position() blocks double-entry.
        self._orphaned_symbols: set = set()

        # Exchange-native stop order tracking (position_id → internal order_id / level)
        self._exchange_stop_orders: Dict[str, str] = {}
        self._exchange_stop_levels: Dict[str, float] = {}
        self._exchange_stop_retry_at: Dict[str, float] = {}
        self._adopted_entry_orders: Dict[str, str] = {}
        # Exchange-native TP order tracking (position_id → internal order_id)
        self._exchange_tp_orders: Dict[str, str] = {}
        # Exchange-native trailing stop tracking (position_id → internal order_id)
        self._exchange_trailing_orders: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start(self, config: LiveTradingConfig) -> Dict[str, Any]:
        if self._lifecycle_busy or self._phase not in ("idle", "stopped"):
            raise LifecycleConflict("Start blocked: stop and resolve the existing session first")
        self._lifecycle_busy = True
        try:
            if self.executor:
                await self._verify_resettable()
                self.executor.close()
                self.executor = None
                self.position_manager = None
            self._phase = "starting"
            self._generation += 1
            self._account_state = "unknown"
            self._account_observed_at = None
            self._recovery_error = None
            self._shutdown_reason = None
            self._shutdown_task = None
            self._account_orders = []
            self._unmanaged_symbols = []
            result = await self._start_session(config)
            if self._phase == "recovering":
                return self.get_status()
            self._phase = "running"
            self.executor.set_entry_admission(self._entry_reconciliation_ready())
            return {**result, "lifecycle": self._lifecycle_status()}
        except BaseException:
            if self._phase == "starting":
                self._running = False
                self.status = LiveBotStatus.ERROR
                self._phase = "recovering" if self.executor else "idle"
                if self.executor:
                    self.executor.set_entry_admission(False)
            raise
        finally:
            self._lifecycle_busy = False

    async def _start_session(self, config: LiveTradingConfig) -> Dict[str, Any]:
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
            target_leverage=config.leverage,
            owner="live_service", generation=f"{self.session_id}:{self._generation}",
        )
        self.executor.set_entry_admission(False)

        # Do not construct a strategy manager over recovered account exposure.
        # The old plans are not serialized; only original request recovery is safe.
        if self.executor.recovery_snapshot().get("recovery_only"):
            return self._begin_restart_recovery("Interrupted execution session restored; strategy resumption blocked")

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
        self._price_cache_observed_at = {}
        self._price_cache_refreshed_at = None
        self._pending_plans = {}
        self._pending_exit_orders = {}
        self._pending_stop_orders = {}
        self._pending_placed_at = {}
        self._pending_placed_price = {}
        self._pending_extended = set()
        self._last_reconcile_at = 0.0
        self._exchange_state_known = False
        self._startup_reconciled = False
        self._exchange_stop_orders = {}
        self._exchange_stop_levels = {}
        self._exchange_stop_retry_at = {}
        self._adopted_entry_orders = {}
        self._exchange_tp_orders = {}
        self._exchange_trailing_orders = {}
        self._ws_task = None
        self._backfill_task = None
        self._ws_client = None

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
        if not self._entry_reconciliation_ready():
            return self._begin_restart_recovery("Startup account state requires reconciliation")
        self.executor.initialize_trading()

        self._scan_task = asyncio.create_task(self._scan_loop(), name=f"live_scan_{self.session_id}")
        generation = self._generation
        self._scan_task.add_done_callback(lambda task: self._task_done_callback(task, generation))
        self._monitor_task = asyncio.create_task(self._monitor_loop(), name=f"live_monitor_{self.session_id}")
        self._monitor_task.add_done_callback(lambda task: self._task_done_callback(task, generation))

        # Start WebSocket order feed for real-time fill detection (skipped in dry_run)
        if not config.dry_run and api_key and api_secret:
            self._ws_client = PhemexWebSocketClient(
                api_key=api_key,
                api_secret=api_secret,
                testnet=config.testnet,
                on_order_update=self.executor.apply_ws_fill,
            )
            self._ws_task = asyncio.create_task(
                self._ws_client.run(), name=f"live_ws_{self.session_id}"
            )
            self._ws_task.add_done_callback(lambda task: self._task_done_callback(task, generation))
            logger.info("Phemex WS order feed started")
        else:
            self._ws_client = None

        # Periodic Phemex fill backfill — protects against fills lost while WS was
        # disconnected or while the bot was offline. Skipped in dry_run.
        if not config.dry_run and self.adapter is not None:
            self._fills_log_path = self._session_log_dir / "phemex_fills.jsonl"
            self._load_last_trade_sync_ts()
            self._backfill_task = asyncio.create_task(
                self._backfill_loop(), name=f"live_backfill_{self.session_id}"
            )
            self._backfill_task.add_done_callback(lambda task: self._task_done_callback(task, generation))
            logger.info("Phemex fill backfill loop started (every 5 min)")

        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "trading_mode": mode_label,
            "balance": self.executor.get_balance(),
            "preflight": preflight,
        }

    async def stop(self) -> Dict[str, Any]:
        return await self._request_shutdown("session_stopped")

    def _begin_restart_recovery(self, reason):
        self._running = False
        self._phase = "recovering"
        self.status = LiveBotStatus.ERROR
        self.started_at = self.started_at or datetime.now(timezone.utc)
        self._recovery_error = reason
        self._shutdown_reason = "restart_recovery"
        self.executor.set_entry_admission(False)
        self._shutdown_task = asyncio.create_task(self._shutdown_loop(self._generation))
        return self.get_status()

    async def kill_switch(self) -> Dict[str, Any]:
        return await self._request_shutdown("kill_switch")

    async def _request_shutdown(self, reason: str) -> Dict[str, Any]:
        if self._lifecycle_busy:
            raise LifecycleConflict("Lifecycle transition in progress; retry shutdown")
        if not self.executor and self._phase == "idle":
            return self.get_status()
        # No await before admission is frozen and shutdown ownership is published.
        self._running = False
        if self.executor:
            self.executor.set_entry_admission(False)
        if reason == "kill_switch" or not self._shutdown_reason:
            self._shutdown_reason = reason
        self.status = (LiveBotStatus.KILL_SWITCHED if self._shutdown_reason == "kill_switch"
                       else LiveBotStatus.STOPPED)
        if not self._shutdown_task or self._shutdown_task.done():
            self._phase = "stopping"
            self._account_state = "unknown"
            self._log_activity("shutdown_requested", {"reason": self._shutdown_reason})
            self._shutdown_task = asyncio.create_task(self._shutdown_loop(self._generation))
        # A caller timeout/disconnect must not cancel execution recovery.
        await asyncio.wait({self._shutdown_task}, timeout=0.25)
        return self.get_status()

    async def _shutdown_loop(self, generation: int):
        try:
            for task in (self._scan_task, self._monitor_task, self._backfill_task):
                if task:
                    task.cancel()
            for task in (self._scan_task, self._monitor_task, self._backfill_task):
                if task:
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        logger.exception("Background task failed during shutdown")
            self._phase = "recovering"
            while generation == self._generation:
                try:
                    # The REST adapter is synchronous. Keep recovery IO off the
                    # API event loop; there is only one shutdown mutation owner.
                    if self._shutdown_step_task is None:
                        self._shutdown_step_task = asyncio.create_task(asyncio.to_thread(self._shutdown_step))
                    try:
                        await asyncio.shield(self._shutdown_step_task)
                    finally:
                        if self._shutdown_step_task.done():
                            self._shutdown_step_task = None
                    if (self._local_shutdown_settled() or
                            self.executor and self.executor.recovery_snapshot().get("recovery_only")):
                        await self._observe_account()
                        if self._account_state == "flat_confirmed" and self._local_shutdown_settled():
                            if self._ws_task:
                                self._ws_task.cancel()
                                try:
                                    await self._ws_task
                                except asyncio.CancelledError:
                                    pass
                            self.executor.checkpoint_flat(self._account_observed_at, self._account_revision)
                            self._phase = "stopped"
                            self.stopped_at = datetime.now(timezone.utc)
                            self._recovery_error = None
                            self._log_activity("shutdown_confirmed", {
                                "scope": "simulation" if self.config and self.config.dry_run else "phemex:swap:USDT",
                            })
                            self._write_session_report()
                            return
                except Exception as exc:
                    self._account_state = "unknown"
                    self._recovery_error = str(exc)
                    logger.exception("Shutdown recovery incomplete; retaining session")
                    self._log_activity("shutdown_recovery_required", {"reason": str(exc)})
                await asyncio.sleep(5 if not self._local_shutdown_settled() else 60)
        except asyncio.CancelledError:
            self._phase = "recovering"
            self._account_state = "unknown"
            self._recovery_error = "Recovery task interrupted; request Stop again to resume"
            raise
        except Exception as exc:
            self._phase = "recovering"
            self._account_state = "unknown"
            self._recovery_error = str(exc)
            logger.exception("Shutdown supervisor failed; session retained")

    def _shutdown_step(self):
        async def recover():
            if not self.executor:
                return
            self.executor.recover_uncertain_orders()
            for order in self.executor.get_open_orders():
                self.executor.refresh_order(order.order_id)
            for order in self.executor.get_open_entry_orders():
                self.executor.cancel_order(order.order_id)
            if self.executor.recovery_snapshot().get("recovery_only"):
                # Publish account positions, but never replay historical fills into
                # fresh strategy positions or flatten exposure of unknown ownership.
                self.executor.reconcile_positions()
                return
            await self._monitor_pending_entries()
            await self._close_all_positions(self._shutdown_reason)
            await self._sync_closed_positions()
        asyncio.run(recover())

    def _local_shutdown_settled(self) -> bool:
        snap = self.executor.recovery_snapshot() if self.executor else {}
        return not (snap.get("requests") or snap.get("storage_error") or snap.get("inflight_mutations")) and not (
            self._pending_plans or self._pending_exit_orders or self._pending_stop_orders
            or (self.position_manager and self.position_manager.get_open_positions()))

    async def _observe_account(self):
        self._account_state = "unknown"
        self._account_observed_at = None
        ex = self.executor
        if not ex:
            raise LifecycleConflict("No executor available to verify account state")
        revision = ex.recovery_snapshot()["revision"]
        if ex.dry_run:
            positions = [{"symbol": s, "contracts": abs(ex.get_position(s))}
                         for s in ex.get_open_position_symbols()]
            orders = [{"id": o.order_id, "symbol": o.symbol} for o in ex.get_open_orders()]
        else:
            snapshot = await asyncio.to_thread(self.adapter.fetch_account_snapshot)
            if not isinstance(snapshot, dict) or snapshot.get("complete") is not True or snapshot.get("scope") != "phemex:swap:USDT":
                raise ValueError("Complete USDT contract account snapshot unavailable")
            positions, orders = snapshot.get("positions"), snapshot.get("orders")
        if not isinstance(positions, list) or not isinstance(orders, list):
            raise ValueError("Incomplete account snapshot collections")
        symbols = set()
        for row in positions:
            if not isinstance(row, dict) or not isinstance(row.get("symbol"), str) or not row["symbol"]:
                raise ValueError("Invalid account position")
            qty = row.get("contracts")
            if isinstance(qty, bool) or not isinstance(qty, (float, int)) or not math.isfinite(qty) or qty < 0:
                raise ValueError("Invalid account position quantity")
            if qty > 1e-9:
                symbols.add(row["symbol"])
        for row in orders:
            if not isinstance(row, dict) or not row.get("id") or not isinstance(row.get("symbol"), str) or not row["symbol"]:
                raise ValueError("Invalid account order")
        if ex is not self.executor or revision != ex.recovery_snapshot()["revision"]:
            raise ValueError("Execution changed during account observation; retry required")
        managed = {p.symbol for p in self.position_manager.get_open_positions()} if self.position_manager else set()
        self._unmanaged_symbols = sorted((symbols | {o["symbol"] for o in orders}) - managed)
        self._account_orders = [{"exchange_id": o["id"], "symbol": o["symbol"]} for o in orders]
        self._account_state = "exposure_present" if symbols or orders else "flat_confirmed"
        self._account_observed_at = datetime.now(timezone.utc).isoformat()
        self._account_observed_monotonic = time.monotonic()
        self._account_revision = revision

    async def _verify_resettable(self):
        if (self._phase != "stopped" or (self._shutdown_task and not self._shutdown_task.done())
                or not self._local_shutdown_settled()):
            raise LifecycleConflict("Start/Reset blocked: shutdown recovery is incomplete")
        try:
            await self._observe_account()
        except Exception as exc:
            raise LifecycleConflict(f"Start/Reset blocked: {exc}") from exc
        if self._account_state != "flat_confirmed":
            raise LifecycleConflict("Start/Reset blocked: USDT contract exposure remains")

    def _lifecycle_status(self) -> Dict[str, Any]:
        snap = self.executor.recovery_snapshot() if self.executor else {"requests": [], "revision": None, "entry_admission_enabled": False}
        state = self._account_state
        # This is the last observation, displayed with its timestamp. Start and
        # Reset always re-observe; elapsed time alone is not a new incident.
        if self._account_revision != snap["revision"]:
            state = "unknown"
        requests = list(snap["requests"])
        known = {r["order_id"] for r in requests}
        for symbol, oid in self._pending_exit_orders.items():
            if oid not in known:
                order = self.executor.get_order(oid) if self.executor else None
                requests.append({"order_id": oid, "symbol": symbol, "purpose": "exit",
                                 "status": order.status.value if order else "UNKNOWN",
                                 "filled_quantity": order.filled_quantity if order else None,
                                 "reason": "Exit quantity requires reconciliation"})
        recovery = bool(snap.get("storage_error")) or self._phase in ("stopping", "recovering") or (self._phase == "stopped" and (state != "flat_confirmed" or bool(requests)))
        return {
            "phase": self._phase, "entry_admission_enabled": snap["entry_admission_enabled"] and self._running,
            "recovery_required": recovery, "account_state": state,
            "scope": "simulation" if self.config and self.config.dry_run else "phemex:swap:USDT",
            "observed_at": self._account_observed_at,
            "reset_allowed": not self._lifecycle_busy and (self._phase == "idle" or
                (self._phase == "stopped" and state == "flat_confirmed" and self._local_shutdown_settled()
                 and (not self._shutdown_task or self._shutdown_task.done()))),
            "unresolved_requests": requests, "unmanaged_symbols": self._unmanaged_symbols,
            "account_open_orders": self._account_orders, "reason": snap.get("storage_error") or self._recovery_error,
        }

    def _write_session_report(self):
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

    async def reset(self) -> Dict[str, Any]:
        if self._lifecycle_busy or self._phase not in ("idle", "stopped") or self.status == LiveBotStatus.RUNNING:
            raise LifecycleConflict("Reset blocked: stop and resolve execution recovery first")
        self._lifecycle_busy = True
        try:
            if self.executor:
                await self._verify_resettable()
            return self._reset_session()
        finally:
            self._lifecycle_busy = False

    def _reset_session(self) -> Dict[str, Any]:
        if self.executor:
            self.executor.close()
        self._generation += 1
        self._phase = "idle"
        self._shutdown_task = None
        self._shutdown_reason = None
        self._account_state = "unknown"
        self._account_observed_at = None
        self._account_orders = []
        self._unmanaged_symbols = []
        self._recovery_error = None

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
        self._price_cache_observed_at = {}
        self._price_cache_refreshed_at = None
        self._pending_plans = {}
        self._pending_exit_orders = {}
        self._pending_stop_orders = {}
        self.started_at = None
        self.stopped_at = None
        self.status = LiveBotStatus.IDLE
        self._exchange_stop_retry_at = {}
        self._adopted_entry_orders = {}
        self._exchange_state_known = False
        self._startup_reconciled = False
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
            "lifecycle": self._lifecycle_status(),
        }

        active_positions = self._get_active_positions()
        result["positions"] = active_positions

        if self.executor:
            current = self.executor.get_balance()
            initial = self.executor._initial_balance
            unrealized = sum(
                pos.unrealized_pnl
                for pos in list(self.position_manager.positions.values())
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
            for order_id, plan in list(self._pending_plans.items()):
                order = self.executor.get_order(order_id)
                if order and order.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
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

    def get_trade_history(
        self,
        limit: int = 50,
        source: str = "merged",
    ) -> List[Dict[str, Any]]:
        """
        Return completed trade history.

        source:
          "session"  — only in-memory trades from the current session (legacy).
          "journal"  — only persistent journal rows (survives restarts).
          "merged"   — in-memory ∪ journal, deduped by trade_id, newest first.
                       This is the default so the UI keeps showing trades
                       after a backend restart instead of going blank.
        """
        in_mem = [t.to_dict() for t in self.completed_trades]

        if source == "session":
            in_mem.sort(key=lambda t: t.get("exit_time") or t.get("entry_time") or "", reverse=True)
            return in_mem[:limit]

        try:
            journal_rows = get_trade_journal().query(
                session_id=self.session_id,
                limit=max(limit * 4, 200),
            )
        except Exception as e:
            logger.warning(f"Trade history: journal read failed, falling back to in-memory only: {e}")
            journal_rows = []

        if source == "journal":
            return journal_rows[:limit]

        # merged: prefer in-memory (freshest), fill in from journal
        seen_ids = {t.get("trade_id") for t in in_mem if t.get("trade_id")}
        merged = list(in_mem)
        for row in journal_rows:
            tid = row.get("trade_id")
            if tid and tid in seen_ids:
                continue
            merged.append(row)
            if tid:
                seen_ids.add(tid)
        merged.sort(key=lambda t: t.get("exit_time") or t.get("entry_time") or "", reverse=True)
        return merged[:limit]

    def get_activity_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.activity_log[-limit:]

    def get_signal_by_id(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the most recent signal_log entry matching the given id, or None.

        Signal ids follow the format `{symbol}_{scan_number}_{tf}_{direction}`
        (see _log_signal). The Pipeline Tracer endpoint uses this to fetch
        the gauntlet outcome for a single signal.
        """
        if not signal_id:
            return None
        # Walk newest-first so a re-emitted (symbol, tf, side) on a later scan
        # returns its latest entry rather than a stale one.
        for entry in reversed(self.signal_log):
            if entry.get("id") == signal_id:
                return entry
        return None

    # ------------------------------------------------------------------
    # Phemex fill backfill (observability + recovery)
    # ------------------------------------------------------------------

    def _last_trade_sync_path(self) -> Optional[Path]:
        if not self._session_log_dir:
            return None
        # Persist at project-root scope, not per-session, so a new session resumes
        # from the prior sync timestamp.
        project_root = Path(__file__).parent.parent.parent
        state_dir = project_root / ".live_trading"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / "last_trade_sync.json"

    def _load_last_trade_sync_ts(self) -> None:
        path = self._last_trade_sync_path()
        if not path or not path.exists():
            self._last_trade_sync_ts = None
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ts = data.get("last_synced_ts")
            self._last_trade_sync_ts = int(ts) if ts is not None else None
        except Exception as e:
            logger.warning(f"Could not read last_trade_sync.json: {e}")
            self._last_trade_sync_ts = None

    def _save_last_trade_sync_ts(self) -> None:
        path = self._last_trade_sync_path()
        if not path or self._last_trade_sync_ts is None:
            return
        try:
            path.write_text(
                json.dumps({"last_synced_ts": self._last_trade_sync_ts}),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Could not persist last_trade_sync.json: {e}")

    async def _backfill_loop(self) -> None:
        """
        Every 5 min, pull Phemex executed-trade history since the last sync
        timestamp and append unseen rows to a session-scoped fills log.

        This does NOT write into the trade_journal — the journal stores
        round-trip CompletedTrades and aggregates win-rate from realized P&L.
        Mixing raw fills in would corrupt those aggregates. Instead this loop
        gives the operator an audit trail of every fill the exchange recorded
        (whether or not WS captured it) and powers the
        /api/integrations/phemex/healthz fill-source breakdown.
        """
        BACKFILL_INTERVAL = 300  # 5 minutes
        # Run once shortly after start, then on the interval, so a freshly-started
        # session immediately picks up fills that happened while offline.
        await asyncio.sleep(15)
        while self._running:
            try:
                await self._run_backfill_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._backfill_metrics["errors_total"] += 1
                self._backfill_metrics["last_error_ts"] = int(time.time() * 1000)
                self._backfill_metrics["last_error_msg"] = str(e)
                logger.warning(f"Phemex backfill iteration failed: {e!r}")
            try:
                await asyncio.sleep(BACKFILL_INTERVAL)
            except asyncio.CancelledError:
                raise

    async def _run_backfill_once(self) -> None:
        if not self.adapter:
            return
        loop = asyncio.get_running_loop()
        since = self._last_trade_sync_ts
        trades = await loop.run_in_executor(
            None,
            lambda: self.adapter.fetch_my_trades(symbol=None, since=since, limit=200),
        )
        self._backfill_metrics["runs_total"] += 1
        self._backfill_metrics["last_run_ts"] = int(time.time() * 1000)
        self._backfill_metrics["rows_seen_total"] += len(trades)

        if not trades:
            return

        # Track max timestamp seen so the next iteration narrows the window.
        max_ts = since or 0
        new_rows = 0
        seen_ids = self._load_existing_fill_ids()
        if self._fills_log_path is None:
            return
        try:
            with self._fills_log_path.open("a", encoding="utf-8") as f:
                for t in trades:
                    ts = int(t.get("timestamp") or 0)
                    if ts > max_ts:
                        max_ts = ts
                    fill_id = str(t.get("id") or f"{t.get('order')}-{ts}-{t.get('amount')}")
                    if fill_id in seen_ids:
                        continue
                    record = {
                        "fill_id": fill_id,
                        "order_id": t.get("order"),
                        "symbol": t.get("symbol"),
                        "side": t.get("side"),
                        "price": t.get("price"),
                        "amount": t.get("amount"),
                        "cost": t.get("cost"),
                        "fee": t.get("fee"),
                        "timestamp": ts,
                        "datetime": t.get("datetime"),
                        "session_id": self.session_id,
                        "backfilled_at": datetime.now(timezone.utc).isoformat(),
                    }
                    f.write(json.dumps(record, default=str) + "\n")
                    seen_ids.add(fill_id)
                    new_rows += 1
        except Exception as e:
            self._backfill_metrics["errors_total"] += 1
            self._backfill_metrics["last_error_ts"] = int(time.time() * 1000)
            self._backfill_metrics["last_error_msg"] = f"write: {e}"
            logger.warning(f"Phemex backfill: failed to write fills log: {e}")
            return

        self._backfill_metrics["rows_new_total"] += new_rows
        if max_ts and (since is None or max_ts > since):
            # +1ms so the next call doesn't re-fetch the boundary trade.
            self._last_trade_sync_ts = max_ts + 1
            self._save_last_trade_sync_ts()
        if new_rows:
            logger.info(f"Phemex backfill: appended {new_rows} new fills (since={since})")

    def _load_existing_fill_ids(self) -> set:
        ids: set = set()
        if not self._fills_log_path or not self._fills_log_path.exists():
            return ids
        try:
            with self._fills_log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    fid = rec.get("fill_id")
                    if fid:
                        ids.add(fid)
        except Exception as e:
            logger.debug(f"Could not load existing fills: {e}")
        return ids

    def get_phemex_healthz(self) -> Dict[str, Any]:
        """
        Snapshot of every Phemex-integration counter and connection state.
        Surfaced via GET /api/integrations/phemex/healthz so the operator can
        see what the integration is doing without rummaging through logs.
        """
        now_ms = int(time.time() * 1000)
        ws_metrics = self._ws_client.metrics.copy() if self._ws_client else {"enabled": False}
        if self._ws_client:
            ws_metrics["enabled"] = True
            last_frame_ts = ws_metrics.get("last_frame_ts")
            ws_metrics["seconds_since_last_frame"] = (
                round((now_ms - last_frame_ts) / 1000.0, 1) if last_frame_ts else None
            )
        adapter_metrics = self.adapter.metrics.copy() if self.adapter else {}
        executor_metrics = (
            getattr(self.executor, "metrics", {}).copy() if self.executor else {}
        )
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "ws": ws_metrics,
            "rest": adapter_metrics,
            "executor": executor_metrics,
            "backfill": {
                **self._backfill_metrics,
                "last_synced_ts": self._last_trade_sync_ts,
                "fills_log_path": str(self._fills_log_path) if self._fills_log_path else None,
            },
            "journal": {
                "session_rows": self._safe_journal_count(session_only=True),
                "total_rows": self._safe_journal_count(session_only=False),
            },
            "in_memory": {
                "completed_trades": len(self.completed_trades),
                "pending_orders": len(self._pending_plans),
            },
        }

    def _safe_journal_count(self, session_only: bool) -> int:
        try:
            if session_only:
                rows = get_trade_journal().query(session_id=self.session_id, limit=10_000)
                return len(rows)
            return get_trade_journal().count()
        except Exception:
            return -1

    # ------------------------------------------------------------------
    # Startup reconciliation
    # ------------------------------------------------------------------

    def _set_exchange_state_known(self, known: bool, reason: str):
        """Report state transitions without treating a failed observation as flat."""
        changed = (getattr(self, "_exchange_state_known", False) != known
                   or getattr(self, "_exchange_state_reason", None) != reason)
        self._exchange_state_known = known
        self._exchange_state_reason = reason
        if changed:
            self._log_activity("exchange_reconciliation", {"known": known, "reason": reason})

    def _entry_reconciliation_ready(self) -> bool:
        return (getattr(self, "_startup_reconciled", False)
                and getattr(self, "_exchange_state_known", False))

    async def _startup_reconcile(self) -> bool:
        """Verify positions and orphan orders before permitting new entries.

        Unknown snapshots/cancellations leave admission blocked and are retried
        by the monitor. Protective orders are preserved; their symbols remain
        blocked for this session rather than inheriting an old stop on a new entry.
        """
        self._startup_reconciled = False
        self._set_exchange_state_known(False, "startup reconciliation pending")
        if not self.adapter or not self.executor:
            return False
        if self.config and self.config.dry_run:
            self._startup_reconciled = True
            self._set_exchange_state_known(True, "dry-run reconciliation")
            return True

        loop = asyncio.get_running_loop()
        try:
            protected_symbols = await loop.run_in_executor(None, self.executor.reconcile_positions)
            if protected_symbols is None:
                raise ValueError("Position snapshot unavailable; order cleanup deferred")
            self._orphaned_symbols.update(protected_symbols)
            for symbol in sorted(protected_symbols):
                qty = self.executor.get_position(symbol)
                self._log_activity("orphaned_position_detected", {
                    "symbol": symbol,
                    "side": "long" if qty > 0 else "short",
                    "quantity": abs(qty),
                    "entry_price": self.executor._position_avg_price.get(symbol, 0.0),
                    "note": "Existing position blocked from new entries; protective orders preserved.",
                })

            snapshot = await loop.run_in_executor(None, self.adapter.fetch_account_snapshot)
            if not isinstance(snapshot, dict) or snapshot.get("complete") is not True or snapshot.get("scope") != "phemex:swap:USDT":
                raise ValueError("Complete USDT contract open-order snapshot unavailable")
            raw_orders = snapshot.get("orders")
            if not isinstance(raw_orders, list):
                raise ValueError("Open-order snapshot must be a list")
            # Validate the entire list before the first cancellation.
            orders = []
            for row in raw_orders:
                if not isinstance(row, dict):
                    raise ValueError("Open-order snapshot contains a non-object row")
                symbol, order_type, oid = row.get("symbol"), row.get("type"), row.get("id")
                if (not isinstance(symbol, str) or not symbol.strip()
                        or not isinstance(order_type, str) or not order_type.strip()
                        or oid is None or not str(oid).strip()):
                    raise ValueError("Open-order snapshot lacks symbol, type or id")
                info = row.get("info") if isinstance(row.get("info"), dict) else {}
                protective = order_type.lower() != "limit" or any(
                    str(value).lower() in ("true", "1")
                    for value in (row.get("reduceOnly"), info.get("reduceOnly"),
                                  info.get("closeOnTrigger"))
                )
                orders.append((symbol, str(oid), protective))

            # Foreign orders are never safe to cancel just because they are limit
            # orders. Known requests are recovered through the journaled executor.
            for symbol, oid, protective in orders:
                self._orphaned_symbols.add(symbol)
                logger.warning("Startup preserves existing order %s on %s; reconciliation required", oid, symbol)
            await self._observe_account()
            if self._account_state != "flat_confirmed":
                raise ValueError("Existing USDT contract exposure requires recovery before a new session")

            # An entry may fill while cleanup is in flight, even when the open
            # order list is empty by the time it arrives. Observe positions again.
            final_symbols = await loop.run_in_executor(None, self.executor.reconcile_positions)
            if final_symbols is None:
                raise ValueError("Post-cleanup position snapshot unavailable")
            self._orphaned_symbols.update(final_symbols)
            if final_symbols:
                raise ValueError("Position exposure appeared during startup reconciliation")
        except Exception as e:
            logger.warning("Startup reconciliation incomplete; new entries blocked: %s", e)
            self._set_exchange_state_known(False, str(e))
            return False

        self._startup_reconciled = True
        self._set_exchange_state_known(True, "startup reconciliation complete")
        return True

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

    def _clear_pending_entry(self, order_id: str):
        self._pending_plans.pop(order_id, None)
        self._pending_placed_at.pop(order_id, None)
        self._pending_placed_price.pop(order_id, None)
        self._pending_extended.discard(order_id)

    async def _monitor_pending_entries(self):
        """Poll active entries, then adopt terminal fills regardless of event source."""
        terminal = {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}
        for order_id, plan in list(self._pending_plans.items()):
            try:
                order = self.executor.get_order(order_id)
                if order is None:
                    logger.error("Pending entry %s has no executor order; retaining plan", order_id)
                    continue
                if order.status not in terminal:
                    price = self._price_cache.get(order.symbol)
                    if price and order.order_type == OrderType.LIMIT:
                        self.executor.execute_limit_order(order_id, price)
                    placed_at = self._pending_placed_at.get(order_id)
                    age = (datetime.now(timezone.utc) - placed_at).total_seconds() if placed_at else 0
                    if order.status not in terminal and placed_at and self.config:
                        trade_type = getattr(plan, "trade_type", "intraday") or "intraday"
                        ttl_seconds = 60 * _PENDING_TTL_MINUTES.get(trade_type, 10.0)
                        if age > ttl_seconds:
                            self.executor.cancel_order(order_id)
                            if order.status not in terminal:
                                logger.warning("Cancel unconfirmed for expired entry %s; will retry", order_id)

                # WS may have already finalized this order before polling starts.
                # A terminal partial cancellation owns only the quantity actually filled.
                if order.status == OrderStatus.FILLED or (
                    order.status in terminal and order.filled_quantity > 0
                ):
                    await self._open_filled_entry(
                        order_id, plan,
                        order.average_fill_price or order.price or 0.0,
                        order.filled_quantity,
                    )
                elif order.status in (OrderStatus.CANCELLED, OrderStatus.REJECTED):
                    self._clear_pending_entry(order_id)
                    event = "order_rejected" if order.status == OrderStatus.REJECTED else "order_cancelled"
                    logger.warning("Entry %s %s without fills; dropping pending plan", order_id, order.status.value)
                    self._log_activity(event, {"symbol": plan.symbol, "order_id": order_id})
            except Exception:
                # Retain the plan for retry, and keep monitoring other positions.
                logger.exception("Pending entry reconciliation failed for %s; retaining plan", order_id)

    async def _monitor_loop(self):
        while self._running:
            try:
                if self.position_manager:
                    await self._refresh_price_cache()

                    if self.executor:
                        self.executor.recover_uncertain_orders()
                        await self._monitor_pending_entries()

                    # Run position monitoring
                    await self.position_manager.monitor_all_positions()
                    await self._sync_exchange_stops()
                    await self._sync_closed_positions()

                    # Periodic balance + position reconciliation
                    if self.executor and self.config:
                        now_ts = time.monotonic()
                        if now_ts - self._last_reconcile_at >= self.config.balance_reconcile_interval:
                            self.executor.reconcile_balance()
                            if not self._startup_reconciled:
                                await self._startup_reconcile()
                                self.executor.set_entry_admission(self._running and self._entry_reconciliation_ready())
                            else:
                                ex_open_symbols = self.executor.reconcile_positions()
                                if ex_open_symbols is None:
                                    self._set_exchange_state_known(False, "position snapshot unavailable")
                                else:
                                    managed = {p.symbol for p in self.position_manager.get_open_positions()}
                                    pending = {p.symbol for p in self._pending_plans.values()}
                                    self._orphaned_symbols.update(ex_open_symbols - managed - pending)
                                    await self._detect_exchange_closed_positions(ex_open_symbols)
                                    self._set_exchange_state_known(True, "position snapshot verified")
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
        if not self._running or not self.orchestrator or not self.config:
            return
        generation = self._generation
        orchestrator = self.orchestrator

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

        # Apply stale-symbol drop regardless of how scan_symbols was built.
        # The user-pinned path (config.symbols) bypasses select_symbols(), so
        # the Stage-0 stale filter inside _select_symbols_impl never sees those
        # symbols. Mirrors paper_trading_service for behavioral parity.
        # See decisions log 2026-05-25__stale_symbol_drop_userpinned.md.
        try:
            from backend.analysis.pair_selection import filter_stale_symbols
            scan_symbols, _stale_dropped = filter_stale_symbols(
                scan_symbols, context="live_trading_service"
            )
        except Exception as _stale_exc:
            # Loud-by-default per CLAUDE.md §11 / §15: a silent debug-level
            # emit on this path would hide regressions in is_symbol_stale or
            # the mass-conservation assert. Scan continues with the unfiltered
            # list — graceful degradation, NOT silent failure.
            logger.warning(f"filter_stale_symbols failed: {_stale_exc}")

        # Apply the LIQUIDITY floor regardless of how scan_symbols was built — covers user-pinned
        # AND auto-selected (operator decision 2026-06-18: pinned symbols ARE liquidity-filtered;
        # an illiquid pinned pair blows through stops on exit). Mirrors paper for parity.
        # regime-strategy-router §9-A "don't trade illiquid pairs". Loud per CLAUDE.md §11.
        try:
            from backend.analysis.pair_selection import filter_illiquid_symbols
            from backend.shared.config.scanner_modes import get_mode
            _lmode = get_mode(getattr(config, "sniper_mode", "stealth")) or get_mode("stealth")
            _liq_floor = getattr(_lmode, "min_24h_volume_usdt", 5_000_000.0)
            _vols = self.orchestrator.exchange_adapter.get_symbol_volumes(scan_symbols)
            if _vols:
                scan_symbols, _illiquid_dropped = filter_illiquid_symbols(
                    scan_symbols, _vols, _liq_floor, context="live_trading_service"
                )
            elif scan_symbols:
                logger.warning(
                    "LIQUIDITY gate SKIPPED this scan: volume lookup returned no data; "
                    "trading {} symbol(s) unfiltered (existing gates still apply)",
                    len(scan_symbols),
                )
        except Exception as _liq_exc:
            # Graceful degradation, NOT silent (CLAUDE.md §11/§15).
            logger.warning(f"filter_illiquid_symbols failed: {_liq_exc}")

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
            if generation != self._generation or not self._running:
                return
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
                lambda: orchestrator.scan_with_heartbeat(
                    symbols=scan_symbols,
                    progress_callback=_progress_callback,
                ),
            )
        except Exception as e:
            logger.error(f"Orchestrator scan failed: {e}")
            if self.current_scan:
                self.current_scan["status"] = "error"
            return

        if generation != self._generation or not self._running:
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

        if not self._entry_reconciliation_ready():
            self._log_signal(plan, "filtered", "Exchange state unverified; waiting for reconciliation",
                             reason_type="exchange_state_unknown")
            return

        symbol = plan.symbol
        score = getattr(plan, "confidence_score", 0.0)

        # Position cap — count in-flight pending entries too. Pending limit orders
        # are committed capital but are invisible to _get_active_positions (open
        # positions only). Without counting them, N signals can each place an order
        # while under cap, then all fill and exceed max_positions — the later fills
        # were previously dropped, stranding a naked live position.
        # See decisions/2026-05-30__fix-design__overcap-filled-order-stranded.md.
        active_count = len(self._get_active_positions()) + len(self._pending_plans)
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

        # Resolve the final entry geometry before calculating quantity.
        prices = self._fresh_price_cache()
        required = {symbol} | self.executor.get_open_position_symbols()
        if not required.issubset(prices):
            await self._refresh_price_cache(extra_symbols={symbol})
            prices = self._fresh_price_cache()
        current_price = prices.get(symbol)
        if current_price is None:
            self._log_signal(plan, "filtered", f"Recent price unavailable for {symbol}",
                             reason_type="price_fetch")
            return

        def positive_number(value):
            return (
                not isinstance(value, bool) and isinstance(value, (int, float))
                and math.isfinite(value) and value > 0
            )

        sl_obj = getattr(plan, "stop_loss", None)
        stop_level = getattr(sl_obj, "level", None) if sl_obj is not None else None
        if (not positive_number(current_price) or not positive_number(stop_level)
                or plan.direction not in ("LONG", "SHORT")):
            self._log_signal(plan, "filtered", "Invalid market price, stop or direction",
                             reason_type="risk_validation")
            return

        # Entry price — use OB near_entry or current price
        ez_obj = getattr(plan, "entry_zone", None)
        near = getattr(ez_obj, "near_entry", None)
        far = getattr(ez_obj, "far_entry", None)
        if any(value is not None and not positive_number(value) for value in (near, far)):
            self._log_signal(plan, "filtered", "Invalid entry zone", reason_type="risk_validation")
            return
        if near and far:
            entry_price = (near + far) / 2
        elif near:
            entry_price = near
        else:
            entry_price = current_price

        # Limit proximity snap: if the OB entry zone is far from current price the limit
        # order will sit pending and expire without filling within the TTL window.
        # Snap the limit closer to market so it has a realistic chance of executing.
        # Mirrors paper_trading_service._MAX_LIMIT_DISTANCE_PCT snap logic exactly.
        is_long = plan.direction == "LONG"
        _trade_type_snap = getattr(plan, "trade_type", "intraday") or "intraday"
        _raw_limit = entry_price
        _max_dist = _MAX_LIMIT_DISTANCE_PCT.get(_trade_type_snap, 0.40)
        if score >= 70.0:
            _max_dist /= 2.0
        _gap_pct = abs(_raw_limit - current_price) / current_price * 100 if current_price else 0
        if _gap_pct > _max_dist and current_price > 0:
            if is_long:
                entry_price = current_price * (1 - _max_dist / 100)
            else:
                entry_price = current_price * (1 + _max_dist / 100)
            logger.info(
                "LIMIT SNAP: %s %s | %.4f → %.4f (gap %.2f%% > max %.2f%%)",
                symbol, plan.direction, _raw_limit, entry_price, _gap_pct, _max_dist,
            )

        # Use the exchange's local precision routines, the same ones used when
        # building the request. Metadata failure must not send an unrounded order.
        planned_stop = stop_level
        try:
            if not self.adapter:
                raise ValueError("exchange adapter unavailable")
            self.adapter.get_market_info(symbol)  # loads/retries the market cache
            exchange = self.adapter.exchange
            market = exchange.market(symbol)
            # Executor/PositionManager quantities and USD caps currently assume
            # one base unit per contract. Do not silently size inverse/non-unit lots.
            if (market.get("linear") is not True or market.get("contract") is not True
                    or market.get("settle") not in ("USDT", "USDC")
                    or market.get("quote") != market.get("settle")
                    or Decimal(str(market.get("contractSize"))) != Decimal("1")):
                raise ValueError("unsupported contract units for live risk sizing")
            entry_price = float(exchange.price_to_precision(symbol, entry_price))
            stop_level = float(exchange.price_to_precision(symbol, planned_stop))
            if not positive_number(entry_price) or not positive_number(stop_level):
                raise ValueError("price precision produced an invalid entry or stop")
        except Exception as exc:
            logger.warning("Entry precision unavailable for %s: %s", symbol, exc)
            self._log_signal(plan, "filtered", f"Entry precision unavailable: {exc}",
                             reason_type="risk_validation")
            return

        if ((is_long and (stop_level >= entry_price or planned_stop >= entry_price))
                or (not is_long and (stop_level <= entry_price or planned_stop <= entry_price))):
            self._log_signal(plan, "filtered", "Stop must remain on the loss side of final entry",
                             reason_type="risk_validation")
            return

        # Stale-entry guard: reject only when the OB zone has already been blown through
        # by price in the wrong direction. A valid OB entry is always "on the other side"
        # of current price — LONG OB is below market (buy the dip), SHORT OB is above
        # market (sell the rally). Rejection applies when:
        #   LONG: entry is >1.5% ABOVE market — price blew through the OB upward
        #   SHORT: entry is >1.5% BELOW market — price blew through the OB downward
        # (The original ETH issue was SHORT entry at $2328 when market was $2380 —
        # OB blown through downward — correct to reject that.)
        if is_long and entry_price > current_price * 1.015:
            self._log_signal(plan, "filtered",
                f"Entry {entry_price:.4f} is >1.5% above market {current_price:.4f} — OB blown through upward",
                reason_type="stale_entry")
            return
        if not is_long and entry_price < current_price * 0.985:
            self._log_signal(plan, "filtered",
                f"Entry {entry_price:.4f} is >1.5% below market {current_price:.4f} — OB blown through downward",
                reason_type="stale_entry")
            return

        if symbol not in self._fresh_price_cache():
            self._log_signal(plan, "filtered", "Entry price expired while preparing order",
                             reason_type="price_fetch")
            return
        equity = self._valuation_equity()
        if not positive_number(equity) or not positive_number(config.risk_per_trade):
            self._log_signal(plan, "filtered", "Equity unavailable or invalid risk percentage",
                             reason_type="risk_validation")
            return

        # Decimal arithmetic avoids rounding a budget-bound quantity up by a lot.
        # Software monitoring retains the planned stop: budget for the farther of
        # that level and the precision-normalized native stop.
        risk_budget = Decimal(str(equity)) * Decimal(str(config.risk_per_trade)) / Decimal("100")
        entry_decimal = Decimal(str(entry_price))
        risk_distance = max(
            abs(entry_decimal - Decimal(str(stop_level))),
            abs(entry_decimal - Decimal(str(planned_stop))),
        )
        try:
            quantity = float(exchange.amount_to_precision(symbol, str(risk_budget / risk_distance)))
            if not positive_number(quantity):
                raise ValueError("position size rounds to zero or is invalid")
            planned_risk = Decimal(str(quantity)) * risk_distance
            if planned_risk > risk_budget:
                raise ValueError("rounded quantity exceeds the risk budget")
        except Exception as exc:
            logger.warning("Entry sizing rejected for %s: %s", symbol, exc)
            self._log_signal(plan, "filtered", f"Entry sizing rejected: {exc}",
                             reason_type="position_size")
            return

        position_value = Decimal(str(quantity)) * entry_decimal
        cap = getattr(config, "max_position_size_usd", None)
        if not positive_number(cap) or position_value > Decimal(str(cap)):
            self._log_signal(
                plan, "filtered",
                f"Final position size ${position_value:.2f} exceeds or has invalid cap ${cap}",
                reason_type="position_size",
            )
            return
        self._log_activity("entry_risk_sized", {
            "symbol": symbol, "direction": plan.direction, "equity": equity,
            "risk_per_trade": config.risk_per_trade, "risk_budget": float(risk_budget),
            "planned_stop_risk": float(planned_risk), "risk_distance": float(risk_distance),
            "entry": entry_price, "stop": stop_level, "planned_stop": planned_stop,
            "quantity": quantity, "notional": float(position_value),
        })

        # Inline SL only: attached to the entry order for atomic crash protection.
        # The SL fires on the exchange even if our server goes down before
        # _place_exchange_stop() runs.  TP1 is NOT attached inline because
        # _place_exchange_stop() places an explicit reduce-only limit order for TP1;
        # having both would create two overlapping TP orders at the same price and
        # quantity, risking a 2× exit on TP hit.
        # Price fetching above can yield to a failed reconciliation. Check again
        # immediately before committing a new entry to the executor.
        if not self._entry_reconciliation_ready():
            self._log_signal(plan, "filtered", "Exchange state changed during sizing; entry deferred",
                             reason_type="exchange_state_unknown")
            return
        order = self.executor.place_order(
            symbol=symbol,
            side="BUY" if is_long else "SELL",
            order_type="LIMIT",
            quantity=quantity,
            price=entry_price,
            sl_price=stop_level,
        )

        if order.status.value in ("REJECTED",):
            reject_msg = getattr(order, "rejection_reason", None) or order.status.value
            logger.warning(f"Order rejected for {symbol}: {reject_msg}")
            self._log_signal(plan, "filtered", reject_msg, reason_type="errors")
            return

        self._pending_plans[order.order_id] = plan
        self._pending_placed_at[order.order_id] = datetime.now(timezone.utc)
        self._pending_placed_price[order.order_id] = current_price

        uncertain = order.status == OrderStatus.PENDING
        self._log_signal(plan, "pending", "Order acknowledgment unavailable; reconciling original request" if uncertain
                         else f"Waiting for limit fill @ {entry_price:.4f}",
                         reason_type="order_outcome_unknown" if uncertain else "pending_fill")
        self._log_activity("order_submission_unknown" if uncertain else "signal_taken", {
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

        _symbol = getattr(plan, "symbol", "Unknown")
        _direction = getattr(plan, "direction", "LONG")
        _tf = getattr(plan, "primary_timeframe", None) or getattr(plan, "signal_timeframe", None) or "?"
        _scan_no = self.stats.scans_completed
        # Stable signal id — same (symbol, scan, tf, side) yields the same id.
        # Slashes from the symbol are replaced with '-' so the id is safe in
        # URL path segments (e.g. /api/signals/{id}/trace). The original
        # symbol is still exposed verbatim in the entry's "symbol" field.
        _id_safe_symbol = _symbol.replace("/", "-")
        _signal_id = f"{_id_safe_symbol}_{_scan_no}_{_tf}_{str(_direction).lower()}"

        entry = {
            "id": _signal_id,
            "timestamp": _now.isoformat(),
            "scan_number": _scan_no,
            "symbol": _symbol,
            "direction": _direction,
            "confluence": round(float(getattr(plan, "confidence_score", 0.0)), 1),
            "setup_type": getattr(plan, "setup_type", "unknown"),
            "trade_type": getattr(plan, "trade_type", "unknown"),
            "timeframe": _tf,
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
        # Cache the confluence breakdown (if the plan carries one) so the
        # /api/signals/{id}/confluence endpoint can serve it without re-scoring.
        # Surfacing failures matters: a silent drop here would orphan the
        # signal_log entry from its breakdown, which is exactly the kind of
        # observability hole this whole rebuild is fixing.
        _br = getattr(plan, "confluence_breakdown", None)
        if _br is not None:
            try:
                from backend.strategy.confluence.cache import record as _record_breakdown
                if not _record_breakdown(_signal_id, _br):
                    logger.warning(
                        f"confluence cache record returned False for {_signal_id} "
                        f"(symbol={_symbol}, scan={_scan_no}, tf={_tf}, dir={_direction}); "
                        f"breakdown will be missing from /api/signals/{{id}}/confluence"
                    )
            except Exception as _be:
                logger.warning(
                    f"confluence cache record raised for {_signal_id}: {_be}",
                    exc_info=True,
                )
        else:
            # Plan reached _log_signal without a breakdown attached.
            # Some pre-execution gates short-circuit before scoring, so this
            # is expected for some reason_types but worth flagging at info.
            _reason_type = extra.get("reason_type", "?")
            if _reason_type not in ("max_positions", "has_position", "pending_order", "pending_fill"):
                logger.info(
                    f"signal {_signal_id} reached _log_signal with no confluence_breakdown "
                    f"(reason_type={_reason_type}, result={result}); cache lookup will miss"
                )
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

    async def _open_filled_entry(
        self, order_id: str, plan: "TradePlan", entry_px: float, entry_qty: float
    ) -> Optional[str]:
        """Adopt a confirmed terminal fill once per entry order in this session."""
        if not self.position_manager:
            logger.error("Cannot adopt filled entry %s without a position manager", order_id)
            return None
        pos_id = self._adopted_entry_orders.get(order_id)
        if not pos_id:
            existing = self.position_manager.find_position_by_order_id(order_id)
            pos_id = existing.position_id if existing else None
        if pos_id:
            self._adopted_entry_orders[order_id] = pos_id
            self._clear_pending_entry(order_id)
            return pos_id

        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0
            for value in (entry_px, entry_qty)
        ):
            logger.error(
                "Cannot adopt filled entry %s %s: invalid price=%s quantity=%s; retaining plan",
                plan.symbol, order_id, entry_px, entry_qty,
            )
            self._log_activity("entry_adoption_deferred", {
                "symbol": plan.symbol, "order_id": order_id, "reason": "invalid_fill",
            })
            return None

        cap = self.config.max_positions if self.config else 3
        active_count = len(self._get_active_positions())
        if active_count >= cap:
            logger.warning(
                "Over-cap fill ADOPTED for %s (active=%d cap=%d); entry already filled",
                plan.symbol, active_count, cap,
            )
            self._log_activity("over_cap_adopted", {
                "symbol": plan.symbol, "active": active_count, "cap": cap,
            })

        pos_id = self.position_manager.open_position(
            trade_plan=plan,
            entry_price=entry_px,
            quantity=entry_qty,
            entry_order_id=order_id,
        )
        # Publish before any await: duplicate events cannot open a second position.
        # Keep the marker after closure so a replay cannot resurrect a closed trade.
        self._adopted_entry_orders[order_id] = pos_id
        self.stats.signals_taken += 1
        self._clear_pending_entry(order_id)
        try:
            await self._place_exchange_stop(pos_id, plan, entry_px, entry_qty)
        except Exception:
            logger.exception(
                "Native exit placement failed for %s (pos %s); local monitoring continues, "
                "missing fixed stop will be retried", plan.symbol, pos_id,
            )
        self._log_activity("trade_opened", {
            "position_id": pos_id,
            "symbol": plan.symbol,
            "direction": plan.direction,
            "entry_price": entry_px,
        })
        return pos_id

    async def _execute_exit_order(self, symbol: str, side: str, quantity: float, price: float) -> bool:
        """Keep protection and the original request until the entire requested exit is confirmed."""
        if not self.executor or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                                   or not math.isfinite(v) or v <= 0 for v in (quantity, price)):
            return False
        try:
            order_id = self._pending_exit_orders.get(symbol)
            order = self.executor.get_order(order_id) if order_id else None
            if order_id and order is None:
                logger.error("EXIT_OUTCOME_UNKNOWN %s: missing local order %s", symbol, order_id)
                return False
            if order is None:
                order = self.executor.place_order(
                    symbol=symbol, side=side, order_type="MARKET",
                    quantity=quantity, price=price, reduce_only=True,
                )
                if order is None:
                    return False
                self._pending_exit_orders[symbol] = order.order_id
            if order.status not in (OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED):
                self.executor.execute_market_order(order.order_id, price)
            if order.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED) and order.filled_quantity <= 0:
                self._pending_exit_orders.pop(symbol, None)
                return False
            # A partial cancellation can be terminal without completing this exit.
            # A changed caller quantity also requires reconciliation, not a duplicate send.
            complete = (order.status == OrderStatus.FILLED
                        and order.side.value == side.upper()
                        and abs(order.quantity - quantity) <= 1e-9
                        and order.filled_quantity >= quantity - 1e-9)
            if not complete:
                logger.warning("EXIT_UNCONFIRMED %s order=%s status=%s filled=%.8f requested=%.8f",
                               symbol, order.order_id, order.status.value, order.filled_quantity, quantity)
                self._log_activity("exit_unconfirmed", {
                    "symbol": symbol, "order_id": order.order_id, "status": order.status.value,
                    "filled_quantity": order.filled_quantity, "requested_quantity": quantity,
                })
                return False
            self._pending_exit_orders.pop(symbol, None)
            # Partial target exits leave the remaining position's protection in place.
            try:
                if self.position_manager:
                    for pos in self.position_manager.get_open_positions():
                        if pos.symbol == symbol and quantity >= pos.remaining_quantity - 1e-9:
                            await self._cancel_exchange_stop(pos.position_id)
                            await self._cancel_exchange_tp(pos.position_id)
                            await self._cancel_exchange_trailing(pos.position_id)
                            break
            except Exception:
                logger.exception("Confirmed exit %s needs protection cleanup", order.order_id)
            return True
        except Exception as exc:
            logger.exception("Exit order failed for %s: %s", symbol, exc)
            return False

    async def _place_exchange_stop(
        self, position_id: str, plan: "TradePlan", entry_price: float, quantity: float
    ):
        """Place exchange-native SL (stop-market) and TP1 (limit) on Phemex after fill."""
        if not self.executor:
            return

        # --- Stop Loss ---
        sl_obj = getattr(plan, "stop_loss", None)
        stop_level = getattr(sl_obj, "level", None) if sl_obj is not None else None
        if not stop_level or stop_level <= 0:
            return
        stop_side = "SELL" if plan.direction == "LONG" else "BUY"
        self._ensure_exchange_stop(position_id, plan.symbol, plan.direction, quantity, stop_level)

        # --- Take Profit (TP1 only) ---
        # Place TP1 as a reduce-only limit order so it shows in the Phemex position
        # card and executes at the exact price rather than market-slipping through it.
        # Remaining targets (TP2, TP3) remain software-managed — placing all targets
        # as exchange orders would conflict with our partial-exit logic.
        targets = getattr(plan, "targets", None) or []
        if targets:
            tp_side = stop_side  # same closing side
            is_long = plan.direction == "LONG"
            # Sort ascending for LONG (nearest TP first), descending for SHORT
            sorted_targets = sorted(targets, key=lambda t: t.level, reverse=not is_long)
            tp1 = sorted_targets[0]
            tp1_qty = round((tp1.percentage / 100.0) * quantity, 8)
            market_info = self.adapter.get_market_info(plan.symbol) if self.adapter else {}
            lot_size = market_info.get("lot_size", 0.0)
            if lot_size > 0:
                tp1_qty = round_to_lot(tp1_qty, lot_size)
            if tp1_qty > 0 and tp1.level > 0:
                tp_order = self.executor.place_take_profit_order(
                    symbol=plan.symbol,
                    side=tp_side,
                    quantity=tp1_qty,
                    tp_price=tp1.level,
                )
                if tp_order.status.value != "REJECTED":
                    self._exchange_tp_orders[position_id] = tp_order.order_id
                    self._log_activity("exchange_tp_pending" if tp_order.status == OrderStatus.PENDING else "exchange_tp_placed", {
                        "position_id": position_id,
                        "symbol": plan.symbol,
                        "tp_price": tp1.level,
                        "quantity": tp1_qty,
                        "direction": plan.direction,
                    })

        # --- Exchange-native trailing stop ---
        # Placed alongside the fixed SL. Phemex manages the moving stop on their
        # servers once activationPrice is touched — survives server restarts.
        # callbackRate = trail_R × stop_distance_pct (scaled by trade type).
        # Both the fixed SL and this trailing stop carry closeOnTrigger=True so
        # only one fires; whichever triggers first closes the position.
        _risk = abs(entry_price - stop_level) if stop_level and stop_level > 0 else 0.0
        if _risk > 0 and entry_price > 0:
            _trail_r = {"scalp": 0.3, "intraday": 0.5, "swing": 1.0}
            _trade_type = getattr(plan, "trade_type", "intraday") or "intraday"
            _callback_rate = max(0.1, round(_trail_r.get(_trade_type, 0.5) * (_risk / entry_price) * 100, 3))
            _is_long = plan.direction == "LONG"
            _activation = entry_price + 1.5 * _risk if _is_long else entry_price - 1.5 * _risk
            trail_order = self.executor.place_trailing_stop_order(
                symbol=plan.symbol,
                side=stop_side,
                quantity=quantity,
                activation_price=_activation,
                callback_rate=_callback_rate,
            )
            if trail_order.status.value != "REJECTED":
                self._exchange_trailing_orders[position_id] = trail_order.order_id
                self._log_activity("exchange_trailing_pending" if trail_order.status == OrderStatus.PENDING else "exchange_trailing_placed", {
                    "position_id": position_id,
                    "symbol": plan.symbol,
                    "activation_price": _activation,
                    "callback_rate": _callback_rate,
                    "direction": plan.direction,
                })

    def _ensure_exchange_stop(
        self, position_id: str, symbol: str, direction: str, quantity: float, stop_level: float
    ) -> bool:
        """Attempt fixed-stop placement at most once per five seconds after a failure."""
        if not self.executor:
            return False
        last_stop = self._exchange_stop_levels.get(position_id)
        old_order_id = self._exchange_stop_orders.get(position_id)
        if (old_order_id and last_stop is not None
                and isinstance(stop_level, (int, float)) and math.isfinite(stop_level)
                and abs(stop_level - last_stop) < 1e-8):
            return True
        now = time.monotonic()
        if now < self._exchange_stop_retry_at.get(position_id, 0.0):
            return False
        self._exchange_stop_retry_at[position_id] = now + 5.0
        try:
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0
                for value in (quantity, stop_level)
            ):
                raise ValueError("invalid stop quantity or level")
            pending_id = self._pending_stop_orders.get(position_id)
            order = self.executor.get_order(pending_id) if pending_id else None
            if pending_id and order is None:
                raise ValueError(f"missing unresolved stop {pending_id}")
            if order is None:
                order = self.executor.place_stop_order(
                    symbol=symbol, side="SELL" if direction == "LONG" else "BUY",
                    quantity=quantity, stop_price=stop_level,
                )
            elif order.status == OrderStatus.PENDING:
                self.executor.refresh_order(order.order_id)
            if order.status == OrderStatus.PENDING:
                self._pending_stop_orders[position_id] = order.order_id
            elif order.status in (OrderStatus.CANCELLED, OrderStatus.REJECTED):
                self._pending_stop_orders.pop(position_id, None)
            if order.status not in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED) or not order.order_id:
                raise ValueError(f"stop not accepted: {order.status.value}")
        except Exception as exc:
            logger.error(
                "Native stop unavailable for %s (pos %s): %s; retry in 5s",
                symbol, position_id, exc,
            )
            self._log_activity("exchange_stop_failed", {
                "position_id": position_id, "symbol": symbol,
                "stop_price": stop_level, "reason": str(exc), "retry_seconds": 5,
            })
            return False

        # Record the replacement before attempting cancellation. A rejected replacement
        # must leave the old protection reference intact.
        self._exchange_stop_orders[position_id] = order.order_id
        self._exchange_stop_levels[position_id] = order.stop_price or stop_level
        self._pending_stop_orders.pop(position_id, None)
        self._exchange_stop_retry_at.pop(position_id, None)
        if old_order_id and old_order_id != order.order_id:
            try:
                if not self.executor.cancel_order(old_order_id):
                    logger.warning("Old exchange stop cancellation unconfirmed: %s", old_order_id)
            except Exception:
                logger.exception("Could not cancel old exchange stop %s", old_order_id)
        event = "exchange_stop_updated" if old_order_id else "exchange_stop_placed"
        self._log_activity(event, {
            "position_id": position_id, "symbol": symbol, "direction": direction,
            "stop_price": self._exchange_stop_levels[position_id], "old_stop": last_stop,
            "new_stop": self._exchange_stop_levels[position_id],
        })
        return abs(self._exchange_stop_levels[position_id] - stop_level) < 1e-8

    async def _sync_exchange_stops(self):
        """Retry missing fixed stops and replace moved stops, without repeating TP/trailing."""
        if not self.position_manager or not self.executor:
            return
        positions = self.position_manager.get_open_positions()
        active_ids = {pos.position_id for pos in positions}
        for pid in list(self._pending_stop_orders):
            if pid not in active_ids:
                await self._cancel_exchange_stop(pid)
        for pid in list(self._exchange_stop_retry_at):
            if pid not in active_ids:
                self._exchange_stop_retry_at.pop(pid, None)
        for pos in positions:
            qty = getattr(pos, "remaining_quantity", None)
            if qty is None:
                qty = pos.quantity
            self._ensure_exchange_stop(
                pos.position_id, pos.symbol, pos.direction, qty, pos.stop_loss,
            )

    async def _detect_exchange_closed_positions(self, ex_open_symbols: Optional[set]):
        """
        Detect positions that are OPEN in the position manager but no longer exist on
        the exchange (exchange-native stop fired, liquidation, or manual close).

        Marks them as STOPPED_OUT so _sync_closed_positions() creates a CompletedTrade
        and stops the monitor from repeatedly sending invalid exit orders.
        """
        if ex_open_symbols is None:
            self._set_exchange_state_known(False, "position snapshot unavailable")
            return
        if not self.position_manager:
            return
        for pos in self.position_manager.get_open_positions():
            if pos.symbol not in ex_open_symbols:
                stop_level = self._exchange_stop_levels.get(pos.position_id)
                exit_price = stop_level or self._price_cache.get(pos.symbol, pos.entry_price)
                logger.warning(
                    f"Position {pos.position_id} ({pos.symbol} {pos.direction}) not found on exchange — "
                    f"native stop fired or liquidation. Marking stopped at {exit_price:.5f}."
                )
                self.position_manager.close_position(
                    pos.position_id,
                    reason="stop_loss",
                    current_price=exit_price,
                )
                self._exchange_stop_orders.pop(pos.position_id, None)
                self._exchange_stop_levels.pop(pos.position_id, None)
                self._exchange_tp_orders.pop(pos.position_id, None)
                self._exchange_trailing_orders.pop(pos.position_id, None)
                self._log_activity("exchange_stop_detected", {
                    "position_id": pos.position_id,
                    "symbol": pos.symbol,
                    "direction": pos.direction,
                    "exit_price": exit_price,
                })

    async def _cancel_exchange_stop(self, position_id: str):
        """Request cleanup after a confirmed exit; executor retains unconfirmed cancellations."""
        pending_id = self._pending_stop_orders.pop(position_id, None)
        order_id = self._exchange_stop_orders.pop(position_id, None)
        self._exchange_stop_levels.pop(position_id, None)
        if not self.executor:
            return
        for oid in {pending_id, order_id} - {None}:
            try:
                confirmed = self.executor.cancel_order(oid)
                logger.info("Exchange stop cancellation requested: pos=%s order=%s confirmed=%s", position_id, oid, confirmed)
            except Exception as exc:
                logger.warning("Could not request stop cleanup for %s: %s", oid, exc)

    async def _cancel_exchange_tp(self, position_id: str):
        """Cancel Phemex native TP limit order — called before software exits and on final close."""
        order_id = self._exchange_tp_orders.pop(position_id, None)
        if not order_id or not self.executor:
            return
        try:
            self.executor.cancel_order(order_id)
            logger.info(f"Exchange TP cancelled before software exit: pos={position_id}")
        except Exception as e:
            logger.warning(f"Could not cancel exchange TP {order_id} (may have already filled): {e}")

    async def _cancel_exchange_trailing(self, position_id: str):
        """Cancel Phemex native trailing stop — called before software exits and on final close."""
        order_id = self._exchange_trailing_orders.pop(position_id, None)
        if not order_id or not self.executor:
            return
        try:
            self.executor.cancel_order(order_id)
            logger.info(f"Exchange trailing stop cancelled before software exit: pos={position_id}")
        except Exception as e:
            logger.warning(f"Could not cancel exchange trailing {order_id} (may have already fired): {e}")

    def _fresh_price_cache(self) -> Dict[str, float]:
        """Only successful local observations within 30 seconds can value new risk."""
        now = time.monotonic()
        return {
            symbol: price for symbol, price in self._price_cache.items()
            if symbol in self._price_cache_observed_at
            and 0 <= now - self._price_cache_observed_at[symbol] <= 30.0
        }

    def _valuation_equity(self) -> Optional[float]:
        if not self.executor:
            return None
        # Allow two scheduled balance intervals; a failed query blocks immediately
        # through balance_known, and a stalled monitor cannot reuse cash forever.
        observed = self.executor.last_balance_observed_at
        interval = getattr(self.config, "balance_reconcile_interval", 60) if self.config else 60
        if (observed is None or not isinstance(interval, (int, float))
                or not math.isfinite(interval) or interval <= 0
                or not 0 <= time.monotonic() - observed <= 2 * interval):
            self.executor.last_equity_error = "Balance observation expired or unavailable"
            return None
        return self.executor.get_equity(self._fresh_price_cache())

    async def _refresh_price_cache(self, extra_symbols=()):
        symbols = set(extra_symbols) | {plan.symbol for plan in self._pending_plans.values()}
        if self.position_manager:
            symbols.update(pos.symbol for pos in self.position_manager.get_open_positions())
        if self.executor:
            symbols.update(self.executor.get_open_position_symbols())
        succeeded = set()
        for symbol in sorted(symbols):
            try:
                price = await self._fetch_price(symbol)
                if (isinstance(price, bool) or not isinstance(price, (int, float))
                        or not math.isfinite(price) or price <= 0):
                    raise ValueError("Invalid ticker price")
                self._price_cache[symbol] = price
                self._price_cache_observed_at[symbol] = time.monotonic()
                succeeded.add(symbol)
            except Exception as exc:
                # Retain last-known display/monitor data, but invalidate it for sizing.
                self._price_cache_observed_at.pop(symbol, None)
                logger.warning("Valuation price refresh failed for %s: %s", symbol, exc)
                self._log_activity("valuation_price_unavailable", {"symbol": symbol, "reason": str(exc)})
        self._price_cache_refreshed_at = (
            datetime.now(timezone.utc) if symbols and succeeded == symbols else None
        )

    def _has_position(self, symbol: str) -> bool:
        # Also block entry on symbols with pre-session exchange positions/orders
        if symbol in self._orphaned_symbols:
            return True
        if not self.position_manager:
            return False
        for pos in list(self.position_manager.positions.values()):
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
                # Tier 1.3: surface to live payload for in-flight NO-TP chip.
                # Mirror of paper_trading_service._get_active_positions.
                "final_targets_remaining": len(getattr(pos, "targets", []) or []),
                "targets_stripped_count": getattr(pos, "targets_stripped_count", 0),
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

            # Cancel any remaining exchange stop/TP/trailing that wasn't cancelled
            # via _execute_exit_order (e.g. stagnation, direction-flip, or native stop
            # that fired while software was lagging).  Pop AFTER attempting cancel so
            # the order_id is still available for the cancel call.
            for _cancel_dict, _label in [
                (self._pending_stop_orders, "pending stop"),
                (self._exchange_stop_orders, "stop"),
                (self._exchange_tp_orders, "tp"),
                (self._exchange_trailing_orders, "trailing"),
            ]:
                _oid = _cancel_dict.pop(pos.position_id, None)
                if _oid and self.executor:
                    try:
                        self.executor.cancel_order(_oid)
                        logger.debug("Cancelled orphaned exchange %s %s on position close", _label, _oid)
                    except Exception as _ce:
                        logger.debug("Could not cancel orphaned %s %s (may have already fired): %s", _label, _oid, _ce)
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
                final_targets_remaining=len(getattr(pos, "targets", []) or []),
                targets_stripped_count=getattr(pos, "targets_stripped_count", 0),
                # Tier 2 macro snapshot pass-through (mirror of paper_trading_service)
                btc_velocity_1h_at_entry=getattr(pos, "btc_velocity_1h_at_entry", 0.0),
                alt_velocity_1h_at_entry=getattr(pos, "alt_velocity_1h_at_entry", 0.0),
                macro_state_at_entry=getattr(pos, "macro_state_at_entry", "unknown"),
                regime_trend_at_entry=getattr(pos, "entry_regime_trend", "sideways"),
                regime_labeled_at=getattr(pos, "regime_labeled_at", "entry"),
                htf_aligned_at_entry=getattr(pos, "htf_aligned_at_entry", False),
                setup_qualifier=getattr(pos, "setup_qualifier", "Unknown"),
            )

            self.completed_trades.append(trade)
            self._completed_trade_ids.add(trade.trade_id)
            self._update_stats(trade)
            if self._session_log_dir:
                try:
                    with open(self._session_log_dir / "trades.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps(trade.to_dict(), default=str) + "\n")
                except Exception as e:
                    logger.warning(
                        f"Failed to append trade {trade.trade_id} to session log: {e}"
                    )
            self._log_activity("trade_closed", {
                "position_id": pos.position_id,
                "symbol": pos.symbol,
                "pnl": pos.total_pnl,
                "exit_reason": exit_reason,
            })

            # Write to journal — use upsert so a re-run / replay doesn't duplicate.
            try:
                get_trade_journal().upsert(trade.to_dict(), self.session_id or "live")
            except Exception as e:
                # Surface persistence failures loudly — losing a trade row is the bug
                # this whole rework is meant to prevent.
                logger.error(
                    f"Failed to write live trade {trade.trade_id} to journal: {e}",
                    exc_info=True,
                )
                self._log_activity("journal_write_error", {
                    "trade_id": trade.trade_id,
                    "error": str(e),
                })

    async def _close_all_positions(self, reason: str):
        """Request exits; retain positions whose full exit has not been confirmed."""
        if not self.position_manager or not self.executor:
            return
        for pos in self.position_manager.get_open_positions():
            try:
                close_side = "SELL" if pos.direction == "LONG" else "BUY"
                qty = getattr(pos, "remaining_quantity", None)
                if qty is None:
                    qty = pos.quantity
                if qty <= 0:
                    continue
                price = self._price_cache.get(pos.symbol, pos.entry_price)
                # The callback retains native protection until the exit is confirmed.
                success = await self._execute_exit_order(pos.symbol, close_side, qty, price)
                if not success:
                    logger.warning(
                        f"Market exit failed for {pos.symbol} {pos.position_id} — "
                        f"position remains locally open; exit requires reconciliation."
                    )
                    continue
                self.position_manager.close_position(pos.position_id, reason, current_price=price)
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
            equity = self._valuation_equity()
            if equity is None:
                logger.warning("Skipping drawdown update: equity unavailable")
                return
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

    def _task_done_callback(self, task: asyncio.Task, generation: Optional[int] = None):
        if generation is not None and generation != self._generation:
            return
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"Live trading task {task.get_name()} crashed: {exc}")
            self.status = LiveBotStatus.ERROR
            if self.executor:
                self.executor.set_entry_admission(False)
            self._running = False
            self._phase = "recovering"
            self._recovery_error = f"Background task failed: {task.get_name()}"


# Global singleton
_live_trading_service: Optional[LiveTradingService] = None


def get_live_trading_service() -> LiveTradingService:
    global _live_trading_service
    if _live_trading_service is None:
        _live_trading_service = LiveTradingService()
    return _live_trading_service
