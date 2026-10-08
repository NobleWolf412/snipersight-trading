"""Exact outcome arithmetic and immutable entry attribution, offline only."""
from dataclasses import replace
from decimal import Decimal as D
import json
import sqlite3
import pytest
from backend.bot.executor.accounting_models import AccountingError, Fee
from backend.bot.executor.execution_outcomes import calculate_outcome, receipt
from backend.bot.executor.execution_journal import ExecutionJournal, JournalError
from backend.tests.unit.test_accounting_models import initial
from backend.tests.unit.test_runtime_journal import runtime
from backend.tests.unit.test_accounting_runtime import executor
from backend.tests.unit.test_phemex_accounting import raw_order


def state(oid, side, qty, cost, fee='0'):
    return replace(initial(side),order_id=oid,exchange_order_id='remote-'+oid,requested_quantity=D(qty),
        status='FILLED',filled_quantity=D(qty),cost=D(cost) if cost is not None else None,
        cost_quantity=D(qty) if cost is not None else D(0),fees_complete=fee is not None,
        fees=(Fee('USDT',D(fee),'fixture'),) if fee is not None else ())


@pytest.mark.parametrize('side,exit_cost,net',[('BUY','1090','87.91'),('SELL','910','88.09')])
def test_actual_execution_cost_and_fees_define_outcome(side,exit_cost,net):
    entry=state('entry',side,'10','1000','1')
    close=state('exit','SELL' if side=='BUY' else 'BUY','10',exit_cost,str(D(exit_cost)*D('.001')))
    result=calculate_outcome(entry,(close,))
    assert result.complete and result.gross_pnl==90
    assert result.pnl_after_execution_fees==D(net)
    assert result.to_dict()['funding'] is None and not result.to_dict()['funding_allocated']


@pytest.mark.parametrize('fee',['0','-.5',None])
def test_zero_rebate_and_missing_fees_remain_distinct(fee):
    result=calculate_outcome(state('entry','BUY','10','1000',fee),(state('exit','SELL','10','1100','0'),))
    assert result.pnl_after_execution_fees == (None if fee is None else D(100)-D(fee))
    assert result.complete == (fee is not None)


def test_multiple_exits_use_weighted_actual_cost():
    result=calculate_outcome(state('entry','BUY','10','1000'),
        (state('tp','SELL','4','440'),state('exit','SELL','6','630')))
    assert result.complete and result.gross_pnl==70 and result.exit_cost==1070


@pytest.mark.parametrize('cost',[None,'1090'])
def test_receipt_quantity_survives_unknown_cost(cost):
    value=receipt(state('exit','SELL','10',cost,None))
    assert value.quantity==10 and value.terminal
    assert value.average_price == (None if cost is None else 109)
    assert value.fees is None


@pytest.mark.parametrize('change,reason',[
    ({'cost':None,'cost_quantity':D(0)},'EXECUTION_COST_UNAVAILABLE'),
    ({'status':'OPEN'},'ORDER_REMAINDER_UNRESOLVED'),
    ({'filled_quantity':D(9),'cost_quantity':D(9)},'EXIT_QUANTITY_MISMATCH'),
    ({'fees':(Fee('PT',D('1'),'fixture'),)},'FEE_CONVERSION_UNAVAILABLE'),
    ({'reasons':('VERIFIED_COST_CONFLICT',)},'VERIFIED_COST_CONFLICT'),
])
def test_incomplete_or_conflicting_evidence_never_becomes_complete(change,reason):
    result=calculate_outcome(state('entry','BUY','10','1000'),(replace(state('exit','SELL','10','1100'),**change),))
    assert reason in result.reasons and result.pnl_after_execution_fees is None


@pytest.mark.parametrize('change',[{'binding':'other'},{'side':'BUY'},{'environment':'production'}])
def test_cross_scope_or_direction_is_rejected(change):
    with pytest.raises(AccountingError):
        calculate_outcome(state('entry','BUY','10','1000'),(replace(state('exit','SELL','10','1100'),**change),))


