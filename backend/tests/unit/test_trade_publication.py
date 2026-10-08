"""Completed-trade publication must remain retryable and preserve durable history."""
import asyncio
import json
from types import SimpleNamespace as S
from unittest.mock import Mock
import pytest
from backend.bot.trade_journal import TradeJournalService
from backend.bot.live_trading_service import LiveTradingService
from backend.bot.paper_trading_service import PaperTradingService
from backend.bot.executor.position_manager import PositionManager, PositionState, PositionStatus


@pytest.mark.parametrize('service',[LiveTradingService,PaperTradingService])
@pytest.mark.parametrize('direction',['LONG','SHORT'])
@pytest.mark.parametrize('after_write',[False,True])
def test_failed_trade_write_remains_retryable_without_duplicate_stats(tmp_path,monkeypatch,service,direction,after_write):
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    svc=service();svc.session_id='session'
    svc.position_manager=PositionManager(price_fetcher=lambda _:105)
    pos=PositionState('position','BTC/USDT:USDT',direction,100,10,0,90,[],
                      status=PositionStatus.CLOSED,realized_pnl=50,
                      exit_price=105 if direction=='LONG' else 95,exit_reason='manual_close')
    svc.position_manager.positions[pos.position_id]=pos
    svc._save_state=Mock()
    original=journal.upsert
    calls=[]
    def write(record,session):
        calls.append(record)
        if len(calls)==1:
            if after_write:
                original(record,session)
            raise OSError('injected acknowledgement failure' if after_write else 'injected disk failure')
        return original(record,session)
    monkeypatch.setattr(journal,'append',write)
    monkeypatch.setattr(journal,'upsert',write)
    monkeypatch.setattr(service.__module__+'.get_trade_journal',lambda:journal)
    asyncio.run(svc._sync_closed_positions())
    assert svc.stats.total_trades==0 and not svc.completed_trades
    assert pos.position_id not in svc._completed_trade_ids
    assert svc.position_manager.positions[pos.position_id] is pos
    asyncio.run(svc._sync_closed_positions())
    asyncio.run(svc._sync_closed_positions())
    assert svc.stats.total_trades==1 and svc.stats.total_pnl==50
    assert len(svc.completed_trades)==1 and len(journal.query())==1
    assert len(calls)==2


def row(**changes):
    return dict({'trade_id':'trade','symbol':'BTC/USDT:USDT','pnl':12.34},**changes)


def test_same_identity_with_changed_money_is_a_visible_conflict(tmp_path):
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    journal.upsert(row(),'session')
    before=journal._path.read_bytes()
    with pytest.raises(ValueError,match='CONFLICT'):
        journal.upsert(row(pnl=-12.34),'session')
    assert journal._path.read_bytes()==before


@pytest.mark.parametrize('tail',[b'{"trade_id":',b'null\n',b'{"pnl":NaN}\n'])
def test_malformed_history_blocks_write_without_modification(tmp_path,tail):
    path=tmp_path/'trades.jsonl'; path.write_bytes(tail)
    journal=TradeJournalService(path)
    with pytest.raises(ValueError,match='CORRUPT'):
        journal.upsert(row(),'session')
    assert path.read_bytes()==tail


def test_failed_replace_preserves_previous_complete_history(tmp_path,monkeypatch):
    import os
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    journal.upsert(row(),'session')
    before=journal._path.read_bytes()
    monkeypatch.setattr(os,'replace',Mock(side_effect=OSError('replace unavailable')))
    with pytest.raises(OSError,match='replace unavailable'):
        journal.upsert(row(trade_id='next'),'session')
    assert journal._path.read_bytes()==before
    assert not list(tmp_path.glob('*.tmp'))


def test_independent_writer_instances_cannot_overlap(tmp_path,monkeypatch):
    import os
    path=tmp_path/'trades.jsonl'
    first,second=TradeJournalService(path),TradeJournalService(path)
    replace=os.replace
    def during_replace(source,target):
        with pytest.raises(OSError,match='WRITER_BUSY'):
            second.upsert(row(trade_id='other'),'session')
        replace(source,target)
    monkeypatch.setattr(os,'replace',during_replace)
    assert first.upsert(row(),'session')
    monkeypatch.setattr(os,'replace',replace)
    assert second.upsert(row(trade_id='other'),'session')
    assert len(first.query())==2


def test_fsync_failure_keeps_old_bytes_and_retry_is_safe(tmp_path,monkeypatch):
    import os
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    journal.upsert(row(),'session')
    before=journal._path.read_bytes()
    with monkeypatch.context() as context:
        context.setattr(os,'fsync',Mock(side_effect=OSError('flush failed')))
        with pytest.raises(OSError,match='flush failed'):
            journal.upsert(row(trade_id='next'),'session')
    assert journal._path.read_bytes()==before
    assert journal.upsert(row(trade_id='next'),'session')
    assert len(journal.query())==2


def test_old_bytes_preserved_and_missing_newline_gets_separator(tmp_path):
    path=tmp_path/'trades.jsonl'
    original=b'{"trade_id":"old","pnl":0,"note":"existing spacing"}'
    path.write_bytes(original)
    journal=TradeJournalService(path)
    journal.upsert(row(),'session')
    assert path.read_bytes().startswith(original+b'\n')
    assert len(journal.query())==2


@pytest.mark.parametrize('pnl',[float('nan'),float('inf'),float('-inf')])
def test_nonfinite_new_money_cannot_be_published(tmp_path,pnl):
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    with pytest.raises(ValueError):
        journal.upsert(row(pnl=pnl),'session')
    assert not journal._path.exists()


@pytest.mark.parametrize('service',[LiveTradingService,PaperTradingService])
def test_stats_failure_after_durable_write_rolls_back_derived_state_for_retry(tmp_path,monkeypatch,service):
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    svc=service();svc.session_id='session'
    svc.position_manager=PositionManager(price_fetcher=lambda _:105)
    pos=PositionState('position','BTC/USDT:USDT','LONG',100,10,0,90,[],
                      status=PositionStatus.CLOSED,realized_pnl=50,exit_price=105,exit_reason='manual_close')
    svc.position_manager.positions[pos.position_id]=pos
    svc._save_state=Mock()
    monkeypatch.setattr(service.__module__+'.get_trade_journal',lambda:journal)
    original=svc._update_stats
    def broken(trade):
        svc.stats.total_trades+=1
        svc.stats.total_pnl+=123
        svc._peak_equity+=456
        raise RuntimeError('injected derived-stat failure')
    peak=svc._peak_equity
    svc._update_stats=broken
    asyncio.run(svc._sync_closed_positions())
    assert len(journal.query())==1
    assert svc.stats.total_trades==0 and svc.stats.total_pnl==0 and svc._peak_equity==peak
    assert not svc.completed_trades and pos.position_id in svc.position_manager.positions
    svc._update_stats=original
    asyncio.run(svc._sync_closed_positions())
    assert svc.stats.total_trades==1 and svc.stats.total_pnl==50
    assert len(journal.query())==1


def test_duplicate_retry_must_confirm_durability_again(tmp_path,monkeypatch):
    import os
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    journal.upsert(row(),'session')
    with monkeypatch.context() as context:
        context.setattr(os,'fsync',Mock(side_effect=OSError('flush unavailable')))
        with pytest.raises(OSError,match='flush unavailable'):
            journal.upsert(row(),'session')
    assert not journal.upsert(row(),'session') and len(journal.query())==1
