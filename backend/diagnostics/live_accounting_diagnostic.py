"""Offline accounting counterexamples against current application methods.

Run with python -B backend/diagnostics/live_accounting_diagnostic.py.
Exit 0: all invariants hold; 1: reproduced defects; 2: harness failure.
Scripted transport only. No application startup, credentials or exchange access.
Temporary artifacts are retained for inspection; historical journals are never opened.
"""
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SOURCES = (
    "backend/diagnostics/live_accounting_diagnostic.py",
    "backend/bot/executor/accounting_runtime.py", "backend/bot/executor/execution_outcomes.py",
    "backend/bot/executor/execution_reports.py", "backend/data/adapters/phemex_accounting.py",
    "backend/bot/executor/live_executor.py", "backend/bot/executor/execution_journal.py",
    "backend/bot/executor/position_manager.py", "backend/bot/live_trading_service.py",
    "backend/bot/paper_trading_service.py", "backend/bot/executor/paper_executor.py",
    "backend/data/adapters/phemex.py", "backend/data/adapters/phemex_ws.py",
    "backend/venv/Lib/site-packages/ccxt/phemex.py",
)


def guard_offline(directory):
    for name in list(os.environ):
        if name.startswith(("PHEMEX_", "BINANCE_", "TELEGRAM_", "DISCORD_")):
            del os.environ[name]
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    sys.dont_write_bytecode = True
    tempfile.tempdir = str(directory)
    os.chdir(directory)

    def guard(event, args):
        if event in ("open", "sqlite3.connect") and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(args[0])
            if event == "sqlite3.connect" and name.startswith("file:"):
                from urllib.parse import unquote, urlsplit
                uri = urlsplit(name)
                if uri.netloc not in ("", "localhost"):
                    raise RuntimeError("Nonlocal SQLite URI blocked")
                name = unquote(uri.path)
                if os.name == "nt" and name.startswith("/"):
                    name = name[1:]
            path = Path(name).resolve()
            if path.name == ".env":
                raise RuntimeError("Credential file access blocked")
            mode = (args[1] or "") if event == "open" else "w"
            flags = (args[2] or 0) if event == "open" else 0
            writing = any(c in mode for c in "wax+") or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            if writing and path != Path(os.devnull).resolve() and not path.is_relative_to(directory):
                raise RuntimeError("Write outside diagnostic fixture blocked")
        if event in ("socket.connect", "socket.bind"):
            # Windows asyncio's local self-pipe; all external endpoints denied.
            address = args[1]
            if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1"):
                raise RuntimeError("Diagnostic network access blocked")
        if event == "socket.getaddrinfo":
            raise RuntimeError("Diagnostic DNS access blocked")
        if event.startswith("subprocess.") or event == "os.system":
            raise OSError("Nested subprocess blocked")
    sys.addaudithook(guard)


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


