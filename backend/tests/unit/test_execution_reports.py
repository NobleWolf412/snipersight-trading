"""Actual execution outcomes, durable reporting context and interrupted delivery."""
from copy import deepcopy
from decimal import Decimal as D
import json
import sqlite3
import asyncio
from unittest.mock import Mock
from threading import Event
import pytest
from backend.bot.executor.accounting_models import AccountingError
from backend.bot.executor.execution_journal import ExecutionJournal, JournalError
from backend.bot.executor.execution_reports import ExecutionReportPublisher, REPORT_KINDS, financial_fields, trade_identity
from backend.bot.executor.live_executor import LiveExecutor
from backend.bot.trade_journal import TradeJournalService
from backend.tests.unit.test_accounting_runtime import executor
from backend.tests.unit.test_phemex_accounting import raw_order


def settled(executor, side='BUY', fee='1'):
    ex, adapter = executor
    entry = ex.place_order('BTC/USDT:USDT', side, 'LIMIT', 10, price=110)
    raw = raw_order()
    raw.pop('execFeeRv', None)
    raw.update(clOrdID=entry.order_id, side=side.title(), cumValueRv='1000', tradeType='Trade',
               execID='entry-fill', execQtyRq='10', execValueRv='1000', currency='USDT')
    if fee is not None:
        raw['execFeeRv'] = fee
    ex.apply_ws_order(raw)
    exit_side = 'SELL' if side == 'BUY' else 'BUY'
    cost = '1090' if side == 'BUY' else '910'
    def send(**wire):
        data = raw_order()
        data.update(orderID='exit-remote', clOrdID=wire['params']['clientOrderId'], side=exit_side.title(),
                    cumValueRv=cost, tradeType='Trade', execID='exit-fill', execQtyRq='10',
                    execValueRv=cost, execFeeRv='1', currency='USDT')
        return {'id': 'exit-remote', 'info': data}
    adapter.create_order.side_effect = send
    ex.place_order('BTC/USDT:USDT', exit_side, 'MARKET', 10, price=100, reduce_only=True,
                   parent_entry_order_id=entry.order_id)
    return entry, raw


def metadata(side='BUY'):
    return dict(trade_id='position', symbol='BTC/USDT:USDT', direction='LONG' if side=='BUY' else 'SHORT',
                entry_time='2026-01-01T00:00:00+00:00', exit_time='2026-01-01T00:01:00+00:00',
                exit_reason='manual_close', pnl=999, pnl_pct=999, quantity=999, entry_price=999, exit_price=999)


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
@pytest.mark.parametrize('fee', ['0', '1', '-.5'])
def test_real_fills_replace_all_estimated_money_and_retry_once(executor, tmp_path, side, fee):
    ex, _ = executor
    entry, _ = settled(executor, side, fee)
    journal = TradeJournalService(tmp_path/'trades.jsonl')
    publisher = ExecutionReportPublisher(ex, journal)
    trade_id = publisher.capture(entry.order_id, metadata(side), 'session')
    result = publisher.publish(entry.order_id)
    assert result['state']=='published'
    trade = result['trade']
    assert trade['pnl']==float(D(89)-D(fee)) and trade['gross_pnl']==90
    assert trade['quantity']==10 and trade['entry_price']==100 and trade['exit_price']==(109 if side=='BUY' else 91)
    assert trade['pnl_pct']==trade['pnl']/10
    assert trade['trade_id']==trade_id and trade_id!=metadata(side)['trade_id']
    assert trade['execution_accounting']['funding'] is None
    assert publisher.publish(entry.order_id)==result
    assert len(journal.query())==1 and len(ex._journal.report_events()[entry.order_id])==3


def test_missing_fee_stays_pending_until_actual_late_fee(executor, tmp_path):
    ex, _ = executor
    entry, raw = settled(executor, fee=None)
    journal = TradeJournalService(tmp_path/'trades.jsonl')
    publisher = ExecutionReportPublisher(ex,journal)
    publisher.capture(entry.order_id, metadata(), 'session')
    result=publisher.publish(entry.order_id)
    assert result['state']=='pending' and 'EXECUTION_FEES_UNAVAILABLE' in result['reasons']
    assert not journal._path.exists()
    raw['execFeeRv']='2'
    ex.apply_ws_order(raw)
    assert publisher.publish(entry.order_id)['trade']['pnl']==87


