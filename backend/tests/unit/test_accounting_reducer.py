"""Overlapping evidence never doubles quantity/cost/fees; conflicts stay loud."""
from dataclasses import replace
from decimal import Decimal as D
import pytest
from backend.bot.executor.accounting_models import Fee
from backend.bot.executor.accounting_reducer import merge_order, merge_fact, project
from backend.tests.unit.test_accounting_models import context, initial, order, fact


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_cumulative_cost_and_late_fee_evidence(side):
    first = merge_order(initial(side), order("4", "400", side=side, status="OPEN")).state
    last = merge_order(first, order(side=side)).state
    assert last.filled_quantity == 10 and last.cost == 1060
    assert last.cost - first.cost == 660 and last.cost / last.filled_quantity == 106
    assert not last.financially_complete
    a, b = fact("a", "4", "400", side=side), fact("b", "6", "660", side=side)
    result = project(last, [a, b])
    assert result.filled_quantity == 10 and result.cost == 1060
    assert result.fees[0].amount == D("0.4") and result.financially_complete
    assert merge_order(result, order(side=side), [a, b]).state == result


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_unknown_terminal_cost_can_be_enriched_without_quantity_replay(side):
    state = merge_order(initial(side), order(cost=None, side=side)).state
    assert state.filled_quantity == 10 and state.cost is None
    state = merge_order(state, order(side=side)).state
    assert state.filled_quantity == 10 and state.cost == 1060
    original = fact(side=side, fees=None)
    richer, disposition = merge_fact(original, fact(side=side, fees=(Fee("USDT", D(0), "raw"),)))
    assert disposition == "applied"
    assert project(state, [richer]).financially_complete
    assert merge_fact(richer, richer) == (richer, "duplicate")


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_partial_cancel_and_unknown_prior_cost(side):
    state = merge_order(initial(side), order("4", None, side=side, status="OPEN")).state
    state = merge_order(state, order("4", "400", side=side, status="CANCELLED")).state
    assert state.filled_quantity == 4 and state.cost == 400 and state.status == "CANCELLED"
    assert project(state, [fact(q="4", cost="400", side=side)]).financially_complete


@pytest.mark.parametrize("change", [{"cost": D(1050)}, {"side": "SELL"}, {"quantity": D(9)},
    {"client_order_id": "other"}, {"fees": (Fee("USDT", D(1), "raw"),)}])
def test_conflicting_execution_id_does_not_replace_known_values(change):
    original = fact()
    conflicting, disposition = merge_fact(original, replace(original, **change))
    assert disposition == "conflict" and conflicting.conflicts
    assert conflicting.quantity == 10 and conflicting.cost == 1060
    assert not project(merge_order(initial(), order()).state, [conflicting]).financially_complete


def test_same_quantity_verified_cost_conflict_blocks_financial_totals():
    state = merge_order(initial(), order()).state
    result = merge_order(state, order(cost="1100"))
    assert result.disposition == "conflict" and result.state.cost is None
    assert result.state.filled_quantity == 10


def test_out_of_order_sequences_and_domains():
    state = merge_order(initial(), order("4", "400", status="OPEN",
        context=context(sequence=10, sequence_domain="rest:order"))).state
    old = order("2", "200", status="OPEN", context=context(sequence=9, sequence_domain="rest:order"))
    assert merge_order(state, old).disposition == "stale"
    newer = replace(old, context=context(sequence=11, sequence_domain="rest:order"))
    assert merge_order(state, newer).disposition == "conflict"
    independent = replace(newer, context=context(sequence=100, sequence_domain="ws:account"))
    assert merge_order(state, independent).disposition == "stale"


@pytest.mark.parametrize("change", [{"client_order_id": "foreign"}, {"exchange_order_id": "foreign"},
    {"context": context(binding="foreign")}, {"symbol": "ETH/USDT:USDT"}, {"side": "SELL"}])
def test_identity_mismatch_quarantined_before_projection(change):
    state = initial()
    result = merge_order(state, order(**change))
    assert result.disposition == "quarantined" and result.state == state


def test_cost_overlap_conflict_and_overfilled_facts_remain_unusable():
    state = merge_order(initial(), order()).state
    assert project(state, [fact(cost="1100")]).cost is None
    over = project(state, [fact(q="11", cost="1166")])
    assert over.filled_quantity == 11 and not over.financially_complete


def test_known_partial_cost_does_not_claim_full_coverage():
    state = merge_order(initial(), order("4", "400", status="OPEN")).state
    state = merge_order(state, order(cost=None)).state
    assert state.cost == 400 and state.cost_quantity == 4 and state.filled_quantity == 10
    assert not state.financially_complete
