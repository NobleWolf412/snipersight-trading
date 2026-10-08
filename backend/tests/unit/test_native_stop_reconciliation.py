"""Adopted native stops reconcile from identified fills, never a price touch."""
import asyncio
from copy import deepcopy
from unittest.mock import Mock, AsyncMock
import pytest
from backend.tests.unit.test_reduction_recovery import partial_market
from backend.tests.unit.test_accounting_runtime import executor
from backend.tests.unit.test_exit_receipts import position
from backend.bot.paper_trading_service import PaperTradingService
from backend.bot.live_trading_service import LiveTradingService
from backend.bot.executor.paper_executor import OrderStatus, OrderType, OrderSide, Order
from backend.bot.executor.position_manager import PositionManager, PositionStatus


def native_stop(executor,direction,status='PartiallyFilled'):
    entry,rows,actual=partial_market(executor,direction,initial_status=status)
    ex,adapter=executor
    stop=ex.place_stop_order(entry.symbol,'SELL' if direction=='LONG' else 'BUY',10,
                            99 if direction=='LONG' else 101,parent_entry_order_id=entry.order_id)
    ex._entry_protection[entry.order_id]=stop.order_id
    svc=PaperTradingService();svc.executor=ex
    callback=AsyncMock(return_value=False)
    svc.position_manager=PositionManager(price_fetcher=lambda _:100,order_executor=callback,receipt_execution=True)
    pos=position(direction);pos.entry_order_id=entry.order_id
    svc.position_manager.positions[pos.position_id]=pos
    return svc,pos,stop,rows,actual,callback


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_adopted_native_stop_partial_then_full_is_reconciled_once(executor,direction):
    svc,pos,stop,rows,actual,callback=native_stop(executor,direction)
    assert asyncio.run(svc._reconcile_testnet_positions(force=True))
    assert pos.remaining_quantity==7 and pos.realized_pnl==12 and pos.exchange_close_pending
    asyncio.run(svc.position_manager._monitor_position(pos));callback.assert_not_awaited()
    rows['exit-0'].update(cumQtyRq='10',cumValueRv=str(actual*10),ordStatus='Filled')
    assert asyncio.run(svc._reconcile_testnet_positions(force=True))
    assert asyncio.run(svc._reconcile_testnet_positions(force=True))
    assert pos.remaining_quantity==0 and pos.realized_pnl==40 and pos.exit_price==actual
    assert pos.status==PositionStatus.CLOSED


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_cancelled_native_partial_keeps_remaining_exit_intent(executor,direction):
    svc,pos,_,_,_,callback=native_stop(executor,direction,status='Canceled')
    assert asyncio.run(svc._reconcile_testnet_positions(force=True))
    assert pos.remaining_quantity==7 and pos.pending_exit_reason=='NATIVE_STOP'
    asyncio.run(svc.position_manager._monitor_position(pos))
    callback.assert_awaited_once()
    assert callback.call_args.kwargs['quantity']==7


@pytest.mark.parametrize('problem',['cost','account'])
def test_native_stop_without_matching_evidence_cannot_settle(executor,problem):
    svc,pos,_,_,_,callback=native_stop(executor,'LONG')
    from dataclasses import replace
    if problem=='cost':
        original=svc.executor.execution_progress
        svc.executor.execution_progress=lambda oid:replace(original(oid),realized_gross=None,reasons=('EXECUTION_COST_UNAVAILABLE',))
    else:
        from backend.tests.unit.test_accounting_runtime import observation
        import time
        def mismatched():
            now=time.monotonic()
            return observation('6',started=now,ended=now)
        executor[1].fetch_account_observation.side_effect=mismatched
    assert not asyncio.run(svc._reconcile_testnet_positions(force=True))
    assert pos.remaining_quantity==10 and pos.realized_pnl==0 and pos.exchange_close_pending
    asyncio.run(svc.position_manager._monitor_position(pos));callback.assert_not_awaited()


