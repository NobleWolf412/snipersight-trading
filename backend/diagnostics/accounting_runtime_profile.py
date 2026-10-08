"""Profile durable runtime publication at 100/1,000/10,000 requests, offline.

Every sample uses a FULL-synchronous disposable SQLite journal and real reducers.
No credentials, real store, network or service is opened. Output is retained in
the reported temporary directory; timing is evidence, not a fixed CI threshold.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    from backend.diagnostics.accounting_storage_diagnostic import guard
    directory = Path(tempfile.mkdtemp(prefix='snipersight-fv2-profile-')).resolve()
    guard(directory, False)
    from decimal import Decimal
    from backend.bot.executor.execution_journal import ExecutionJournal
    from backend.bot.executor.accounting_models import ObservationContext, OrderExecutionObservation
    journal = ExecutionJournal(directory / 'profile.sqlite3', 'fixture', runtime=True, environment='testnet')
    results = []
    started = time.perf_counter()
    try:
        for index in range(1, 10001):
            oid = str(index)
            now = datetime.now(timezone.utc).isoformat()
            intent = dict(order_id=oid, symbol='BTC/USDT:USDT', side='BUY', order_type='LIMIT', quantity=1,
                price=100, stop_price=None, purpose='entry', reduce_only=False, owner='fixture', generation='fixture',
                wire=dict(symbol='BTC/USDT:USDT', side='buy', amount=1, params={'clientOrderId': oid}))
            state = dict(status='PENDING', filled_quantity=0, average_fill_price=0, exchange_id=None,
                unknown_reason='awaiting response', cancel_requested=False, rejection_reason=None, created_at=now, updated_at=now)
            journal.submit_intent(intent, state)
            if index in (100, 1000, 10000):
                timings = []
                for n in range(5):
                    ctx = ObservationContext('testnet', 'fixture', 'profile', f'{oid}-{n}', now, 1., 2.)
                    evidence = OrderExecutionObservation(ctx, intent['symbol'], 'BUY', oid, 'remote-' + oid,
                        Decimal(1), Decimal(100), 'FILLED', 'raw_fixture')
                    begin = time.perf_counter()
                    journal.record_execution(oid, [evidence], exchange_id='remote-' + oid)
                    timings.append((time.perf_counter() - begin) * 1000)
                results.append(dict(requests=index, publication_ms=timings,
                    store_bytes=journal.path.stat().st_size, elapsed_seconds=time.perf_counter() - started))
                print(json.dumps(results[-1]), flush=True)
        journal.close()
        begin = time.perf_counter()
        check = ExecutionJournal.inspect(journal.path)
        assert not check.get('error'), check
        report = dict(results=results, full_replay_seconds=time.perf_counter() - begin,
            source='FULL synchronous disposable runtime journal', artifact_directory=str(directory))
        (directory / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps(report))
    finally:
        journal.close()


if __name__ == '__main__':
    main()
