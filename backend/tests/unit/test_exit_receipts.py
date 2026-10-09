"""Financial exit prices must come from confirmed fills, not management quotes."""
import asyncio
import ast
import inspect
import textwrap
from types import SimpleNamespace as S
from decimal import Decimal as D
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
import pytest
from backend.bot.executor.execution_outcomes import ExecutionReceipt
from backend.bot.executor.position_manager import PositionManager, PositionState, PositionStatus
from backend.shared.models.planner import Target
from backend.bot.paper_trading_service import PaperTradingService
from backend.bot.live_trading_service import LiveTradingService
from backend.tests.unit.test_accounting_runtime import executor
from backend.tests.unit.test_phemex_accounting import raw_order


def received(quantity=10, price=96, reasons=(), terminal=True):
    return ExecutionReceipt('exit', D(quantity), None if price is None else D(quantity)*D(price),
                            None, terminal, reasons)


def position(direction, targets=None):
    return PositionState('position','BTC/USDT:USDT',direction,100,10,10,
                         99 if direction=='LONG' else 101, targets or [], entry_order_id='entry')


def monitor(manager, pos):
    manager.positions[pos.position_id]=pos
    with patch('backend.bot.telemetry.logger.get_telemetry_logger',return_value=Mock()):
        asyncio.run(manager._monitor_position(pos))


@pytest.mark.parametrize('direction', ['LONG','SHORT'])
def test_stop_uses_actual_fill_without_another_slippage_model(direction):
    quote, actual=(98,96) if direction=='LONG' else (102,104)
    callback=AsyncMock(return_value=received(price=actual))
    mgr=PositionManager(price_fetcher=lambda _:quote,order_executor=callback)
    pos=position(direction)
    monitor(mgr,pos)
    assert pos.status==PositionStatus.STOPPED_OUT
    assert pos.exit_price==actual and pos.total_pnl==-40
    assert callback.call_args.kwargs['entry_order_id']=='entry'


@pytest.mark.parametrize('direction', ['LONG','SHORT'])
@pytest.mark.parametrize('result', [received(price=None),received(quantity=4),
                                  received(reasons=('CONFLICT',)),received(terminal=False)])
def test_incomplete_receipt_cannot_settle_position(direction,result):
    mgr=PositionManager(price_fetcher=lambda _:98 if direction=='LONG' else 102,
                        order_executor=AsyncMock(return_value=result))
    pos=position(direction)
    monitor(mgr,pos)
    assert pos.status==PositionStatus.OPEN and pos.remaining_quantity==10
    assert pos.realized_pnl==0 and pos.exit_price is None


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_partial_target_books_only_filled_slice_at_actual_cost(direction):
    quote,actual=(105,104) if direction=='LONG' else (95,96)
    targets=[Target(level=quote,percentage=40,rationale='fixture'),
             Target(level=110 if direction=='LONG' else 90,percentage=60,rationale='fixture')]
    mgr=PositionManager(price_fetcher=lambda _:quote,order_executor=AsyncMock(return_value=received(4,actual)))
    pos=position(direction,targets)
    monitor(mgr,pos)
    assert pos.status==PositionStatus.PARTIAL and pos.remaining_quantity==6
    assert pos.realized_pnl==16 and pos.unrealized_pnl==30


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_last_target_does_not_erase_unfilled_remaining_exposure(direction):
    quote,actual=(105,104) if direction=='LONG' else (95,96)
    pos=position(direction,[Target(level=quote,percentage=40,rationale='last remaining target')])
    mgr=PositionManager(price_fetcher=lambda _:quote,order_executor=AsyncMock(return_value=received(4,actual)))
    monitor(mgr,pos)
    assert not pos.targets and pos.status==PositionStatus.PARTIAL
    assert pos.remaining_quantity==6 and pos.realized_pnl==16


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_max_age_exit_uses_receipt(direction):
    actual=101 if direction=='LONG' else 99
    mgr=PositionManager(price_fetcher=lambda _:100,order_executor=AsyncMock(return_value=received(price=actual)),max_hours_open=1)
    pos=position(direction)
    pos.created_at=datetime.now(timezone.utc)-timedelta(hours=2)
    monitor(mgr,pos)
    assert pos.status==PositionStatus.CLOSED and pos.exit_price==actual
    assert pos.total_pnl==10


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_direction_flip_cannot_close_or_advance_after_failed_exit(direction):
    # Execute the actual signal-method prefix through the active-position branch.
    # The rest of signal selection is deliberately outside this offline probe.
    method=PaperTradingService._process_signal
    node=ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]
    boundary=next(i for i,n in enumerate(node.body) if isinstance(n,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=='_old_placed_at' for t in n.targets))
    node.body=node.body[:boundary]+[ast.Return(value=ast.Constant(True))]
    module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]))
    ns=dict(method.__globals__)
    exec(compile(module,'<actual-signal-prefix>','exec'),ns)
    svc=PaperTradingService()
    svc.config=S(max_positions=3, sniper_mode='stealth')
    svc.executor=S(_accounting=True)
    svc.position_manager=PositionManager(price_fetcher=lambda _:100)
    pos=position(direction)
    svc.position_manager.positions[pos.position_id]=pos
    svc._execute_exit_order=AsyncMock(return_value=False)
    svc._fetch_price=AsyncMock(return_value=100)
    svc._get_active_positions=lambda:[pos]
    svc._has_position=lambda _:True
    plan=S(symbol=pos.symbol,direction='SHORT' if direction=='LONG' else 'LONG',confidence_score=80)
    advanced=asyncio.run(ns['_process_signal'](svc,plan))
    assert not advanced
    assert pos.status==PositionStatus.OPEN and pos.remaining_quantity==10


