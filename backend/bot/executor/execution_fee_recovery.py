"""Bounded, observable fee recovery for explicit durable execution requests."""
import asyncio
import logging
import math
import time
from threading import Event, Lock

logger = logging.getLogger(__name__)


class _RecoveryStopped(Exception):
    pass


class ExecutionFeeRecovery:
    def __init__(self, executor, interval=30.0, max_pages=50, report_journal=None):
        if (type(interval) not in (int, float) or not math.isfinite(interval) or interval <= 0
                or type(max_pages) is not int or not 1 <= max_pages <= 50):
            raise ValueError('Invalid fee recovery bounds')
        self.executor = executor
        self.report_journal = report_journal
        self.interval = interval
        self.max_pages = max_pages
        self._attempted = {}
        self._lock = Lock()
        self._stopping = Event()
        self._status = {'state': 'idle', 'running': False, 'attempts': 0, 'pending_orders': 0, 'last_error': None}

    def request_stop(self):
        self._stopping.set()

    def _check_running(self):
        if self._stopping.is_set():
            raise _RecoveryStopped()

    def status(self):
        return dict(self._status)

    def recover_once(self):
        if not self._lock.acquire(blocking=False):
            return self.status()
        ex = self.executor
        entered = False
        try:
            self._check_running()
            with ex._state_lock:
                ex._require_storage()
                candidates = [(oid, state) for oid, state in ex._financial_states.items()
                              if state.filled_quantity > 0 and not state.financially_complete]
                if not candidates:
                    self._status = {**self._status, 'state': 'idle', 'pending_orders': 0, 'last_error': None}
                    return self.status()
                oid, state = min(candidates, key=lambda item: (self._attempted.get(item[0], -1), item[0]))
                self._attempted[oid] = time.monotonic()
                order = ex.get_order(oid)
                stamp = state.order_context.exchange_timestamp_ns if state.order_context else None
                created = int(order.created_at.timestamp() * 1000)
                start = max(0, min(created, stamp // 1_000_000 if stamp else created) - 1000)
                end = max(int(time.time() * 1000), stamp // 1_000_000 if stamp else 0)
                symbol, remote = order.symbol, state.exchange_order_id
                ex._inflight_history = getattr(ex, '_inflight_history', 0) + 1
                entered = True
            self._status = {**self._status, 'state': 'recovering', 'order_id': oid,
                            'attempts': self._status['attempts'] + 1, 'pending_orders': len(candidates),
                            'last_error': None, 'pages': 0, 'matched_executions': 0,
                            'consistent_requested_window': False, 'order_financially_complete': False,
                            'start_ms': start, 'end_ms': end}
            offset, first, seen, matched = 0, None, set(), []
            finished = False
            for page_number in range(self.max_pages):
                self._check_running()
                rows = ex._adapter.fetch_trade_execution_page(symbol, start, end, offset=offset, limit=200)
                self._check_running()
                if not isinstance(rows, list) or len(rows) > 200:
                    raise ValueError('FEE_HISTORY_PAGE_INVALID')
                if first is None:
                    first = rows
                for row in rows:
                    eid = row.get('execID')
                    if not eid or eid in seen:
                        raise ValueError('FEE_HISTORY_PAGE_OVERLAP')
                    seen.add(eid)
                    if row.get('clOrdID') == oid or (remote is not None and row.get('orderID') == remote):
                        matched.append(row)
                self._status = {**self._status, 'pages': page_number + 1, 'matched_executions': len(matched)}
                offset += len(rows)
                if len(rows) < 200:
                    finished = True
                    break
            if not finished:
                raise ValueError('FEE_HISTORY_PAGE_LIMIT')
            if ex._adapter.fetch_trade_execution_page(symbol, start, end, offset=0, limit=200) != first:
                raise ValueError('FEE_HISTORY_CHANGED_DURING_SWEEP')
            self._check_running()
            ex.import_execution_history(oid, matched)
            with ex._state_lock:
                result = ex._financial_states[oid]
                pending_count = sum(s.filled_quantity > 0 and not s.financially_complete
                                    for s in ex._financial_states.values())
            complete = result.financially_complete
            self._status = {**self._status, 'state': 'ready' if complete else 'pending',
                            'last_error': None if complete else 'EXECUTION_FEE_COVERAGE_PENDING',
                            'consistent_requested_window': True,
                            'order_financially_complete': complete,
                            'pending_orders': pending_count,
                            'last_finished_at_ms': int(time.time() * 1000)}
            if not complete:
                logger.warning('EXECUTION_FEE_COVERAGE_PENDING %s matched=%s', oid, len(matched))
            return self.status()
        except _RecoveryStopped:
            self._status = {**self._status, 'state': 'stopped'}
            return self.status()
        except Exception as exc:
            self._status = {**self._status, 'state': 'pending', 'last_error': str(exc),
                            'consistent_requested_window': False, 'order_financially_complete': False}
            logger.exception('EXECUTION_FEE_RECOVERY_PENDING')
            return self.status()
        finally:
            if entered:
                with ex._state_lock:
                    ex._inflight_history -= 1
            self._lock.release()

    def recover_reports(self):
        if self.report_journal is None:
            return []
        from .execution_reports import ExecutionReportPublisher
        results = ExecutionReportPublisher(self.executor, self.report_journal).recover()
        self._status = {**self._status, 'report_error': None, 'reports': [
            {k: v for k, v in result.items() if k != 'trade'} for result in results]}
        for result in results:
            if result['state'] == 'error':
                logger.error('EXECUTION_REPORT_RECOVERY_FAILED %s: %s', result['entry_order_id'], result['reasons'])
        return results

    def _iteration(self):
        self.recover_once()
        if not self._stopping.is_set():
            try:
                self.recover_reports()
            except Exception as exc:
                self._status = {**self._status, 'report_error': str(exc)}
                logger.exception('EXECUTION_REPORT_RECOVERY_FAILED')

    async def run(self):
        """Cancellation drains the current thread before ownership can be released."""
        self._status = {**self._status, 'running': True}
        try:
            while not self._stopping.is_set():
                pending = asyncio.get_running_loop().run_in_executor(None, self._iteration)
                try:
                    await asyncio.shield(pending)
                except asyncio.CancelledError:
                    self.request_stop()
                    while not pending.done():
                        try:
                            await asyncio.shield(pending)
                        except asyncio.CancelledError:
                            continue
                    pending.result()
                    raise
                await asyncio.sleep(self.interval)
        finally:
            self._status = {**self._status, 'running': False}