@pytest.mark.parametrize('after_write', [False, True])
def test_interrupted_delivery_restarts_identical_row_without_strategy_replay(executor,tmp_path,after_write):
    ex, adapter = executor
    entry, _ = settled(executor)
    journal = TradeJournalService(tmp_path/'trades.jsonl')
    publisher=ExecutionReportPublisher(ex,journal)
    publisher.capture(entry.order_id,metadata(),'original-session')
    original=journal.upsert
    def fail(*args):
        if after_write:
            original(*args)
        raise OSError('injected delivery failure')
    journal.upsert=fail
    with pytest.raises(OSError):
        publisher.publish(entry.order_id)
    assert REPORT_KINDS[1] in ex._journal.report_events()[entry.order_id]
    path=ex._journal.path
    ex.close()
    journal.upsert=original
    adapter.create_order.reset_mock()
    reopened=LiveExecutor(adapter,journal=ExecutionJournal(path,'fixture',runtime=True,environment='testnet'))
    try:
        result=ExecutionReportPublisher(reopened,journal).recover()
        assert len(result)==1 and result[0]['state']=='published'
        assert result[0]['session_id']=='original-session' and len(journal.query())==1
        assert reopened._positions=={} and not reopened.get_trade_history()
        adapter.create_order.assert_not_called()
    finally:
        reopened.close()


def test_later_contradictory_fee_is_visible_and_preserves_published_snapshot(executor,tmp_path):
    ex,_=executor
    entry,raw=settled(executor)
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    publisher=ExecutionReportPublisher(ex,journal)
    publisher.capture(entry.order_id,metadata(),'session')
    publisher.publish(entry.order_id)
    original=journal._path.read_bytes()
    raw['execFeeRv']='3'
    ex.apply_ws_order(raw)
    with pytest.raises(AccountingError,match='EVIDENCE_CHANGED'):
        publisher.publish(entry.order_id)
    assert publisher.recover()[0]['state']=='error'
    assert journal._path.read_bytes()==original and not ex.execution_outcome(entry.order_id).complete


def test_owner_cannot_close_during_report_delivery(executor,tmp_path):
    ex,_=executor
    entry,_=settled(executor)
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    publisher=ExecutionReportPublisher(ex,journal)
    publisher.capture(entry.order_id,metadata(),'session')
    original=journal.upsert
    def deliver(*args):
        with pytest.raises(JournalError,match='report delivery'):
            ex.close()
        return original(*args)
    journal.upsert=deliver
    assert publisher.publish(entry.order_id)['state']=='published' and ex._inflight_reports==0


@pytest.mark.parametrize('change', [{'symbol':'OTHER/USDT:USDT'}, {'direction':'SHORT'}])
def test_foreign_context_rejected_before_event(executor,tmp_path,change):
    ex,_=executor
    entry,_=settled(executor)
    publisher=ExecutionReportPublisher(ex,TradeJournalService(tmp_path/'trades.jsonl'))
    with pytest.raises(AccountingError,match='SCOPE'):
        publisher.capture(entry.order_id,{**metadata(),**change},'session')
    assert ex._journal.report_events()=={}


def test_report_replay_detects_tampered_snapshot(executor,tmp_path):
    ex,_=executor
    entry,_=settled(executor)
    publisher=ExecutionReportPublisher(ex,TradeJournalService(tmp_path/'trades.jsonl'))
    publisher.capture(entry.order_id,metadata(),'session')
    publisher.publish(entry.order_id)
    path=ex._journal.path
    ex.close()
    with sqlite3.connect(path) as connection:
        value=json.loads(connection.execute('SELECT payload FROM events WHERE kind=?',(REPORT_KINDS[1],)).fetchone()[0])
        value['trade']['pnl']=500
        connection.execute('UPDATE events SET payload=? WHERE kind=?',(json.dumps(value),REPORT_KINDS[1]))
    assert 'SNAPSHOT_CONFLICT' in ExecutionJournal.inspect(path)['error']


def test_scope_changes_report_identity():
    assert len({trade_identity(b,e,o) for b,e,o in [('a','testnet','1'),('b','testnet','1'),('a','production','1'),('a','testnet','2')]})==4


def test_restart_before_context_capture_recovers_only_financial_metadata(executor,tmp_path):
    ex,adapter=executor
    entry,_=settled(executor)
    path=ex._journal.path;ex.close()
    adapter.create_order.reset_mock()
    reopened=LiveExecutor(adapter,journal=ExecutionJournal(path,'fixture',runtime=True,environment='testnet'))
    try:
        journal=TradeJournalService(tmp_path/'trades.jsonl')
        result=ExecutionReportPublisher(reopened,journal).recover()
        assert len(result)==1 and result[0]['state']=='published'
        record=result[0]['trade']
        assert record['pnl']==88 and record['report_metadata_basis']=='recovered_execution_only'
        assert record['regime_labeled_at']=='unknown' and 'max_favorable' not in record
        assert record['trade_id']==trade_identity('fixture','testnet',entry.order_id)
        assert record['execution_report_prepared_at']
        assert reopened._positions=={} and not reopened.get_trade_history()
        adapter.create_order.assert_not_called()
    finally:
        reopened.close()


