"""Real queue, executor, journal and status consumers under scripted transport."""
import asyncio
import json
import time
from threading import Event
from types import SimpleNamespace as S
from unittest.mock import Mock
import pytest
from backend.data.adapters.phemex_ws import PhemexWebSocketClient
from backend.bot.executor.accounting_models import AccountingError
from backend.bot.executor.execution_journal import ExecutionJournal, JournalError
from backend.bot.live_trading_service import LiveTradingService
from backend.bot.paper_trading_service import PaperTradingService
from backend.tests.unit.test_accounting_runtime import executor
from backend.tests.unit.test_phemex_accounting import raw_order
from backend.bot.executor.paper_executor import OrderStatus, OrderSide
from backend.bot.executor.accounting_runtime import Commitment
from backend.bot.executor.execution_outcomes import ExecutionReceipt
from decimal import Decimal as D


def client_for(ex):
    return PhemexWebSocketClient('fixture', 'fixture', True, on_raw_order=ex.apply_ws_order,
        on_invalidate=ex.invalidate_account, on_pending=ex.ws_event_pending, on_complete=ex.ws_event_complete)


def test_documented_frame_same_exec_sequence_is_not_an_order_revision(executor):
    ex, _ = executor
    order = ex.place_order('BTC/USDT:USDT', 'BUY', 'LIMIT', 10, price=110)
    raw = raw_order()
    raw.update(clOrdID=order.order_id, cumQty='10', execSeq=77, tradeType='Trade', execID='trade',
               execQty='10', execValueRv='1060', execFeeRv='0.2', currency='USDT')
    del raw['cumQtyRq']
    opened = {**raw, 'cumQty': '0', 'cumValueRv': '0', 'ordStatus': 'New', 'execQty': '0',
              'execValueRv': '0', 'execID': '00000000-0000-0000-0000-000000000000', 'tradeType': 'Amend'}
    async def run():
        client = client_for(ex)
        client._worker = asyncio.create_task(client._consume_orders())
        client._dispatch(json.dumps({'type': 'incremental', 'sequence': 9, 'orders_p': [opened, raw, raw]}))
        assert ex._accounting.pending_events == 3
        assert not ex.accounting_status()['entry_eligible']
        await client.stop()
        assert ex._accounting.pending_events == 0
        assert client.metrics['callback_failures_total'] == 0
    asyncio.run(run())
    assert order.filled_quantity == 10 and order.average_fill_price == 106
    assert len(ex.get_trade_history()) == 1
    assert ex.get_trade_history()[0].fee == .2
    assert ex.get_statistics()['total_fees'] == .2
    assert ex._positions == {} and ex._cached_balance == 750


def test_queue_keeps_event_loop_responsive_and_stop_waits_for_commit(executor):
    ex, _ = executor
    entered, release = Event(), Event()
    def slow(raw):
        entered.set()
        assert release.wait(3)
    async def run():
        client = client_for(ex)
        client._on_raw_order = slow
        client._worker = asyncio.create_task(client._consume_orders())
        client._dispatch(json.dumps({'type': 'snapshot', 'orders_p': [{'orderID': 'fixture'}]}))
        assert await asyncio.to_thread(entered.wait, 1)
        tick = asyncio.Event()
        asyncio.get_running_loop().call_soon(tick.set)
        await asyncio.wait_for(tick.wait(), .5)
        stop = asyncio.create_task(client.stop())
        await asyncio.sleep(0)
        assert not stop.done()
        with pytest.raises(AccountingError, match='IN_FLIGHT'):
            ex.close()
        with pytest.raises(JournalError, match='owned'):
            ExecutionJournal(ex._journal.path, 'fixture')
        release.set()
        await stop
        assert ex._accounting.pending_events == 0
    try:
        asyncio.run(run())
    finally:
        release.set()


def test_queue_overflow_and_foreign_orders_need_full_order_sweep(executor):
    ex, adapter = executor
    async def run():
        client = client_for(ex)
        client._on_raw_order = lambda row: None
        client._dispatch(json.dumps({'type': 'snapshot', 'orders_p': [{}] * 257}))
        assert client._queue.qsize() == 256
        assert client.metrics['queue_overflows_total'] == 1
        client._worker = asyncio.create_task(client._consume_orders())
        await client.stop()
    asyncio.run(run())
    assert ex._accounting.order_sweep_required
    adapter.fetch_account_snapshot = Mock(return_value={'complete': True, 'scope': 'phemex:swap:USDT',
                                                       'orders': [{'id': 'foreign'}], 'positions': []})
    assert not ex.reconcile_account(force=True)['entry_eligible']
    assert ex._accounting.order_sweep_required
    adapter.fetch_account_snapshot.return_value['orders'] = []
    assert ex.reconcile_account(force=True)['entry_eligible']


