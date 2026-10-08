"""Financial evidence preserves decimal values, identity and unknown fields."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal as D
import json
import pytest
from backend.bot.executor.accounting_models import (
    AccountingError, ObservationContext, OrderExecutionObservation, OrderExecutionState,
    ExecutionFact, Fee, amount, exact_sum, exact_product, to_payload, from_payload,
)


def context(**changes):
    values = dict(environment="testnet", binding="fixture", source="rest", observation_id="obs",
                  received_at="2026-10-08T00:00:00+00:00", started_monotonic=1.0, ended_monotonic=2.0)
    return ObservationContext(**dict(values, **changes))


def initial(side="BUY"):
    return OrderExecutionState("order", "BTC/USDT:USDT", side, "fixture", "testnet", D(10), "remote")


def order(q="10", cost="1060", **changes):
    values = dict(context=context(), symbol="BTC/USDT:USDT", side="BUY", client_order_id="order",
                  exchange_order_id="remote", quantity=D(q), cost=D(cost) if cost is not None else None,
                  status="FILLED", cost_provenance="raw" if cost is not None else None)
    return OrderExecutionObservation(**dict(values, **changes))


def fact(eid="e1", q="10", cost="1060", **changes):
    values = dict(context=context(), symbol="BTC/USDT:USDT", side="BUY", client_order_id="order",
                  exchange_order_id="remote", execution_id=eid, quantity=D(q), cost=D(cost) if cost is not None else None,
                  fees=(Fee("USDT", D("0.2"), "raw"),), cost_provenance="raw" if cost is not None else None)
    return ExecutionFact(**dict(values, **changes))


@pytest.mark.parametrize("value", [None, True, False, 0.1, float("nan"), "NaN", "Infinity", "1e999", "9" * 81])
def test_raw_amount_rejects_ambiguous_or_unbounded_values(value):
    with pytest.raises(AccountingError):
        amount(value)


@pytest.mark.parametrize("value", ["0", "-1.25", "0.000000000000000001", "10000000000000000000000000000.1"])
def test_exact_raw_decimal_and_roundtrip(value):
    fee = Fee("USDT", amount(value), "raw")
    assert from_payload(json.loads(json.dumps(to_payload(fee)))) == fee
    assert exact_sum([fee.amount, fee.amount.copy_negate()]) == 0


@pytest.mark.parametrize("obj", [context(), order(cost=None), fact(cost=None, fees=None), initial(), Fee("PT", D("-0.2"), "raw")])
def test_versioned_roundtrip_and_immutability(obj):
    assert from_payload(json.loads(json.dumps(to_payload(obj)))) == obj
    with pytest.raises(FrozenInstanceError):
        obj.__setattr__(next(iter(vars(obj))), "mutated")


@pytest.mark.parametrize("change", [{"received_at": "2026-10-08"}, {"ended_monotonic": 0},
    {"started_monotonic": True}, {"scope": "spot"}, {"environment": "unknown"},
    {"sequence": 1}, {"sequence_domain": "order"}, {"exchange_timestamp_ns": -1}])
def test_context_contract(change):
    with pytest.raises(AccountingError):
        context(**change)


@pytest.mark.parametrize("key,value", [("version", 2), ("quantity", 10.0), ("quantity", "NaN"), ("status", "guess"), ("cost_provenance", None)])
def test_corrupt_serialization_is_not_replayed(key, value):
    payload = to_payload(order())
    payload[key] = value
    with pytest.raises(AccountingError):
        from_payload(payload)


def test_unknown_price_does_not_destroy_confirmed_quantity():
    observation = order(cost=None)
    assert observation.quantity == 10 and observation.cost is None
    assert exact_product(D("0.000000001"), D("10000000000.0001")) == D("10.0000000000001")


def test_zero_and_rebate_fee_are_evidence_not_unknown():
    for value in (D(0), D("-0.02")):
        assert from_payload(to_payload(fact(fees=(Fee("USDT", value, "raw"),)))).fees[0].amount == value
    with pytest.raises(AccountingError):
        fact(fees=())
