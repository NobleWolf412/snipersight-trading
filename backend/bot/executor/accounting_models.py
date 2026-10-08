"""Versioned financial evidence. No exchange access or active executor routing.

Amounts are Decimal internally and strings on the wire. Unknown is None, never
an inferred zero. Receive clocks establish local observation order only.
"""
from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal, Inexact, Rounded, localcontext
import math
from types import UnionType
from typing import get_args, get_origin, get_type_hints

SCOPE = "phemex:swap:USDT"
VERSION = 1


class AccountingError(ValueError):
    """Financial evidence cannot be used as supplied."""


def amount(value):
    if type(value) not in (str, int, Decimal):
        raise AccountingError("AMOUNT_TYPE: raw decimal required")
    try:
        result = Decimal(value)
        if (not result.is_finite() or len(result.as_tuple().digits) > 80
                or abs(result.as_tuple().exponent) > 80):
            raise ValueError()
        return result
    except (ValueError, ArithmeticError):
        raise AccountingError("AMOUNT_RANGE: nonfinite or unsupported precision") from None


def exact_sum(values):
    with localcontext() as ctx:
        ctx.prec = 256
        ctx.traps[Inexact] = ctx.traps[Rounded] = True
        return sum(values, Decimal(0))


def exact_product(left, right):
    with localcontext() as ctx:
        ctx.prec = 256
        ctx.traps[Inexact] = ctx.traps[Rounded] = True
        return left * right


def _typed(value, annotation):
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is UnionType:
        return any(_typed(value, option) for option in args)
    if origin is tuple:
        return type(value) is tuple and all(_typed(item, args[0]) for item in value)
    if annotation is float:
        return type(value) in (int, float) and math.isfinite(value)
    return type(value) is annotation


def _validate(obj):
    for key, annotation in get_type_hints(type(obj)).items():
        value = getattr(obj, key)
        if not _typed(value, annotation):
            raise AccountingError(f"FIELD_TYPE: {type(obj).__name__}.{key}")
        if isinstance(value, Decimal):
            amount(value)


def _text(value):
    if not value or value != value.strip() or len(value) > 512:
        raise AccountingError("IDENTITY_INVALID")


@dataclass(frozen=True)
class ObservationContext:
    environment: str
    binding: str
    source: str
    observation_id: str
    received_at: str
    started_monotonic: float
    ended_monotonic: float
    sequence_domain: str | None = None
    sequence: int | None = None
    exchange_timestamp_ns: int | None = None
    scope: str = SCOPE

    def __post_init__(self):
        _validate(self)
        for value in (self.binding, self.source, self.observation_id):
            _text(value)
        if self.environment not in ("testnet", "production") or self.scope != SCOPE:
            raise AccountingError("SCOPE_UNSUPPORTED")
        try:
            timestamp = datetime.fromisoformat(self.received_at)
            if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
                raise ValueError()
        except ValueError:
            raise AccountingError("RECEIVE_TIME_INVALID") from None
        if self.started_monotonic < 0 or self.ended_monotonic < self.started_monotonic:
            raise AccountingError("RECEIVE_INTERVAL_INVALID")
        if (self.sequence is None) != (self.sequence_domain is None):
            raise AccountingError("SEQUENCE_DOMAIN_REQUIRED")
        if self.sequence_domain is not None:
            _text(self.sequence_domain)
        if any(v is not None and v < 0 for v in (self.sequence, self.exchange_timestamp_ns)):
            raise AccountingError("EXCHANGE_CLOCK_INVALID")


@dataclass(frozen=True)
class Fee:
    currency: str
    amount: Decimal
    provenance: str

    def __post_init__(self):
        _validate(self)
        _text(self.currency)
        _text(self.provenance)


@dataclass(frozen=True)
class AccountPositionObservation:
    market_id: str
    symbol: str | None
    side: str | None
    contracts: Decimal
    multiplier: Decimal | None
    base_quantity: Decimal | None
    entry_price: Decimal | None
    mark_price: Decimal | None
    unrealized_pnl: Decimal | None
    reasons: tuple[str, ...] = ()

    def __post_init__(self):
        _validate(self)
        _text(self.market_id)
        if self.contracts < 0 or self.side not in (None, "BUY", "SELL"):
            raise AccountingError("POSITION_INVALID")
        for value in (self.multiplier, self.entry_price, self.mark_price):
            if value is not None and value <= 0:
                raise AccountingError("POSITION_PRICE_OR_UNIT_INVALID")
        if self.contracts > 0 and self.side is None:
            raise AccountingError("POSITION_SIDE_REQUIRED")
        if self.base_quantity is not None and (self.base_quantity < 0 or self.multiplier is None
                or self.base_quantity != exact_product(self.contracts, self.multiplier)):
            raise AccountingError("POSITION_UNIT_CONFLICT")