def test_duplicate_and_overclosed_exit_never_double_count():
    entry=state('entry','BUY','10','1000'); close=state('exit','SELL','10','1100')
    with pytest.raises(AccountingError,match='DUPLICATE'):
        calculate_outcome(entry,(close,close))
    result=calculate_outcome(entry,(close,replace(close,order_id='second')))
    assert result.gross_pnl is None and 'EXIT_QUANTITY_MISMATCH' in result.reasons


def child_intent(runtime, **changes):
    parent,previous=runtime.records()[0]
    child=dict(parent,order_id='exit',side='SELL',purpose='exit',reduce_only=True,parent_entry_order_id='order',
               wire=dict(parent['wire'],side='sell',params={'clientOrderId':'exit'}))
    child.update(changes)
    state=dict(previous,status='PENDING',exchange_id=None,unknown_reason='awaiting')
    return child,state


def test_parent_identity_persists_across_reopen(runtime):
    child,legacy=child_intent(runtime)
    runtime.submit_intent(child,legacy)
    assert runtime.records()[1][0]['parent_entry_order_id']=='order'
    path=runtime.path
    runtime.close()
    reopened=ExecutionJournal(path,'fixture',runtime=True,environment='testnet')
    try:
        assert reopened.records()[1][0]['parent_entry_order_id']=='order'
    finally:
        reopened.close()


@pytest.mark.parametrize('changes',[{'parent_entry_order_id':'missing'},{'generation':'other'},{'owner':'other'},
                                 {'side':'BUY','wire':dict(symbol='BTC/USDT:USDT',side='buy',amount=10,params={'clientOrderId':'exit'})}])
def test_parent_missing_or_wrong_scope_blocks_durable_request(runtime,changes):
    intent,legacy=child_intent(runtime,**changes)
    with pytest.raises(JournalError,match='Parent'):
        runtime.submit_intent(intent,legacy)


def test_removed_parent_cannot_hide_from_replay(runtime):
    child,legacy=child_intent(runtime)
    runtime.submit_intent(child,legacy)
    path=runtime.path
    runtime.close()
    child.pop('parent_entry_order_id')
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE requests SET intent=? WHERE order_id=?',(json.dumps(child),'exit'))
    assert 'Parent entry evidence mismatch' in ExecutionJournal.inspect(path)['error']


@pytest.mark.parametrize('side', ['BUY','SELL'])
def test_real_executor_publishes_owned_outcome_and_restores_links(executor,side):
    ex,adapter=executor
    entry=ex.place_order('BTC/USDT:USDT',side,'LIMIT',10,price=110)
    raw=raw_order()
    raw.update(clOrdID=entry.order_id,side=side.title(),cumValueRv='1000',tradeType='Trade',
               execID='entry-fill',execQtyRq='10',execValueRv='1000',execFeeRv='1',currency='USDT')
    ex.apply_ws_order(raw)
    exit_side='SELL' if side=='BUY' else 'BUY'
    exit_cost='1090' if side=='BUY' else '910'
    def send(**wire):
        data=raw_order()
        data.update(orderID='exit-remote',clOrdID=wire['params']['clientOrderId'],side=exit_side.title(),
                    cumValueRv=exit_cost,tradeType='Trade',execID='exit-fill',execQtyRq='10',
                    execValueRv=exit_cost,execFeeRv=str(D(exit_cost)*D('.001')),currency='USDT')
        return {'id':'exit-remote','info':data}
    adapter.create_order.side_effect=send
    close=ex.place_order('BTC/USDT:USDT',exit_side,'MARKET',10,price=100,reduce_only=True,
                         parent_entry_order_id=entry.order_id)
    outcome=ex.execution_outcome(entry.order_id)
    assert outcome.complete and outcome.gross_pnl==90
    assert ex.execution_receipt(close.order_id).average_price == (109 if side=='BUY' else 91)
    path=ex._journal.path
    ex.close()
    from backend.bot.executor.live_executor import LiveExecutor
    fresh=LiveExecutor(adapter,journal=ExecutionJournal(path,'fixture',runtime=True,environment='testnet'))
    try:
        assert fresh.get_order(close.order_id).parent_entry_order_id==entry.order_id
        assert fresh.execution_outcome(entry.order_id)==outcome
        assert not fresh.get_trade_history() and fresh._positions=={}
    finally:
        fresh.close()