@pytest.mark.parametrize('direction',['LONG','SHORT'])
@pytest.mark.parametrize('running_loop',[False,True])
def test_emergency_close_waits_and_retains_unconfirmed_position(direction,running_loop):
    callback=AsyncMock(return_value=False)
    mgr=PositionManager(price_fetcher=lambda _:100,order_executor=callback)
    pos=position(direction)
    mgr.positions[pos.position_id]=pos
    if running_loop:
        async def run():
            task=mgr.emergency_close_all()
            assert pos.remaining_quantity==10
            if task is not None:
                await task
        asyncio.run(run())
    else:
        mgr.emergency_close_all()
    assert pos.status==PositionStatus.OPEN and pos.remaining_quantity==10
    callback.assert_awaited_once()


@pytest.mark.parametrize('service',[LiveTradingService,PaperTradingService])
@pytest.mark.parametrize('side',['BUY','SELL'])
def test_services_preserve_parent_and_unknown_cost_order_until_receipt(executor,service,side):
    ex,adapter=executor
    entry=ex.place_order('BTC/USDT:USDT',side,'LIMIT',10,price=110)
    row=raw_order(); row.update(clOrdID=entry.order_id,side=side.title(),cumValueRv='1000')
    ex.apply_ws_order(row)
    adapter.create_order.reset_mock()
    close_side='SELL' if side=='BUY' else 'BUY'
    raw={}
    def submit(**wire):
        raw.update(raw_order()); raw.update(orderID='exit-remote',clOrdID=wire['params']['clientOrderId'],side=close_side.title())
        raw.pop('cumValueRv')
        return {'id':'exit-remote','info':dict(raw)}
    adapter.create_order.side_effect=submit
    adapter.fetch_order=Mock(side_effect=lambda *a:{'id':'exit-remote','info':dict(raw)})
    svc=service(); svc.executor=ex
    async def exit_once():
        return await svc._execute_exit_order(entry.symbol,close_side,10,100,entry_order_id=entry.order_id)
    assert not asyncio.run(exit_once())
    pending=svc._pending_exit_orders if service is LiveTradingService else svc._pending_testnet_exits
    oid=pending[entry.symbol]
    assert ex.get_order(oid).parent_entry_order_id==entry.order_id
    assert not asyncio.run(exit_once())
    raw['cumValueRv']='960' if side=='BUY' else '1040'
    result=asyncio.run(exit_once())
    assert isinstance(result,ExecutionReceipt) and result.order_id==oid
    assert result.average_price==(96 if side=='BUY' else 104)
    adapter.create_order.assert_called_once()
    assert entry.symbol not in pending


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_native_absence_needs_owned_execution_and_does_not_invent_stop(direction):
    from backend.tests.unit.test_execution_outcomes import state
    from backend.bot.executor.execution_outcomes import calculate_outcome
    side='BUY' if direction=='LONG' else 'SELL'
    cost='960' if side=='BUY' else '1040'
    entry=state('entry',side,'10','1000')
    close=state('exit','SELL' if side=='BUY' else 'BUY','10',cost)
    result=calculate_outcome(entry,())
    svc=LiveTradingService()
    callback=AsyncMock(return_value=True)
    svc.position_manager=PositionManager(price_fetcher=lambda _:100,order_executor=callback)
    pos=position(direction)
    svc.position_manager.positions[pos.position_id]=pos
    svc.executor=S(_accounting=True,execution_outcome=lambda _:result,execution_receipt=lambda _:received(price=100))
    svc._exchange_stop_levels[pos.position_id]=pos.stop_loss
    asyncio.run(svc._detect_exchange_closed_positions(set()))
    assert pos.status==PositionStatus.OPEN and pos.exchange_close_pending
    assert pos.exit_price is None and pos.realized_pnl==0
    monitor(svc.position_manager,pos)
    callback.assert_not_awaited()
    result=calculate_outcome(entry,(close,))
    asyncio.run(svc._detect_exchange_closed_positions(set()))
    assert pos.status==PositionStatus.CLOSED and not pos.exchange_close_pending
    assert pos.exit_reason=='exchange_exit' and pos.total_pnl==-40
    assert pos.exit_price==(96 if side=='BUY' else 104)


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_unreconciled_native_partial_cannot_send_another_software_target(direction):
    svc=LiveTradingService()
    callback=AsyncMock(return_value=True)
    svc.position_manager=PositionManager(price_fetcher=lambda _:105 if direction=='LONG' else 95,order_executor=callback)
    pos=position(direction)
    svc.position_manager.positions[pos.position_id]=pos
    svc.executor=S(_accounting=True,get_position=lambda _:6 if direction=='LONG' else -6)
    asyncio.run(svc._detect_exchange_closed_positions({pos.symbol}))
    assert pos.exchange_close_pending
    monitor(svc.position_manager,pos)
    callback.assert_not_awaited()
    assert pos.remaining_quantity==10
