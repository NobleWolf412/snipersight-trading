"""Documented raw history pages, durable dedupe and explicit incomplete sweeps."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock
import pytest

from backend.bot.live_trading_service import LiveTradingService
from backend.data.adapters.phemex import PhemexAdapter


def rows(count=201):
    return [dict(execId=f'fill-{i}', createdAt=1000, currency='USDT', symbol='BTCUSDT',
                 execQtyRq='1', execPriceRp='100', execValueRv='100', execFeeRv='0',
                 side=1, tradeType=1) for i in range(count)]


def service(tmp_path, items=None):
    items = rows() if items is None else items
    svc = LiveTradingService()
    svc._fills_log_path = tmp_path/'testnet-account.fills.jsonl'
    def page(offset=0, limit=200):
        return dict(scope='phemex:swap:USDT', offset=offset, total=len(items), rows=items[offset:offset+limit])
    svc.adapter = S(fetch_execution_history_page=Mock(side_effect=page))
    return svc


def test_same_timestamp_pages_and_restart_never_skip_or_duplicate(tmp_path):
    svc = service(tmp_path)
    asyncio.run(svc._run_backfill_once())
    records = svc._load_existing_fill_records()
    assert len(records) == 201 and 'fill-200' in records
    assert records['fill-200']['execFeeRv'] == '0'
    assert [c.kwargs['offset'] for c in svc.adapter.fetch_execution_history_page.call_args_list] == [0,200,0]
    fresh = service(tmp_path, rows(202))
    fresh._load_last_trade_sync_ts()
    assert fresh._last_trade_sync_ts is not None
    asyncio.run(fresh._run_backfill_once())
    assert len(fresh._load_existing_fill_records()) == 202
    assert fresh._backfill_metrics['rows_new_total'] == 1
    assert fresh._backfill_metrics['completeness'] == 'consistent_available_history'


@pytest.mark.parametrize('failure', ['overlap','count_change','missing_id','wrong_scope','changed_head','transport','page_limit'])
def test_incomplete_history_never_advances_or_claims_success(tmp_path, failure):
    svc = service(tmp_path, rows(10001) if failure == 'page_limit' else None)
    original = svc.adapter.fetch_execution_history_page.side_effect
    calls = []
    def changed(**kw):
        calls.append(kw)
        result = original(**kw)
        result['rows'] = [dict(r) for r in result['rows']]
        if failure == 'overlap' and kw['offset']:
            result['rows'][0] = rows(1)[0]
        if failure == 'count_change' and kw['offset']:
            result['total'] += 1
        if failure == 'missing_id':
            result['rows'][0].pop('execId')
        if failure == 'wrong_scope':
            result['scope'] = 'spot'
        if failure == 'changed_head' and len(calls) == 3:
            result['rows'][0]['execFeeRv'] = '.1'
        if failure == 'transport':
            raise RuntimeError('scripted unavailable')
        return result
    svc.adapter.fetch_execution_history_page.side_effect = changed
    svc._last_trade_sync_ts = 777
    with pytest.raises((ValueError, RuntimeError)):
        asyncio.run(svc._run_backfill_once())
    assert svc._last_trade_sync_ts == 777
    assert svc._backfill_metrics['state'] == 'incomplete'
    assert not svc._fills_log_path.exists()


def test_history_identity_conflict_is_not_silently_deduplicated(tmp_path):
    svc = service(tmp_path, rows(1))
    asyncio.run(svc._run_backfill_once())
    changed = rows(1)
    changed[0]['execQtyRq'] = '2'
    svc.adapter = service(tmp_path, changed).adapter
    with pytest.raises(ValueError, match='CONFLICT'):
        asyncio.run(svc._run_backfill_once())
    assert svc._load_existing_fill_records()['fill-0']['execQtyRq'] == '1'


def test_malformed_existing_log_is_visible_and_not_overwritten(tmp_path):
    svc = service(tmp_path)
    svc._fills_log_path.write_text('{truncated', encoding='utf8')
    with pytest.raises(json.JSONDecodeError):
        asyncio.run(svc._run_backfill_once())
    assert svc._fills_log_path.read_text(encoding='utf8') == '{truncated'
    svc.adapter.fetch_execution_history_page.assert_not_called()


def test_checkpoint_failure_keeps_fsynced_rows_and_retry_deduplicates(tmp_path, monkeypatch):
    svc = service(tmp_path)
    original = svc._save_last_trade_sync_ts
    monkeypatch.setattr(svc, '_save_last_trade_sync_ts', Mock(side_effect=OSError('disk full')))
    with pytest.raises(OSError):
        asyncio.run(svc._run_backfill_once())
    assert len(svc._load_existing_fill_records()) == 201
    assert svc._last_trade_sync_ts is None
    monkeypatch.setattr(svc, '_save_last_trade_sync_ts', original)
    asyncio.run(svc._run_backfill_once())
    assert len(svc._load_existing_fill_records()) == 201
    assert svc._backfill_metrics['state'] == 'ready'


def test_raw_adapter_requires_documented_count_and_retains_strings():
    adapter = object.__new__(PhemexAdapter)
    adapter.supports_trading = lambda: True
    adapter.metrics = dict(rest_calls_total=0,fetch_my_trades_calls_total=0,fetch_my_trades_rows_total=0)
    adapter.exchange = S(privateGetExchangeOrderV2TradingList=Mock(return_value={'code':0,'data':{'total':1,'rows':rows(1)}}))
    page = adapter.fetch_execution_history_page(offset=0,limit=200)
    assert page['rows'][0]['execFeeRv'] == '0'
    adapter.exchange.privateGetExchangeOrderV2TradingList.assert_called_once_with(
        {'currency':'USDT','offset':0,'limit':200,'withCount':True})
    adapter.exchange.privateGetExchangeOrderV2TradingList.return_value = {'code':0,'data':rows(1)}
    with pytest.raises(ValueError, match='COUNT'):
        adapter.fetch_execution_history_page()


def test_empty_history_is_explicit_and_repeated_checkpoint_replaces(tmp_path):
    svc = service(tmp_path, [])
    asyncio.run(svc._run_backfill_once())
    asyncio.run(svc._run_backfill_once())
    assert svc._load_existing_fill_records() == {}
    assert svc._backfill_metrics['available_rows'] == 0
    assert json.loads(svc._last_trade_sync_path().read_text())['version'] == 2
