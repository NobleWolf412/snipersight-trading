"""A venue-owned TP must not race a second software target reduction."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace as S
from unittest.mock import AsyncMock, Mock
import pytest
from backend.bot.live_trading_service import LiveTradingService
from backend.bot.executor.paper_executor import Order, OrderSide, OrderType, OrderStatus
from backend.bot.executor.position_manager import PositionManager
from backend.shared.models.planner import Target
from backend.tests.unit.test_exit_receipts import position, received
from backend.tests.unit.test_accounting_runtime import executor, observation
from backend.tests.unit.test_phemex_accounting import raw_order


def configured(direction,status):
    target_price=105 if direction=='LONG' else 95
    target=Target(level=target_price,percentage=40,rationale='TP1')
    pos=position(direction,[target])
    callback=AsyncMock(return_value=received(4,target_price))
    manager=PositionManager(price_fetcher=lambda _:target_price,order_executor=callback)
    manager.positions[pos.position_id]=pos
    svc=LiveTradingService();svc.position_manager=manager
    native=Order('native-target',pos.symbol,OrderSide.SELL if direction=='LONG' else OrderSide.BUY,
                 OrderType.LIMIT,4,price=target_price,status=status,parent_entry_order_id='entry')
    svc.executor=S(_accounting=True,place_take_profit_order=Mock(return_value=native),
                   place_trailing_stop_order=Mock(return_value=S(status=OrderStatus.REJECTED)))
    svc.adapter=S(get_market_info=lambda _: {})
    svc._ensure_exchange_stop=Mock(return_value=True)
    plan=S(symbol=pos.symbol,direction=direction,targets=[target],stop_loss=S(level=pos.stop_loss))
    return svc,pos,plan,callback


@pytest.mark.parametrize('direction',['LONG','SHORT'])
@pytest.mark.parametrize('status',[OrderStatus.OPEN,OrderStatus.PENDING,OrderStatus.PARTIALLY_FILLED,OrderStatus.FILLED])
def test_native_target_owns_slice_until_execution_reconciliation(direction,status):
    svc,pos,plan,callback=configured(direction,status)
    async def run():
        await svc._place_exchange_stop(pos.position_id,plan,100,10)
        await svc.position_manager._monitor_position(pos)
    asyncio.run(run())
    callback.assert_not_awaited()
    assert pos.remaining_quantity==10 and pos.targets and not pos.targets_hit


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_rejected_native_target_leaves_software_fallback_available(direction):
    svc,pos,plan,callback=configured(direction,OrderStatus.REJECTED)
    async def run():
        await svc._place_exchange_stop(pos.position_id,plan,100,10)
        await svc.position_manager._monitor_position(pos)
    asyncio.run(run())
    callback.assert_awaited_once()
    assert pos.remaining_quantity==6


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_native_profit_target_does_not_suppress_stop_exit(direction):
    svc,pos,plan,callback=configured(direction,OrderStatus.OPEN)
    callback.return_value=received(10,98 if direction=='LONG' else 102)
    svc.position_manager.price_fetcher=lambda _:98 if direction=='LONG' else 102
    async def run():
        await svc._place_exchange_stop(pos.position_id,plan,100,10)
        await svc.position_manager._monitor_position(pos)
    asyncio.run(run())
    callback.assert_awaited_once()
    assert pos.remaining_quantity==0


def real_partial(executor,direction):
    ex,adapter=executor
    side='BUY' if direction=='LONG' else 'SELL'
    entry=ex.place_order('BTC/USDT:USDT',side,'LIMIT',10,price=110)
    row=raw_order();row.update(clOrdID=entry.order_id,side=side.title(),cumValueRv='1000')
    ex.apply_ws_order(row)
    level=105 if direction=='LONG' else 95
    raw={}
    def submit(**wire):
        raw.update(raw_order());raw.update(orderID='native-remote',clOrdID=wire['params']['clientOrderId'],
            side='Sell' if direction=='LONG' else 'Buy',orderQtyRq='4',cumQtyRq='1',cumValueRv=str(level),ordStatus='PartiallyFilled')
        return {'id':'native-remote','info':deepcopy(raw)}
    adapter.create_order.side_effect=submit
    native=ex.place_order(entry.symbol,'SELL' if direction=='LONG' else 'BUY','LIMIT',4,price=level,
                          reduce_only=True,parent_entry_order_id=entry.order_id)
    adapter.fetch_order=Mock(side_effect=lambda *a:{'id':'native-remote','info':deepcopy(raw)})
    pos=position(direction,[Target(level=level,percentage=40,rationale='TP1')]);pos.entry_order_id=entry.order_id
    pos.native_target_order_id=native.order_id;pos.native_target_level=level;pos.native_target_quantity='4'
    svc=LiveTradingService();svc.executor=ex
    svc.position_manager=PositionManager(price_fetcher=lambda _:level,order_executor=AsyncMock(return_value=False))
    svc.position_manager.positions[pos.position_id]=pos
    svc._get_price=lambda _:level
    svc._exchange_tp_orders[pos.position_id]=native.order_id
    def account_read():
        import time
        now=time.monotonic()
        return observation(str(10-float(raw['cumQtyRq'])),side=side.title(),started=now,ended=now)
    adapter.fetch_account_observation.side_effect=account_read
    return svc,pos,raw,level


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_real_native_partial_then_complete_fill_updates_manager_once(executor,direction):
    svc,pos,raw,level=real_partial(executor,direction)
    assert asyncio.run(svc._detect_exchange_closed_positions({pos.symbol}))
    assert pos.remaining_quantity==9 and pos.realized_pnl==5 and pos.native_target_order_id
    raw.update(cumQtyRq='4',cumValueRv=str(level*4),ordStatus='Filled')
    assert asyncio.run(svc._detect_exchange_closed_positions({pos.symbol}))
    assert asyncio.run(svc._detect_exchange_closed_positions({pos.symbol}))
    assert pos.remaining_quantity==6 and pos.realized_pnl==20 and not pos.native_target_order_id
    assert len(pos.targets_hit)==1 and pos.position_id not in svc._exchange_tp_orders
    svc.position_manager.order_executor.assert_not_awaited()


@pytest.mark.parametrize('problem',['opposite','missing_cost'])
def test_unmatched_account_or_unpriced_native_fill_remains_pending(executor,problem):
    svc,pos,raw,_=real_partial(executor,'LONG')
    if problem=='opposite':
        def wrong_account():
            import time
            now=time.monotonic()
            return observation('9',side='Sell',started=now,ended=now)
        executor[1].fetch_account_observation.side_effect=wrong_account
    else:
        # Remove cost from all evidence for this test using a fresh source-only
        # projection fixture; actual reducer cost cannot regress from known to absent.
        from dataclasses import replace
        original=svc.executor.execution_progress
        svc.executor.execution_progress=lambda oid: replace(original(oid),realized_gross=None,reasons=('EXECUTION_COST_UNAVAILABLE',))
    assert not asyncio.run(svc._detect_exchange_closed_positions({pos.symbol}))
    assert pos.remaining_quantity==10 and pos.realized_pnl==0 and pos.exchange_close_pending
    assert not svc._exchange_state_known


def test_monitor_reconciles_native_slice_before_software_and_stop_sync(executor,monkeypatch):
    svc,pos,_,_=real_partial(executor,'LONG')
    svc._running=True;svc._startup_reconciled=True
    svc.config=S(balance_reconcile_interval=0,kill_switch_enabled=False)
    svc.executor._accounting.next_refresh=0  # fixture account cadence is due too
    svc._refresh_price_cache=AsyncMock();svc._monitor_pending_entries=AsyncMock()
    observed=[]
    async def monitor():
        observed.append(('monitor',pos.remaining_quantity))
    async def stops():
        observed.append(('stops',pos.remaining_quantity))
    svc.position_manager.monitor_all_positions=monitor
    svc._sync_exchange_stops=stops;svc._sync_closed_positions=AsyncMock()
    async def end_cycle(*args):
        svc._running=False
    monkeypatch.setattr('backend.bot.live_trading_service.asyncio.sleep',end_cycle)
    asyncio.run(svc._monitor_loop())
    assert observed==[('monitor',9),('stops',9)]