@pytest.mark.parametrize('service', [LiveTradingService, PaperTradingService])
def test_status_preserves_unavailable_and_mark_basis(executor, service):
    ex, _ = executor
    svc = service()
    svc.executor = ex
    status = svc.get_status()
    assert status['accounting']['basis'] == 'exchange_mark'
    assert status['balance']['equity'] == 1000
    assert status['balance']['current'] == 750
    assert status['balance']['initial'] == 1000
    ex.invalidate_account('fixture_failure')
    status = svc.get_status()
    assert status['balance']['equity'] is None and status['balance']['pnl'] is None
    assert status['balance']['current'] is None


def test_quarantined_identity_cannot_clear_unknown_request(executor):
    ex, _ = executor
    order = ex.place_order('BTC/USDT:USDT', 'BUY', 'LIMIT', 10, price=110)
    ex._submission_unknown(order, 'original outcome uncertain')
    raw = raw_order()
    raw.update(clOrdID='different', cumQtyRq='0', cumValueRv='0', ordStatus='New')
    ex.apply_ws_order(raw)
    assert order.order_id in ex._unacknowledged_orders
    assert ex._accounting.order_sweep_required
    assert order.filled_quantity == 0


def plan_fixture():
    return S(symbol='BTC/USDT:USDT', direction='LONG', entry_zone=S(near_entry=100),
             stop_loss=S(level=90), targets=[], confidence_score=80, trade_type='intraday')


def test_testnet_sizing_uses_one_snapshot_equity_and_free_margin():
    svc = PaperTradingService()
    svc.config = S(leverage=2, risk_per_trade=1.)
    svc.executor = S(_accounting=True, accounting_status=Mock(return_value={
        'entry_eligible': True, 'equity': 1000., 'free': 1.}))
    svc._get_adapted_risk_pct = lambda: 1.
    svc._get_regime_size_multiplier = lambda: 1.
    assert svc._calculate_position_size(plan_fixture()) == .01
    svc.executor.accounting_status.assert_called_once()
    svc.executor.accounting_status.return_value['entry_eligible'] = False
    assert svc._calculate_position_size(plan_fixture()) == 0


@pytest.mark.parametrize('service', [LiveTradingService, PaperTradingService])
def test_unknown_cost_terminal_entry_stays_visible(executor, service):
    ex, _ = executor
    o = ex.place_order('BTC/USDT:USDT', 'BUY', 'LIMIT', 10, price=110)
    raw = raw_order()
    raw['clOrdID'] = o.order_id
    del raw['cumValueRv']
    ex._process_exchange_order(o, {'info': raw})
    svc = service()
    svc.executor = ex
    svc._pending_plans[o.order_id] = plan_fixture()
    pending = svc.get_status()['pending_orders']
    assert len(pending) == 1 and pending[0]['filled_qty'] == 10
    assert pending[0]['awaiting_adoption'] and pending[0]['average_fill_price'] is None


def test_testnet_late_cost_adopts_once_and_retains_native_protection():
    svc = PaperTradingService()
    order = S(order_id='entry', status=OrderStatus.FILLED, filled_quantity=10, average_fill_price=None)
    protector = S(filled_quantity=0)
    svc.executor = S(refresh_order=Mock(), get_order=Mock(return_value=order),
                     protect_confirmed_entry=Mock(return_value=protector))
    svc.position_manager = S(find_position_by_order_id=Mock(return_value=None), open_position=Mock())
    svc._pending_plans['entry'] = plan_fixture()
    asyncio.run(svc._monitor_testnet_entries())
    assert 'entry' in svc._pending_plans
    svc.position_manager.open_position.assert_not_called()
    order.average_fill_price = 106
    asyncio.run(svc._monitor_testnet_entries())
    asyncio.run(svc._monitor_testnet_entries())
    svc.position_manager.open_position.assert_called_once()
    assert svc.position_manager.open_position.call_args.kwargs['entry_price'] == 106
    assert svc.stats.signals_taken == 1


