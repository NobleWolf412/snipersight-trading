"""Offline workflow boundaries; fixture stores and mocked transports only."""
import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace as S
from unittest.mock import AsyncMock, Mock

import pytest

from backend.analysis.sentiment_evidence import parse_sentiment_observation
from backend.bot.trade_journal import TradeJournalService
from backend.bot.paper_trading_service import PaperTradingService, PaperBotStatus
from backend.services.scanner_service import ScannerService, ScanJob
from backend.shared.config.scanner_modes import MODES, list_modes


def test_workflow_completed_scan_json_covers_rejections_and_preserves_boolean_evidence():
    import numpy as np
    from fastapi.encoders import jsonable_encoder
    job = ScanJob(run_id='fixture', params={}, status='completed',
        signals=[{'evidence_eligible': True, 'score': np.float64(75.)}],
        metadata={'missing': float('nan'), 'tuple': (np.int64(2), np.bool_(False))},
        rejections={'details': [{'numeric_pass': np.bool_(True), 'evidence_eligible': np.bool_(False)}]})
    payload = json.loads(json.dumps(jsonable_encoder(job.to_response()), allow_nan=False))
    assert payload['signals'][0]['evidence_eligible'] is True
    assert payload['rejections']['details'][0]['numeric_pass'] is True
    assert payload['rejections']['details'][0]['evidence_eligible'] is False
    assert payload['metadata']['missing'] is None
    assert payload['metadata']['tuple'] == [2, False]


def test_workflow_scan_retry_reuses_request_identity_without_duplicate_worker():
    async def scenario():
        service = ScannerService(Mock(), {})
        service._execute_scan = AsyncMock()
        identity = '00acb4dc-9ba4-4cdd-b198-d78fc65439a7'
        jobs = await asyncio.gather(*(service.create_scan(request_id=identity, limit=5) for _ in range(5)))
        await jobs[0].task
        assert all(job is jobs[0] for job in jobs)
        assert service._execute_scan.await_count == 1
        with pytest.raises(ValueError, match='different parameters'):
            await service.create_scan(request_id=identity, limit=6)
        assert len(service.list_jobs()) == 1
    asyncio.run(scenario())


def test_workflow_mode_dto_exposes_actual_planning_and_admission_values():
    for summary in list_modes():
        mode = MODES[summary['name']]
        assert summary['critical_timeframes'] == mode.critical_timeframes
        assert summary['primary_planning_timeframe'] == mode.primary_planning_timeframe
        assert summary['min_rr_ratio'] == mode.overrides['min_rr_ratio']


def test_workflow_journal_utc_day_filter_and_filtered_count(tmp_path):
    rows = [
        {'trade_id': 'before', 'symbol': 'BTC/USDT', 'exit_time': '2026-10-08T23:59:59Z'},
        {'trade_id': 'open', 'symbol': 'BTC/USDT', 'exit_time': '2026-10-09T00:00:00Z'},
        {'trade_id': 'close', 'symbol': 'BTC/USDT', 'exit_time': '2026-10-09T23:59:59.999Z'},
        {'trade_id': 'offset', 'symbol': 'BTC/USDT', 'exit_time': '2026-10-10T01:00:00+02:00'},
        {'trade_id': 'next', 'symbol': 'BTC/USDT', 'exit_time': '2026-10-10T00:00:00Z'},
        {'trade_id': 'other', 'symbol': 'ETH/USDT', 'exit_time': '2026-10-09T12:00:00Z'},
    ]
    path = tmp_path/'journal.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    original = path.read_bytes()
    journal = TradeJournalService(path)
    filters = dict(symbol='BTC/USDT', start_date='2026-10-09', end_date='2026-10-09')
    assert [row['trade_id'] for row in journal.query(**filters)] == ['close', 'offset', 'open']
    assert journal.count(**filters) == 3
    assert journal.query(**filters, limit=1, offset=1)[0]['trade_id'] == 'offset'
    assert path.read_bytes() == original


