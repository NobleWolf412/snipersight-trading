"""Reconcile early native fills before publishing manager exposure."""
import asyncio
from types import SimpleNamespace as S
from unittest.mock import AsyncMock
import pytest
from backend.tests.unit.test_accounting_runtime import executor
from backend.tests.unit.test_native_stop_reconciliation import native_stop
from backend.bot.paper_trading_service import PaperTradingService
from backend.bot.live_trading_service import LiveTradingService
from backend.bot.executor.position_manager import PositionStatus


@pytest.mark.parametrize('service',[LiveTradingService,PaperTradingService])
@pytest.mark.parametrize('direction',['LONG','SHORT'])
@pytest.mark.parametrize('filled',[3,10])
def test_pre_adoption_native_fill_publishes_only_verified_remaining_exposure(executor,service,direction,filled):
    paper,old,stop,rows,actual,_=native_stop(executor,direction)
    svc=paper if service is PaperTradingService else LiveTradingService()
    svc.executor=paper.executor;svc.position_manager=paper.position_manager
    seen=[]
    class Published(dict):
        def __setitem__(self,key,pos):
            seen.append((pos.remaining_quantity,pos.realized_pnl,pos.status))
            super().__setitem__(key,pos)
    svc.position_manager.positions=Published()
    svc._place_exchange_stop=AsyncMock()
    plan=S(symbol=old.symbol,direction=direction,trade_type='intraday',targets=[],stop_loss=S(level=old.stop_loss))
    svc._pending_plans[old.entry_order_id]=plan
    if filled==10:
        rows['exit-0'].update(cumQtyRq='10',cumValueRv=str(actual*10),ordStatus='Filled')
    for _ in range(2):
        if service is PaperTradingService:
            asyncio.run(svc._monitor_testnet_entries())
        else:
            asyncio.run(svc._open_filled_entry(old.entry_order_id,plan,100,10))
    assert seen==[(10-filled,filled*4,PositionStatus.CLOSED if filled==10 else PositionStatus.PARTIAL)]
    assert old.entry_order_id not in svc._pending_plans
    assert svc.stats.signals_taken==1
    assert executor[1].create_order.call_count==1  # original protector only
    svc._place_exchange_stop.assert_not_awaited()


@pytest.mark.parametrize('service',[LiveTradingService,PaperTradingService])
def test_unpriced_early_native_exit_retains_plan_without_publication(executor,service):
    from dataclasses import replace
    paper,old,_,_,_,_=native_stop(executor,'LONG')
    svc=paper if service is PaperTradingService else LiveTradingService()
    svc.executor=paper.executor;svc.position_manager=paper.position_manager
    svc.position_manager.positions.clear()
    plan=S(symbol=old.symbol,direction='LONG',trade_type='intraday',targets=[],stop_loss=S(level=old.stop_loss))
    svc._pending_plans[old.entry_order_id]=plan
    original=svc.executor.execution_progress
    svc.executor.execution_progress=lambda oid:replace(original(oid),realized_gross=None,reasons=('EXECUTION_COST_UNAVAILABLE',))
    if service is PaperTradingService:
        asyncio.run(svc._monitor_testnet_entries())
    else:
        asyncio.run(svc._open_filled_entry(old.entry_order_id,plan,100,10))
    assert not svc.position_manager.positions and old.entry_order_id in svc._pending_plans


def protection_fixture(executor,direction):
    from copy import deepcopy
    from unittest.mock import Mock
    from backend.tests.unit.test_reduction_recovery import partial_market
    from backend.tests.unit.test_phemex_accounting import raw_order
    from backend.tests.unit.test_accounting_runtime import observation
    import time
    entry,_,_=partial_market(executor,direction)
    ex,adapter=executor;rows={};actions=[]
    def submit(**wire):
        oid='protection-'+str(len(rows));filled=0 if 'stopPrice' in wire['params'] else wire['amount']
        row=raw_order();row.update(orderID=oid,clOrdID=wire['params']['clientOrderId'],
            side=wire['side'].title(),orderQtyRq=str(wire['amount']),cumQtyRq=str(filled),cumValueRv=str(filled*100),
            ordStatus='New' if not filled else 'Filled')
        rows[oid]=row;actions.append(('submit',oid,wire['amount']))
        return {'id':oid,'info':deepcopy(row)}
    def read(oid,*args):return {'id':oid,'info':deepcopy(rows[oid])}
    def cancel(oid,*args):
        actions.append(('cancel',oid));rows[oid]['ordStatus']='Canceled'
        return dict(read(oid),status='canceled')
    def account():
        now=time.monotonic();remaining=10-sum(float(row['cumQtyRq']) for row in rows.values())
        return observation(str(int(remaining)),side='Buy' if direction=='LONG' else 'Sell',started=now,ended=now)
    adapter.create_order.side_effect=submit;adapter.fetch_order=Mock(side_effect=read)
    adapter.cancel_order=Mock(side_effect=cancel);adapter.fetch_account_observation.side_effect=account
    ex.reconcile_account(force=True)
    return entry,rows,actions


