"""Offline D10 discovery probe, not a trading client or a passing regression suite.

Run with Python -B. Compiles selected current source definitions without importing
application modules. All adapter responses are scripted in memory. Exit 1 means
the listed lifecycle defects reproduced; exit 2 means the probe itself failed.
Writes only temporary execution journals, never reads credentials or contacts an exchange.
"""

import ast
from copy import deepcopy
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import logging
import math
import os
from pathlib import Path
from threading import RLock
import sys
import time
from types import SimpleNamespace as S
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock
import uuid
import tempfile
from decimal import Decimal


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.bot.executor.execution_journal import ExecutionJournal, JournalError
from backend.bot.executor.accounting_runtime import AccountRuntime, Commitment
from backend.bot.executor.execution_fee_recovery import ExecutionFeeRecovery
from backend.bot.trade_journal import TradeJournalService
from backend.bot.executor.accounting_models import AccountingError, ObservationContext, amount, execution_update
from backend.data.adapters.phemex_accounting import normalize_order, normalize_execution

DIAGNOSTIC_ROOT = None
EXECUTORS = []
SOURCES = {
    "orders": "backend/bot/executor/paper_executor.py",
    "executor": "backend/bot/executor/live_executor.py",
    "service": "backend/bot/live_trading_service.py",
}


def offline_guard(event, args):
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0]))
        if path.name == ".env":
            raise RuntimeError("Credential-file access blocked")
        if any(c in (args[1] or "") for c in "wax+") or (args[2] or 0) & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
        ):
            if DIAGNOSTIC_ROOT is None or not path.resolve().is_relative_to(DIAGNOSTIC_ROOT):
                raise RuntimeError("Diagnostic writes outside temporary fixtures blocked")
    if event in ("socket.connect", "socket.bind"):
        if not isinstance(args[1], tuple) or args[1][0] not in ("127.0.0.1", "::1"):
            raise RuntimeError("External socket blocked")
    if event == "socket.getaddrinfo" and args[0] not in ("127.0.0.1", "::1", "localhost", None):
        raise RuntimeError("External DNS blocked")
    if event.startswith("subprocess.") or event == "os.system":
        raise RuntimeError("Child process blocked")


class FixtureRejection(Exception):
    pass


def load_definitions():
    logger = logging.getLogger("offline.lifecycle.probe")
    logger.handlers = [logging.NullHandler()]
    logger.propagate = False
    namespace = dict(globals(), logger=logger, PhemexAdapter=S,
                     get_trade_journal=lambda: TradeJournalService(DIAGNOSTIC_ROOT / 'reports.jsonl'),
                     LiveTradingConfig=S, PaperTradingStats=lambda: S(to_dict=lambda: {}),
                     ccxt=S(InsufficientFunds=FixtureRejection, InvalidOrder=FixtureRejection))
    hashes, selected = {}, {}

    def extract(key, name, methods=None):
        path = ROOT / SOURCES[key]
        raw = path.read_bytes()
        hashes[SOURCES[key]] = hashlib.sha256(raw).hexdigest()
        cls = next(n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef) and n.name == name)
        if methods is not None:
            cls.body = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in methods]
            if {n.name for n in cls.body} != set(methods):
                raise RuntimeError(f"Source definitions changed: {name}")
        selected[name] = {n.name: n.lineno for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), str(path), "exec", dont_inherit=True), namespace)

    for name in ("OrderSide", "OrderType", "OrderStatus", "Order", "Fill"):
        extract("orders", name)
    extract("service", "LiveBotStatus")
    extract("service", "LifecycleConflict")
    extract("executor", "LiveExecutor", (
        "__init__", "_generate_order_id", "_submission_unknown", "_accept_submission",
        "refresh_order", "_reject_submission", "_fetch_balance_from_exchange", "_total_exposure_usd",
        "place_order", "cancel_order", "get_order", "get_open_orders", "get_open_entry_orders",
        "get_balance", "get_position", "get_open_position_symbols", "reconcile_positions",
        "_process_exchange_order", "_record_fill", "_update_position",
        "set_entry_admission", "recovery_snapshot", "recover_uncertain_orders",
        "_restore_execution", "_durable_state", "_storage_failure", "_require_storage",
        "_persist_order", "_send_journaled_order", "checkpoint_flat", "close",
        "accounting_status", "balance_status", "reconcile_account", "invalidate_account",
        "execution_receipt", "execution_outcome",
        "_check_account_admission_lease", "_process_accounting_order", "_execution_context",
    ))
    extract("service", "LiveTradingService", (
        "__init__", "stop", "kill_switch", "reset", "get_status", "_get_uptime_seconds",
        "_close_all_positions", "_set_exchange_state_known", "_entry_reconciliation_ready", "_startup_reconcile",
        "_request_shutdown", "_shutdown_loop", "_shutdown_step", "_local_shutdown_settled", "_recover_execution_reports",
        "_observe_account", "_verify_resettable", "_lifecycle_status", "_write_session_report", "_reset_session",
    ))
    return namespace, hashes, selected


