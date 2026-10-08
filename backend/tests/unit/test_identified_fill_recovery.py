"""F0: account positions cannot settle an individual execution request.

Use scripted transport and temporary durable stores; no exchange is constructed.
The service cases exercise real pending-entry adoption and native-stop routing.
"""
import asyncio
from datetime import timedelta
from types import SimpleNamespace as S
from unittest.mock import Mock

import ccxt
import pytest

from backend.bot.executor.execution_journal import ExecutionJournal
from backend.bot.executor.live_executor import LiveExecutor
from backend.tests.unit.runtime_fixtures import prepare_adapter, initialize_fixture
from backend.bot.executor.paper_executor import OrderStatus
from backend.tests.unit.test_live_fill_protection import state, assert_adopted


SYMBOL = "FIXTURE/USDT"


@pytest.fixture(params=["BUY", "SELL"])
def execution(request, tmp_path):
    adapter = S(
        supports_trading=lambda: True,
        fetch_balance=Mock(return_value={"free": {"USDT": 1000}}),
        set_margin_mode=Mock(), set_leverage=Mock(),
        create_order=Mock(return_value={"id": "remote", "status": "open", "filled": 0}),
        fetch_order=Mock(return_value={"id": "remote", "status": "open", "filled": 0}),
        fetch_order_by_client_id=Mock(),
        fetch_positions=Mock(return_value=[]),
        cancel_order=Mock(return_value={"id": "remote", "status": "canceled", "filled": 0}),
    )
    prepare_adapter(adapter, SYMBOL, "offline-f0")
    path = tmp_path / "execution.sqlite3"
    ex = LiveExecutor(adapter, journal=ExecutionJournal(path, "offline-f0", runtime=True, environment="testnet"),
                      max_position_size_usd=2000, max_total_exposure_usd=2000)
    initialize_fixture(ex)
    yield S(ex=ex, adapter=adapter, side=request.param, path=path)
    ex.close()


def place(fixture):
    return fixture.ex.place_order(SYMBOL, fixture.side, "LIMIT", 10, price=100)


def assert_unfilled(ex, order):
    assert order.filled_quantity == 0
    assert not ex.get_trade_history()
    assert ex.get_position(SYMBOL) == 0
    assert ex._cached_balance == 1000
    assert ex.get_balance() is None
    assert not ex.accounting_status()['entry_eligible']
    if not ex._recovery_only:
        assert ex.accounting_status()['held_commitments'] == 1000
    assert ex.metrics["fills_recovered_via_position_check"] == 0


@pytest.mark.parametrize("same_side", [True, False])
@pytest.mark.parametrize("quantity", [3, 10, 20])
def test_unattributed_position_never_settles_original_order(execution, same_side, quantity):
    ex, ad = execution.ex, execution.adapter
    order = place(execution)
    matching = "long" if execution.side == "BUY" else "short"
    other = "short" if matching == "long" else "long"
    ad.fetch_positions.return_value = [{"symbol": SYMBOL, "contracts": quantity,
                                        "side": matching if same_side else other, "entryPrice": 105}]
    for _ in range(3):
        assert ex.check_fill_via_positions(order.order_id) is None
        assert order.status == OrderStatus.OPEN
        assert_unfilled(ex, order)
    ad.fetch_positions.assert_not_called()
    assert ad.fetch_order.call_count == 3
    ad.fetch_order.assert_called_with("remote", SYMBOL)
    ad.create_order.assert_called_once()


@pytest.mark.parametrize("positions", [None, [None], [{}],
    [{"symbol": SYMBOL, "contracts": "bad"}],
    [{"symbol": SYMBOL, "contracts": float("nan"), "entryPrice": 100}],
    [{"symbol": SYMBOL, "contracts": 10, "entryPrice": None}]])
def test_malformed_positions_are_never_consulted(execution, positions):
    order = place(execution)
    execution.adapter.fetch_positions.return_value = positions
    execution.ex.check_fill_via_positions(order.order_id)
    assert_unfilled(execution.ex, order)
    assert order.status == OrderStatus.OPEN
    execution.adapter.fetch_positions.assert_not_called()
    execution.adapter.fetch_order.assert_called_once_with("remote", SYMBOL)