@pytest.mark.parametrize('direction',['LONG','SHORT'])
@pytest.mark.parametrize('change',['size','level'])
def test_confirmed_entry_protection_replaces_changed_request_before_cancel(executor,direction,change):
    entry,rows,actions=protection_fixture(executor,direction)
    ex,adapter=executor;level=99 if direction=='LONG' else 101
    old=ex.protect_confirmed_entry(entry.order_id,level)
    desired=10
    if change=='size':
        ex.place_order(entry.symbol,'SELL' if direction=='LONG' else 'BUY','MARKET',4,price=100,
                       reduce_only=True,parent_entry_order_id=entry.order_id)
        desired=6
    else:
        level=100
    ex.reconcile_account(force=True);actions.clear()
    new=ex.protect_confirmed_entry(entry.order_id,level,quantity=desired)
    assert new.order_id!=old.order_id and new.quantity==desired and new.stop_price==level
    assert [a[0] for a in actions]==['submit','cancel']
    assert ex._entry_protection[entry.order_id]==new.order_id
    ex.reconcile_account(force=True)
    assert ex.protect_confirmed_entry(entry.order_id,level,quantity=desired).order_id==new.order_id
    assert len(actions)==2


@pytest.mark.parametrize('failure',['rejected','unknown'])
def test_replacement_failure_preserves_old_and_unknown_identity(executor,failure):
    from unittest.mock import Mock
    import ccxt
    entry,_,actions=protection_fixture(executor,'LONG')
    ex,adapter=executor
    old=ex.protect_confirmed_entry(entry.order_id,99)
    ex.reconcile_account(force=True)
    adapter.create_order.side_effect=ccxt.InvalidOrder('fixture') if failure=='rejected' else TimeoutError('fixture')
    new=ex.protect_confirmed_entry(entry.order_id,100,quantity=10)
    assert ex._entry_protection[entry.order_id]==old.order_id
    adapter.cancel_order.assert_not_called()
    if failure=='unknown':
        assert ex._pending_entry_protection[entry.order_id]==new.order_id
        count=adapter.create_order.call_count
        adapter.fetch_order_by_client_id=Mock(side_effect=TimeoutError('history lag'))
        # Unpriced/native admission uses original quantity; it still cannot duplicate.
        assert ex.protect_confirmed_entry(entry.order_id,100).order_id==new.order_id
        assert adapter.create_order.call_count==count


def test_rejected_testnet_replacement_keeps_software_risk_management_active(executor):
    import ccxt
    from backend.bot.executor.position_manager import PositionManager
    from backend.tests.unit.test_exit_receipts import position
    entry,_,_=protection_fixture(executor,'LONG')
    ex,adapter=executor
    old=ex.protect_confirmed_entry(entry.order_id,99)
    svc=PaperTradingService();svc.executor=ex
    svc.position_manager=PositionManager(price_fetcher=lambda _:100,receipt_execution=True)
    pos=position('LONG');pos.entry_order_id=entry.order_id;pos.stop_loss=100
    svc.position_manager.positions[pos.position_id]=pos
    adapter.create_order.side_effect=ccxt.InvalidOrder('rejected replacement')
    assert not asyncio.run(svc._reconcile_testnet_positions(force=True))
    assert not pos.exchange_close_pending and pos.remaining_quantity==10
    assert ex._entry_protection[entry.order_id]==old.order_id
    adapter.cancel_order.assert_not_called()


def test_flat_cleanup_retries_superseded_protector_after_unknown_cancellation(executor):
    entry,_,_=protection_fixture(executor,'LONG')
    ex,adapter=executor
    old=ex.protect_confirmed_entry(entry.order_id,99)
    ex.reconcile_account(force=True)
    cancel=adapter.cancel_order.side_effect
    adapter.cancel_order.side_effect=TimeoutError('cancellation unavailable')
    new=ex.protect_confirmed_entry(entry.order_id,100,quantity=10)
    assert ex._entry_protection[entry.order_id]==new.order_id
    ex.place_order(entry.symbol,'SELL','MARKET',10,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    adapter.cancel_order.side_effect=cancel;adapter.cancel_order.reset_mock()
    ex.cleanup_flat_protection()
    assert {call.args[0] for call in adapter.cancel_order.call_args_list}=={
        ex._exchange_order_map[old.order_id],ex._exchange_order_map[new.order_id]}
    before=adapter.cancel_order.call_count
    ex.cleanup_flat_protection()
    assert adapter.cancel_order.call_count==before