async def run_probes(ns):
    records = []

    def record(name, direction, safe, **observed):
        records.append(dict(check=name, direction=direction, safety_condition_met=bool(safe), observed=observed))

    def adapter():
        from backend.tests.unit.runtime_fixtures import prepare_adapter
        return prepare_adapter(S(
            supports_trading=lambda: True, set_position_mode_one_way=Mock(return_value=True),
            fetch_balance=Mock(return_value={"free": {"USDT": 1000}}),
            fetch_positions=Mock(return_value=[]), exchange=S(fetch_open_orders=Mock(return_value=[])),
            fetch_account_snapshot=Mock(return_value={"complete": True, "scope": "phemex:swap:USDT", "positions": [], "orders": []}),
            fetch_order=Mock(return_value={"status": "open", "filled": 0}),
            set_margin_mode=Mock(), set_leverage=Mock(), cancel_order=Mock(return_value={"status": "canceled", "filled": 0}),
            create_order=Mock(side_effect=TimeoutError("fixture: acknowledgment lost")),
            fetch_order_by_client_id=Mock(side_effect=LookupError("fixture: order not visible")),
        ), symbol='FIXTURE/USDT', binding='offline-fixture')

    def executor(ad, path=None):
        from backend.tests.unit.runtime_fixtures import initialize_fixture
        journal = ExecutionJournal(path or DIAGNOSTIC_ROOT / f"{uuid.uuid4().hex}.sqlite3", "offline-fixture",
                                   runtime=True, environment='testnet')
        ex = ns["LiveExecutor"](ad, max_position_size_usd=2000, max_total_exposure_usd=2000, journal=journal)
        initialize_fixture(ex)
        EXECUTORS.append(ex)
        return ex

    def service(ex):
        svc = ns["LiveTradingService"]()
        svc.executor, svc.adapter = ex, ex._adapter
        svc.config = S(dry_run=False, testnet=True, to_dict=lambda: {})
        svc.status = ns["LiveBotStatus"].RUNNING
        svc._running = True
        svc._phase = "running"
        svc._log_activity = Mock()
        svc._monitor_pending_entries = AsyncMock()
        svc._sync_closed_positions = AsyncMock()
        # Position presentation is deliberately outside this lifecycle probe.
        svc._get_active_positions = lambda: []
        svc.position_manager = S(positions={}, get_open_positions=lambda: [], close_position=Mock())
        return svc

    for direction, side in (("LONG", "BUY"), ("SHORT", "SELL")):
        ad = adapter()
        ex = executor(ad)
        order = ex.place_order("FIXTURE/USDT", side, "LIMIT", 10, price=100)
        svc = service(ex)
        svc._pending_plans[order.order_id] = S(direction=direction)
        before = svc.get_status()
        record("uncertain_entry_visible_in_status", direction,
               any(row["order_id"] == order.order_id for row in before["pending_orders"]),
               order_status=order.status.value, pending_display_count=len(before["pending_orders"]),
               reserved_usd=ex.accounting_status()['held_commitments'])

        async def background():
            await asyncio.Event().wait()

        svc._monitor_task = asyncio.create_task(background())
        await asyncio.sleep(0)
        stopped = await svc.stop()
        cancel_attempts = ad.cancel_order.call_count + ad.fetch_order_by_client_id.call_count
        record("stop_attempts_pending_entry_cancellation", direction, cancel_attempts > 0,
               cancellation_or_identity_lookup_attempts=cancel_attempts,
               order_status=order.status.value, response_status=stopped["status"])
        record("stop_retains_recovery_for_unresolved_requests", direction,
               not svc._shutdown_task.done() or not ex._unacknowledged_orders,
               monitor_cancelled=svc._monitor_task.cancelled(), unresolved_orders=len(ex._unacknowledged_orders))

        svc._pending_exit_orders["FIXTURE/USDT"] = "fixture-exit"
        svc._pending_stop_orders["fixture-position"] = "fixture-stop"
        try:
            await svc.reset()
            reset_refused = False
        except ValueError:
            reset_refused = True
        record("reset_preserves_unresolved_state", direction, reset_refused,
               reset_refused=reset_refused, executor_retained=svc.executor is ex,
               pending_exit_count=len(svc._pending_exit_orders), pending_stop_count=len(svc._pending_stop_orders))

        # The new constructor is the production reconstruction boundary; this is
        # a fresh object with the same scripted adapter, not an OS-crash test.
        svc._shutdown_task.cancel()
        try:
            await svc._shutdown_task
        except asyncio.CancelledError:
            pass
        if svc._shutdown_step_task:
            await svc._shutdown_step_task
        path = ex._journal.path
        ex.close()
        fresh = executor(ad, path)
        restarted = service(fresh)
        lookup_before = ad.fetch_order_by_client_id.call_count
        fresh.refresh_order(order.order_id)
        startup_ready = fresh.recovery_snapshot()["entry_admission_enabled"]
        record("fresh_executor_retains_prior_uncertain_identity", direction,
               fresh.get_order(order.order_id) is not None and not startup_ready,
               original_executor_unresolved=len(ex._unacknowledged_orders),
               new_executor_unresolved=len(fresh._unacknowledged_orders),
               startup_ready=startup_ready, client_identity_lookups=ad.fetch_order_by_client_id.call_count - lookup_before)

        # Control: kill DOES request cancellation, but cannot confirm it in this fixture.
        ad2 = adapter()
        ex2 = executor(ad2)
        pending = ex2.place_order("FIXTURE/USDT", side, "LIMIT", 10, price=100)
        killed = service(ex2)
        killed._monitor_task = asyncio.create_task(background())
        await asyncio.sleep(0)
        result = await killed.kill_switch()
        assert ad2.fetch_order_by_client_id.call_count > 0, "Kill-switch cancellation control failed"
        record("kill_retains_recovery_after_uncertain_cancel", direction,
               not killed._shutdown_task.done() or not ex2._unacknowledged_orders,
               response_status=result["status"], monitor_cancelled=killed._monitor_task.cancelled(),
               unresolved_orders=len(ex2._unacknowledged_orders),
               cancellation_intent_retained=pending.order_id in ex2._cancel_requested_orders)

        accepted_adapter = adapter()
        accepted_adapter.create_order.side_effect = None
        accepted_adapter.create_order.return_value = {"id": "fixture-remote", "status": "open", "filled": 0}
        accepted_executor = executor(accepted_adapter)
        accepted = accepted_executor.place_order("FIXTURE/USDT", side, "LIMIT", 10, price=100)
        assert accepted.status == ns["OrderStatus"].OPEN, "Acknowledged-entry control failed"
        await service(accepted_executor).stop()
        record("stop_cancels_acknowledged_entry", direction,
               accepted_adapter.cancel_order.call_count > 0,
               order_status=accepted.status.value, cancellation_attempts=accepted_adapter.cancel_order.call_count)

        # Stop's real task-cancellation await is a scheduling boundary. Observe
        # the worker's cancellation without injecting an await into the exit path.
        race = service(executor(adapter()))
        pos = S(position_id="fixture-position", symbol="FIXTURE/USDT", direction=direction,
                quantity=10, remaining_quantity=10, entry_price=100)
        original_manager = S(positions={}, get_open_positions=lambda: [pos], close_position=Mock())
        race.position_manager = original_manager
        cancelled = asyncio.Event()

        async def cancellable_scan():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        race._execute_exit_order = AsyncMock(return_value=True)
        race._scan_task = asyncio.create_task(cancellable_scan())
        await asyncio.sleep(0)  # Start the worker so cancellation reaches its finally.
        stop_task = asyncio.create_task(race.stop())
        # No wait_for wrapper here: the observer wakes before Stop resumes from
        # awaiting the cancelled worker. The whole diagnostic is externally bounded.
        await cancelled.wait()
        try:
            await race.reset()
            refused = False
        except ValueError:
            refused = True
        result = await asyncio.wait_for(stop_task, timeout=2)
        record("reset_excluded_while_stop_awaits_task", direction, refused,
               reset_refused=refused, original_manager_close_calls=original_manager.close_position.call_count,
               final_response_status=result["status"])

        # D9 control: unconfirmed full exits must keep the local position open.
        protected = service(executor(adapter()))
        protected.position_manager = S(positions={}, get_open_positions=lambda: [pos], close_position=Mock())
        protected._execute_exit_order = AsyncMock(return_value=False)
        await protected._close_all_positions("fixture")
        assert protected.position_manager.close_position.call_count == 0, "D9 unconfirmed-exit control failed"
        for fixture in (svc, killed, race):
            if fixture._shutdown_task:
                fixture._shutdown_task.cancel()
                try:
                    await fixture._shutdown_task
                except asyncio.CancelledError:
                    pass
    return records


