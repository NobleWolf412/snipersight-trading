"""Cancelled partial exits retain identity and submit only a proven remainder."""
import asyncio
from copy import deepcopy
from decimal import Decimal as D
import time
from unittest.mock import Mock
import pytest
from backend.bot.live_trading_service import LiveTradingService
from backend.bot.paper_trading_service import PaperTradingService
from backend.bot.executor.execution_outcomes import ExecutionReceipt, reduction_receipt
from backend.bot.executor.accounting_models import AccountingError
from backend.tests.unit.test_accounting_runtime import executor, observation
from backend.tests.unit.test_phemex_accounting import raw_order


def partial_market(executor, direction='LONG', goal=10, initial_status='Canceled'):
    ex, adapter = executor
    side = 'BUY' if direction == 'LONG' else 'SELL'
    entry = ex.place_order('BTC/USDT:USDT', side, 'LIMIT', 10, price=110)
    row = raw_order(); row.update(clOrdID=entry.order_id, side=side.title(), cumValueRv='1000')
    ex.apply_ws_order(row)
    rows = {}
    actual = 104 if direction == 'LONG' else 96
    def submit(**wire):
        remote = 'exit-' + str(len(rows))
        filled = 3 if not rows else wire['amount']
        row = raw_order()
        row.update(orderID=remote, clOrdID=wire['params']['clientOrderId'], side=wire['side'].title(),
                   orderQtyRq=str(wire['amount']), cumQtyRq=str(filled), cumValueRv=str(filled*actual),
                   ordStatus=initial_status if not rows else 'Filled')
        rows[remote] = row
        return {'id':remote, 'info':deepcopy(row)}
    adapter.create_order.reset_mock(); adapter.create_order.side_effect=submit
    adapter.fetch_order=Mock(side_effect=lambda oid,*args: {'id':oid,'info':deepcopy(rows[oid])})
    def account_read():
        now = time.monotonic()
        remaining = D(10)-sum(D(r['cumQtyRq']) for r in rows.values())
        return observation(str(remaining), side=side.title(), started=now, ended=now)
    adapter.fetch_account_observation.side_effect=account_read
    return entry, rows, actual


@pytest.mark.parametrize('service',[LiveTradingService,PaperTradingService])
@pytest.mark.parametrize('direction',['LONG','SHORT'])
@pytest.mark.parametrize('goal',[4,10])
def test_terminal_partial_market_finishes_only_remainder(executor,service,direction,goal):
    entry,rows,actual=partial_market(executor,direction,goal)
    ex,adapter=executor
    svc=service(); svc.executor=ex
    result=asyncio.run(svc._execute_exit_order(entry.symbol,'SELL' if direction=='LONG' else 'BUY',
                                             goal,100,entry_order_id=entry.order_id))
    assert isinstance(result,ExecutionReceipt) and result.confirms(goal)
    assert result.average_price==actual
    assert [c.kwargs['amount'] for c in adapter.create_order.call_args_list]==[goal,goal-3]
    root=ex.get_order(result.order_id)
    child=next(o for o in ex._orders.values() if o.reduction_root_order_id==root.order_id)
    assert child.parent_entry_order_id==entry.order_id
    assert ex.execution_outcome(entry.order_id).exit_quantity==D(goal)
    assert len(rows)==2


