"""Bounded history recovery, identity filtering and shutdown lifetime ownership."""
import asyncio
from dataclasses import replace
from threading import Event
from types import SimpleNamespace as S
from unittest.mock import AsyncMock, Mock
import pytest
from backend.bot.executor.execution_fee_recovery import ExecutionFeeRecovery
from backend.bot.executor.execution_journal import JournalError
from backend.tests.unit.test_accounting_runtime import executor
from backend.tests.unit.test_phemex_accounting import raw_order
from backend.tests.unit.test_execution_fee_history import trade


def pending(ex):
    order=ex.place_order('BTC/USDT:USDT','BUY','LIMIT',10,price=110)
    raw=raw_order();raw.update(clOrdID=order.order_id,cumValueRv='1000')
    ex.apply_ws_order(raw)
    return order,trade(orderID=raw['orderID'])


def test_paged_recovery_ignores_foreign_orders_and_deduplicates_retries(executor):
    ex,ad=executor
    order,owned=pending(ex)
    rows=[trade(execID=f'foreign-{i}',orderID=f'other-{i}') for i in range(200)]+[owned]
    ad.fetch_trade_execution_page=Mock(side_effect=lambda *a,offset,limit:rows[offset:offset+limit])
    worker=ExecutionFeeRecovery(ex)
    result=worker.recover_once()
    assert result['state']=='ready' and result['matched_executions']==1 and result['pages']==2
    assert ex.execution_receipt(order.order_id).fees[0].amount==1
    assert [c.kwargs['offset'] for c in ad.fetch_trade_execution_page.call_args_list]==[0,200,0]
    assert worker.recover_once()['state']=='idle'
    assert ad.fetch_trade_execution_page.call_count==3


@pytest.mark.parametrize('failure',['overlap','changed_head','limit','transport'])
def test_incomplete_sweep_does_not_import_partial_history(executor,failure):
    ex,ad=executor
    order,owned=pending(ex)
    first=[owned]+[trade(execID=f'other-{i}',orderID=f'other-{i}') for i in range(199)]
    def page(*a,offset,limit):
        if failure=='transport':
            raise OSError('unavailable')
        if failure=='overlap':
            return first if offset==0 else [owned]
        if failure=='limit':
            return first
        return [owned] if ad.fetch_trade_execution_page.call_count==1 else []
    ad.fetch_trade_execution_page=Mock(side_effect=page)
    worker=ExecutionFeeRecovery(ex,max_pages=1 if failure=='limit' else 50)
    result=worker.recover_once()
    assert result['state']=='pending' and result['last_error']
    assert ex.execution_receipt(order.order_id).fees is None
    assert ex._inflight_history==0


def test_empty_retained_history_remains_unknown_and_fair_rotation_advances(executor):
    ex,ad=executor
    order,_=pending(ex)
    # Selection fixture: a second immutable candidate shares the same transport
    # scope; neither yields facts, so no invented journal request is imported.
    ex._financial_states['second']=replace(ex._financial_states[order.order_id],order_id='second')
    ex._orders['second']=replace(order,order_id='second')
    ad.fetch_trade_execution_page=Mock(return_value=[])
    ex.import_execution_history=Mock()
    worker=ExecutionFeeRecovery(ex)
    first=worker.recover_once()
    second=worker.recover_once()
    assert first['state']==second['state']=='pending'
    assert first['order_id']!=second['order_id']
    assert ex.execution_receipt(order.order_id).fees is None


def test_cancel_drains_fetch_and_blocks_owner_release_without_blocking_event_loop(executor):
    ex,ad=executor
    order,owned=pending(ex)
    entered,release=Event(),Event()
    def slow(*a,**kw):
        entered.set()
        assert release.wait(3)
        return [owned]
    ad.fetch_trade_execution_page=Mock(side_effect=slow)
    worker=ExecutionFeeRecovery(ex)
    async def run():
        task=asyncio.create_task(worker.run())
        assert await asyncio.to_thread(entered.wait,1)
        heartbeat=asyncio.Event()
        asyncio.get_running_loop().call_soon(heartbeat.set)
        await asyncio.wait_for(heartbeat.wait(),.5)
        with pytest.raises(JournalError,match='transport'):
            ex.close()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and ex._inflight_history==1
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert ex._inflight_history==0 and not worker.status()['running']
    try:
        asyncio.run(run())
    finally:
        release.set()
    assert ex.execution_receipt(order.order_id).fees is None
    ad.fetch_trade_execution_page.assert_called_once()


async def draining_task(release):
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        await release.wait()
        raise


@pytest.mark.parametrize('already_stopped', [False, True])
def test_paper_stop_exits_before_draining_history_and_waits_for_storage_owner(already_stopped):
    from backend.bot.paper_trading_service import PaperTradingService, PaperBotStatus
    svc = PaperTradingService()
    svc.executor = S(_accounting=True, set_entry_admission=Mock(), recovery_snapshot=lambda: {})
    svc.status = PaperBotStatus.STOPPED if already_stopped else PaperBotStatus.RUNNING
    svc._fee_recovery = S(request_stop=Mock())
    svc._save_state = Mock()
    svc._generate_session_report = Mock(return_value=None)
    svc._release_testnet_owner = Mock()
    svc._log_activity = Mock()
    svc.get_status = lambda: {}
    async def run():
        release, exited = asyncio.Event(), asyncio.Event()
        svc._close_all_positions = AsyncMock(side_effect=lambda *a: exited.set())
        svc._fee_recovery_task = asyncio.create_task(draining_task(release))
        await asyncio.sleep(0)
        stopping = asyncio.create_task(svc._stop_session())
        try:
            await asyncio.wait_for(exited.wait(), 1)
            assert not stopping.done()
            svc._release_testnet_owner.assert_not_called()
            svc._save_state.assert_not_called()
            svc._fee_recovery.request_stop.assert_called_once()
        finally:
            release.set()
            await asyncio.wait_for(stopping, 1)
        assert svc._fee_recovery_task is None
    asyncio.run(run())


def test_live_stop_exits_before_draining_history_and_checkpoints_only_afterwards():
    from backend.bot.live_trading_service import LiveTradingService
    svc = LiveTradingService()
    svc.executor = S(checkpoint_flat=Mock())
    svc._fee_recovery = S(request_stop=Mock())
    svc._local_shutdown_settled = lambda: True
    svc._write_session_report = Mock()
    svc._log_activity = Mock()
    exited = Event()
    svc._shutdown_step = lambda: exited.set()
    async def observe():
        svc._account_state = 'flat_confirmed'
        svc._account_observed_at = 123
        svc._account_revision = 4
    svc._observe_account = observe
    async def run():
        release = asyncio.Event()
        svc._fee_recovery_task = asyncio.create_task(draining_task(release))
        await asyncio.sleep(0)
        stopping = asyncio.create_task(svc._shutdown_loop(svc._generation))
        try:
            assert await asyncio.to_thread(exited.wait, 1)
            assert not stopping.done()
            svc.executor.checkpoint_flat.assert_not_called()
            svc._fee_recovery.request_stop.assert_called_once()
        finally:
            release.set()
            await asyncio.wait_for(stopping, 1)
        svc.executor.checkpoint_flat.assert_called_once_with(123, 4)
        assert svc._phase == 'stopped' and svc._fee_recovery_task is None
    asyncio.run(run())
