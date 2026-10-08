"""Runtime lifecycle and financial state cross a single durable boundary."""
from dataclasses import replace
from unittest.mock import patch
import json
import sqlite3
import pytest
from backend.bot.executor.execution_journal import ExecutionJournal, JournalError, upgrade_accounting_schema
from backend.tests.unit.test_accounting_journal import seed
from backend.tests.unit.test_accounting_models import order, fact


@pytest.fixture
def runtime(tmp_path):
    path = tmp_path / 'runtime.sqlite3'
    seed(path)
    upgrade_accounting_schema(path, 'fixture', environment='testnet', target_version=3)
    journal = ExecutionJournal(path, 'fixture', runtime=True, environment='testnet')
    yield journal
    journal.close()


def test_new_runtime_store_and_old_store_requires_explicit_upgrade(tmp_path):
    path = tmp_path / 'new.sqlite3'
    store = ExecutionJournal(path, 'fixture', runtime=True, environment='testnet')
    assert store.schema_version == 3
    store.close()
    assert ExecutionJournal.inspect(path).get('error') is None
    old = tmp_path / 'old.sqlite3'
    seed(old)
    with pytest.raises(JournalError, match='offline runtime'):
        ExecutionJournal(old, 'fixture', runtime=True, environment='testnet')
    with sqlite3.connect(old) as c:
        assert c.execute('SELECT version FROM metadata').fetchone() == (1,)


@pytest.mark.parametrize('through_v2', [False, True])
def test_migration_preserves_history_and_marks_legacy_price_unverified(tmp_path, through_v2):
    path = tmp_path / 'legacy.sqlite3'
    _, old = seed(path, filled=10)
    marker = path.with_suffix('.initialized').read_bytes()
    if through_v2:
        upgrade_accounting_schema(path, 'fixture', environment='testnet')
    result = upgrade_accounting_schema(path, 'fixture', environment='testnet', target_version=3)
    assert result['schema'] == 3 and result['backup']
    assert path.with_suffix('.initialized').read_bytes() == marker
    store = ExecutionJournal(path, 'fixture', runtime=True, environment='testnet')
    try:
        assert store.records()[0][1]['average_fill_price'] is None
        assert store.records()[0][1]['filled_quantity'] == 10
        assert 'LEGACY_QUANTITY_UNVERIFIED' in store.financial_state('order').reasons
        preserved = json.loads(store._connection.execute("SELECT payload FROM events WHERE kind='runtime_seed'").fetchone()[0])
        assert preserved['previous_lifecycle'] == old
        restored = store.record_execution('order', [order()])
        assert restored['lifecycle']['average_fill_price'] == 106
    finally:
        store.close()
    assert upgrade_accounting_schema(path, 'fixture', environment='testnet', target_version=3)['already_upgraded']


def test_quantity_can_commit_without_cost_and_enrich_after_terminal(runtime):
    result = runtime.record_execution('order', [order(cost=None)])
    assert result['lifecycle']['status'] == 'FILLED'
    assert result['lifecycle']['filled_quantity'] == 10
    assert result['lifecycle']['average_fill_price'] is None
    result = runtime.record_execution('order', [order(), fact()])
    assert result['lifecycle']['average_fill_price'] == 106
    assert result['state'].financially_complete
    assert str(result['state'].fees[0].amount) == '0.2'
    repeat = runtime.record_execution('order', [order(), fact()])
    assert repeat['state'] == result['state']
    path = runtime.path
    runtime.close()
    reopened = ExecutionJournal(path, 'fixture', runtime=True, environment='testnet')
    try:
        assert reopened.financial_state('order') == result['state']
        assert reopened.records()[0][1]['average_fill_price'] == 106
    finally:
        reopened.close()


@pytest.mark.parametrize('failed_event', ['financial_observation', 'execution_publication'])
def test_failure_never_commits_only_one_projection(runtime, failed_event):
    previous = runtime.records()
    original = runtime._event
    def fail(oid, kind, source, payload):
        original(oid, kind, source, payload)
        if kind == failed_event:
            raise OSError('fixture interruption')
    with patch.object(runtime, '_event', side_effect=fail), pytest.raises(JournalError):
        runtime.record_execution('order', [order(), fact()])
    assert runtime.records() == previous
    assert runtime.financial_state('order').filled_quantity == 0
    assert runtime.failed


def test_v3_forbids_separate_financial_publication(runtime):
    with pytest.raises(JournalError, match='record_execution'):
        runtime.record_accounting(order())


def test_known_cost_conflict_invalidates_legacy_price_without_replaying_qty(runtime):
    runtime.record_execution('order', [order()])
    result = runtime.record_execution('order', [order(cost='1070')])
    assert result['lifecycle']['filled_quantity'] == 10
    assert result['lifecycle']['average_fill_price'] is None
    assert 'VERIFIED_COST_CONFLICT' in result['state'].reasons


def test_mismatched_owner_rolls_back_even_financial_observation(runtime):
    with pytest.raises(JournalError, match='different execution'):
        runtime.record_execution(None, [order()])
    assert runtime.financial_state('order').filled_quantity == 0


def test_replay_rejects_lifecycle_quantity_divergence(runtime):
    runtime.record_execution('order', [order()])
    path = runtime.path
    runtime.close()
    with sqlite3.connect(path) as connection:
        state = json.loads(connection.execute('SELECT state FROM requests').fetchone()[0])
        state['filled_quantity'] = 9
        connection.execute('UPDATE requests SET state=?', (json.dumps(state),))
    assert 'disagree' in ExecutionJournal.inspect(path)['error']
    with pytest.raises(JournalError, match='disagree'):
        ExecutionJournal(path, 'fixture', runtime=True, environment='testnet')


@pytest.mark.parametrize('external', [False, True])
def test_validation_cache_cannot_hide_unexpected_writes(runtime, external):
    runtime.record_execution('order', [order()])
    connection = sqlite3.connect(runtime.path) if external else runtime._connection
    try:
        state = json.loads(connection.execute('SELECT state FROM requests').fetchone()[0])
        state['filled_quantity'] = 9
        connection.execute('UPDATE requests SET state=?', (json.dumps(state),))
        connection.commit()
    finally:
        if external:
            connection.close()
    with pytest.raises(JournalError, match='disagree'):
        runtime.record_execution('order', [order()])
    assert runtime.failed