def test_fee_worker_recovers_previously_captured_report(executor,tmp_path):
    from backend.bot.executor.execution_fee_recovery import ExecutionFeeRecovery
    ex,_=executor
    entry,_=settled(executor)
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    ExecutionReportPublisher(ex,journal).capture(entry.order_id,metadata(),'session')
    worker=ExecutionFeeRecovery(ex,report_journal=journal)
    worker._iteration()
    assert worker.status()['reports'][0]['state']=='published'
    assert 'trade' not in worker.status()['reports'][0] and len(journal.query())==1


def test_live_restart_shutdown_replays_reports_without_managing_positions(executor,tmp_path,monkeypatch):
    from backend.bot.live_trading_service import LiveTradingService
    ex,adapter=executor
    entry,_=settled(executor)
    path=ex._journal.path;ex.close()
    reopened=LiveExecutor(adapter,journal=ExecutionJournal(path,'fixture',runtime=True,environment='testnet'))
    try:
        journal=TradeJournalService(tmp_path/'trades.jsonl')
        monkeypatch.setattr('backend.bot.live_trading_service.get_trade_journal',lambda:journal)
        svc=LiveTradingService();svc.executor=reopened
        reopened.recover_uncertain_orders=Mock()
        reopened.reconcile_positions=Mock()
        svc._shutdown_step()
        assert svc._reporting_status[entry.order_id]['state']=='published'
        assert svc.position_manager is None and len(journal.query())==1
    finally:
        reopened.close()


@pytest.mark.parametrize('service_name', ['live', 'paper'])
@pytest.mark.parametrize('side', ['BUY', 'SELL'])
@pytest.mark.parametrize('fee_known', [True, False])
def test_services_count_only_complete_execution_results(executor,tmp_path,monkeypatch,service_name,side,fee_known):
    from backend.bot.live_trading_service import LiveTradingService
    from backend.bot.paper_trading_service import PaperTradingService
    from backend.bot.executor.position_manager import PositionManager, PositionState, PositionStatus
    ex,_=executor
    entry,raw=settled(executor,side, '1' if fee_known else None)
    service_type=LiveTradingService if service_name=='live' else PaperTradingService
    svc=service_type();svc.executor=ex;svc.session_id='session'
    svc.position_manager=PositionManager(price_fetcher=lambda _:105)
    pos=PositionState('position','BTC/USDT:USDT','LONG' if side=='BUY' else 'SHORT',100,10,0,90,[],
                      status=PositionStatus.CLOSED,realized_pnl=999,entry_order_id=entry.order_id,
                      exit_price=105,exit_reason='manual_close')
    svc.position_manager.positions[pos.position_id]=pos
    svc._save_state=Mock()
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    monkeypatch.setattr(service_type.__module__+'.get_trade_journal',lambda:journal)
    asyncio.run(svc._sync_closed_positions())
    if not fee_known:
        assert not svc.completed_trades and svc.stats.total_trades==0
        assert svc._reporting_status[entry.order_id]['state']=='pending'
        assert pos.position_id in svc.position_manager.positions
        raw['execFeeRv']='1';ex.apply_ws_order(raw)
        asyncio.run(svc._sync_closed_positions())
    asyncio.run(svc._sync_closed_positions())
    assert len(svc.completed_trades)==1 and svc.stats.total_trades==1 and svc.stats.total_pnl==88
    result=svc.completed_trades[0].to_dict()
    assert result['pnl']==88 and result['exit_price']==(109 if side=='BUY' else 91)
    assert result['execution_accounting']['complete'] and len(journal.query())==1
    assert result==ex._journal.report_events(entry.order_id)[entry.order_id][REPORT_KINDS[1]]['trade']
    assert svc._reporting_status[entry.order_id]['state']=='published'