@pytest.mark.parametrize('status',['New','PartiallyFilled'])
def test_working_exit_is_never_replaced(executor,status):
    entry,rows,_=partial_market(executor,initial_status=status)
    ex,adapter=executor
    root=ex.place_order(entry.symbol,'SELL','MARKET',10,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    for _ in range(2):
        result=ex.advance_reduction(root.order_id,100)
        assert not result.confirms(10)
    assert adapter.create_order.call_count==1


@pytest.mark.parametrize('problem',['cost','account','rejected_child'])
def test_unproven_remainder_cannot_create_another_order(executor,problem):
    entry,rows,_=partial_market(executor)
    ex,adapter=executor
    original=adapter.create_order.side_effect
    def submit(**wire):
        result=original(**wire)
        if problem=='cost':
            rows[result['id']].pop('cumValueRv',None); result['info'].pop('cumValueRv',None)
        if problem=='rejected_child' and len(rows)>1:
            rows[result['id']].update(ordStatus='Rejected',cumQtyRq='0',cumValueRv='0')
            result['info']=deepcopy(rows[result['id']])
        return result
    adapter.create_order.side_effect=submit
    root=ex.place_order(entry.symbol,'SELL','MARKET',10,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    if problem=='account':
        def bad_account():
            now=time.monotonic()
            return observation('6',started=now,ended=now)
        adapter.fetch_account_observation.side_effect=bad_account
    for _ in range(2):
        try:
            result=ex.advance_reduction(root.order_id,100)
            assert not result.confirms(10)
        except AccountingError:
            pass
    assert adapter.create_order.call_count==(2 if problem=='rejected_child' else 1)


def test_group_receipt_uses_all_costs_and_cannot_hide_overfill():
    parts=(ExecutionReceipt('root',D(3),D(300),None,True,()),
           ExecutionReceipt('child',D(7),D(714),None,True,()))
    result=reduction_receipt('root',D(10),parts)
    assert result.confirms(10) and result.average_price==101.4 and result.fees is None
    assert 'REDUCTION_GOAL_EXCEEDED' in reduction_receipt('root',D(9),parts).reasons
    with pytest.raises(AccountingError):
        reduction_receipt('root',D(10),(parts[0],parts[0]))


@pytest.mark.parametrize('direction',['LONG','SHORT'])
@pytest.mark.parametrize('trigger',['stop','target'])
def test_pending_exit_survives_price_recross(direction,trigger):
    from unittest.mock import AsyncMock
    from backend.bot.executor.position_manager import PositionManager
    from backend.shared.models.planner import Target
    from backend.tests.unit.test_exit_receipts import position, received
    quote=[98 if direction=='LONG' else 102]
    targets=[]; quantity=10; actual=96 if direction=='LONG' else 104
    if trigger=='target':
        quote[0]=105 if direction=='LONG' else 95
        targets=[Target(level=quote[0],percentage=40,rationale='fixture')]
        quantity=4; actual=104 if direction=='LONG' else 96
    callback=AsyncMock(side_effect=[False,received(quantity,actual)])
    manager=PositionManager(price_fetcher=lambda _:quote[0],order_executor=callback,receipt_execution=True)
    pos=position(direction,targets); manager.positions[pos.position_id]=pos
    asyncio.run(manager._monitor_position(pos))
    assert pos.remaining_quantity==10 and callback.await_count==1
    quote[0]=100
    pos.exchange_close_pending=True  # account poll sees a partially filled original request
    asyncio.run(manager._monitor_position(pos))
    assert pos.remaining_quantity==10-quantity and callback.await_count==2
    assert pos.realized_pnl==(-40 if trigger=='stop' else 16)
    assert pos.pending_exit_reason is None and pos.pending_target is None


@pytest.mark.parametrize('service',[LiveTradingService,PaperTradingService])
def test_concurrent_service_callbacks_share_one_reduction(executor,service):
    entry,_,_=partial_market(executor)
    ex,adapter=executor
    svc=service();svc.executor=ex
    async def run():
        return await asyncio.gather(*(svc._execute_exit_order(entry.symbol,'SELL',10,100,
                                       entry_order_id=entry.order_id) for _ in range(2)))
    results=asyncio.run(run())
    assert sum(isinstance(r,ExecutionReceipt) for r in results)==1
    assert adapter.create_order.call_count==2


def test_unknown_child_is_recovered_by_same_identity_without_resending(executor):
    entry,rows,_=partial_market(executor)
    ex,adapter=executor
    root=ex.place_order(entry.symbol,'SELL','MARKET',10,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    submit=adapter.create_order.side_effect
    def timeout(**wire):
        submit(**wire)
        raise TimeoutError('lost acknowledgment')
    adapter.create_order.side_effect=timeout
    result=ex.advance_reduction(root.order_id,100)
    assert not result.confirms(10)
    adapter.fetch_order_by_client_id=Mock(side_effect=TimeoutError('history lag'))
    with pytest.raises(AccountingError,match='OUTCOME_UNKNOWN'):
        ex.advance_reduction(root.order_id,100)
    adapter.fetch_order_by_client_id.side_effect=lambda oid,*args: {'id':'exit-1','clientOrderId':oid,'info':deepcopy(rows['exit-1'])}
    assert ex.advance_reduction(root.order_id,100).confirms(10)
    assert adapter.create_order.call_count==2


def test_concurrent_advance_and_close_cannot_duplicate_or_release_owner(executor):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from backend.bot.executor.execution_journal import JournalError
    entry,_,_=partial_market(executor)
    ex,adapter=executor
    root=ex.place_order(entry.symbol,'SELL','MARKET',10,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    entered,release=Event(),Event()
    submit=adapter.create_order.side_effect
    def blocked(**wire):
        entered.set()
        assert release.wait(5)
        return submit(**wire)
    adapter.create_order.side_effect=blocked
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(ex.advance_reduction,root.order_id,100)
        try:
            assert entered.wait(5)
            with pytest.raises(AccountingError,match='INFLIGHT'):
                ex.advance_reduction(root.order_id,100)
            with pytest.raises(JournalError,match='ownership'):
                ex.close()
        finally:
            release.set()
        assert future.result(timeout=5).confirms(10)
    assert adapter.create_order.call_count==2


def test_links_and_total_receipt_restore_without_strategy_resume(executor):
    from backend.bot.executor.execution_journal import ExecutionJournal
    from backend.bot.executor.live_executor import LiveExecutor
    entry,_,_=partial_market(executor)
    ex,adapter=executor
    root=ex.place_order(entry.symbol,'SELL','MARKET',10,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    expected=ex.advance_reduction(root.order_id,100)
    path=ex._journal.path; ex.close()
    restored=LiveExecutor(adapter,journal=ExecutionJournal(path,'fixture',runtime=True,environment='testnet'))
    try:
        assert restored.reduction_receipt(root.order_id)==expected
        assert restored._recovery_only
        assert restored.advance_reduction(root.order_id,100)==expected
        assert adapter.create_order.call_count==2
    finally:
        restored.close()


@pytest.mark.parametrize('goal',['0','-1','NaN','Infinity'])
def test_invalid_logical_goal_fails_loudly(goal):
    with pytest.raises(AccountingError,match='GOAL_INVALID'):
        reduction_receipt('root',D(goal),())


def test_restarted_partial_root_cannot_start_a_new_remainder(executor):
    from backend.bot.executor.execution_journal import ExecutionJournal, JournalError
    from backend.bot.executor.live_executor import LiveExecutor
    entry,_,_=partial_market(executor)
    ex,adapter=executor
    root=ex.place_order(entry.symbol,'SELL','MARKET',10,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    path=ex._journal.path; ex.close()
    restored=LiveExecutor(adapter,journal=ExecutionJournal(path,'fixture',runtime=True,environment='testnet'))
    try:
        with pytest.raises((JournalError,AccountingError)):
            restored.advance_reduction(root.order_id,100)
        assert adapter.create_order.call_count==1
        assert restored.reduction_receipt(root.order_id).quantity==3
    finally:
        restored.close()


def test_persisted_child_cannot_be_relinked_without_original_evidence(executor):
    import json,sqlite3
    from backend.bot.executor.execution_journal import ExecutionJournal,JournalError
    entry,_,_=partial_market(executor)
    ex,_=executor
    root=ex.place_order(entry.symbol,'SELL','MARKET',10,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    ex.advance_reduction(root.order_id,100)
    child=next(o for o in ex._orders.values() if o.reduction_root_order_id)
    path=ex._journal.path;ex.close()
    with sqlite3.connect(path) as db:
        row=json.loads(db.execute('SELECT intent FROM requests WHERE order_id=?',(child.order_id,)).fetchone()[0])
        row.pop('reduction_root_order_id')
        db.execute('UPDATE requests SET intent=? WHERE order_id=?',(json.dumps(row),child.order_id))
    with pytest.raises(JournalError,match='Reduction root evidence mismatch'):
        ExecutionJournal(path,'fixture',runtime=True,environment='testnet')


@pytest.mark.parametrize('root_kind',['missing','entry','child'])
def test_invalid_reduction_link_never_reaches_transport(executor,root_kind):
    entry,_,_=partial_market(executor)
    ex,adapter=executor
    root=ex.place_order(entry.symbol,'SELL','MARKET',10,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    link='missing' if root_kind=='missing' else entry.order_id
    if root_kind=='child':
        ex.advance_reduction(root.order_id,100)
        link=next(o.order_id for o in ex._orders.values() if o.reduction_root_order_id)
    before=adapter.create_order.call_count
    ex.place_order(entry.symbol,'SELL','MARKET',1,price=100,reduce_only=True,
                   parent_entry_order_id=entry.order_id,reduction_root_order_id=link)
    assert adapter.create_order.call_count==before
    assert ex._journal_error


def test_late_root_evidence_during_account_read_cannot_overshoot_target(executor):
    entry,rows,_=partial_market(executor,goal=4)
    ex,adapter=executor
    root=ex.place_order(entry.symbol,'SELL','MARKET',4,price=100,reduce_only=True,parent_entry_order_id=entry.order_id)
    account_read=adapter.fetch_account_observation.side_effect
    def late_fill():
        rows['exit-0'].update(cumQtyRq='4',cumValueRv='416',ordStatus='Canceled')
        ex.apply_ws_order(deepcopy(rows['exit-0']))
        return account_read()
    adapter.fetch_account_observation.side_effect=late_fill
    with pytest.raises(AccountingError,match='EVIDENCE_CHANGED'):
        ex.advance_reduction(root.order_id,100)
    assert adapter.create_order.call_count==1
    result=ex.advance_reduction(root.order_id,100)
    assert not result.confirms(4) and 'TERMINAL_ORDER_CONFLICT' in result.reasons
    assert adapter.create_order.call_count==1


@pytest.mark.parametrize('service',[LiveTradingService,PaperTradingService])
@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_shutdown_finishes_pending_target_before_closing_the_rest(executor,service,direction):
    from unittest.mock import AsyncMock
    from backend.bot.executor.position_manager import PositionManager
    from backend.shared.models.planner import Target
    from backend.tests.unit.test_exit_receipts import position
    entry,rows,actual=partial_market(executor,direction,goal=4,initial_status='PartiallyFilled')
    ex,adapter=executor
    svc=service();svc.executor=ex;svc._sync_closed_positions=AsyncMock()
    quote=105 if direction=='LONG' else 95
    manager=PositionManager(price_fetcher=lambda _:quote,order_executor=svc._execute_exit_order,receipt_execution=True)
    pos=position(direction,[Target(level=quote,percentage=40,rationale='fixture')]);pos.entry_order_id=entry.order_id
    manager.positions[pos.position_id]=pos;svc.position_manager=manager
    asyncio.run(manager._monitor_position(pos))
    assert pos.pending_target and pos.remaining_quantity==10
    rows['exit-0']['ordStatus']='Canceled'
    asyncio.run(svc._close_all_positions('STOP'))
    assert pos.remaining_quantity==0 and pos.realized_pnl==40
    assert [c.kwargs['amount'] for c in adapter.create_order.call_args_list]==[4,1,6]


@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_emergency_finishes_pending_target_then_closes_the_rest(direction):
    from unittest.mock import AsyncMock
    from backend.bot.executor.position_manager import PositionManager
    from backend.shared.models.planner import Target
    from backend.tests.unit.test_exit_receipts import position,received
    level=105 if direction=='LONG' else 95
    callback=AsyncMock(side_effect=[False,received(4,104 if direction=='LONG' else 96),
                                         received(6,104 if direction=='LONG' else 96)])
    manager=PositionManager(price_fetcher=lambda _:level,order_executor=callback,receipt_execution=True)
    pos=position(direction,[Target(level=level,percentage=40,rationale='fixture')]);manager.positions[pos.position_id]=pos
    asyncio.run(manager._monitor_position(pos))
    manager.emergency_close_all()
    assert pos.remaining_quantity==0 and pos.realized_pnl==40
    assert [call.kwargs['quantity'] for call in callback.call_args_list]==[4,4,6]