@pytest.mark.parametrize('direction',['LONG','SHORT'])
@pytest.mark.parametrize('problem',['size','cancelled','unknown','triggered'])
def test_unchanged_stop_level_does_not_certify_wrong_or_dead_protection(direction,problem):
    from types import SimpleNamespace as S
    pos=position(direction)
    side=OrderSide.SELL if direction=='LONG' else OrderSide.BUY
    old=Order('old',pos.symbol,side,OrderType.STOP_LOSS,10,stop_price=pos.stop_loss,
              status=OrderStatus.OPEN,parent_entry_order_id=pos.entry_order_id)
    new=Order('new',pos.symbol,side,OrderType.STOP_LOSS,6,stop_price=pos.stop_loss,
              status=OrderStatus.OPEN,parent_entry_order_id=pos.entry_order_id)
    if problem=='cancelled':old.status=OrderStatus.CANCELLED
    if problem=='unknown':old.status=OrderStatus.PENDING
    if problem=='triggered':old.status=OrderStatus.PARTIALLY_FILLED;old.filled_quantity=3
    qty=6 if problem=='size' else 10;new.quantity=qty
    svc=LiveTradingService();svc.position_manager=PositionManager(price_fetcher=lambda _:100)
    svc.position_manager.positions[pos.position_id]=pos
    svc.executor=S(_accounting=True,get_order=lambda oid:old if oid=='old' else new,
                   refresh_order=Mock(),place_stop_order=Mock(return_value=new),cancel_order=Mock(return_value=True))
    svc._exchange_stop_orders[pos.position_id]='old';svc._exchange_stop_levels[pos.position_id]=pos.stop_loss
    result=svc._ensure_exchange_stop(pos.position_id,pos.symbol,direction,qty,pos.stop_loss)
    if problem in ('unknown','triggered'):
        assert not result
        svc.executor.place_stop_order.assert_not_called()
    else:
        assert result
        svc.executor.place_stop_order.assert_called_once()
        assert svc._exchange_stop_orders[pos.position_id]=='new'


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_live_native_stop_partial_then_full_uses_same_owned_progress(executor,direction):
    paper,pos,stop,rows,actual,_=native_stop(executor,direction)
    svc=LiveTradingService();svc.executor=paper.executor;svc.position_manager=paper.position_manager
    svc._exchange_stop_orders[pos.position_id]=stop.order_id
    svc._get_price=lambda _:100
    assert not asyncio.run(svc._detect_exchange_closed_positions({pos.symbol}))
    assert pos.remaining_quantity==7 and pos.realized_pnl==12 and pos.exchange_close_pending
    rows['exit-0'].update(cumQtyRq='10',cumValueRv=str(actual*10),ordStatus='Filled')
    assert asyncio.run(svc._detect_exchange_closed_positions(set()))
    assert pos.remaining_quantity==0 and pos.realized_pnl==40 and pos.exit_price==actual


@pytest.mark.parametrize('service',[LiveTradingService,PaperTradingService])
def test_software_pending_slice_is_not_also_booked_by_native_reconciliation(executor,service):
    paper,pos,stop,_,_,_=native_stop(executor,'LONG')
    svc=paper if service is PaperTradingService else LiveTradingService()
    svc.executor=paper.executor;svc.position_manager=paper.position_manager
    if service is PaperTradingService:
        svc._pending_testnet_exits={pos.symbol:'logical-market'}
        asyncio.run(svc._reconcile_testnet_positions(force=True))
    else:
        svc._pending_exit_orders={pos.symbol:'logical-market'}
        svc._exchange_stop_orders[pos.position_id]=stop.order_id
        asyncio.run(svc._detect_exchange_closed_positions({pos.symbol}))
    assert pos.remaining_quantity==10 and pos.realized_pnl==0


def test_testnet_monitor_reconciles_before_software_management(executor,monkeypatch):
    svc,pos,_,_,_,_=native_stop(executor,'LONG')
    svc._running=True;svc._refresh_price_cache=AsyncMock();svc._monitor_testnet_entries=AsyncMock()
    svc._sync_closed_positions=AsyncMock();seen=[]
    from datetime import datetime,timezone
    svc._last_drawdown_check=datetime.now(timezone.utc)
    async def monitor():seen.append(pos.remaining_quantity)
    async def stop(*args):svc._running=False
    svc.position_manager.monitor_all_positions=monitor
    monkeypatch.setattr('backend.bot.paper_trading_service.asyncio.sleep',stop)
    asyncio.run(svc._monitor_loop())
    assert seen==[7]


@pytest.mark.parametrize('cancelled',[True,False])
def test_late_replacement_ack_cannot_cancel_old_protection_with_wrong_size(cancelled):
    from types import SimpleNamespace as S
    pos=position('LONG');pos.remaining_quantity=6
    old=Order('old',pos.symbol,OrderSide.SELL,OrderType.STOP_LOSS,10,stop_price=98,
              status=OrderStatus.OPEN,parent_entry_order_id=pos.entry_order_id)
    pending=Order('pending',pos.symbol,OrderSide.SELL,OrderType.STOP_LOSS,10,stop_price=99,
                  status=OrderStatus.PENDING,parent_entry_order_id=pos.entry_order_id)
    def refresh(oid):
        if oid=='pending':pending.status=OrderStatus.OPEN
    svc=LiveTradingService();svc.position_manager=PositionManager(price_fetcher=lambda _:100)
    svc.position_manager.positions[pos.position_id]=pos
    svc.executor=S(_accounting=True,get_order=lambda oid:old if oid=='old' else pending,
                   refresh_order=Mock(side_effect=refresh),place_stop_order=Mock(),
                   cancel_order=Mock(return_value=cancelled))
    svc._exchange_stop_orders[pos.position_id]='old';svc._exchange_stop_levels[pos.position_id]=98
    svc._pending_stop_orders[pos.position_id]='pending'
    assert not svc._ensure_exchange_stop(pos.position_id,pos.symbol,'LONG',6,99)
    assert svc._exchange_stop_orders[pos.position_id]=='old'
    svc.executor.place_stop_order.assert_not_called()
    svc.executor.cancel_order.assert_called_once_with('pending')
    assert (pos.position_id in svc._pending_stop_orders)==(not cancelled)


def test_testnet_unknown_native_exit_prevents_a_new_market_request(executor):
    svc,pos,_,_,_,_=native_stop(executor,'LONG')
    pos.exchange_close_pending=True
    before=executor[1].create_order.call_count
    assert not asyncio.run(svc._execute_testnet_exit(pos.symbol,'SELL',10,100,pos.entry_order_id))
    assert executor[1].create_order.call_count==before
