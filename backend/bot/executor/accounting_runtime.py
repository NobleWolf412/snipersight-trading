"""Account observations and entry commitments. No exchange or strategy mutations.

The executor supplies its state lock so publication and final admission share one
critical section. Local facts never alter observed account cash or quantities.
"""
from dataclasses import dataclass
from decimal import Decimal
from threading import RLock
import time

from backend.bot.executor.accounting_models import AccountObservation, AccountingError, amount, exact_sum, exact_product


def non_runtime_status(balance, *, simulation):
    """Label unchanged simulation arithmetic or an account with no observation."""
    return dict(version=1, basis='simulation' if simulation else 'exchange_mark',
        state='ready' if simulation else 'unavailable',
        reasons=() if simulation else ('ACCOUNT_OBSERVATION_REQUIRED',), entry_eligible=False,
        observation_valid=simulation, received_at=None, age_seconds=None, wallet=balance['current'],
        free=balance['current'], used=None, unrealized_pnl=None, equity=balance['equity'])


@dataclass(frozen=True)
class Commitment:
    symbol: str
    side: str
    quantity: Decimal
    reference_price: Decimal | None
    reduce_only: bool
    filled: Decimal = Decimal(0)
    terminal: bool = False
    cost_known: bool = True

    def __post_init__(self):
        if (not isinstance(self.symbol, str) or not self.symbol or self.side not in ('BUY', 'SELL')
                or type(self.reduce_only) is not bool or type(self.terminal) is not bool
                or type(self.cost_known) is not bool):
            raise AccountingError('COMMITMENT_IDENTITY_INVALID')
        if type(self.quantity) is not Decimal or type(self.filled) is not Decimal:
            raise AccountingError('COMMITMENT_DECIMAL_REQUIRED')
        if amount(self.quantity) <= 0 or not 0 <= amount(self.filled) <= self.quantity:
            raise AccountingError('COMMITMENT_QUANTITY_INVALID')
        if self.reference_price is not None and (type(self.reference_price) is not Decimal or amount(self.reference_price) <= 0):
            raise AccountingError('COMMITMENT_PRICE_INVALID')


