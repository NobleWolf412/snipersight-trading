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
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace as S
    from unittest.mock import AsyncMock, Mock, patch
    import time
    import ccxt
    from backend.bot.executor.execution_journal import ExecutionJournal
    from backend.bot.executor.live_executor import LiveExecutor
    from backend.bot.executor.position_manager import PositionManager, PositionState, PositionStatus
    from backend.bot.live_trading_service import LiveTradingService
    from backend.data.adapters.phemex_ws import PhemexWebSocketClient

    results, executors = [], []

    def record(name, expected, actual, control=False):
        def equal(a, b):
            if isinstance(a, dict) and isinstance(b, dict):
                return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
            if isinstance(a, (float, int)) and not isinstance(a, bool) and isinstance(b, (float, int)):
                return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
            return a == b
        results.append(dict(case=name, invariant_holds=equal(expected, actual), control=control,
                            expected=expected, actual=actual))

    def executor(fee_rate=0.0):
        state = S(balance={"free": {"USDT": 1000}, "total": {"USDT": 1000}, "used": {"USDT": 0}},
                  positions=[], next_fill=None, submissions=[], cancellations=[])
        def send(**wire):
            state.submissions.append(wire)
            response = {"id": f"remote-{len(state.submissions)}", "status": "open", "filled": 0}
            if state.next_fill is not None:
                response.update(state.next_fill)
                state.next_fill = None
            return response
        def cancel(oid, *a, **kw):
            state.cancellations.append(oid)
            return {"id": oid, "status": "canceled", "filled": 0}
        adapter = S(supports_trading=lambda: True, fetch_balance=lambda: state.balance,
                    fetch_positions=lambda: state.positions, create_order=send, cancel_order=cancel,
                    set_margin_mode=lambda *a, **k: None, set_leverage=lambda *a, **k: None)
        journal = ExecutionJournal(directory / f"ledger-{len(executors)}.sqlite3", "offline-accounting")
        ex = LiveExecutor(adapter, fee_rate=fee_rate, journal=journal,
                          max_position_size_usd=10000, max_total_exposure_usd=20000)
        executors.append(ex)
        ex.set_entry_admission(True)
        return ex, state

    def position(direction):
        return PositionState("position", "BTC/USDT:USDT", direction, 100, 10, 10,
                             99 if direction == "LONG" else 101, [])

    def service(ex, pos=None):
        svc = LiveTradingService()
        svc.executor = ex
        svc._price_cache = {"BTC/USDT:USDT": 100}
        svc._price_cache_observed_at = {"BTC/USDT:USDT": time.monotonic()}
        svc.position_manager = PositionManager(svc._get_price, svc._execute_exit_order)
        if pos:
            svc.position_manager.positions[pos.position_id] = pos
        return svc

    symbol = "BTC/USDT:USDT"
    try:
        # Installed CCXT parser, not an invented interpretation of free/total.
        parser = ccxt.phemex()
        parser.currencies = {"USDT": {"id": "USDT", "code": "USDT", "precision": 8}}
        parser.currencies_by_id = {"USDT": parser.currencies["USDT"]}
        parsed = parser.parse_swap_balance({"data": {"account": {
            "currency": "USDT", "accountBalanceRv": "1000", "totalUsedBalanceRv": "250"}}})
        record("ccxt_balance_parser_control", {"free": 750, "used": 250, "total": 1000},
               {k: parsed[k]["USDT"] for k in ("free", "used", "total")}, True)
        ex, state = executor()
        record("no_reserved_margin_control", 1000, ex.get_equity({}), True)
        state.balance = parsed
        ex.reconcile_balance()
        record("reserved_margin_is_not_loss", {"equity": 1000, "pnl": 0},
               {"equity": ex.get_equity({}), "pnl": ex.get_pnl({})})

        for side, direction in (("BUY", "LONG"), ("SELL", "SHORT")):
            ex, state = executor()
            order = ex.place_order(symbol, side, "LIMIT", 10, price=110)
            ex._process_exchange_order(order, {"status": "open", "filled": 4, "average": 100, "cost": 400})
            record(f"{direction}_first_fill_control", 100, order.average_fill_price, True)
            ex._process_exchange_order(order, {"status": "open", "filled": 4, "average": 100, "cost": 400})
            record(f"{direction}_duplicate_watermark_control", 4, abs(ex._positions[symbol]), True)
            ex._process_exchange_order(order, {"status": "closed", "filled": 10, "average": 106, "cost": 1060})
            record(f"{direction}_cumulative_average", {"average": 106, "fill_cost": 1060, "pnl_at_106": 0},
                   {"average": order.average_fill_price, "fill_cost": sum(f.quantity * f.price for f in ex.get_trade_history()),
                    "pnl_at_106": ex.get_pnl({symbol: 106})})

            ex, state = executor()
            order = ex.place_order(symbol, side, "LIMIT", 10, price=100)
            state.positions = [{"symbol": symbol, "contracts": 10, "side": direction.lower(), "entryPrice": 100}]
            ex.reconcile_positions()
            ex._process_exchange_order(order, {"status": "closed", "filled": 10, "average": 100})
            record(f"{direction}_snapshot_then_delayed_fill", 10, abs(ex._positions[symbol]))

            ex, state = executor(0.001)
            order = ex.place_order(symbol, side, "LIMIT", 10, price=100)
            ex._process_exchange_order(order, {"status": "closed", "filled": 10, "average": 100,
                                               "fee": {"currency": "USDT", "cost": 0.2}})
            record(f"{direction}_reported_fee", 0.2, sum(f.fee for f in ex.get_trade_history()))

            ex, state = executor(0.001)
            order = ex.place_order(symbol, side, "LIMIT", 10, price=100)
            state.balance = {"free": {"USDT": 999}, "total": {"USDT": 999}, "used": {"USDT": 0}}
            ex.reconcile_balance()  # Exchange balance already includes the $1 fee.
            ex._process_exchange_order(order, {"status": "closed", "filled": 10, "average": 100,
                                               "fee": {"currency": "USDT", "cost": 1}})
            record(f"{direction}_balance_snapshot_then_fill_fee", 999, ex.get_balance())

            # Full service close with actual executor receipt; only transport is scripted.
            ex, state = executor(0.001)
            state.next_fill = {"status": "closed", "filled": 10, "average": 100}
            ex.place_order(symbol, side, "LIMIT", 10, price=100)
            pos = position(direction)
            svc = service(ex, pos)
            quote, executed = (110, 109) if direction == "LONG" else (90, 91)
            svc._price_cache[symbol] = quote
            state.next_fill = {"status": "closed", "filled": 10, "average": executed,
                               "fee": {"currency": "USDT", "cost": 10 * executed * 0.001}}
            await svc._close_all_positions("diagnostic")
            sink = Mock()
            with patch("backend.bot.live_trading_service.get_trade_journal", return_value=sink):
                await svc._sync_closed_positions()
            if len(svc.completed_trades) != 1 or sink.upsert.call_count != 1:
                raise RuntimeError("Close did not reach the journal boundary")
            trade = svc.completed_trades[0]
            record(f"{direction}_confirmed_exit_price", executed, trade.exit_price)
            record(f"{direction}_journal_net_result", ex.get_balance() - 1000, trade.pnl)

            ex, state = executor()
            pos = position(direction)
            svc = service(ex, pos)
            svc._exchange_stop_levels[pos.position_id] = pos.stop_loss
            await svc._detect_exchange_closed_positions(set())
            record(f"{direction}_absence_does_not_prove_exit_price_or_cause",
                   {"price": None, "reason": "unverified"},
                   {"price": pos.exit_price, "reason": pos.exit_reason})

            # Most important safety counterexample: feed loss creates a false close,
            # then real service completion cleanup cancels the native protective stop.
            ex, state = executor()
            state.next_fill = {"status": "closed", "filled": 10, "average": 100}
            ex.place_order(symbol, side, "LIMIT", 10, price=100)
            pos = position(direction)
            pos.created_at = datetime.now(timezone.utc) - timedelta(days=100)
            svc = service(ex, pos)
            stop = ex.place_stop_order(symbol, "SELL" if side == "BUY" else "BUY", 10, pos.stop_loss)
            svc._exchange_stop_orders[pos.position_id] = stop.order_id
            svc._exchange_stop_levels[pos.position_id] = pos.stop_loss
            before_sends = len(state.submissions)
            # Use the actual service callback: a missing cache entry returns zero.
            svc._price_cache.clear()
            svc._price_cache_observed_at.clear()
            await svc.position_manager.monitor_all_positions()
            sink = Mock()
            with patch("backend.bot.live_trading_service.get_trade_journal", return_value=sink):
                await svc._sync_closed_positions()
            record(f"{direction}_orphan_retains_exposure_and_protection",
                   {"remaining": 10, "closed_records": 0, "protection_cancels": 0},
                   {"remaining": pos.remaining_quantity, "closed_records": len(svc.completed_trades),
                    "protection_cancels": len(state.cancellations)})
            record(f"{direction}_orphan_fixture_no_exit_was_sent", 0, len(state.submissions) - before_sends, True)

            # An old positive cache has the opposite failure: failed refresh still
            # looks like a new price delivery to the shared manager.
            ex, state = executor()
            state.positions = [{"symbol": symbol, "contracts": 10, "side": direction.lower(), "entryPrice": 100}]
            ex.reconcile_positions()
            pos = position(direction)
            last_observation = datetime.now(timezone.utc) - timedelta(days=100)
            pos._last_monitored_at = last_observation
            svc = service(ex, pos)
            svc._fetch_price = AsyncMock(side_effect=RuntimeError("scripted ticker outage"))
            await svc._refresh_price_cache()
            await svc.position_manager.monitor_all_positions()
            record(f"{direction}_stale_cache_is_not_new_observation", True,
                   pos._last_monitored_at == last_observation)
            record(f"{direction}_stale_cache_risk_control", None, svc._valuation_equity(), True)

            # Negative confirmation control: ordinary stop must remain open.
            pos = position(direction)
            callback = AsyncMock(return_value=False)
            pm = PositionManager(lambda _: pos.stop_loss, callback)
            pm.positions[pos.position_id] = pos
            await pm.monitor_all_positions()
            record(f"{direction}_unconfirmed_stop_control", {"remaining": 10, "callbacks": 1},
                   {"remaining": pos.remaining_quantity, "callbacks": callback.await_count}, True)

        ex, state = executor()
        svc = service(ex)
        ex.balance_known = False
        record("invalid_balance_status_agrees_with_risk", None, svc.get_status()["balance"]["equity"])
        record("invalid_balance_risk_control", None, svc._valuation_equity(), True)

        updates = []
        ws = PhemexWebSocketClient("offline-placeholder", "offline-placeholder", True,
                                   lambda *args: updates.append(args))
        row = {"orderID": "fixture", "clOrdID": "fixture-client", "ordStatus": "Filled",
               "cumQty": "10", "cumValueRv": "1060", "priceRp": "110", "execPriceRp": "110"}
        for kind in ("snapshot", "incremental"):
            updates.clear()
            ws._dispatch(json.dumps({"type": kind, "orders_p": [row], "sequence": 1, "timestamp": 1}))
            record(f"documented_ws_{kind}_delivered", 1, len(updates))
        updates.clear()
        ws._handle_order_event(row)
        if len(updates) != 1:
            raise RuntimeError("Direct WS handler fixture did not invoke callback")
        record("ws_cumulative_cost_price", 106, updates[0][4])

        ex, state = executor()
        order = ex.place_order(symbol, "BUY", "LIMIT", 10, price=110)
        ws = PhemexWebSocketClient("offline-placeholder", "offline-placeholder", True, ex.apply_ws_fill)
        row.update(orderID=ex._exchange_order_map[order.order_id], clOrdID=order.order_id)
        ws._handle_order_event(row)
        ex._process_exchange_order(order, {"status": "closed", "filled": 10, "average": 106, "cost": 1060})
        record("terminal_rest_price_correction", 106, order.average_fill_price)
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