def main():
    global DIAGNOSTIC_ROOT
    sys.dont_write_bytecode = True
    temporary = tempfile.TemporaryDirectory(prefix="snipersight-lifecycle-probe-")
    DIAGNOSTIC_ROOT = Path(temporary.name).resolve()
    sys.addaudithook(offline_guard)
    try:
        ns, before, selected = load_definitions()
        async def bounded_probes():
            async with asyncio.timeout(5):
                return await run_probes(ns)

        records = asyncio.run(bounded_probes())
        after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in before}
        if before != after:
            raise RuntimeError("Inspected source changed while diagnostic ran")
        failures = sum(not row["safety_condition_met"] for row in records)
        print(json.dumps(dict(
            summary=f"{failures}/{len(records)} lifecycle safety conditions violated in offline fixtures",
            classification="lifecycle safety probe with durable executor reconstruction",
            controls="kill attempts cancellation; D9 does not book an unconfirmed exit (both directions)",
            limitations="AST-selected production definitions; scripted adapters and presentation; no app import, exchange, UI runtime, or actual process crash",
            source_sha256=before, selected_symbols=selected, observations=records,
        ), indent=2))
        return 1 if failures else 0
    except Exception as exc:
        print(json.dumps({"probe_error": f"{type(exc).__name__}: {exc}"}))
        return 2
    finally:
        for ex in EXECUTORS:
            ex.close()
        temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
