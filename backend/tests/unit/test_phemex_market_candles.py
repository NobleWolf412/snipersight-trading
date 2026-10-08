"""Data source selection and failure behavior, with all transport replaced."""
from types import SimpleNamespace
from unittest.mock import Mock

import ccxt
import pytest

from backend.data.adapters.phemex import PhemexAdapter


def adapter():
    value=object.__new__(PhemexAdapter)
    value.default_type='swap'; value.testnet=False
    markets={
        'BTC/USDT': {'symbol':'BTC/USDT','type':'spot','spot':True},
        'BTC/USDT:USDT': {'symbol':'BTC/USDT:USDT','type':'swap','spot':False},
    }
    def candles(symbol, timeframe, **kwargs):
        price=100. if symbol=='BTC/USDT' else 110.
        return [[978307200000,price,price+2,price-2,price+1,10.]]
    value.exchange=SimpleNamespace(markets=markets,options={'defaultType':'swap'},
        load_markets=Mock(return_value=markets),fetch_ohlcv=Mock(side_effect=candles),
        fetch_ticker=Mock(side_effect=lambda symbol,**kwargs:{'last':100. if symbol=='BTC/USDT' else 110.}))
    return value


@pytest.mark.parametrize('requested,expected', [(None,'BTC/USDT:USDT'),('swap','BTC/USDT:USDT'),('spot','BTC/USDT')])
def test_plain_symbol_resolves_the_requested_market(requested, expected):
    value=adapter()
    frame=value.fetch_ohlcv('BTC/USDT','1h',market_type=requested,limit=5)
    assert value.exchange.fetch_ohlcv.call_args.args[0]==expected
    assert frame.close.iloc[0]==(101. if requested=='spot' else 111.)
    value.fetch_ticker('BTC/USDT',market_type=requested)
    assert value.exchange.fetch_ticker.call_args.args[0]==expected


@pytest.mark.parametrize('scenario', ['missing','ambiguous','qualified_conflict','bad_market_type'])
def test_unresolvable_source_rejects_before_price_transport(scenario):
    value=adapter();symbol='BTC/USDT';market_type='swap'
    if scenario=='missing':
        value.exchange.markets.pop('BTC/USDT:USDT')
    elif scenario=='ambiguous':
        value.exchange.markets['BTC/USDT:BTC']={'symbol':'BTC/USDT:BTC','type':'swap'}
    elif scenario=='qualified_conflict':
        symbol='BTC/USDT:USDT';market_type='spot'
    else:
        market_type='unknown'
    with pytest.raises(ValueError,match='MARKET_SOURCE_UNRESOLVED'):
        value.fetch_ohlcv(symbol,'1h',market_type=market_type)
    assert value.exchange.fetch_ohlcv.call_count==0


def test_failed_ccxt_fetch_cannot_publish_misparsed_direct_rest_candles(monkeypatch):
    import requests
    import backend.data.adapters.phemex as module
    value=adapter()
    value.exchange.fetch_ohlcv.side_effect=ccxt.ExchangeError('scripted unavailable')
    # Documented Phemex row: time, interval, previous close, open, high, low,
    # close, base volume, turnover. The retired path treated interval as open.
    direct=Mock(return_value=SimpleNamespace(json=lambda:{'code':0,'data':{'rows':[
        [978307200,3600,100.,101.,105.,99.,103.,20.,2060.]]}}))
    monkeypatch.setattr(requests,'get',direct)
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    value._derive_fallback_scale=lambda *args:1.
    with pytest.raises(ccxt.ExchangeError,match='scripted unavailable'):
        value.fetch_ohlcv('BTC/USDT:USDT','1h')
    assert direct.call_count==0


def test_transient_network_retry_stays_in_the_same_ccxt_source(monkeypatch):
    import backend.data.adapters.retry as retry
    monkeypatch.setattr(retry.time,'sleep',lambda _:None)
    value=adapter()
    value.exchange.fetch_ohlcv.side_effect=[ccxt.NetworkError('once'),[[978307200000,100,102,99,101,10]]]
    frame=value.fetch_ohlcv('BTC/USDT','1h')
    assert frame.close.iloc[0]==101
    assert value.exchange.fetch_ohlcv.call_count==2
    assert all(call.args[0]=='BTC/USDT:USDT' for call in value.exchange.fetch_ohlcv.call_args_list)


def test_market_configuration_keeps_transport_and_cache_identity_consistent():
    value=adapter()
    value.set_market_type('spot')
    assert value.default_type==value.exchange.options['defaultType']=='spot'
    value.set_market_type('swap')
    assert value.default_type==value.exchange.options['defaultType']=='swap'


@pytest.mark.parametrize('mode,price,amount,expected', [
    (ccxt.TICK_SIZE,1,1,{'tick_size':1.,'lot_size':1.}),
    (ccxt.TICK_SIZE,.5,.001,{'tick_size':.5,'lot_size':.001}),
    (ccxt.DECIMAL_PLACES,2,3,{'tick_size':.01,'lot_size':.001}),
])
def test_market_precision_uses_ccxt_mode_not_python_numeric_type(mode,price,amount,expected):
    value=adapter()
    market=value.exchange.markets['BTC/USDT:USDT']
    market['precision']={'price':price,'amount':amount}
    value.exchange.precisionMode=mode
    value.exchange.market=Mock(side_effect=value.exchange.markets.__getitem__)
    assert value.get_market_info('BTC/USDT')==expected
    assert value.exchange.market.call_args.args[0]=='BTC/USDT:USDT'


@pytest.mark.parametrize('mode,price', [(ccxt.SIGNIFICANT_DIGITS,3),(ccxt.TICK_SIZE,None),(ccxt.TICK_SIZE,float('nan'))])
def test_unusable_precision_does_not_claim_zero_constraints(mode,price):
    value=adapter()
    market=value.exchange.markets['BTC/USDT:USDT']
    market['precision']={'price':price,'amount':1}
    value.exchange.precisionMode=mode
    value.exchange.market=Mock(side_effect=value.exchange.markets.__getitem__)
    with pytest.raises(ValueError,match='MARKET_PRECISION_UNAVAILABLE'):
        value.get_market_info('BTC/USDT')


def test_scanner_propagates_precision_failure_to_a_rejection():
    import ast
    import inspect
    from datetime import datetime, timezone
    from backend.engine import orchestrator as module
    tree=ast.parse(inspect.getsource(module.Orchestrator))
    loop=next(n for n in ast.walk(tree) if isinstance(n,ast.For)
              and isinstance(n.target,ast.Name) and n.target.id=='sym'
              and any(isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute)
                      and call.func.attr=='get_market_info' for call in ast.walk(n)))
    timestamp=datetime(2001,1,1,tzinfo=timezone.utc)
    engine=SimpleNamespace(exchange_adapter=SimpleNamespace(get_market_info=Mock(side_effect=ValueError('missing precision'))),
                           config=object(),macro_context=None,current_regime=None,scanner_mode=None)
    ns=dict(module.__dict__,self=engine,symbols=['BTC/USDT'],run_id='precision',timestamp=timestamp,prefetched_data={},worker_args=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[loop],type_ignores=[])),'production-worker-inputs','exec'),ns)
    assert ns['worker_args'][0][-2:]==(None,None)
    result,rejection=module.Orchestrator._process_symbol(object.__new__(module.Orchestrator),
        'BTC/USDT','precision',timestamp,tick_size=None,lot_size=None)
    assert result is None and rejection['reason_type']=='market_precision_unavailable'
