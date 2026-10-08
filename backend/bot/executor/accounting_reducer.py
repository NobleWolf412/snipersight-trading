"""Pure evidence merging. Never applies money deltas to account snapshots."""
from dataclasses import dataclass, replace
from decimal import Decimal
from backend.bot.executor.accounting_models import (
    AccountingError, ExecutionFact, Fee, OrderExecutionState, exact_sum,
)


@dataclass(frozen=True)
class MergeResult:
    state: OrderExecutionState
    disposition: str
    reasons: tuple[str, ...] = ()


def _reasons(*collections):
    return tuple(sorted(set().union(*collections)))


def check_link(state, evidence):
    if (evidence.context.binding != state.binding or evidence.context.environment != state.environment
            or evidence.symbol != state.symbol or evidence.side != state.side
            or (evidence.client_order_id is not None and evidence.client_order_id != state.order_id)
            or (state.exchange_order_id is not None and evidence.exchange_order_id is not None
                and evidence.exchange_order_id != state.exchange_order_id)):
        raise AccountingError("ORDER_IDENTITY_CONFLICT")
    if not (evidence.client_order_id == state.order_id or (
            state.exchange_order_id is not None and evidence.exchange_order_id == state.exchange_order_id)):
        raise AccountingError("ORDER_LINK_UNPROVEN")


def project(state, facts):
    """Compare overlapping cumulative/individual evidence, never add them."""
    relevant = []
    for fact in facts:
        check_link(state, fact)
        if fact.kind != "FUNDING":
            relevant.append(fact)
    quantities = exact_sum(f.quantity for f in relevant)
    filled = max(state.order_quantity, quantities)
    reasons = set(state.reasons)
    if filled >= state.legacy_quantity:
        reasons.discard("LEGACY_QUANTITY_UNVERIFIED")
    reasons.update(r for f in relevant for r in f.conflicts)
    if filled > state.requested_quantity:
        reasons.add("CONFIRMED_QUANTITY_EXCEEDS_REQUEST")
    if state.status in ("FILLED", "CANCELLED", "REJECTED") and quantities > state.order_quantity:
        reasons.add("TERMINAL_QUANTITY_CONFLICT")
    cost, coverage = state.order_cost, state.order_cost_quantity
    known = [f for f in relevant if f.cost is not None and not f.conflicts]
    fact_cost = exact_sum(f.cost for f in known)
    fact_coverage = exact_sum(f.quantity for f in known)
    if cost is not None and coverage == filled == fact_coverage and cost != fact_cost:
        reasons.add("CUMULATIVE_EXECUTION_COST_CONFLICT")
    if fact_coverage > coverage:
        cost, coverage = fact_cost, fact_coverage
    if any("CONFLICT" in r for r in reasons):
        cost, coverage = None, Decimal(0)
    fee_totals = {}
    for fact in relevant:
        if fact.fees is not None and not fact.conflicts:
            for fee in fact.fees:
                fee_totals.setdefault(fee.currency, []).append(fee.amount)
    fees = tuple(Fee(currency, exact_sum(values), "identified_execution_totals")
                 for currency, values in sorted(fee_totals.items()))
    complete = (filled > 0 and quantities == filled and bool(relevant)
                and all(f.fees is not None and not f.conflicts for f in relevant) and not reasons)
    return replace(state, filled_quantity=filled, cost=cost, cost_quantity=coverage,
                   fees=fees, fees_complete=complete, reasons=tuple(sorted(reasons)))


