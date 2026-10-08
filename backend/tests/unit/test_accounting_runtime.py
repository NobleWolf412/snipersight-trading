"""Scripted account/execution races with real runtime journal, never an exchange."""
from decimal import Decimal as D
from types import SimpleNamespace as S
from unittest.mock import Mock
import time
import pytest
from backend.bot.executor.accounting_runtime import AccountRuntime, Commitment
from backend.bot.executor.execution_journal import ExecutionJournal
from backend.bot.executor.live_executor import LiveExecutor
from backend.bot.executor.paper_executor import OrderStatus
from backend.data.adapters.phemex_accounting import normalize_account
from backend.tests.unit.test_accounting_models import context
from backend.tests.unit.test_phemex_accounting import market, account, raw_order


def observation(q='0', *, side='Buy', started=1.0, ended=2.0):
    body = account(side)
    row = body['data']['positions'][0]
    row.update(sizeRq=q)
    if q == '0':
        row.update(side='None', avgEntryPriceRp='0', unRealisedPnlRv='0')
    return normalize_account(body, {'btc': market()}, context(started_monotonic=started, ended_monotonic=ended))


def ready_runtime():
    clock = [1.0]
    r = AccountRuntime('fixture', 'testnet', 'generation', clock=lambda: clock[0])
    r.establish_flat_baseline()
    token = r.begin_refresh()
    clock[0] = 2.0
    assert r.finish_refresh(token, observation())
    return r, clock


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
def test_snapshot_alone_owns_money_and_quantity(side):
    r, clock = ready_runtime()
    assert r.balance_status()['equity'] == 1000
    assert r.balance_status()['current'] == 750
    r.reserve('o', Commitment('BTC/USDT:USDT', side, D(10), D(110), False))
    r.update_order('o', filled=D(10), terminal=True, cost_known=True)
    assert not r.view()['entry_eligible']
    assert r.view()['held_commitments'] == 1100
    token = r.begin_refresh(force=True)
    clock[0] = 3.0
    assert r.finish_refresh(token, observation('10', side='Buy' if side == 'BUY' else 'Sell', started=2., ended=3.))
    assert r.view()['equity'] == (1060 if side == 'BUY' else 940)
    assert r.view()['held_commitments'] == 0
    assert r.view()['observed_exposure'] == 1000


def test_overlap_stale_failure_and_refresh_coalescing():
    r, clock = ready_runtime()
    assert r.begin_refresh() is None
    token = r.begin_refresh(force=True)
    assert r.begin_refresh(force=True) is None
    r.invalidate('fill')
    clock[0] = 3.
    assert not r.finish_refresh(token, observation(started=2., ended=3.))
    assert not r.view()['entry_eligible'] and r.view()['equity'] is None
    token = r.begin_refresh(force=True)
    clock[0] = 4.
    assert r.finish_refresh(token, observation(started=3., ended=4.))
    clock[0] = 125.
    assert r.view()['state'] == 'stale' and r.balance_status()['equity'] is None
    token = r.begin_refresh()
    assert not r.finish_refresh(token, error=ValueError('failed'))
    assert r.view()['free'] is None


def test_unknown_cost_and_foreign_position_block_entries():
    r, clock = ready_runtime()
    r.reserve('o', Commitment('BTC/USDT:USDT', 'BUY', D(10), D(110), False))
    r.update_order('o', filled=D(10), terminal=True, cost_known=False)
    token = r.begin_refresh(force=True)
    clock[0] = 3.
    assert not r.finish_refresh(token, observation('10', started=2., ended=3.))
    assert 'EXECUTION_COST_UNAVAILABLE' in r.view()['reasons']
    assert r.view()['equity'] == 1060  # account value may be known while strategy cost is not
    r.update_order('o', filled=D(10), terminal=True, cost_known=True)
    token = r.begin_refresh(force=True)
    clock[0] = 4.
    assert not r.finish_refresh(token, observation('9', started=3., ended=4.))
    assert 'ACCOUNT_OWNED_QUANTITY_MISMATCH' in r.view()['reasons']


@pytest.fixture
def executor(tmp_path):
    journal = ExecutionJournal(tmp_path / 'runtime.sqlite3', 'fixture', runtime=True, environment='testnet')
    adapter = S(testnet=True, supports_trading=lambda: True,
        exchange=S(markets={'BTC/USDT:USDT': market()}),
        set_margin_mode=Mock(), set_leverage=Mock(), create_order=Mock())
    def observed():
        now = time.monotonic()
        return observation(started=now, ended=now)
    adapter.fetch_account_observation = Mock(side_effect=observed)
    ex = LiveExecutor(adapter, journal=journal, max_position_size_usd=5000, max_total_exposure_usd=10000)
    ex._accounting.establish_flat_baseline()
    ex.reconcile_account(force=True)
    ex.set_entry_admission(True)
    def create(**wire):
        raw = raw_order()
        raw.update(clOrdID=wire['params']['clientOrderId'], side=wire['side'].title(), ordStatus='New', cumQtyRq='0', cumValueRv='0')
        return {'id': 'remote', 'clientOrderId': raw['clOrdID'], 'info': raw}
    adapter.create_order.side_effect = create
    yield ex, adapter
    ex.close()