def test_delayed_identified_fill_is_recorded_once(execution):
    ex, ad = execution.ex, execution.adapter
    order = place(execution)
    for _ in range(3):
        assert ex.check_fill_via_positions(order.order_id) is None
        assert_unfilled(ex, order)
    ad.fetch_order.return_value = {"id": "remote", "status": "closed", "filled": 10, "average": 100}
    fill = ex.check_fill_via_positions(order.order_id)
    assert fill.quantity == 10 and fill.price == 100
    assert order.status == OrderStatus.FILLED
    for _ in range(3):
        assert ex.check_fill_via_positions(order.order_id) is None
    assert len(ex.get_trade_history()) == 1
    assert ex.get_position(SYMBOL) == 0  # only a combined snapshot owns account quantities
    assert ex.get_balance() is None and ex._cached_balance == 1000
    assert ad.fetch_order.call_count == 7
    ad.create_order.assert_called_once()
    ad.fetch_positions.assert_not_called()


@pytest.mark.parametrize("acknowledged", [True, False])
@pytest.mark.parametrize("failure", ["not_found", "wrong_identity"])
def test_unknown_identity_keeps_original_reservation_then_recovers(execution, acknowledged, failure):
    ex, ad = execution.ex, execution.adapter
    if not acknowledged:
        ad.create_order.side_effect = ccxt.RequestTimeout("lost acknowledgment")
    order = place(execution)
    poll = ad.fetch_order if acknowledged else ad.fetch_order_by_client_id
    if failure == "not_found":
        poll.side_effect = ccxt.OrderNotFound("history is not visible yet")
    else:
        poll.return_value = {"id": "different-remote", "clientOrderId": "different-request",
                             "status": "closed", "filled": 10, "average": 100}
    for _ in range(3):
        assert ex.check_fill_via_positions(order.order_id) is None
        assert order.status == OrderStatus.PENDING
        assert order.order_id in ex._unacknowledged_orders
        assert_unfilled(ex, order)
    poll.assert_called_with("remote" if acknowledged else order.order_id, SYMBOL)
    poll.side_effect = None
    poll.return_value = {"id": "remote", "clientOrderId": order.order_id,
                         "status": "closed", "filled": 10, "average": 100}
    assert ex.check_fill_via_positions(order.order_id).quantity == 10
    assert order.status == OrderStatus.FILLED
    assert len(ex.get_trade_history()) == 1
    ad.create_order.assert_called_once()
    ad.fetch_positions.assert_not_called()


@pytest.mark.parametrize("filled", [0, 4])
def test_identified_partial_cancel_releases_only_confirmed_remainder(execution, filled):
    ex, ad = execution.ex, execution.adapter
    order = place(execution)
    ad.fetch_order.return_value = {"id": "remote", "status": "open", "filled": filled, "average": 100}
    ex.check_fill_via_positions(order.order_id)
    assert order.status == (OrderStatus.PARTIALLY_FILLED if filled else OrderStatus.OPEN)
    assert ex.accounting_status()['held_commitments'] == 1000
    ad.fetch_order.return_value = {"id": "remote", "status": "canceled", "filled": filled, "average": 100}
    for _ in range(3):
        ex.check_fill_via_positions(order.order_id)
    # Existing terminal convention uses FILLED for the confirmed portion of a
    # cancellation; quantity and released remainder carry the partial outcome.
    assert order.status == (OrderStatus.FILLED if filled else OrderStatus.CANCELLED)
    assert order.filled_quantity == filled
    assert sum(fill.quantity for fill in ex.get_trade_history()) == filled
    assert ex.accounting_status()['held_commitments'] == filled * 100
    assert ex._cached_balance == 1000  # no modeled fee debit
    ad.create_order.assert_called_once()
    ad.fetch_positions.assert_not_called()