def merge_order(state, observation, facts=()):
    try:
        check_link(state, observation)
    except AccountingError as exc:
        return MergeResult(state, "quarantined", (str(exc),))
    old_ctx, ctx = state.order_context, observation.context
    comparable = (old_ctx is not None and old_ctx.sequence_domain is not None
                  and old_ctx.sequence_domain == ctx.sequence_domain)
    if comparable and ctx.sequence < old_ctx.sequence:
        return MergeResult(state, "stale", ("OLDER_SEQUENCE",))
    reasons = set(state.reasons)
    if observation.quantity < state.order_quantity:
        if comparable and ctx.sequence >= old_ctx.sequence:
            reasons.add("NEWER_QUANTITY_REGRESSION_CONFLICT")
        else:
            return MergeResult(state, "stale", ("LOWER_CUMULATIVE_QUANTITY",))
    if comparable and ctx.sequence == old_ctx.sequence and (
            observation.quantity != state.order_quantity
            or (observation.cost is not None and state.order_cost_quantity == observation.quantity
                and state.order_cost is not None and observation.cost != state.order_cost)):
        reasons.add("SAME_SEQUENCE_CONFLICT")
    quantity = max(state.order_quantity, observation.quantity)
    cost, coverage = state.order_cost, state.order_cost_quantity
    if observation.cost is not None:
        if observation.quantity == coverage and cost is not None and observation.cost != cost:
            reasons.add("VERIFIED_COST_CONFLICT")
        elif observation.quantity >= coverage:
            if cost is not None and observation.quantity > coverage and observation.cost <= cost:
                reasons.add("CUMULATIVE_COST_REGRESSION_CONFLICT")
            else:
                cost, coverage = observation.cost, observation.quantity
    terminal = state.status in ("FILLED", "CANCELLED", "REJECTED")
    status = state.status if terminal else observation.status
    if terminal and (observation.quantity != state.order_quantity or (
            observation.status != "OPEN" and observation.status != state.status)):
        reasons.add("TERMINAL_ORDER_CONFLICT")
    if observation.quantity >= state.legacy_quantity:
        reasons.discard("LEGACY_QUANTITY_UNVERIFIED")
    candidate = replace(state, order_quantity=quantity, order_cost=cost, order_cost_quantity=coverage,
                        status=status, exchange_order_id=state.exchange_order_id or observation.exchange_order_id,
                        reasons=tuple(sorted(reasons)))
    candidate = project(candidate, facts)
    changed_clock = comparable and ctx.sequence > old_ctx.sequence
    if candidate == state and not changed_clock:
        return MergeResult(state, "duplicate")
    candidate = replace(candidate, order_context=ctx, revision=state.revision + 1)
    return MergeResult(candidate, "conflict" if any("CONFLICT" in r for r in candidate.reasons) else "applied",
                       candidate.reasons)


def merge_fact(previous, incoming):
    """Return a single enriched fact; known conflicting values never overwrite."""
    if incoming.execution_id is None:
        raise AccountingError("EXECUTION_ID_REQUIRED")
    if previous is None:
        return incoming, "applied"
    if (previous.context.binding, previous.context.environment, previous.symbol, previous.execution_id) != (
            incoming.context.binding, incoming.context.environment, incoming.symbol, incoming.execution_id):
        raise AccountingError("EXECUTION_SCOPE_CONFLICT")
    reasons = set(previous.conflicts)
    for name in ("side", "quantity", "kind", "client_order_id", "exchange_order_id", "cost"):
        old, new = getattr(previous, name), getattr(incoming, name)
        if old is not None and new is not None and old != new:
            reasons.add("EXECUTION_DUPLICATE_CONFLICT")
    if previous.fees is not None and incoming.fees is not None:
        if {f.currency: f.amount for f in previous.fees} != {f.currency: f.amount for f in incoming.fees}:
            reasons.add("EXECUTION_FEE_CONFLICT")
    if reasons:
        result = replace(previous, conflicts=tuple(sorted(reasons)))
        return result, "conflict"
    values = {}
    for name in ("client_order_id", "exchange_order_id", "cost", "cost_provenance", "fees"):
        if getattr(previous, name) is None:
            values[name] = getattr(incoming, name)
    result = replace(previous, **values)
    return result, "duplicate" if result == previous else "applied"