def test_real_runtime_unknown_price_and_late_enrichment_no_local_cash(executor):
    ex, adapter = executor
    o = ex.place_order('BTC/USDT:USDT', 'BUY', 'LIMIT', 10, price=110)
    assert o.status == OrderStatus.OPEN
    raw = raw_order()
    raw['clOrdID'] = o.order_id
    del raw['cumValueRv']
    update = ex._process_exchange_order(o, {'info': raw})
    assert update.quantity == 10 and update.price is None and update.fee is None
    assert o.filled_quantity == 10 and o.average_fill_price is None
    assert ex._positions == {} and ex._cached_balance == 750
    raw['cumValueRv'] = '1060'
    update = ex._process_exchange_order(o, {'info': raw})
    assert update.quantity == 0 and o.average_fill_price == 106
    assert ex._process_exchange_order(o, {'info': raw}) is None
    assert ex._positions == {} and ex._cached_balance == 750


def test_refresh_failure_between_admission_and_send_blocks_transport(executor):
    ex, adapter = executor
    def interleave(*args):
        ex.invalidate_account('WS_EVENT')
    adapter.set_leverage.side_effect = interleave
    o = ex.place_order('BTC/USDT:USDT', 'BUY', 'LIMIT', 10, price=110)
    assert o.status == OrderStatus.REJECTED
    adapter.create_order.assert_not_called()


def test_publication_failure_does_not_publish_order_or_cash(executor, monkeypatch):
    ex, adapter = executor
    o = ex.place_order('BTC/USDT:USDT', 'BUY', 'LIMIT', 10, price=110)
    raw = raw_order()
    raw['clOrdID'] = o.order_id
    original = ex._journal._event
    def fail(oid, kind, *args):
        if kind == 'execution_publication':
            raise RuntimeError('disk full')
        return original(oid, kind, *args)
    monkeypatch.setattr(ex._journal, '_event', fail)
    with pytest.raises(Exception, match='disk full'):
        ex._process_exchange_order(o, {'info': raw})
    assert o.filled_quantity == 0 and ex._positions == {}


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
def test_cumulative_cost_produces_true_incremental_price(executor, side):
    ex, _ = executor
    o = ex.place_order('BTC/USDT:USDT', side, 'LIMIT', 10, price=110)
    raw = raw_order()
    raw.update(clOrdID=o.order_id, side=side.title(), ordStatus='PartiallyFilled', cumQtyRq='4', cumValueRv='400')
    first = ex._process_exchange_order(o, {'info': raw})
    raw.update(ordStatus='Filled', cumQtyRq='10', cumValueRv='1060')
    second = ex._process_exchange_order(o, {'info': raw})
    assert (first.quantity, first.price) == (4, 100)
    assert (second.quantity, second.price) == (6, 110)
    assert o.average_fill_price == 106
    assert first.fee is None and second.fee is None
    assert ex.get_statistics()['total_fees'] is None


def test_account_read_during_transport_cannot_grant_entry(executor):
    ex, _ = executor
    ex._inflight_mutations = 1
    try:
        assert not ex.reconcile_account(force=True)['entry_eligible']
        assert ex.get_balance() is None
    finally:
        ex._inflight_mutations = 0


def test_unknown_account_work_blocks_clean_shutdown_and_reset(executor):
    ex, _ = executor
    token = ex._accounting.begin_refresh(force=True)
    assert ex.recovery_snapshot()['inflight_account_reads']
    with pytest.raises(Exception, match='Execution changed'):
        ex.checkpoint_flat('fixture', expected_revision=ex.recovery_snapshot()['revision'])
    ex._accounting.finish_refresh(token, error=RuntimeError('fixture ended'))


def test_old_generation_completion_cannot_publish_account():
    runtime, clock = ready_runtime()
    token = runtime.begin_refresh(force=True)
    runtime.generation = 'replacement'
    clock[0] = 3.
    assert not runtime.finish_refresh(token, observation(started=2., ended=3.))
    assert runtime.view()['equity'] is None
    assert not runtime.view()['entry_eligible']


def test_configured_account_interval_controls_receipt_expiry():
    runtime, clock = ready_runtime()
    runtime.interval = 150.
    clock[0] = 302.
    assert runtime.view()['entry_eligible']
    clock[0] = 302.1
    assert runtime.view()['state'] == 'stale'
