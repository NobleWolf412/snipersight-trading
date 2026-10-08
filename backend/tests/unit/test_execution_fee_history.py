"""Documented raw execution-history contract and exact owned fee enrichment."""
from decimal import Decimal as D
from types import SimpleNamespace as S
from unittest.mock import Mock
import pytest
from backend.data.adapters.phemex import PhemexAdapter
from backend.data.adapters.phemex_accounting import normalize_execution
from backend.bot.executor.accounting_models import AccountingError
from backend.tests.unit.test_accounting_models import context
from backend.tests.unit.test_phemex_accounting import market, raw_order
from backend.tests.unit.test_accounting_runtime import executor


def trade(**changes):
    return dict(dict(symbol='BTCUSDT',currency='USDT',orderID='remote',clOrdID='',
        execID='fill',tradeType='Trade',side='Buy',execQtyRq='10',execValueRv='1000',
        execFeeRv='1',transactTimeNs=1500000000),**changes)


def adapter(response):
    ad=object.__new__(PhemexAdapter)
    ad.supports_trading=lambda:True
    ad.default_type='swap'
    ad.metrics=dict(rest_calls_total=0,fetch_my_trades_calls_total=0,fetch_my_trades_rows_total=0)
    ad.exchange=S(markets={'BTC/USDT:USDT':market()},privateGetApiDataGFuturesTrades=Mock(return_value=response))
    return ad


def test_documented_empty_client_id_retains_exchange_identity():
    evidence=normalize_execution(trade(),market(),context())
    assert evidence.client_order_id is None and evidence.exchange_order_id=='remote'
    assert evidence.fees[0].amount==1


def test_raw_symbol_reader_uses_explicit_window_and_preserves_strings():
    ad=adapter([trade()])
    result=ad.fetch_trade_execution_page('BTC/USDT:USDT',1000,2000,offset=0,limit=200)
    assert result==[trade()] and result[0]['execFeeRv']=='1'
    ad.exchange.privateGetApiDataGFuturesTrades.assert_called_once_with(
        {'symbol':'BTCUSDT','start':1000,'end':2000,'offset':0,'limit':200})


@pytest.mark.parametrize('response',[{}, {'code':0,'data':[]}, [None],
    [trade(symbol='ETHUSDT')],[trade(currency='USD')],[trade(execID='')],
    [trade(orderID='')],[trade(transactTimeNs=999000000)],[trade(side=1)]])
def test_raw_reader_rejects_missing_or_wrong_scope(response):
    with pytest.raises(ValueError):
        adapter(response).fetch_trade_execution_page('BTC/USDT:USDT',1000,2000)


@pytest.mark.parametrize('side',['BUY','SELL'])
@pytest.mark.parametrize('fee',['0','1','-0.1'])
def test_history_enriches_actual_fee_once_without_double_quantity_or_cash(executor,side,fee):
    ex,ad=executor
    order=ex.place_order('BTC/USDT:USDT',side,'LIMIT',10,price=110)
    raw=raw_order();raw.update(clOrdID=order.order_id,side=side.title(),cumValueRv='1000')
    ex.apply_ws_order(raw)
    cash=ex._cached_balance
    evidence=trade(orderID=raw['orderID'],side=side.title(),execFeeRv=fee)
    ex.import_execution_history(order.order_id,[evidence])
    ex.import_execution_history(order.order_id,[evidence])
    receipt=ex.execution_receipt(order.order_id)
    assert receipt.quantity==10 and receipt.cost==1000
    assert receipt.fees[0].amount==D(fee)
    assert order.filled_quantity==10 and ex._cached_balance==cash and ex._positions=={}


@pytest.mark.parametrize('change',[{'orderID':'foreign'},{'clOrdID':'foreign'},
                                  {'side':'Sell'},{'symbol':'ETHUSDT'}])
def test_explicit_order_import_rejects_unrelated_or_contradictory_evidence(executor,change):
    ex,_=executor
    order=ex.place_order('BTC/USDT:USDT','BUY','LIMIT',10,price=110)
    raw=raw_order();raw.update(clOrdID=order.order_id,cumValueRv='1000')
    ex.apply_ws_order(raw)
    evidence=trade(orderID=raw['orderID'],**change) if 'orderID' not in change else trade(**change)
    with pytest.raises(AccountingError):
        ex.import_execution_history(order.order_id,[evidence])
    assert ex.execution_receipt(order.order_id).fees is None


def test_unknown_fee_is_not_zero_and_late_fee_enriches_same_execution(executor):
    ex,_=executor
    order=ex.place_order('BTC/USDT:USDT','BUY','LIMIT',10,price=110)
    raw=raw_order();raw.update(clOrdID=order.order_id,cumValueRv='1000')
    ex.apply_ws_order(raw)
    evidence=trade(orderID=raw['orderID']);evidence.pop('execFeeRv')
    ex.import_execution_history(order.order_id,[evidence])
    assert ex.execution_receipt(order.order_id).fees is None
    evidence['execFeeRv']='0'
    ex.import_execution_history(order.order_id,[evidence])
    assert ex.execution_receipt(order.order_id).fees[0].amount==0


def test_conflicting_fee_invalidates_receipt_instead_of_overwriting(executor):
    ex,_=executor
    order=ex.place_order('BTC/USDT:USDT','BUY','LIMIT',10,price=110)
    raw=raw_order();raw.update(clOrdID=order.order_id,cumValueRv='1000')
    ex.apply_ws_order(raw)
    evidence=trade(orderID=raw['orderID'])
    ex.import_execution_history(order.order_id,[evidence])
    ex.import_execution_history(order.order_id,[dict(evidence,execFeeRv='2')])
    receipt=ex.execution_receipt(order.order_id)
    assert receipt.reasons and receipt.fees is None and not receipt.confirms(10)
    assert not ex.accounting_status()['entry_eligible']


def test_restart_fee_enrichment_does_not_emit_strategy_fill(executor):
    from backend.bot.executor.execution_journal import ExecutionJournal
    from backend.bot.executor.live_executor import LiveExecutor
    ex,ad=executor
    order=ex.place_order('BTC/USDT:USDT','BUY','LIMIT',10,price=110)
    raw=raw_order();raw.update(clOrdID=order.order_id,cumValueRv='1000')
    ex.apply_ws_order(raw)
    path=ex._journal.path
    ex.close()
    fresh=LiveExecutor(ad,journal=ExecutionJournal(path,'fixture',runtime=True,environment='testnet'))
    try:
        fresh.import_execution_history(order.order_id,[trade(orderID=raw['orderID'])])
        assert fresh.execution_receipt(order.order_id).fees[0].amount==1
        assert not fresh.get_trade_history() and fresh._positions=={}
    finally:
        fresh.close()


@pytest.mark.parametrize('arguments',[(True,2000,0,200),(2000,1000,0,200),(1000,2000,-1,200),(1000,2000,0,201)])
def test_bounds_fail_before_transport(arguments):
    ad=adapter([])
    with pytest.raises(ValueError):
        ad.fetch_trade_execution_page('BTC/USDT:USDT',*arguments)
    ad.exchange.privateGetApiDataGFuturesTrades.assert_not_called()


def test_history_alias_conflict_is_not_hidden_by_empty_client_id():
    with pytest.raises(AccountingError,match='ALIAS_CONFLICT'):
        normalize_execution(trade(clOrdId='different'),market(),context())