@dataclass(frozen=True)
class AccountObservation:
    context: ObservationContext
    wallet: Decimal
    used: Decimal
    free: Decimal | None
    bonus: Decimal | None
    unrealized_pnl: Decimal | None
    equity: Decimal | None
    positions: tuple[AccountPositionObservation, ...]
    reasons: tuple[str, ...]
    provenance: str = "g-accounts/positions:raw"

    def __post_init__(self):
        _validate(self)
        if self.used < 0:
            raise AccountingError("USED_MARGIN_INVALID")
        if not self.reasons and (self.free is None or self.equity is None or self.bonus != 0
                                 or self.unrealized_pnl is None or any(p.reasons for p in self.positions)):
            raise AccountingError("ACCOUNT_COMPLETENESS_INVALID")
        if self.free is not None and (self.bonus != 0 or self.free != exact_sum((self.wallet, self.used.copy_negate()))):
            raise AccountingError("ACCOUNT_FREE_CONFLICT")
        if self.equity is not None and (self.unrealized_pnl is None or self.reasons
                or self.equity != exact_sum((self.wallet, self.unrealized_pnl))):
            raise AccountingError("ACCOUNT_EQUITY_CONFLICT")

    @property
    def complete(self):
        return not self.reasons


@dataclass(frozen=True)
class OrderExecutionObservation:
    context: ObservationContext
    symbol: str
    side: str
    client_order_id: str | None
    exchange_order_id: str | None
    quantity: Decimal
    cost: Decimal | None
    status: str
    cost_provenance: str | None = None

    def __post_init__(self):
        _validate(self)
        _execution_identity(self)
        if not self.client_order_id and not self.exchange_order_id:
            raise AccountingError("ORDER_ID_REQUIRED")
        if self.quantity < 0 or (self.cost is not None and (self.cost < 0 or (self.quantity > 0 and self.cost <= 0))):
            raise AccountingError("ORDER_AMOUNT_INVALID")
        if self.quantity == 0 and self.cost not in (None, Decimal(0)):
            raise AccountingError("COST_WITHOUT_QUANTITY")
        if (self.cost is None) != (self.cost_provenance is None):
            raise AccountingError("COST_PROVENANCE_REQUIRED")
        if self.status not in ("OPEN", "FILLED", "CANCELLED", "REJECTED"):
            raise AccountingError("ORDER_STATUS_INVALID")
        if self.status == "FILLED" and self.quantity == 0:
            raise AccountingError("FILLED_WITHOUT_QUANTITY")


def _execution_identity(obj):
    _text(obj.symbol)
    if obj.side not in ("BUY", "SELL"):
        raise AccountingError("EXECUTION_SIDE_INVALID")
    for value in (obj.client_order_id, obj.exchange_order_id):
        if value is not None:
            _text(value)


@dataclass(frozen=True)
class ExecutionFact:
    context: ObservationContext
    symbol: str
    side: str
    execution_id: str | None
    client_order_id: str | None
    exchange_order_id: str | None
    quantity: Decimal
    cost: Decimal | None
    fees: tuple[Fee, ...] | None
    kind: str = "TRADE"
    cost_provenance: str | None = None
    conflicts: tuple[str, ...] = ()

    def __post_init__(self):
        _validate(self)
        _execution_identity(self)
        if self.execution_id is not None:
            _text(self.execution_id)
        if self.kind not in ("TRADE", "FUNDING", "LIQUIDATION", "ADL") or self.quantity < 0:
            raise AccountingError("EXECUTION_KIND_OR_QUANTITY_INVALID")
        if self.kind != "FUNDING" and self.quantity <= 0:
            raise AccountingError("EXECUTION_QUANTITY_REQUIRED")
        if self.cost is not None and (self.cost < 0 or (self.quantity > 0 and self.cost == 0)):
            raise AccountingError("EXECUTION_COST_INVALID")
        if (self.cost is None) != (self.cost_provenance is None):
            raise AccountingError("COST_PROVENANCE_REQUIRED")
        if self.fees is not None and (not self.fees or len({f.currency for f in self.fees}) != len(self.fees)):
            raise AccountingError("FEE_COMPONENTS_INVALID")


