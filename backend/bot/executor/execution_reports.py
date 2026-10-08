"""Durable, identified execution-result snapshots and retryable report delivery.

This outbox never sends orders or derives strategy ownership from account exposure.
Prepared records are immutable historical snapshots; later conflicts are visible.
"""
from copy import deepcopy
from decimal import Decimal, localcontext
from datetime import datetime, timezone
import hashlib
import json
import math

from .accounting_models import AccountingError, exact_sum

REPORT_KINDS = ('trade_report_context', 'trade_report_prepared', 'trade_report_published')
FINANCIAL_KEYS = {'quantity', 'entry_price', 'exit_price', 'pnl', 'pnl_pct',
                  'gross_pnl', 'execution_fees', 'execution_accounting', 'outcome_basis', 'execution_report_prepared_at'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()


def trade_identity(binding, environment, entry_order_id):
    return 'execution-' + digest([binding, environment, entry_order_id])


def numeric(value, *, positive=False):
    result = float(value)
    if (not value.is_finite() or not math.isfinite(result)
            or (value != 0 and result == 0) or positive and result <= 0):
        raise AccountingError('EXECUTION_REPORT_NUMERIC_RANGE')
    return result


def financial_fields(outcome, side):
    """Validate the immutable financial snapshot, retaining exact strings too."""
    expected_keys = {'version', 'basis', 'complete', 'entry_order_id', 'exit_order_ids',
                     'entry_quantity', 'exit_quantity', 'entry_cost', 'exit_cost', 'gross_pnl',
                     'fees', 'fees_complete', 'pnl_after_execution_fees', 'funding', 'funding_allocated', 'reasons'}
    if (type(outcome) is not dict or set(outcome) != expected_keys
            or any(type(outcome[key]) is not str for key in ('entry_quantity', 'exit_quantity',
                   'entry_cost', 'exit_cost', 'gross_pnl', 'pnl_after_execution_fees'))
            or type(outcome['fees']) is not dict
            or any(type(k) is not str or not k or type(v) is not str for k, v in outcome['fees'].items())):
        raise AccountingError('EXECUTION_REPORT_FINANCIAL_SHAPE')
    if (outcome.get('version') != 1 or outcome.get('complete') is not True
            or outcome.get('fees_complete') is not True or outcome.get('reasons') != []
            or outcome.get('basis') != 'executions_excluding_funding_and_transfers'
            or outcome.get('funding') is not None or outcome.get('funding_allocated') is not False):
        raise AccountingError('EXECUTION_REPORT_INCOMPLETE')
    quantity, exited, entry, exit_cost, gross, pnl = (
        Decimal(outcome[key]) for key in ('entry_quantity', 'exit_quantity', 'entry_cost',
                                         'exit_cost', 'gross_pnl', 'pnl_after_execution_fees'))
    fees = {key: Decimal(value) for key, value in outcome['fees'].items()}
    if (not all(v.is_finite() for v in (quantity, exited, entry, exit_cost, gross, pnl, *fees.values()))
            or quantity <= 0 or quantity != exited or entry <= 0 or exit_cost <= 0
            or side not in ('BUY', 'SELL') or any(k != 'USDT' and v != 0 for k, v in fees.items())):
        raise AccountingError('EXECUTION_REPORT_FINANCIAL_SHAPE')
    expected_gross = exact_sum((exit_cost, entry.copy_negate()))
    if side == 'SELL':
        expected_gross = expected_gross.copy_negate()
    fee = exact_sum(fees.values())
    if gross != expected_gross or pnl != exact_sum((gross, fee.copy_negate())):
        raise AccountingError('EXECUTION_REPORT_ARITHMETIC_CONFLICT')
    with localcontext() as context:
        context.prec = 256
        return dict(quantity=numeric(quantity, positive=True), entry_price=numeric(entry / quantity, positive=True),
                    exit_price=numeric(exit_cost / quantity, positive=True), pnl=numeric(pnl),
                    pnl_pct=numeric(pnl / entry * 100), gross_pnl=numeric(gross),
                    execution_fees={key: str(value) for key, value in fees.items()},
                    execution_accounting=deepcopy(outcome), outcome_basis=outcome['basis'])


def validate_report_events(connection, binding, environment, order_id=None):
    """Validate shape, entry scope and the context -> prepared -> delivered chain."""
    where = ' AND order_id=?' if order_id is not None else ''
    rows = connection.execute("SELECT order_id,kind,payload FROM events WHERE kind IN (?,?,?)" + where + ' ORDER BY sequence',
                              (*REPORT_KINDS, order_id) if order_id is not None else REPORT_KINDS).fetchall()
    result = {}
    for oid, kind, raw in rows:
        payload = json.loads(raw)
        values = result.setdefault(oid, {})
        if kind in values or type(payload) is not dict or payload.get('version') != 1:
            raise AccountingError('EXECUTION_REPORT_EVENT_INVALID')
        intent_row = connection.execute('SELECT intent FROM requests WHERE order_id=?', (oid,)).fetchone()
        if not intent_row:
            raise AccountingError('EXECUTION_REPORT_ENTRY_MISSING')
        intent = json.loads(intent_row[0])
        if intent['purpose'] != 'entry':
            raise AccountingError('EXECUTION_REPORT_ENTRY_REQUIRED')
        if kind == REPORT_KINDS[0]:
            if (set(payload) != {'version', 'entry_order_id', 'session_id', 'trade'}
                    or payload['entry_order_id'] != oid or not isinstance(payload['session_id'], str)
                    or not payload['session_id'] or type(payload['trade']) is not dict):
                raise AccountingError('EXECUTION_REPORT_CONTEXT_INVALID')
            trade = payload['trade']
            if (trade.get('trade_id') != trade_identity(binding, environment, oid)
                    or trade.get('symbol') != intent['symbol']
                    or trade.get('direction') != ('LONG' if intent['side'] == 'BUY' else 'SHORT')
                    or FINANCIAL_KEYS.intersection(trade)):
                raise AccountingError('EXECUTION_REPORT_CONTEXT_SCOPE')
        elif kind == REPORT_KINDS[1]:
            context = values.get(REPORT_KINDS[0])
            if (not context or set(payload) != {'version', 'context_digest', 'prepared_at', 'trade'}
                    or payload['context_digest'] != digest(context)):
                raise AccountingError('EXECUTION_REPORT_CONTEXT_LINK')
            trade = payload['trade']
            outcome = trade['execution_accounting']
            if outcome.get('entry_order_id') != oid:
                raise AccountingError('EXECUTION_REPORT_ENTRY_CONFLICT')
            exit_ids = outcome.get('exit_order_ids')
            if not isinstance(exit_ids, list) or not exit_ids or len(set(exit_ids)) != len(exit_ids):
                raise AccountingError('EXECUTION_REPORT_EXITS_INVALID')
            for exit_id in exit_ids:
                child = connection.execute('SELECT intent FROM requests WHERE order_id=?', (exit_id,)).fetchone()
                if not child or json.loads(child[0]).get('parent_entry_order_id') != oid:
                    raise AccountingError('EXECUTION_REPORT_EXIT_LINK')
            if datetime.fromisoformat(payload['prepared_at']).tzinfo is None:
                raise AccountingError('EXECUTION_REPORT_TIMESTAMP_INVALID')
            expected = {**context['trade'], **financial_fields(outcome, intent['side']),
                        'execution_report_prepared_at': payload['prepared_at']}
            if trade != expected:
                raise AccountingError('EXECUTION_REPORT_SNAPSHOT_CONFLICT')
        else:
            prepared = values.get(REPORT_KINDS[1])
            if (not prepared or set(payload) != {'version', 'prepared_digest'}
                    or payload['prepared_digest'] != digest(prepared)):
                raise AccountingError('EXECUTION_REPORT_DELIVERY_LINK')
        canonical(payload)
        values[kind] = payload
    return result


class ExecutionReportPublisher:
    """A stateless outbox reader; all retry authority lives in the execution store."""
    def __init__(self, executor, journal):
        self.executor = executor
        self.journal = journal

    def capture(self, entry_order_id, trade, session_id):
        ex = self.executor
        with ex._state_lock:
            ex._require_storage()
            order = ex._orders[entry_order_id]
            state = ex._financial_states[entry_order_id]
            if trade.get('symbol') != order.symbol or trade.get('direction') != ('LONG' if order.side.value == 'BUY' else 'SHORT'):
                raise AccountingError('EXECUTION_REPORT_CONTEXT_SCOPE')
            # Context carries observations, never financial authority.
            metadata = {k: v for k, v in trade.items() if k not in FINANCIAL_KEYS}
            metadata.setdefault('report_metadata_basis', 'managed_position')
            if trade.get('trade_id'):
                metadata.setdefault('source_position_id', trade['trade_id'])
            metadata['trade_id'] = trade_identity(state.binding, state.environment, entry_order_id)
            payload = dict(version=1, entry_order_id=entry_order_id, session_id=session_id, trade=metadata)
            ex._journal.record_report_event(entry_order_id, REPORT_KINDS[0], payload)
            return metadata['trade_id']

    def publish(self, entry_order_id):
        ex = self.executor
        with ex._state_lock:
            ex._require_storage()
            ex._inflight_reports = getattr(ex, '_inflight_reports', 0) + 1
        try:
            return self._publish(entry_order_id)
        finally:
            with ex._state_lock:
                ex._inflight_reports -= 1

    def _publish(self, entry_order_id):
        ex = self.executor
        with ex._state_lock:
            ex._require_storage()
            events = ex._journal.report_events(entry_order_id).get(entry_order_id, {})
            context = events.get(REPORT_KINDS[0])
            if context is None:
                raise AccountingError('EXECUTION_REPORT_CONTEXT_REQUIRED')
            outcome = ex.execution_outcome(entry_order_id)
            previous = events.get(REPORT_KINDS[1])
            if previous and previous['trade']['execution_accounting'] != outcome.to_dict():
                raise AccountingError('EXECUTION_REPORT_EVIDENCE_CHANGED')
            if not outcome.complete:
                return {'state': 'pending', 'entry_order_id': entry_order_id, 'reasons': list(outcome.reasons)}
            prepared_at = previous['prepared_at'] if previous else datetime.now(timezone.utc).isoformat()
            trade = {**context['trade'], **financial_fields(outcome.to_dict(), ex._orders[entry_order_id].side.value),
                     'execution_report_prepared_at': prepared_at}
            prepared = dict(version=1, context_digest=digest(context), prepared_at=prepared_at, trade=trade)
            ex._journal.record_report_event(entry_order_id, REPORT_KINDS[1], prepared)
            delivered = REPORT_KINDS[2] in events
        # Keep slow JSONL IO out of the execution state lock. The durable message
        # is immutable: it describes evidence at preparation, not future truth.
        if not delivered:
            self.journal.upsert(trade, context['session_id'])
            with ex._state_lock:
                ex._require_storage()
                if ex.execution_outcome(entry_order_id).to_dict() != outcome.to_dict():
                    raise AccountingError('EXECUTION_REPORT_EVIDENCE_CHANGED')
                ex._journal.record_report_event(entry_order_id, REPORT_KINDS[2],
                                               dict(version=1, prepared_digest=digest(prepared)))
        return {'state': 'published', 'entry_order_id': entry_order_id, 'session_id': context['session_id'], 'trade': deepcopy(trade)}

    def recover(self):
        """Replay reports; recover missing context only for explicitly opted-in entries."""
        ex = self.executor
        with ex._state_lock:
            ex._require_storage()
            ex._inflight_reports = getattr(ex, '_inflight_reports', 0) + 1
        try:
            with ex._state_lock:
                captured = ex._journal.report_events()
                for intent, legacy in ex._journal.records():
                    oid = intent['order_id']
                    if oid not in ex._restored_ids or intent['purpose'] != 'entry' or oid in captured:
                        continue
                    outcome = ex.execution_outcome(oid)
                    if outcome.entry_quantity <= 0 or outcome.entry_quantity != outcome.exit_quantity:
                        continue
                    # Older requests may already have a differently identified historical row.
                    # Never create a second report by guessing its previous identity.
                    if intent.get('report_version') != 1:
                        continue
                    trade = dict(symbol=intent['symbol'], direction='LONG' if intent['side']=='BUY' else 'SHORT',
                        entry_time=legacy['created_at'],
                        exit_time=max(ex._orders[eid].updated_at.isoformat() for eid in outcome.exit_order_ids),
                        exit_reason='exchange_exit', report_metadata_basis='recovered_execution_only',
                        time_basis='local_request_and_observation', regime_labeled_at='unknown',
                        execution_owner=intent['owner'], execution_generation=intent['generation'])
                    self.capture(oid, trade, 'execution-recovery:' + intent['generation'])
                candidates = list(ex._journal.report_events())
            results = []
            for entry_order_id in candidates:
                try:
                    results.append(self.publish(entry_order_id))
                except Exception as exc:
                    results.append({'state': 'error', 'entry_order_id': entry_order_id, 'reasons': [str(exc)]})
            return results
        finally:
            with ex._state_lock:
                ex._inflight_reports -= 1