def test_live_late_price_after_native_stop_does_not_resurrect_position():
    svc = LiveTradingService()
    svc.executor = S(_entry_protection={'entry': 'stop'}, refresh_order=Mock(),
                     get_order=Mock(return_value=S(filled_quantity=10)))
    svc.position_manager = S(find_position_by_order_id=Mock(return_value=None), open_position=Mock())
    svc._pending_plans['entry'] = plan_fixture()
    assert asyncio.run(svc._open_filled_entry('entry', plan_fixture(), 106, 10)) is None
    svc.position_manager.open_position.assert_not_called()
    assert 'entry' in svc._pending_plans


def test_testnet_exit_retries_original_identity_and_requires_full_quantity():
    svc = PaperTradingService()
    order = S(order_id='exit', status=OrderStatus.OPEN, side=OrderSide.SELL, quantity=10, filled_quantity=0,
              parent_entry_order_id='entry')
    svc.executor = S(get_order=Mock(return_value=order), place_order=Mock(return_value=order),
                     refresh_order=Mock(), cleanup_flat_protection=Mock(),
                     advance_reduction=lambda *_:ExecutionReceipt('exit',D(order.filled_quantity),
                         D(order.filled_quantity)*100,None,order.status==OrderStatus.FILLED,()))
    assert not asyncio.run(svc._execute_testnet_exit('BTC/USDT:USDT', 'SELL', 10, 100, 'entry'))
    order.filled_quantity = 4
    assert not asyncio.run(svc._execute_testnet_exit('BTC/USDT:USDT', 'SELL', 10, 100, 'entry'))
    order.filled_quantity, order.status = 10, OrderStatus.FILLED
    assert asyncio.run(svc._execute_testnet_exit('BTC/USDT:USDT', 'SELL', 10, 100, 'entry'))
    svc.executor.place_order.assert_called_once()
    assert svc.executor.place_order.call_args.kwargs['reduce_only']
    svc.executor.cleanup_flat_protection.assert_called_once()


def test_flat_native_stop_blocks_new_entries_until_cancel_confirmed(executor):
    ex, _ = executor
    ex._accounting.reserve('stop', Commitment('BTC/USDT:USDT', 'SELL', D(10), D(90), True))
    assert not ex.reconcile_account(force=True)['entry_eligible']
    assert 'ORPHAN_REDUCE_ONLY_ORDER' in ex.accounting_status()['reasons']
    ex._accounting.update_order('stop', filled=D(0), terminal=True, cost_known=True)
    assert ex.reconcile_account(force=True)['entry_eligible']


def test_real_journal_duplicate_burst_keeps_heartbeat_and_single_fill(executor):
    ex, _ = executor
    order = ex.place_order('BTC/USDT:USDT', 'BUY', 'LIMIT', 10, price=110)
    raw = raw_order()
    raw['clOrdID'] = order.order_id
    async def run():
        client = client_for(ex)
        client._worker = asyncio.create_task(client._consume_orders())
        gaps = []
        done = False
        async def heartbeat():
            previous = time.monotonic()
            while not done:
                await asyncio.sleep(.01)
                now = time.monotonic()
                gaps.append(now - previous)
                previous = now
        pulse = asyncio.create_task(heartbeat())
        client._dispatch(json.dumps({'type': 'incremental', 'orders_p': [raw] * 200}))
        await client.stop()
        done = True
        await pulse
        assert client.metrics['callback_failures_total'] == 0
        assert client.metrics['queue_overflows_total'] == 0
        assert len(gaps) > 5 and max(gaps) < .5
    asyncio.run(run())
    assert len(ex.get_trade_history()) == 1 and order.filled_quantity == 10
    assert ex._accounting.pending_events == 0


def test_flat_protection_cancellation_failure_is_retained_for_retry(executor):
    ex, _ = executor
    ex._orders['entry'] = S(filled_quantity=10, symbol='BTC/USDT:USDT')
    ex._orders['stop'] = S(status=OrderStatus.OPEN)
    ex._entry_protection['entry'] = 'stop'
    ex.cancel_order = Mock(side_effect=RuntimeError('transport unavailable'))
    ex.cleanup_flat_protection()
    assert ex._entry_protection['entry'] == 'stop'
    ex.cancel_order.side_effect = lambda oid: setattr(ex._orders[oid], 'status', OrderStatus.CANCELLED)
    ex.cleanup_flat_protection()
    ex.cleanup_flat_protection()
    assert ex.cancel_order.call_count == 2