class AccountRuntime:
    def __init__(self, binding, environment, generation, *, lock=None, interval=60.0, clock=time.monotonic):
        if not isinstance(interval, (int, float)) or isinstance(interval, bool) or not 0 < interval < float('inf'):
            raise AccountingError('ACCOUNT_REFRESH_INTERVAL_INVALID')
        self.binding, self.environment, self.generation = binding, environment, generation
        self.lock, self.clock = lock or RLock(), clock
        self.interval = float(interval)
        self.revision = 0
        self.observation = None
        self.observation_revision = None
        self.baseline = None
        self.flat_baseline = False
        self.commitments = {}
        self.failure = 'ACCOUNT_OBSERVATION_REQUIRED'
        self.inflight = None
        self.next_refresh = 0.0
        self.closed = False
        self.pending_events = 0
        self.order_sweep_required = False

    def invalidate(self, reason='EXECUTION_CHANGED'):
        with self.lock:
            self.revision += 1
            self.failure = reason

    def establish_flat_baseline(self):
        with self.lock:
            # This is called only after the separate full account/order sweep.
            if any(c.filled for c in self.commitments.values()):
                raise AccountingError('FLAT_BASELINE_HAS_EXECUTION')
            self.flat_baseline = True
            self.invalidate('ACCOUNT_RECONCILIATION_REQUIRED')

    def reserve(self, order_id, commitment):
        with self.lock:
            if order_id in self.commitments:
                raise AccountingError('ENTRY_COMMITMENT_ID_REUSED')
            self.commitments[order_id] = commitment
            self.invalidate()

    def update_order(self, order_id, *, filled, terminal, cost_known):
        from dataclasses import replace
        with self.lock:
            old = self.commitments.get(order_id)
            if old is None:
                return  # Historical generations do not create strategy ownership.
            if filled < old.filled or filled > old.quantity:
                self.invalidate('EXECUTION_QUANTITY_CONFLICT')
                raise AccountingError('EXECUTION_QUANTITY_CONFLICT')
            new = replace(old, filled=filled, terminal=terminal, cost_known=cost_known)
            if old != new:
                self.commitments[order_id] = new
                self.invalidate()

    def reject_unsent(self, order_id):
        with self.lock:
            old = self.commitments.get(order_id)
            if old is not None and old.filled == 0:
                self.update_order(order_id, filled=Decimal(0), terminal=True, cost_known=True)

    def begin_refresh(self, *, force=False):
        with self.lock:
            now = self.clock()
            if self.closed or self.inflight is not None or (not force and now < self.next_refresh):
                return None
            token = (self.generation, self.revision, now)
            self.inflight = token
            # Event invalidation coalesces into the existing account cadence.
            self.next_refresh = now + self.interval
            return token

    def finish_refresh(self, token, observation=None, error=None):
        with self.lock:
            if token != self.inflight:
                return False
            self.inflight = None
            if self.closed or token[:2] != (self.generation, self.revision):
                self.failure = 'ACCOUNT_READ_OVERLAPPED_EXECUTION'
                return False
            if error is not None:
                self.invalidate('ACCOUNT_REFRESH_FAILED: ' + str(error))
                return False
            if (type(observation) is not AccountObservation or observation.context.binding != self.binding
                    or observation.context.environment != self.environment):
                self.invalidate('ACCOUNT_OBSERVATION_SCOPE_MISMATCH')
                return False
            now = self.clock()
            if not token[2] <= observation.context.started_monotonic <= observation.context.ended_monotonic <= now:
                self.invalidate('ACCOUNT_RECEIVE_CLOCK_INVALID')
                return False
            self.observation, self.observation_revision = observation, self.revision
            self.failure = None
            view = self.view()
            if view['entry_eligible'] and self.baseline is None:
                self.baseline = observation.equity
            return view['entry_eligible']

    def expected_positions(self):
        amounts = {}
        for c in self.commitments.values():
            amounts.setdefault(c.symbol, []).append(c.filled if c.side == 'BUY' else c.filled.copy_negate())
        return {symbol: q for symbol, values in amounts.items() if (q := exact_sum(values)) != 0}

    def view(self):
        with self.lock:
            observation, now = self.observation, self.clock()
            age = None if observation is None else now - observation.context.ended_monotonic
            reasons = []
            if self.closed:
                reasons.append('ACCOUNT_OWNER_CLOSED')
            if self.pending_events:
                reasons.append('EXCHANGE_EVENTS_PENDING')
            if self.order_sweep_required:
                reasons.append('ACCOUNT_ORDER_OWNERSHIP_UNVERIFIED')
            if observation is None:
                reasons.append('ACCOUNT_OBSERVATION_REQUIRED')
            elif age < 0 or age > 2 * self.interval:
                reasons.append('ACCOUNT_OBSERVATION_EXPIRED')
            elif not observation.complete:
                reasons.extend(observation.reasons)
            if self.failure:
                reasons.append(self.failure)
            if not self.flat_baseline:
                reasons.append('ACCOUNT_FLAT_BASELINE_REQUIRED')
            if self.observation_revision != self.revision:
                reasons.append('ACCOUNT_RECONCILIATION_REQUIRED')
            positions = {}
            exposure = []
            expected_positions = self.expected_positions()
            if observation is not None and observation.complete:
                for p in observation.positions:
                    if not p.contracts:
                        continue
                    positions[p.symbol] = p.base_quantity if p.side == 'BUY' else p.base_quantity.copy_negate()
                    exposure.append(exact_product(p.base_quantity, p.entry_price))
                if positions != expected_positions:
                    reasons.append('ACCOUNT_OWNED_QUANTITY_MISMATCH')
            for c in self.commitments.values():
                if c.filled and not c.cost_known:
                    reasons.append('EXECUTION_COST_UNAVAILABLE')
                if c.reduce_only and not c.terminal and c.symbol not in expected_positions:
                    reasons.append('ORPHAN_REDUCE_ONLY_ORDER')
            reconciled = not reasons
            held = []
            for c in self.commitments.values():
                if c.reduce_only:
                    continue
                qty = Decimal(0) if c.terminal else exact_sum((c.quantity, c.filled.copy_negate()))
                if not reconciled:
                    qty = exact_sum((qty, c.filled))
                if qty:
                    if c.reference_price is None:
                        reasons.append('COMMITMENT_PRICE_UNAVAILABLE')
                    else:
                        held.append(exact_product(qty, c.reference_price))
            state = ('unavailable' if observation is None else 'unsupported' if not observation.complete else
                     'stale' if age < 0 or age > 2 * self.interval else 'reconciling' if reasons else 'ready')
            known = observation is not None and observation.complete and age is not None and 0 <= age <= 2 * self.interval and not self.failure
            return dict(version=1, basis='exchange_mark', state=state, reasons=tuple(sorted(set(reasons))),
                observation_id=observation.context.observation_id if observation else None,
                received_at=observation.context.received_at if observation else None, age_seconds=age,
                generation=self.generation, revision=self.revision, observation_revision=self.observation_revision,
                observation_valid=known, entry_eligible=not reasons,
                wallet=float(observation.wallet) if known else None,
                free=float(observation.free) if known else None,
                used=float(observation.used) if known else None,
                unrealized_pnl=float(observation.unrealized_pnl) if known else None,
                equity=float(observation.equity) if known else None,
                initial_equity=float(self.baseline) if self.baseline is not None else None,
                observed_exposure=float(exact_sum(exposure)) if known else None,
                held_commitments=float(exact_sum(held)) if 'COMMITMENT_PRICE_UNAVAILABLE' not in reasons else None)

    def balance_status(self, view=None):
        view = self.view() if view is None else view
        initial, equity = view['initial_equity'], view['equity']
        pnl = equity - initial if equity is not None and initial is not None else None
        return dict(initial=initial, current=view['free'], equity=equity, pnl=pnl,
                    pnl_pct=pnl / initial * 100 if pnl is not None and initial > 0 else None)

    def close(self):
        with self.lock:
            if self.inflight is not None or self.pending_events:
                raise AccountingError('ACCOUNT_REFRESH_STILL_IN_FLIGHT')
            self.closed = True
            self.invalidate('ACCOUNT_OWNER_CLOSED')