@pytest.mark.parametrize("acknowledged", [True, False])
def test_restart_recovers_same_identity_without_replaying_cash_or_positions(execution, acknowledged):
    ex, ad = execution.ex, execution.adapter
    if not acknowledged:
        ad.create_order.side_effect = ccxt.RequestTimeout("lost acknowledgment")
    order = place(execution)
    ex.close()
    restored = LiveExecutor(ad, journal=ExecutionJournal(execution.path, "offline-f0", runtime=True, environment="testnet"))
    initialize_fixture(restored)
    try:
        recovered = restored.get_order(order.order_id)
        assert order.order_id in restored._restored_ids and restored._recovery_only
        poll = ad.fetch_order if acknowledged else ad.fetch_order_by_client_id
        poll.side_effect = ccxt.OrderNotFound("not yet visible")
        restored.check_fill_via_positions(order.order_id)
        assert recovered.status == OrderStatus.PENDING
        assert_unfilled(restored, recovered)
        poll.side_effect = None
        poll.return_value = {"id": "remote", "clientOrderId": order.order_id,
                             "status": "closed", "filled": 10, "average": 100}
        for _ in range(3):
            assert restored.check_fill_via_positions(order.order_id) is None
        assert recovered.status == OrderStatus.FILLED and recovered.filled_quantity == 10
        assert not restored.get_trade_history() and restored.get_position(SYMBOL) == 0
        assert restored.get_balance() is None and restored._cached_balance == 1000
        assert restored._recovery_only and not restored._entry_admission_enabled
        _, durable = restored._journal.records()[0]
        assert durable["status"] == "FILLED" and durable["exchange_id"] == "remote"
        ad.create_order.assert_called_once()
        ad.fetch_positions.assert_not_called()
    finally:
        restored.close()


def test_legacy_helper_ignores_unknown_and_dry_run_orders(execution):
    ex, ad = execution.ex, execution.adapter
    assert ex.check_fill_via_positions("unknown") is None
    order = place(execution)
    ex.dry_run = True
    try:
        assert ex.check_fill_via_positions(order.order_id) is None
        assert_unfilled(ex, order)
    finally:
        ex.dry_run = False
    ad.fetch_order.assert_not_called()
    ad.fetch_positions.assert_not_called()


@pytest.mark.parametrize("terminal,quantity", [("closed", 10), ("canceled", 4)])
def test_old_pending_entry_waits_for_identified_fill_and_protects_once(state, terminal, quantity):
    svc, ex, ad = state.svc, state.ex, state.ex._adapter
    svc._pending_placed_at["entry"] -= timedelta(minutes=3)
    ex.check_fill_via_positions = Mock(wraps=LiveExecutor.check_fill_via_positions.__get__(ex))
    ad.fetch_positions = Mock(return_value=[{"symbol": SYMBOL, "contracts": 3,
        "side": "short" if state.direction == "LONG" else "long", "entryPrice": 105}])
    for _ in range(3):
        asyncio.run(svc._monitor_pending_entries())
        assert state.order.status == OrderStatus.OPEN
        assert "entry" in svc._pending_plans
        assert not svc.position_manager.positions and not ex.get_trade_history()
        assert ex.get_balance() == 1000 and not state.calls
    ex.check_fill_via_positions.assert_not_called()
    ad.fetch_positions.assert_not_called()
    assert ad.fetch_order.call_count == 3
    ad.fetch_order.return_value = {"id": "exchange-entry", "status": terminal,
                                   "filled": quantity, "average": 100}
    for _ in range(3):
        asyncio.run(svc._monitor_pending_entries())
    assert_adopted(state, quantity)
    assert len(ex.get_trade_history()) == 1 and len(state.calls) == 1
    assert state.calls[0]["quantity"] == quantity
    assert ad.fetch_order.call_count == 4
    ad.cancel_order.assert_not_called()


def test_expired_unconfirmed_cancel_retains_plan_without_using_position(state):
    svc, ex, ad = state.svc, state.ex, state.ex._adapter
    svc._pending_placed_at["entry"] -= timedelta(minutes=121)
    ad.cancel_order.side_effect = ccxt.RequestTimeout("cancel outcome unknown")
    ad.fetch_positions = Mock()
    for _ in range(3):
        asyncio.run(svc._monitor_pending_entries())
        assert "entry" in svc._pending_plans
        assert state.order.status == OrderStatus.PENDING and not ex.get_trade_history()
        assert not svc.position_manager.positions and not state.calls
    ex.check_fill_via_positions.assert_not_called()
    ad.fetch_positions.assert_not_called()
    assert ad.cancel_order.call_count == 3
