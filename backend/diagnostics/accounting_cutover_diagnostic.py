"""Offline FV2 integration constraints, not a live-accounting safety verdict.

Exit 0 means all design probes match the recorded constraints; 1 means drift.
No service, exchange client or actual execution store is constructed.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.diagnostics.live_accounting_diagnostic import guard_offline

SOURCES = (
    "backend/bot/executor/accounting_models.py",
    "backend/bot/executor/accounting_reducer.py",
    "backend/bot/executor/execution_journal.py",
    "backend/data/adapters/phemex_accounting.py",
)


def exercise():
    from decimal import Decimal as D
    from backend.bot.executor.accounting_models import (
        AccountingError, ObservationContext, OrderExecutionState, OrderExecutionObservation,
    )
    from backend.bot.executor.accounting_reducer import merge_order
    from backend.bot.executor.execution_journal import JournalError, validate_record
    from backend.data.adapters.phemex_accounting import normalize_execution

    results = []
    def record(case, expected, observed):
        results.append(dict(case=case, expected=expected, observed=observed,
                            probe_matches_expected=expected == observed))

    def context(seq=None, obs="fixture"):
        return ObservationContext("testnet", "fixture", "ws", obs,
            "2026-10-08T00:00:00+00:00", 1.0, 2.0,
            sequence_domain="naive-execSeq" if seq is not None else None, sequence=seq)

    market = dict(id="BTCUSDT", symbol="BTC/USDT:USDT", swap=True, linear=True,
                  inverse=False, quote="USDT", settle="USDT", contractSize=1)
    for side in ("BUY", "SELL"):
        raw = dict(symbol="BTCUSDT", side=side.title(), clOrdID="fixture", orderID="remote",
                   tradeType="Trade", execID="identified-fill", execQty="10",
                   execValueRv="1060", execFeeRv="0.2", currency="USDT")
        try:
            normalize_execution(raw, market, context())
            rejected = False
        except AccountingError:
            rejected = True
        record(f"{side}_documented_ws_execQty_supported", False, rejected)
        raw["execQtyRq"] = raw.pop("execQty")
        fact = normalize_execution(raw, market, context())
        record(f"{side}_supported_execQtyRq_control", ["10", "1060", "0.2"],
               [str(fact.quantity), str(fact.cost), str(fact.fees[0].amount)])

        def observed(qty, cost, status, seq):
            return OrderExecutionObservation(context(seq, status), market["symbol"], side,
                "fixture", "remote", D(qty), D(cost), status, "raw_cumulative_value")
        initial = OrderExecutionState("fixture", market["symbol"], side, "fixture", "testnet", D(10), "remote")
        opened = merge_order(initial, observed("0", "0", "OPEN", 77)).state
        filled = merge_order(opened, observed("10", "1060", "FILLED", 77)).state
        record(f"{side}_execSeq_is_not_unique_order_revision", True,
               "SAME_SEQUENCE_CONFLICT" in filled.reasons)
        opened = merge_order(initial, observed("0", "0", "OPEN", None)).state
        filled = merge_order(opened, observed("10", "1060", "FILLED", None)).state
        record(f"{side}_unproven_sequence_left_unordered_control", ["10", "1060", []],
               [str(filled.filled_quantity), str(filled.cost), list(filled.reasons)])

        intent = dict(order_id="fixture", symbol=market["symbol"], owner="offline", generation="fixture",
                      side=side, order_type="LIMIT", purpose="entry", reduce_only=False,
                      quantity=10, price=100, stop_price=None,
                      wire={"symbol": market["symbol"], "side": side.lower(), "amount": 10,
                            "params": {"clientOrderId": "fixture"}})
        state = dict(status="FILLED", filled_quantity=10, average_fill_price=106,
                     cancel_requested=False, exchange_id="remote", unknown_reason=None,
                     rejection_reason=None, created_at=context().received_at, updated_at=context().received_at)
        validate_record(intent, state)
        record(f"{side}_legacy_known_price_control", True, True)
        for price in (None, 0):
            try:
                validate_record(intent, dict(state, average_fill_price=price))
                rejected = False
            except JournalError:
                rejected = True
            record(f"{side}_confirmed_quantity_unknown_price_{price}_requires_contract_change", True, rejected)
        validate_record(intent, dict(state, average_fill_price=None), runtime=True)
        record(f'{side}_runtime_known_quantity_unknown_cost_is_explicit', True, True)
    return results


def main():
    directory = Path(tempfile.mkdtemp(prefix="snipersight-fv2-plan-")).resolve()
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}
    guard_offline(directory)
    results = exercise()
    unchanged = all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
                    for name, digest in hashes.items())
    report = dict(scope="FV2 design constraints; expected gaps are not safety passes",
                  cases=len(results), unexpected_results=sum(not r["probe_matches_expected"] for r in results),
                  sources_unchanged=unchanged, source_hashes=hashes, results=results,
                  artifact_directory=str(directory))
    (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return int(bool(report["unexpected_results"] or not unchanged))


if __name__ == "__main__":
    raise SystemExit(main())
