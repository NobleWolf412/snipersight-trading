"""Offline evidence for the proposed account/execution ownership boundary.

Uses installed CCXT parsers and actual executor/backfill methods with scripted
transport. Exit 1 denotes reproduced application defects; 2 a harness failure.
No production changes, credentials, exchange calls or historical writes.
"""
import asyncio
import hashlib
import json
import logging
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.diagnostics.live_accounting_diagnostic import guard_offline, source_hashes


async def exercise(directory):
    from types import SimpleNamespace as S
    from unittest.mock import Mock
    import ccxt
    from backend.bot.executor.execution_journal import ExecutionJournal
    from backend.bot.executor.live_executor import LiveExecutor
    from backend.bot.live_trading_service import LiveTradingService
    from backend.tests.unit.runtime_fixtures import prepare_adapter, initialize_fixture

    results = []
    def record(name, expected, actual, control=False):
        results.append(dict(case=name, expected=expected, actual=actual,
                            invariant_holds=expected == actual, control=control))

    market = {"id": "BTCUSDT", "symbol": "BTC/USDT:USDT", "type": "swap", "swap": True,
              "spot": False, "linear": True, "inverse": False, "contract": True,
              "settle": "USDT", "settleId": "USDT", "base": "BTC", "quote": "USDT",
              "baseId": "BTC", "quoteId": "USDT", "contractSize": 1,
              "precision": {"price": 0.1, "amount": 0.001}, "info": {}}
    client = ccxt.phemex({"options": {"defaultType": "swap"}})
    client.set_markets([market])
    client.load_markets = lambda *a, **k: client.markets
    symbol = market["symbol"]
    position = {"symbol": "BTCUSDT", "currency": "USDT", "side": "Buy", "sizeRq": "10",
                "avgEntryPriceRp": "100", "markPriceRp": "106", "valueRv": "1000",
                "unRealisedPnlRv": "60", "positionMarginRv": "250", "assignedPosBalanceRv": "250",
                "leverageRr": "4", "maintMarginReqRr": "0.01", "crossMargin": False,
                "posSide": "Merged", "posMode": "OneWay", "execSeq": 9}
    body = {"code": 0, "data": {"account": {"currency": "USDT", "accountBalanceRv": "1000",
                                               "totalUsedBalanceRv": "250", "bonusBalanceRv": "0"},
                                "positions": [position]}}
    client.privateGetGAccountsPositions = Mock(return_value=body)
    parsed_positions = client.fetch_positions(params={"method": "privateGetGAccountsPositions"})
    parsed_balance = client.parse_swap_balance(body)
    record("combined_valuation_route_and_units", {"calls": 1, "currency": "USDT", "wallet": 1000,
           "free": 750, "base_qty": 10, "upnl": 60, "equity": 1060},
           {"calls": client.privateGetGAccountsPositions.call_count,
            "currency": client.privateGetGAccountsPositions.call_args.args[0]["currency"],
            "wallet": parsed_balance["total"]["USDT"], "free": parsed_balance["free"]["USDT"],
            "base_qty": parsed_positions[0]["contracts"] * parsed_positions[0]["contractSize"],
            "upnl": parsed_positions[0]["unrealizedPnl"],
            "equity": parsed_balance["total"]["USDT"] + parsed_positions[0]["unrealizedPnl"]}, True)
    bad_side = dict(position, side="unexpected")
    record("parser_requires_raw_side_validation", "short", client.parse_position(bad_side, market)["side"], True)
    record("position_timestamp_not_snapshot_time", None, parsed_positions[0]["timestamp"], True)

    raw_order = {"orderID": "fixture-order", "clOrdID": "fixture-client", "symbol": "BTCUSDT",
                 "ordStatus": "Filled", "ordType": "Limit", "side": "Buy", "orderQty": "10",
                 "cumQty": "10", "leavesQty": "0", "priceRp": "110", "cumValueRv": "1060",
                 "execFeeRv": "0.2", "actionTimeNs": 1000000000}
    parsed = client.parse_order(raw_order, market)
    record("order_cost_average_and_fee_parser", {"average": 106, "cost": 1060, "fee": "0.2"},
           {"average": parsed["average"], "cost": parsed["cost"], "fee": parsed["fee"]["cost"]}, True)
    no_cost = dict(raw_order)
    del no_cost["cumValueRv"]
    parsed = client.parse_order(no_cost, market)
    record("unified_cost_can_be_inferred_from_limit", {"average": None, "cost": 1100},
           {"average": parsed["average"], "cost": parsed["cost"]}, True)
    zero_fee = client.parse_order(dict(raw_order, execFeeRv="0"), market)
    record("zero_order_fee_normalizes_to_unknown", None, zero_fee["fee"], True)

    # The raw documented account response contains no order identity. Nevertheless
    # the current fallback attributes both same-side and opposite exposure to it.
    for side in ("BUY", "SELL"):
        for same_side in (True, False):
            position_side = ("long" if side == "BUY" else "short") if same_side else ("short" if side == "BUY" else "long")
            adapter = S(supports_trading=lambda: True, fetch_balance=lambda: {"free": {"USDT": 1000}},
                        set_margin_mode=lambda *a, **k: None, set_leverage=lambda *a, **k: None,
                        create_order=Mock(return_value={"id": "remote", "status": "open", "filled": 0}),
                        fetch_order=Mock(return_value={"id": "remote", "status": "open", "filled": 0}),
                        fetch_positions=Mock(return_value=[]))
            prepare_adapter(adapter, symbol=symbol, binding='offline-boundary')
            journal = ExecutionJournal(directory / f"{side}-{same_side}.sqlite3", "offline-boundary",
                                       runtime=True, environment='testnet')
            ex = LiveExecutor(adapter, journal=journal, max_position_size_usd=2000, max_total_exposure_usd=2000)
            try:
                initialize_fixture(ex)
                order = ex.place_order(symbol, side, "LIMIT", 10, price=100)
                adapter.fetch_positions.return_value = [{"symbol": symbol, "contracts": 3,
                    "side": position_side, "entryPrice": 100}]
                ex.refresh_order(order.order_id)
                if order.status.value != "OPEN" or order.filled_quantity != 0:
                    raise RuntimeError("Original-identity order probe must show an unfilled order")
                ex.check_fill_via_positions(order.order_id)
                record(f"{side}_unattributed_{'same' if same_side else 'opposite'}_position",
                       {"status": "OPEN", "filled": 0, "local_fills": 0},
                       {"status": order.status.value, "filled": order.filled_quantity,
                        "local_fills": len(ex.get_trade_history())})
            finally:
                ex.close()

    # A full page can end on the same millisecond as the omitted next row.
    rows = [{"execId": f"fill-{i}", "orderId": "fixture", "symbol": "BTCUSDT", "side": 1,
             "currency": "USDT", "execQtyRq": "1", "execValueRv": "100", "execFeeRv": ".1",
             "createdAt": 1000} for i in range(201)]
    svc = LiveTradingService()
    def page(offset=0, limit=200):
        return dict(scope='phemex:swap:USDT',offset=offset,total=len(rows),rows=rows[offset:offset+limit])
    svc.adapter = S(fetch_execution_history_page=Mock(side_effect=page))
    svc._fills_log_path = directory / "fills.jsonl"
    svc._save_last_trade_sync_ts = Mock()  # Cursor persistence is not under examination.
    await svc._run_backfill_once()
    await svc._run_backfill_once()
    saved = [json.loads(line) for line in svc._fills_log_path.read_text(encoding="utf-8").splitlines()]
    record("backfill_equal_timestamp_page_boundary", 201, len(saved))
    record("backfill_fixture_reached_second_page_and_repeated_sweep", [0,200,0,0,200,0],
           [c.kwargs['offset'] for c in svc.adapter.fetch_execution_history_page.call_args_list], True)
    return results


def main():
    directory = Path(tempfile.mkdtemp(prefix="snipersight-account-boundary-")).resolve()
    before = source_hashes()
    guard_offline(directory)
    results = []
    try:
        results = asyncio.run(exercise(directory))
        after = source_hashes()
        if before != after or any(r["control"] and not r["invariant_holds"] for r in results):
            raise RuntimeError("Diagnostic control/source preservation failed")
        failed = sum(not r["invariant_holds"] for r in results)
        report = {"scope": "offline parser contracts, unattributed position fallback and backfill boundary",
                  "cases": len(results), "violations": failed, "controls": sum(r["control"] for r in results),
                  "source_hashes": after, "sources_unchanged": True,
                  "diagnostic_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "artifact_directory": str(directory), "results": results}
        status = int(failed > 0)
    except Exception:
        import traceback
        report = {"harness_error": traceback.format_exc(), "artifact_directory": str(directory), "results": results}
        status = 2
    finally:
        logging.shutdown()
    report["exit_code"] = status
    (directory / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
