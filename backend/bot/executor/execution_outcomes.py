"""Pure receipts and explicitly attributed outcomes, excluding funding/transfers.

No account snapshots, trigger quotes, fee models or implicit order allocation.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
import math
from .accounting_models import AccountingError, Fee, OrderExecutionState, exact_sum


@dataclass(frozen=True)
class ExecutionReceipt:
    order_id: str
    quantity: Decimal
    cost: Decimal | None
    fees: tuple[Fee, ...] | None
    terminal: bool
    reasons: tuple[str, ...]

    @property
    def average_price(self):
        if not self.quantity or self.cost is None:
            return None
        with localcontext() as ctx:
            ctx.prec = 256
            return float(self.cost / self.quantity)

    def confirms(self, quantity: float) -> bool:
        """A terminal, fully priced slice; fee completeness is a separate concern."""
        price = self.average_price
        return (self.terminal and not self.reasons and self.quantity > 0
                and self.quantity == Decimal(str(quantity))
                and price is not None and math.isfinite(price) and price > 0)


def receipt(state: OrderExecutionState) -> ExecutionReceipt:
    known = state.cost is not None and state.cost_quantity == state.filled_quantity and not state.reasons
    return ExecutionReceipt(state.order_id, state.filled_quantity, state.cost if known else None,
        state.fees if state.fees_complete and not state.reasons else None,
        state.status in ('FILLED', 'CANCELLED', 'REJECTED'), state.reasons)


def reduction_receipt(root_order_id: str, goal: Decimal, parts: tuple[ExecutionReceipt, ...]) -> ExecutionReceipt:
    """Aggregate only explicitly linked requests for one logical reduction."""
    if not isinstance(goal, Decimal) or not goal.is_finite() or goal <= 0:
        raise AccountingError('REDUCTION_GOAL_INVALID')
    if any(not r.quantity.is_finite() or r.quantity < 0
           or (r.cost is not None and (not r.cost.is_finite() or r.cost < 0)) for r in parts):
        raise AccountingError('REDUCTION_AMOUNT_INVALID')
    ids = [r.order_id for r in parts]
    if not parts or ids[0] != root_order_id or len(ids) != len(set(ids)):
        raise AccountingError('REDUCTION_REQUEST_IDENTITY')
    quantity = exact_sum(r.quantity for r in parts)
    reasons = set(reason for r in parts for reason in r.reasons)
    if quantity > goal:
        reasons.add('REDUCTION_GOAL_EXCEEDED')
    cost = None if any(r.quantity and r.cost is None for r in parts) else exact_sum(r.cost for r in parts if r.quantity)
    currencies = {}
    complete_fees = all(r.fees is not None for r in parts if r.quantity)
    for r in parts:
        for fee in r.fees or ():
            currencies.setdefault(fee.currency, []).append(fee.amount)
    fees = tuple(Fee(currency, exact_sum(values), 'logical_reduction') for currency, values in sorted(currencies.items())) if complete_fees else None
    return ExecutionReceipt(root_order_id, quantity, cost, fees, all(r.terminal for r in parts), tuple(sorted(reasons)))


@dataclass(frozen=True)
class ExecutionOutcome:
    entry_order_id: str
    exit_order_ids: tuple[str, ...]
    entry_quantity: Decimal
    exit_quantity: Decimal
    entry_cost: Decimal | None
    exit_cost: Decimal | None
    gross_pnl: Decimal | None
    fees: tuple[Fee, ...]
    fees_complete: bool
    pnl_after_execution_fees: Decimal | None
    reasons: tuple[str, ...]
    basis: str = 'executions_excluding_funding_and_transfers'

    @property
    def complete(self):
        return not self.reasons and self.pnl_after_execution_fees is not None

    def to_dict(self):
        return dict(version=1, basis=self.basis, complete=self.complete,
            entry_order_id=self.entry_order_id, exit_order_ids=list(self.exit_order_ids),
            entry_quantity=str(self.entry_quantity), exit_quantity=str(self.exit_quantity),
            entry_cost=str(self.entry_cost) if self.entry_cost is not None else None,
            exit_cost=str(self.exit_cost) if self.exit_cost is not None else None,
            gross_pnl=str(self.gross_pnl) if self.gross_pnl is not None else None,
            fees={fee.currency: str(fee.amount) for fee in self.fees}, fees_complete=self.fees_complete,
            pnl_after_execution_fees=str(self.pnl_after_execution_fees) if self.pnl_after_execution_fees is not None else None,
            funding=None, funding_allocated=False, reasons=list(self.reasons))


@dataclass(frozen=True)
class ExecutionProgress:
    entry_order_id: str
    side: str
    entry_quantity: Decimal
    exit_quantity: Decimal
    remaining_quantity: Decimal
    entry_cost: Decimal | None
    exit_cost: Decimal | None
    realized_gross: Decimal | None
    exits: tuple[ExecutionReceipt, ...]
    reasons: tuple[str, ...]

    @property
    def ready(self):
        return not self.reasons and self.realized_gross is not None


def calculate_progress(entry: OrderExecutionState, exits: tuple[OrderExecutionState, ...]) -> ExecutionProgress:
    """Cumulative owned reductions; fees and terminal exit remainders are separate."""
    outcome = calculate_outcome(entry, exits)  # validates scope/direction/duplicate identities
    entry_receipt = receipt(entry)
    exit_receipts = tuple(receipt(state) for state in exits)
    reasons = set(reason for item in (entry_receipt, *exit_receipts) for reason in item.reasons)
    if not entry_receipt.terminal:
        reasons.add('ENTRY_REMAINDER_UNRESOLVED')
    if entry.filled_quantity <= 0:
        reasons.add('ENTRY_EXECUTION_REQUIRED')
    remaining = exact_sum((outcome.entry_quantity, outcome.exit_quantity.copy_negate()))
    if remaining < 0:
        reasons.add('EXIT_QUANTITY_EXCEEDS_ENTRY')
    if entry_receipt.cost is None or any(r.quantity and r.cost is None for r in exit_receipts):
        reasons.add('EXECUTION_COST_UNAVAILABLE')
    gross = None
    if not reasons:
        with localcontext() as context:
            context.prec = 256
            # Full closure uses the full entry cost, avoiding prorating residue.
            allocated = entry_receipt.cost if remaining == 0 else entry_receipt.cost * outcome.exit_quantity / outcome.entry_quantity
            gross = exact_sum((outcome.exit_cost, allocated.copy_negate()))
            if entry.side == 'SELL':
                gross = gross.copy_negate()
    return ExecutionProgress(entry.order_id, entry.side, outcome.entry_quantity, outcome.exit_quantity, remaining,
                             entry_receipt.cost, outcome.exit_cost, gross, exit_receipts, tuple(sorted(reasons)))


def calculate_outcome(entry: OrderExecutionState, exits: tuple[OrderExecutionState, ...]) -> ExecutionOutcome:
    """Caller supplies only exits whose immutable intents name this entry."""
    if type(entry) is not OrderExecutionState or type(exits) is not tuple:
        raise AccountingError('OUTCOME_INPUT_TYPE')
    if any(type(s) is not OrderExecutionState for s in exits):
        raise AccountingError('OUTCOME_INPUT_TYPE')
    ids = [s.order_id for s in exits]
    if len(set(ids)) != len(ids) or entry.order_id in ids:
        raise AccountingError('OUTCOME_DUPLICATE_ORDER')
    for state in exits:
        if (state.binding, state.environment, state.symbol) != (entry.binding, entry.environment, entry.symbol):
            raise AccountingError('OUTCOME_SCOPE_CONFLICT')
        if state.side == entry.side:
            raise AccountingError('OUTCOME_DIRECTION_CONFLICT')
    receipts = tuple(receipt(s) for s in (entry, *exits))
    reasons = set(reason for r in receipts for reason in r.reasons)
    entry_qty = entry.filled_quantity
    exit_qty = exact_sum(s.filled_quantity for s in exits)
    if entry_qty <= 0:
        reasons.add('ENTRY_EXECUTION_REQUIRED')
    if exit_qty != entry_qty:
        reasons.add('EXIT_QUANTITY_MISMATCH')
    if any(not r.terminal for r in receipts):
        reasons.add('ORDER_REMAINDER_UNRESOLVED')
    entry_cost = receipts[0].cost
    exit_cost = None if any(r.cost is None and r.quantity for r in receipts[1:]) else exact_sum(
        r.cost for r in receipts[1:] if r.quantity)
    if entry_cost is None or exit_cost is None:
        reasons.add('EXECUTION_COST_UNAVAILABLE')
    gross = None
    if entry_qty > 0 and exit_qty == entry_qty and entry_cost is not None and exit_cost is not None:
        gross = exact_sum((exit_cost, entry_cost.copy_negate()))
        if entry.side == 'SELL':
            gross = gross.copy_negate()
    fees_complete = all(r.fees is not None for r in receipts if r.quantity)
    currencies = {}
    for r in receipts:
        if r.quantity and r.fees is not None:
            for fee in r.fees:
                currencies.setdefault(fee.currency, []).append(fee.amount)
    fees = tuple(Fee(currency, exact_sum(values), 'attributed_execution_fees') for currency, values in sorted(currencies.items()))
    if not fees_complete:
        reasons.add('EXECUTION_FEES_UNAVAILABLE')
    if any(f.currency != 'USDT' and f.amount != 0 for f in fees):
        reasons.add('FEE_CONVERSION_UNAVAILABLE')
    pnl = exact_sum((gross, exact_sum(f.amount for f in fees).copy_negate())) if gross is not None and not reasons else None
    return ExecutionOutcome(entry.order_id, tuple(ids), entry_qty, exit_qty, entry_cost, exit_cost,
                            gross, fees, fees_complete, pnl, tuple(sorted(reasons)))