async def exercise(directory):
    """Exercise raw runtime authority with disposable stores and identified evidence."""
    from copy import deepcopy
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal as D
    from types import SimpleNamespace as S
    from unittest.mock import AsyncMock, Mock, patch
    import asyncio
    import time
    import ccxt
    from loguru import logger as loguru_logger
    loguru_logger.remove()
    loguru_logger.add(str(directory / "diagnostic.log"))
    logging.basicConfig(filename=directory / "diagnostic.log", level=logging.INFO)
    from backend.bot.executor.accounting_models import ObservationContext
    from backend.bot.executor.execution_journal import ExecutionJournal
    from backend.bot.executor.live_executor import LiveExecutor
    from backend.bot.executor.position_manager import PositionManager, PositionState
    from backend.bot.live_trading_service import LiveTradingService
    from backend.bot.trade_journal import TradeJournalService
    from backend.data.adapters.phemex_accounting import normalize_account
    from backend.data.adapters.phemex_ws import PhemexWebSocketClient

    results, executors = [], []
    symbol, binding = "BTC/USDT:USDT", "offline-accounting"
    market = dict(id="BTCUSDT", symbol=symbol, swap=True, linear=True, inverse=False,
                  quote="USDT", settle="USDT", contractSize=1)

    def record(name, expected, actual, control=False):
        def equal(a, b):
            if isinstance(a, dict) and isinstance(b, dict):
                return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
            if type(a) in (float, int) and type(b) in (float, int):
                return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
            return a == b
        results.append(dict(case=name, invariant_holds=equal(expected, actual), control=control,
                            expected=expected, actual=actual))

    def executor():
        state = S(wallet="1000", used="250", quantity="0", side="Buy", entry="100", mark="100",
                  upnl="0", next_fill=None, submissions=[], cancellations=[], rows={})
        def account():
            now = time.monotonic()
            position = dict(accountID=1, currency="USDT", symbol="BTCUSDT", side=state.side,
                sizeRq=state.quantity, posMode="OneWay", posSide="Merged", avgEntryPriceRp=state.entry,
                markPriceRp=state.mark, unRealisedPnlRv=state.upnl)
            if D(state.quantity) == 0:
                position.update(side="None", avgEntryPriceRp="0", unRealisedPnlRv="0")
            raw = dict(code=0, data=dict(account=dict(accountId=1, currency="USDT",
                accountBalanceRv=state.wallet, totalUsedBalanceRv=state.used, bonusBalanceRv="0"),
                positions=[position]))
            context = ObservationContext(environment="testnet", binding=binding, source="offline:account",
                observation_id=str(time.monotonic_ns()), received_at=datetime.now(timezone.utc).isoformat(),
                started_monotonic=now, ended_monotonic=now)
            return normalize_account(raw, {symbol: market}, context)
        def send(**wire):
            state.submissions.append(wire)
            oid = "remote-" + str(len(state.submissions))
            row = dict(orderID=oid, clOrdID=wire["params"]["clientOrderId"], symbol="BTCUSDT",
                side=wire["side"].title(), orderQtyRq=str(wire["amount"]), cumQtyRq="0",
                cumValueRv="0", execFeeRv="0", ordStatus="New")
            if state.next_fill:
                row.update(state.next_fill)
                state.next_fill = None
                row.update(execID=oid + '-fill', execQtyRq=row['cumQtyRq'],
                           execValueRv=row['cumValueRv'], tradeType='Trade', currency='USDT')
            state.rows[oid] = row
            return dict(id=oid, info=deepcopy(row))
        def fetch(oid, *args):
            return dict(id=oid, info=deepcopy(state.rows[oid]))
        def cancel(oid, *args):
            state.cancellations.append(oid)
            state.rows[oid]["ordStatus"] = "Canceled"
            return dict(fetch(oid), status="canceled")
        adapter = S(testnet=True, supports_trading=lambda: True, exchange=S(markets={symbol: market}),
            create_order=send, fetch_order=fetch, cancel_order=cancel, fetch_account_observation=account,
            set_margin_mode=lambda *a, **k: None, set_leverage=lambda *a, **k: None)
        journal = ExecutionJournal(directory / ("ledger-" + str(len(executors)) + ".sqlite3"),
                                   binding, runtime=True, environment="testnet")
        ex = LiveExecutor(adapter, journal=journal, max_position_size_usd=10000, max_total_exposure_usd=20000)
        executors.append(ex)
        ex._accounting.establish_flat_baseline()
        ex.reconcile_account(force=True)
        ex.set_entry_admission(True)
        return ex, state

    def update(ex, state, order, quantity, cost, *, status="Filled", fee="0.2"):
        row = state.rows[ex._exchange_order_map[order.order_id]]
        previous_qty, previous_cost = D(row['cumQtyRq']), row.get('cumValueRv')
        if D(str(quantity)) > previous_qty:
            row.update(execID=order.order_id + '-fill-' + str(quantity),
                       execQtyRq=str(D(str(quantity)) - previous_qty), tradeType='Trade', currency='USDT')
            if cost is not None and previous_cost is not None:
                row['execValueRv'] = str(D(str(cost)) - D(previous_cost))
            else:
                row.pop('execValueRv', None)
        elif cost is not None and row.get('execValueRv') is None:
            row['execValueRv'] = str(cost)
        row.update(cumQtyRq=str(quantity), ordStatus=status)
        if cost is None:
            row.pop("cumValueRv", None)
        else:
            row["cumValueRv"] = str(cost)
        if fee is None:
            row.pop("execFeeRv", None)
        else:
            row["execFeeRv"] = fee
        ex.apply_ws_order(deepcopy(row))

    def observed(ex, state, quantity, side, *, entry="100", mark="100", upnl="0"):
        state.quantity, state.side = str(quantity), side.title()
        state.entry, state.mark, state.upnl = entry, mark, upnl
        return ex.reconcile_account(force=True)

    def service(ex, entry, direction):
        pos = PositionState("position", symbol, direction, 100, 10, 10,
                            99 if direction == "LONG" else 101, [], entry_order_id=entry.order_id)
        svc = LiveTradingService()
        svc.executor = ex
        svc._price_cache = {symbol: 100}
        svc._price_cache_observed_at = {symbol: time.monotonic()}
        svc.position_manager = PositionManager(svc._get_price, svc._execute_exit_order, receipt_execution=True)
        svc.position_manager.positions[pos.position_id] = pos
        return svc, pos

    try:
        parser = ccxt.phemex()
        parser.currencies = {"USDT": {"id": "USDT", "code": "USDT", "precision": 8}}
        parser.currencies_by_id = {"USDT": parser.currencies["USDT"]}
        parsed = parser.parse_swap_balance({"data": {"account": {
            "currency": "USDT", "accountBalanceRv": "1000", "totalUsedBalanceRv": "250"}}})
        record("ccxt_balance_parser_control", {"free": 750, "used": 250, "total": 1000},
               {k: parsed[k]["USDT"] for k in ("free", "used", "total")}, True)
        ex, state = executor()
        record("reserved_margin_is_not_loss", {"equity": 1000, "free": 750, "change": 0},
               {"equity": ex.get_equity({}), "free": ex.get_balance(), "change": ex.get_pnl({})})

        for side, direction in (("BUY", "LONG"), ("SELL", "SHORT")):
            ex, state = executor()
            order = ex.place_order(symbol, side, "LIMIT", 10, price=110)
            update(ex, state, order, 4, 400, status="PartiallyFilled", fee="0.08")
            record(direction + "_first_fill_control", 100, ex.execution_receipt(order.order_id).average_price, True)
            observed(ex, state, 4, side)
            update(ex, state, order, 4, 400, status="PartiallyFilled", fee="0.08")
            record(direction + "_duplicate_watermark", 4, float(ex.execution_receipt(order.order_id).quantity))
            update(ex, state, order, 10, 1060, fee='0.12')
            observed(ex, state, 10, side, entry="106", mark="106")
            receipt = ex.execution_receipt(order.order_id)
            record(direction + "_cumulative_average", {"average": 106, "cost": 1060, "position": 10},
                   {"average": receipt.average_price, "cost": float(receipt.cost) if receipt.cost is not None else None, "position": abs(ex.get_position(symbol))})
            record(direction + "_reported_fee", 0.2, float(receipt.fees[0].amount) if receipt.fees else None)
            state.wallet = "999.8"
            observed(ex, state, 10, side, entry="106", mark="106")
            update(ex, state, order, 10, 1060, fee='0.12')
            observed(ex, state, 10, side, entry="106", mark="106")
            record(direction + "_snapshot_fee_not_charged_again", 999.8, ex.get_equity({}))

            ex, state = executor()
            order = ex.place_order(symbol, side, "LIMIT", 10, price=110)
            observed(ex, state, 10, side)
            update(ex, state, order, 10, 1000)
            record(direction + "_snapshot_then_delayed_fill", 10, abs(ex.get_position(symbol)))
            observed(ex, state, 10, side)
            svc, pos = service(ex, order, direction)
            quote, executed = (110, 109) if direction == "LONG" else (90, 91)
            svc._price_cache[symbol] = quote
            state.next_fill = dict(ordStatus="Filled", cumQtyRq="10", cumValueRv=str(10 * executed), execFeeRv="0.3")
            await svc._close_all_positions("diagnostic")
            sink = TradeJournalService(directory / (direction + "-reports.jsonl"))
            with patch("backend.bot.live_trading_service.get_trade_journal", return_value=sink):
                await svc._sync_closed_positions()
            record(direction + "_completed_report_count", 1, len(svc.completed_trades))
            trade = svc.completed_trades[0] if svc.completed_trades else None
            record(direction + "_confirmed_exit_price", executed, trade.exit_price if trade else None)
            record(direction + "_journal_actual_net_result", 89.5, trade.pnl if trade else None)

            ex, state = executor()
            order = ex.place_order(symbol, side, "LIMIT", 10, price=110)
            update(ex, state, order, 10, None, fee=None)
            view = observed(ex, state, 10, side)
            record(direction + "_unknown_cost_does_not_use_quote", None, ex.execution_receipt(order.order_id).cost)
            record(direction + "_unknown_cost_blocks_new_entry", False, view["entry_eligible"])
            update(ex, state, order, 10, 1000, fee="0")
            observed(ex, state, 10, side)
            record(direction + "_late_cost_without_second_fill", {"quantity": 10, "price": 100, "fee": 0},
                   {"quantity": float(ex.execution_receipt(order.order_id).quantity),
                    "price": ex.execution_receipt(order.order_id).average_price,
                    "fee": (float(ex.execution_receipt(order.order_id).fees[0].amount)
                            if ex.execution_receipt(order.order_id).fees else None)})
            svc, pos = service(ex, order, direction)
            observed(ex, state, 0, side)
            await svc._detect_exchange_closed_positions(set())
            record(direction + "_absence_cannot_establish_closure", {"remaining": 10, "price": None, "pending": True},
                   {"remaining": pos.remaining_quantity, "price": pos.exit_price, "pending": pos.exchange_close_pending})

            ex, state = executor()
            order = ex.place_order(symbol, side, "LIMIT", 10, price=110)
            update(ex, state, order, 10, 1000)
            observed(ex, state, 10, side)
            svc, pos = service(ex, order, direction)
            stop = ex.place_stop_order(symbol, "SELL" if side == "BUY" else "BUY", 10, pos.stop_loss,
                                       parent_entry_order_id=order.order_id)
            svc._exchange_stop_orders[pos.position_id] = stop.order_id
            pos.created_at = datetime.now(timezone.utc) - timedelta(days=100)
            before_sends = len(state.submissions)
            svc._price_cache.clear()
            svc._price_cache_observed_at.clear()
            await svc.position_manager.monitor_all_positions()
            record(direction + "_feed_loss_keeps_exposure_and_protection", {"remaining": 10, "sends": 0, "cancels": 0},
                   {"remaining": pos.remaining_quantity, "sends": len(state.submissions) - before_sends,
                    "cancels": len(state.cancellations)})
            previous = datetime.now(timezone.utc) - timedelta(days=100)
            pos._last_monitored_at = previous
            svc._price_cache[symbol] = 100
            svc._price_cache_observed_at[symbol] = time.monotonic() - 120
            svc._fetch_price = AsyncMock(side_effect=RuntimeError("scripted ticker outage"))
            await svc._refresh_price_cache()
            await svc.position_manager.monitor_all_positions()
            record(direction + "_stale_cache_is_not_new_observation", True, pos._last_monitored_at == previous)

            callback = AsyncMock(return_value=False)
            pm = PositionManager(lambda _: pos.stop_loss, callback, receipt_execution=True)
            pos.created_at = datetime.now(timezone.utc)
            pm.positions[pos.position_id] = pos
            await pm.monitor_all_positions()
            record(direction + "_unconfirmed_stop_control", {"remaining": 10, "callbacks": 1},
                   {"remaining": pos.remaining_quantity, "callbacks": callback.await_count}, True)

        for kind in ("snapshot", "incremental"):
            ex, state = executor()
            order = ex.place_order(symbol, "BUY", "LIMIT", 10, price=110)
            raw = state.rows[ex._exchange_order_map[order.order_id]]
            raw.update(cumQtyRq="10", cumValueRv="1060", execFeeRv="0.2", ordStatus="Filled")
            client = PhemexWebSocketClient("offline", "offline", True, on_raw_order=ex.apply_ws_order,
                on_invalidate=ex.invalidate_account, on_pending=ex.ws_event_pending, on_complete=ex.ws_event_complete)
            client._worker = asyncio.create_task(client._consume_orders())
            client._dispatch(json.dumps({"type": kind, "orders_p": [raw, raw]}))
            await client.stop()
            record("raw_ws_" + kind + "_drained_once", {"quantity": 10, "price": 106, "pending": 0, "failures": 0},
                   {"quantity": float(ex.execution_receipt(order.order_id).quantity),
                    "price": ex.execution_receipt(order.order_id).average_price,
                    "pending": ex._accounting.pending_events, "failures": client.metrics["callback_failures_total"]})
        ex, state = executor()
        ex.invalidate_account("fixture_gap")
        svc = LiveTradingService()
        svc.executor = ex
        record("invalidated_account_status_is_unknown", None, svc.get_status()["balance"]["equity"])
        return results
    finally:
        for ex in executors:
            ex.close()


def main():
    directory = Path(tempfile.mkdtemp(prefix="snipersight-accounting-")).resolve()
    before = source_hashes()
    guard_offline(directory)
    import asyncio
    try:
        results = asyncio.run(exercise(directory))
        after = source_hashes()
        if before != after or any(r["control"] and not r["invariant_holds"] for r in results):
            raise RuntimeError("Source preservation or diagnostic control failed")
        failures = sum(not r["invariant_holds"] for r in results)
        report = {"scope": "scripted offline counterexamples; no live incidence established",
                  "cases": len(results), "invariant_failures": failures,
                  "controls_passed": sum(r["control"] for r in results),
                  "sources_unchanged": before == after, "source_hashes": after,
                  "ccxt_version": __import__("ccxt").__version__,
                  "artifact_directory": str(directory), "results": results}
        exit_code = int(failures > 0)
    except Exception:
        import traceback
        report = {"harness_error": traceback.format_exc(), "artifact_directory": str(directory)}
        exit_code = 2
    finally:
        logging.shutdown()
    (directory / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