@dataclass(frozen=True)
class OrderExecutionState:
    order_id: str
    symbol: str
    side: str
    binding: str
    environment: str
    requested_quantity: Decimal
    exchange_order_id: str | None = None
    order_quantity: Decimal = Decimal(0)
    order_cost: Decimal | None = None
    order_cost_quantity: Decimal = Decimal(0)
    order_context: ObservationContext | None = None
    status: str = "UNOBSERVED"
    filled_quantity: Decimal = Decimal(0)
    cost: Decimal | None = None
    cost_quantity: Decimal = Decimal(0)
    fees: tuple[Fee, ...] = ()
    fees_complete: bool = False
    reasons: tuple[str, ...] = ()
    revision: int = 0
    legacy_quantity: Decimal = Decimal(0)

    def __post_init__(self):
        _validate(self)
        for value in (self.order_id, self.symbol, self.binding):
            _text(value)
        if self.side not in ("BUY", "SELL") or self.environment not in ("testnet", "production"):
            raise AccountingError("STATE_IDENTITY_INVALID")
        if self.requested_quantity <= 0 or self.revision < 0:
            raise AccountingError("STATE_QUANTITY_OR_REVISION_INVALID")
        if any(v < 0 for v in (self.order_quantity, self.filled_quantity, self.cost_quantity,
                               self.order_cost_quantity, self.legacy_quantity)):
            raise AccountingError("STATE_QUANTITY_INVALID")
        if self.order_cost_quantity > self.order_quantity or self.cost_quantity > self.filled_quantity:
            raise AccountingError("STATE_COST_COVERAGE_INVALID")
        for cost, qty in ((self.order_cost, self.order_cost_quantity), (self.cost, self.cost_quantity)):
            if cost is None and qty != 0 or cost is not None and (cost < 0 or (qty > 0 and cost <= 0)):
                raise AccountingError("STATE_COST_INVALID")
        if self.status not in ("UNOBSERVED", "OPEN", "FILLED", "CANCELLED", "REJECTED"):
            raise AccountingError("STATE_STATUS_INVALID")
        if self.order_context is not None and (self.order_context.binding != self.binding
                or self.order_context.environment != self.environment):
            raise AccountingError("STATE_CONTEXT_CONFLICT")

    @property
    def financially_complete(self):
        return (self.filled_quantity > 0 and self.cost is not None
                and self.cost_quantity == self.filled_quantity and self.fees_complete and not self.reasons)


@dataclass(frozen=True)
class LiveExecutionUpdate:
    """Committed live evidence, distinct from a simulated Fill.

    quantity/price describe a verified incremental cost only when coverage permits;
    cumulative average remains available independently. Missing fees stay None.
    """
    order_id: str
    quantity: float
    price: float | None
    fee: float | None
    state: OrderExecutionState
    timestamp: str

    def __post_init__(self):
        _validate(self)
        if self.order_id != self.state.order_id or self.quantity < 0:
            raise AccountingError("LIVE_UPDATE_IDENTITY_OR_QUANTITY")
        if self.price is not None and self.price <= 0:
            raise AccountingError("LIVE_UPDATE_PRICE")


def execution_update(previous, current, timestamp):
    """Project an incremental view without inventing costs of earlier fills."""
    quantity = exact_sum((current.filled_quantity, previous.filled_quantity.copy_negate()))
    price = None
    if (quantity > 0 and current.cost is not None and current.cost_quantity == current.filled_quantity
            and not current.reasons and (previous.filled_quantity == 0 or (
                previous.cost is not None and previous.cost_quantity == previous.filled_quantity and not previous.reasons))):
        cost = exact_sum((current.cost, (previous.cost or Decimal(0)).copy_negate()))
        if cost > 0:
            with localcontext() as ctx:
                ctx.prec = 80
                price = float(cost / quantity)
    fee = None
    if current.fees_complete and (previous.filled_quantity == 0 or previous.fees_complete):
        if all(f.currency == "USDT" for f in current.fees + previous.fees):
            fee = float(exact_sum([f.amount for f in current.fees] + [f.amount.copy_negate() for f in previous.fees]))
    return LiveExecutionUpdate(current.order_id, float(max(Decimal(0), quantity)), price, fee, current, timestamp)


_TYPES = {c.__name__: c for c in (ObservationContext, Fee, AccountPositionObservation,
    AccountObservation, OrderExecutionObservation, ExecutionFact, OrderExecutionState, LiveExecutionUpdate)}


def to_payload(value):
    if type(value) in _TYPES.values():
        return {"type": type(value).__name__, "version": VERSION,
                **{f.name: to_payload(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return [to_payload(v) for v in value]
    return value


def from_payload(payload):
    if not isinstance(payload, dict) or type(payload.get("version")) is not int or payload["version"] != VERSION:
        raise AccountingError("PAYLOAD_VERSION_INVALID")
    cls = _TYPES.get(payload.get("type"))
    if cls is None or set(payload) != {"type", "version"} | {f.name for f in fields(cls)}:
        raise AccountingError("PAYLOAD_SHAPE_INVALID")
    def decode(value, annotation):
        origin, args = get_origin(annotation), get_args(annotation)
        if origin is UnionType:
            if value is None and type(None) in args:
                return None
            annotation = next(a for a in args if a is not type(None))
            origin, args = get_origin(annotation), get_args(annotation)
        if annotation is Decimal:
            if type(value) is not str:
                raise AccountingError("DECIMAL_STRING_REQUIRED")
            return amount(value)
        if origin is tuple:
            if type(value) is not list:
                raise AccountingError("ARRAY_REQUIRED")
            return tuple(decode(v, args[0]) for v in value)
        if annotation in _TYPES.values():
            result = from_payload(value)
            if type(result) is not annotation:
                raise AccountingError("NESTED_TYPE_INVALID")
            return result
        return value
    return cls(**{k: decode(payload[k], a) for k, a in get_type_hints(cls).items()})