def test_workflow_journal_export_handles_all_heterogeneous_records(tmp_path):
    rows = [{'trade_id': str(i), 'exit_time': '2026-10-09T12:00:00Z', 'pnl': i} for i in range(10002)]
    rows[0]['legacy_only'] = 'old'
    rows[-1]['execution_accounting'] = {'fees': ['USDT', '1.25']}
    path = tmp_path/'journal.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    journal = TradeJournalService(path)
    exported = list(csv.DictReader(io.StringIO(journal.export_csv())))
    assert len(exported) == len(rows)
    assert exported[0]['legacy_only'] == 'old'
    assert json.loads(exported[-1]['execution_accounting']) == rows[-1]['execution_accounting']


def test_workflow_testnet_stop_retry_releases_only_after_verified_flat():
    service = PaperTradingService()
    service.status = PaperBotStatus.STOPPED
    executor = S(recovery_snapshot=Mock(return_value={'requests': []}),
        verify_flat_account=Mock(side_effect=ValueError('account unavailable')),
        checkpoint_flat=Mock(), close=Mock())
    service.executor = executor
    service.get_status = lambda: {'recovery_required': service.executor is not None}
    first = asyncio.run(service.stop())
    assert first['recovery_required'] and service.executor is executor
    executor.close.assert_not_called()
    executor.verify_flat_account.side_effect = None
    executor.verify_flat_account.return_value = 'verified-observation'
    result = asyncio.run(service.stop())
    assert not result['recovery_required'] and service.executor is None
    executor.checkpoint_flat.assert_called_once_with('verified-observation')
    executor.close.assert_called_once()


@pytest.mark.parametrize('change', [
    {'value': None}, {'value': True}, {'value': 'NaN'}, {'value': 101}, {'value': -1}, {'value': 2.5},
    {'timestamp': None}, {'timestamp': True}, {'timestamp': 'NaN'}, {'timestamp': 100000000000},
    {'timestamp': 1}, {'value_classification': None},
])
def test_workflow_sentiment_rejects_fabricated_or_invalid_observation(change):
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    row = {'value': '50', 'value_classification': 'Neutral', 'timestamp': str(int(now.timestamp()))}
    with pytest.raises(ValueError):
        parse_sentiment_observation({**row, **change}, now=now)


def test_workflow_sentiment_preserves_provider_observation():
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    value, classification, observed = parse_sentiment_observation(
        {'value': '62', 'value_classification': 'Greed', 'timestamp': str(int(now.timestamp()) - 3600)}, now=now)
    assert (value, classification, observed) == (62, 'Greed', '2026-10-09T11:00:00+00:00')


@pytest.mark.parametrize('kind', ['paper', 'live'])
def test_workflow_bot_status_json_preserves_nested_analysis_without_mutating_runtime(kind):
    import numpy as np
    from fastapi.encoders import jsonable_encoder
    from backend.bot.live_trading_service import LiveTradingService

    service = PaperTradingService() if kind == 'paper' else LiveTradingService()
    evidence = {'numeric_pass': np.bool_(True), 'evidence_eligible': np.bool_(False),
                'score': np.float64(63.5), 'unknown': np.float64('nan'),
                'counts': (np.int64(2), np.bool_(False))}
    service.signal_log = [evidence]
    service.current_scan = {'status': 'completed', 'metadata': {'eligible': np.bool_(False)}}
    service.activity_log = [{'data': {'confirmed': np.bool_(True)}}]
    payload = json.loads(json.dumps(jsonable_encoder(service.get_status()), allow_nan=False))
    assert payload['signal_log'][0] == {
        'numeric_pass': True, 'evidence_eligible': False, 'score': 63.5,
        'unknown': None, 'counts': [2, False]}
    assert payload['current_scan']['metadata']['eligible'] is False
    assert payload['recent_activity'][0]['data']['confirmed'] is True
    assert isinstance(service.signal_log[0]['numeric_pass'], np.bool_)
    assert np.isnan(service.signal_log[0]['unknown'])
    assert isinstance(service.signal_log[0]['counts'], tuple)
    payload['current_scan']['metadata']['eligible'] = True
    assert not service.current_scan['metadata']['eligible']