@pytest.mark.parametrize('service_name', ['live','paper'])
@pytest.mark.parametrize('failure', [False,True])
def test_overlapping_publications_preserve_stats_without_double_count(executor,tmp_path,monkeypatch,service_name,failure):
    from backend.bot.live_trading_service import LiveTradingService
    from backend.bot.paper_trading_service import PaperTradingService
    from backend.bot.executor.position_manager import PositionManager, PositionState, PositionStatus
    ex,_=executor
    entry,_=settled(executor)
    service_type=LiveTradingService if service_name=='live' else PaperTradingService
    svc=service_type();svc.executor=ex;svc.session_id='session'
    svc.position_manager=PositionManager(price_fetcher=lambda _:105)
    pos=PositionState('position','BTC/USDT:USDT','LONG',100,10,0,90,[],
                      status=PositionStatus.CLOSED,realized_pnl=999,entry_order_id=entry.order_id,
                      exit_price=105,exit_reason='manual_close')
    svc.position_manager.positions[pos.position_id]=pos
    svc._save_state=Mock()
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    monkeypatch.setattr(service_type.__module__+'.get_trade_journal',lambda:journal)
    entered,release=Event(),Event()
    original=journal.upsert
    def slow(*args):
        entered.set()
        assert release.wait(3)
        if failure:
            raise OSError('write unavailable')
        return original(*args)
    journal.upsert=slow
    async def run():
        first=asyncio.create_task(svc._sync_closed_positions())
        try:
            assert await asyncio.to_thread(entered.wait,1)
            if failure:
                # A different completed trade updates statistics while this IO waits.
                svc.stats.total_trades=5;svc.stats.total_pnl=50
            second=asyncio.create_task(svc._sync_closed_positions())
            await asyncio.sleep(0)
        finally:
            release.set()
        await asyncio.gather(first,second)
    asyncio.run(run())
    assert svc.stats.total_trades==(5 if failure else 1)
    assert svc.stats.total_pnl==(50 if failure else 88)
    assert len(svc.completed_trades)==(0 if failure else 1)


def test_removed_report_protocol_marker_fails_replay(executor):
    ex,_=executor
    entry,_=settled(executor)
    path=ex._journal.path;ex.close()
    with sqlite3.connect(path) as connection:
        intent=json.loads(connection.execute('SELECT intent FROM requests WHERE order_id=?',(entry.order_id,)).fetchone()[0])
        intent.pop('report_version')
        connection.execute('UPDATE requests SET intent=? WHERE order_id=?',(json.dumps(intent),entry.order_id))
    assert 'Report version evidence mismatch' in ExecutionJournal.inspect(path)['error']


@pytest.mark.parametrize('kind',[REPORT_KINDS[1],REPORT_KINDS[2]])
def test_execution_store_failure_during_prepare_or_ack_restarts_safely(executor,tmp_path,kind):
    ex,adapter=executor
    entry,_=settled(executor)
    journal=TradeJournalService(tmp_path/'trades.jsonl')
    publisher=ExecutionReportPublisher(ex,journal)
    publisher.capture(entry.order_id,metadata(),'session')
    original=ex._journal._event
    def fail(oid,event,*args):
        original(oid,event,*args)
        if event==kind:
            raise OSError('injected transaction interruption')
    ex._journal._event=fail
    with pytest.raises(JournalError):
        publisher.publish(entry.order_id)
    path=ex._journal.path;ex.close()
    reopened=LiveExecutor(adapter,journal=ExecutionJournal(path,'fixture',runtime=True,environment='testnet'))
    try:
        result=ExecutionReportPublisher(reopened,journal).recover()
        assert result[0]['state']=='published' and len(journal.query())==1
    finally:
        reopened.close()


def test_legacy_requests_without_protocol_marker_do_not_create_duplicate_history(executor,tmp_path):
    ex,adapter=executor
    entry,_=settled(executor)
    path=ex._journal.path;ex.close()
    # Simulate an older compatible request which never opted into report identities.
    with sqlite3.connect(path) as connection:
        intent=json.loads(connection.execute('SELECT intent FROM requests WHERE order_id=?',(entry.order_id,)).fetchone()[0])
        intent.pop('report_version')
        connection.execute('UPDATE requests SET intent=? WHERE order_id=?',(json.dumps(intent),entry.order_id))
        connection.execute("UPDATE events SET payload=? WHERE order_id=? AND kind='submit_intent'",(json.dumps(intent),entry.order_id))
    reopened=LiveExecutor(adapter,journal=ExecutionJournal(path,'fixture',runtime=True,environment='testnet'))
    try:
        journal=TradeJournalService(tmp_path/'trades.jsonl')
        assert ExecutionReportPublisher(reopened,journal).recover()==[]
        assert not journal._path.exists()
    finally:
        reopened.close()
