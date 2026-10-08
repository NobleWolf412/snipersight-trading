"""Public candles cannot cross venue/environment/market or requested-depth boundaries."""
import asyncio
from types import SimpleNamespace
import pandas as pd
import pytest
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.ohlcv_cache import OHLCVCache


class Adapter:
    def __init__(self,venue='phemex',market='swap',sandbox=False,price=100.):
        self.default_type=market;self.testnet=sandbox;self.price=price;self.calls=[]
        self.exchange=SimpleNamespace(id=venue,options={'defaultType':market},isSandboxModeEnabled=sandbox,
                                      urls={'api':{'public':'https://example.invalid/'+venue+str(sandbox)}})

    def fetch_ohlcv(self,symbol,timeframe,limit=500):
        self.calls.append((symbol,timeframe,limit))
        return pd.DataFrame(dict(timestamp=pd.date_range(end='2026-10-08T09:00:00Z',periods=limit,freq='1h'),
                                 open=self.price,high=self.price+1,low=self.price-1,close=self.price,volume=1.))


@pytest.fixture
def cache(monkeypatch):
    cache=OHLCVCache()
    monkeypatch.setattr('backend.data.ingestion_pipeline.get_ohlcv_cache',lambda:cache)
    monkeypatch.setattr('backend.data.ohlcv_cache.time.time',lambda:pd.Timestamp('2026-10-08T10:30:00Z').timestamp())
    return cache


@pytest.mark.parametrize('difference',[{'venue':'bybit'},{'market':'spot'},{'sandbox':True}])
def test_distinct_sources_do_not_share_candles(cache,difference):
    first=Adapter();second=Adapter(price=200.,**difference)
    IngestionPipeline(first).fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    data=IngestionPipeline(second).fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    assert data.timeframes['1h'].close.iloc[-1]==200. and len(second.calls)==1


def test_larger_history_request_is_not_satisfied_by_short_cache(cache):
    adapter=Adapter();pipeline=IngestionPipeline(adapter)
    pipeline.fetch_multi_timeframe('BTC/USDT',['1h'],limit=2)
    result=pipeline.fetch_multi_timeframe('BTC/USDT',['1h'],limit=6)
    assert len(result.timeframes['1h'])==6 and len(adapter.calls)==2


def test_same_source_reuses_cache_across_adapter_instances(cache):
    first=Adapter();second=Adapter()
    IngestionPipeline(first).fetch_multi_timeframe('BTC/USDT',['1h'],limit=6)
    data=IngestionPipeline(second).fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    assert len(data.timeframes['1h'])>=5 and not second.calls


def test_anonymous_reader_does_not_receive_scoped_production_rows(cache):
    IngestionPipeline(Adapter()).fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    assert cache.get('BTC/USDT','1h') is None


def test_market_chart_uses_requested_exchange_instead_of_first_cached_source(cache,monkeypatch):
    from backend.routers import data as router
    first=Adapter();second=Adapter(venue='bybit',price=200.)
    IngestionPipeline(first).fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    monkeypatch.setattr(router,'get_ohlcv_cache',lambda:cache)
    monkeypatch.setattr(router,'get_or_create_adapter',lambda venue:second)
    result=asyncio.run(router.get_candles('BTC/USDT',timeframe=router.Timeframe.H1,limit=5,exchange='bybit',market_type='swap'))
    assert result['candles'][-1]['close']==200.


def test_custom_endpoints_and_changed_market_defaults_do_not_reuse(cache):
    first=Adapter();pipeline=IngestionPipeline(first)
    pipeline.fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    first.exchange.urls['api']['public']='https://another.invalid'
    first.price=201.
    assert pipeline.fetch_multi_timeframe('BTC/USDT',['1h'],limit=5).timeframes['1h'].close.iloc[-1]==201.
    first.exchange.options['defaultType']='spot';first.default_type='spot';first.price=202.
    assert pipeline.fetch_multi_timeframe('BTC/USDT',['1h'],limit=5).timeframes['1h'].close.iloc[-1]==202.
    assert len(first.calls)==3


def test_unidentified_adapter_cannot_reuse_anonymous_rows(cache):
    adapter=Adapter();del adapter.exchange.isSandboxModeEnabled
    cache.set('BTC/USDT','1h',Adapter(price=9.).fetch_ohlcv('BTC/USDT','1h',limit=5))
    pipeline=IngestionPipeline(adapter)
    assert pipeline.fetch_multi_timeframe('BTC/USDT',['1h'],limit=5).timeframes['1h'].close.iloc[-1]==100.
    assert pipeline.get_cached('BTC/USDT','1h') is None


def test_pipeline_invalidation_is_scoped_and_operator_invalidation_is_global(cache):
    first=IngestionPipeline(Adapter());second=IngestionPipeline(Adapter(venue='bybit'))
    for pipeline in (first,second):
        pipeline.fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    assert first.invalidate_symbol_cache('BTC/USDT')==1
    assert first.get_cached('BTC/USDT','1h') is None
    assert second.get_cached('BTC/USDT','1h') is not None
    assert cache.invalidate('BTC/USDT','1h')==1
    assert second.get_cached('BTC/USDT','1h') is None


def test_depth_tracks_fetch_request_even_when_forming_row_is_stripped(cache):
    adapter=Adapter();fetch=adapter.fetch_ohlcv
    def with_forming(*args,**kwargs):
        df=fetch(*args,**kwargs);df.timestamp+=pd.Timedelta(hours=1)
        return df
    adapter.fetch_ohlcv=with_forming
    pipeline=IngestionPipeline(adapter)
    first=pipeline.fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    second=pipeline.fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    assert len(first.timeframes['1h'])==len(second.timeframes['1h'])==4
    assert len(adapter.calls)==1


@pytest.mark.parametrize('scenario',['matching','unsupported_exchange','unsupported_market'])
def test_chart_matching_cache_and_explicit_source_errors(cache,monkeypatch,scenario):
    from backend.routers import data as router
    adapter=Adapter(venue='bybit')
    IngestionPipeline(adapter).fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    adapter.calls.clear()
    monkeypatch.setattr(router,'get_ohlcv_cache',lambda:cache)
    monkeypatch.setattr(router,'get_or_create_adapter',lambda venue:None if scenario=='unsupported_exchange' else adapter)
    request=router.get_candles('BTC/USDT',timeframe=router.Timeframe.H1,limit=5,
                              exchange='bybit',market_type='spot' if scenario=='unsupported_market' else 'swap')
    if scenario=='matching':
        assert len(asyncio.run(request)['candles'])==5
    else:
        with pytest.raises(router.HTTPException) as error:
            asyncio.run(request)
        assert error.value.status_code==400
    assert not adapter.calls


def test_paper_price_fallback_reads_only_its_own_source(cache):
    from backend.bot.paper_trading_service import PaperTradingService
    first=Adapter();second=Adapter(venue='bybit',price=200.)
    IngestionPipeline(first).fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    own=IngestionPipeline(second);own.fetch_multi_timeframe('BTC/USDT',['1h'],limit=5)
    def fail_ticker(symbol):
        raise RuntimeError('scripted ticker unavailable')
    second.fetch_ticker=fail_ticker
    service=object.__new__(PaperTradingService)
    service.orchestrator=SimpleNamespace(exchange_adapter=second,ingestion_pipeline=own)
    service.executor=SimpleNamespace(_accounting=None)
    assert asyncio.run(service._fetch_price('BTC/USDT'))==200.
    service.executor._accounting=object()
    with pytest.raises(ValueError,match='Fresh testnet ticker unavailable'):
        asyncio.run(service._fetch_price('BTC/USDT'))
