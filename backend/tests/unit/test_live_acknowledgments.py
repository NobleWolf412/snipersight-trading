"""Offline order-acknowledgment regressions; never constructs an exchange client."""

import asyncio
from types import SimpleNamespace as S
from unittest.mock import AsyncMock, Mock

import ccxt
import pytest

from backend.bot.executor.paper_executor import OrderStatus
from backend.bot.executor.live_executor import LiveExecutor
from backend.bot.live_trading_service import LiveTradingService
from backend.data.adapters.phemex import PhemexAdapter
from backend.tests.unit.test_live_valuation_exposure import executor
from backend.tests.unit.execution_fixtures import seed_order


def transport(ex):
    ex.dry_run = False
    for order in ex._orders.values():
        if order.order_id not in ex._journaled_ids:
            seed_order(ex, order)
    ex._hedge_mode = False
    ex._leverage_confirmed = {"A", "B"}
    ex._adapter.create_order = Mock(side_effect=ccxt.RequestTimeout("response lost"))
    ex._adapter.fetch_order_by_client_id = Mock(side_effect=ccxt.OrderNotFound("not visible yet"))
    ex._adapter.fetch_order = Mock(return_value={"status": "open", "filled": 0, "remaining": 10})
    return ex


def place(ex, **kwargs):
    return ex.place_order("A", ex.side, "LIMIT", 10, price=100, **kwargs)


def test_timeout_keeps_reservation_and_late_ws_fill_is_not_discarded(executor):
    ex = transport(executor)
    order = place(ex)
    assert order.status == OrderStatus.PENDING
    assert ex._total_exposure_usd() == 1000
    ex.apply_ws_fill("remote-A", order.order_id, "filled", 10, 100)
    assert order.status == OrderStatus.FILLED
    assert ex.get_position("A") == ex.sign * 10
    assert ex._exchange_order_map[order.order_id] == "remote-A"
    assert ex._total_exposure_usd() == 1000


def test_cancellation_without_remote_identity_keeps_reservation(executor):
    ex = executor
    order = place(ex)  # local dry-run order has no exchange identity
    seed_order(ex, order)  # Model an intent committed before a lost acknowledgment.
    transport(ex)
    assert ex.cancel_order(order.order_id) is False
    assert order.status not in (OrderStatus.CANCELLED, OrderStatus.REJECTED)
    assert ex._total_exposure_usd() == 1000


def test_uncertain_native_stop_is_queried_before_any_new_submission(executor):
    ex = transport(executor)
    svc = LiveTradingService()
    svc.executor = ex
    svc._log_activity = Mock()
    direction = "LONG" if ex.sign == 1 else "SHORT"
    assert not svc._ensure_exchange_stop("position", "A", direction, 10, 99)
    svc._exchange_stop_retry_at.clear()
    assert not svc._ensure_exchange_stop("position", "A", direction, 10, 99)
    assert ex._adapter.create_order.call_count == 1
    assert "position" not in svc._exchange_stop_levels


def test_close_all_does_not_book_an_unconfirmed_exit(executor):
    svc = LiveTradingService()
    svc.executor = executor
    svc._log_activity = Mock()
    pos = S(position_id="position", symbol="A", direction="LONG" if executor.sign == 1 else "SHORT",
            remaining_quantity=10, quantity=10, entry_price=100)
    svc.position_manager = S(get_open_positions=lambda: [pos], close_position=Mock())
    svc._execute_exit_order = AsyncMock(return_value=False)
    asyncio.run(svc._close_all_positions("kill_switch"))
    svc.position_manager.close_position.assert_not_called()


@pytest.mark.parametrize("response", [None, {}, {"id": ""}, {"id": "remote", "clientOrderId": "other"}])
def test_malformed_acknowledgment_never_releases_committed_exposure(executor, response):
    ex = transport(executor)
    ex._adapter.create_order.side_effect = None
    ex._adapter.create_order.return_value = response
    order = place(ex)
    assert order.status == OrderStatus.PENDING
    assert ex._total_exposure_usd() == 1000
    assert ex.place_order("B", ex.side, "LIMIT", 1, price=100).status == OrderStatus.REJECTED
    assert ex._adapter.create_order.call_count == 1


@pytest.mark.parametrize("failure", [ccxt.InsufficientFunds("funds"), ccxt.InvalidOrder("invalid")])
def test_definitive_rejection_releases_reservation(executor, failure):
    ex = transport(executor)
    ex._adapter.create_order.side_effect = failure
    assert place(ex).status == OrderStatus.REJECTED
    assert ex._total_exposure_usd() == 0
    assert not ex._unacknowledged_orders


@pytest.mark.parametrize("status,filled", [("open", 0), ("closed", 10), ("canceled", 0), ("canceled", 4), ("rejected", 0)])
def test_client_id_recovery_applies_original_order_without_resubmission(executor, status, filled):
    ex = transport(executor)
    order = place(ex)
    ex._adapter.fetch_order_by_client_id.side_effect = None
    ex._adapter.fetch_order_by_client_id.return_value = {
        "id": "remote", "clientOrderId": order.order_id, "status": status, "filled": filled, "average": 100,
    }
    ex.execute_limit_order(order.order_id, 100)
    ex._adapter.fetch_order_by_client_id.assert_called_once_with(order.order_id, "A")
    assert not ex._unacknowledged_orders
    assert ex._adapter.create_order.call_count == 1
    assert ex.get_position("A") == filled * ex.sign
    assert ex._total_exposure_usd() == (1000 if status == "open" else filled * 100)


@pytest.mark.parametrize("response", [{"status": "open"}, {"status": "closed"}, {"status": "closed", "filled": 0},
                                    {"status": "canceled"}, {"status": "closed", "filled": float("nan")},
                                    {"status": "closed", "filled": 11, "average": 100}])
def test_incomplete_or_invalid_execution_data_does_not_invent_fills(executor, response):
    order = place(executor)
    executor._process_exchange_order(order, response)
    assert not executor._fills
    assert order.status not in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED)
    assert executor._total_exposure_usd() == 1000


def test_not_found_and_wrong_client_id_keep_original_order_unresolved(executor):
    ex = transport(executor)
    order = place(ex)
    ex.refresh_order(order.order_id)
    ex._adapter.fetch_order_by_client_id.side_effect = None
    ex._adapter.fetch_order_by_client_id.return_value = {"id": "someone-else", "clientOrderId": "other", "status": "closed", "filled": 10, "average": 100}
    ex.refresh_order(order.order_id)
    assert order.status == OrderStatus.PENDING and not ex._fills
    assert order.order_id not in ex._exchange_order_map
    assert ex._adapter.create_order.call_count == 1


@pytest.mark.parametrize("method,args", [("place_stop_order", (99,)), ("place_take_profit_order", (110,)), ("place_trailing_stop_order", (105, 1))])
def test_protection_timeout_reuses_request_then_recovers_remote_acceptance(executor, method, args):
    ex = transport(executor)
    fn = getattr(ex, method)
    side = "SELL" if ex.sign == 1 else "BUY"
    first = fn("A", side, 10, *args)
    assert fn("A", side, 10, *args) is first
    ex._adapter.fetch_order_by_client_id.side_effect = None
    ex._adapter.fetch_order_by_client_id.return_value = {"id": "remote", "clientOrderId": first.order_id, "status": "open", "filled": 0}
    assert fn("A", side, 10, *args) is first
    assert first.status == OrderStatus.OPEN and not ex._unacknowledged_orders
    assert ex._adapter.create_order.call_count == 1 and not ex._positions


def exit_service(ex):
    svc = LiveTradingService()
    svc.executor = ex
    svc._log_activity = Mock()
    svc.position_manager = S(get_open_positions=lambda: [S(symbol="A", position_id="position", remaining_quantity=10)])
    svc._cancel_exchange_stop = AsyncMock()
    svc._cancel_exchange_tp = AsyncMock()
    svc._cancel_exchange_trailing = AsyncMock()
    return svc


def test_exit_timeout_retains_protection_and_recovers_same_request(executor):
    ex = transport(executor)
    ex._positions = {"A": ex.sign * 10}
    ex._position_avg_price = {"A": 100}
    svc = exit_service(ex)
    side = "SELL" if ex.sign == 1 else "BUY"
    assert not asyncio.run(svc._execute_exit_order("A", side, 10, 100))
    assert not asyncio.run(svc._execute_exit_order("A", side, 10, 100))
    svc._cancel_exchange_stop.assert_not_called()
    order_id = svc._pending_exit_orders["A"]
    ex._adapter.fetch_order_by_client_id.side_effect = None
    ex._adapter.fetch_order_by_client_id.return_value = {"id": "exit-remote", "clientOrderId": order_id, "status": "closed", "filled": 10, "average": 100}
    assert asyncio.run(svc._execute_exit_order("A", side, 10, 100))
    assert ex.get_position("A") == 0
    assert ex._adapter.create_order.call_count == 1
    svc._cancel_exchange_stop.assert_awaited_once_with("position")
    assert not svc._pending_exit_orders


def test_partial_exit_confirmation_cannot_book_full_closure_or_resubmit(executor):
    ex = transport(executor)
    svc = exit_service(ex)
    side = "SELL" if ex.sign == 1 else "BUY"
    assert not asyncio.run(svc._execute_exit_order("A", side, 10, 100))
    order_id = svc._pending_exit_orders["A"]
    ex.apply_ws_fill("remote", order_id, "canceled", 4, 100)
    assert not asyncio.run(svc._execute_exit_order("A", side, 10, 100))
    svc._cancel_exchange_stop.assert_not_called()
    assert ex._adapter.create_order.call_count == 1


def test_ws_confirmation_arriving_before_timeout_survives_exception(executor):
    ex = transport(executor)
    def send(**kwargs):
        ex.apply_ws_fill("remote", kwargs["params"]["clientOrderId"], "filled", 10, 100)
        raise ccxt.RequestTimeout("response lost after WS confirmation")
    ex._adapter.create_order.side_effect = send
    order = place(ex)
    assert order.status == OrderStatus.FILLED and not ex._unacknowledged_orders
    assert ex.get_position("A") == ex.sign * 10


def test_recovery_polls_orphaned_protection_without_entry_plan(executor):
    ex = transport(executor)
    stop = ex.place_stop_order("A", "SELL", 10, 99)
    ex._adapter.fetch_order_by_client_id.side_effect = None
    ex._adapter.fetch_order_by_client_id.return_value = {"id": "remote", "clientOrderId": stop.order_id, "status": "open", "filled": 0}
    ex.recover_uncertain_orders()
    ex.recover_uncertain_orders()
    assert stop.status == OrderStatus.OPEN
    ex._adapter.fetch_order_by_client_id.assert_called_once()


def test_adapter_uses_client_id_lookup_and_executor_ids_do_not_reset():
    adapter = object.__new__(PhemexAdapter)
    adapter.supports_trading = lambda: True
    adapter.exchange = S(fetch_order=Mock(return_value={"id": "remote"}))
    assert adapter.fetch_order_by_client_id("client", "A") == {"id": "remote"}
    adapter.exchange.fetch_order.assert_called_once_with(None, "A", {"clientOrderId": "client"})
    first, second = LiveExecutor(adapter, dry_run=True), LiveExecutor(adapter, dry_run=True)
    ids = [first._generate_order_id(), second._generate_order_id()]
    assert ids[0] != ids[1] and all(len(oid) <= 40 for oid in ids)


@pytest.mark.parametrize("recovery", ["rest", "ws"])
def test_stop_recovered_between_ticks_is_adopted_without_duplicate(executor, recovery):
    ex = transport(executor)
    svc = LiveTradingService()
    svc.executor = ex
    svc._log_activity = Mock()
    direction = "LONG" if ex.sign == 1 else "SHORT"
    assert not svc._ensure_exchange_stop("position", "A", direction, 10, 99)
    oid = svc._pending_stop_orders["position"]
    if recovery == "ws":
        ex.apply_ws_fill("remote", oid, "new", 0, 0)
    else:
        ex._adapter.fetch_order_by_client_id.side_effect = None
        ex._adapter.fetch_order_by_client_id.return_value = {"id": "remote", "clientOrderId": oid, "status": "open", "filled": 0}
        ex.recover_uncertain_orders()
    svc._exchange_stop_retry_at.clear()
    assert svc._ensure_exchange_stop("position", "A", direction, 10, 99)
    assert svc._exchange_stop_orders["position"] == oid
    assert not svc._pending_stop_orders
    assert ex._adapter.create_order.call_count == 1


def test_cancel_timeout_is_retried_after_known_open_observation(executor):
    ex = executor
    order = place(ex)
    transport(ex)
    ex._exchange_order_map[order.order_id] = "remote"
    ex._adapter.cancel_order.side_effect = ccxt.RequestTimeout("cancel response lost")
    assert not ex.cancel_order(order.order_id)
    ex._adapter.cancel_order.side_effect = None
    ex._adapter.cancel_order.return_value = {"status": "canceled", "filled": 0}
    ex.recover_uncertain_orders()
    assert order.status == OrderStatus.CANCELLED
    assert ex._adapter.cancel_order.call_count == 2
    assert not ex._cancel_requested_orders and ex._total_exposure_usd() == 0


def test_regressing_terminal_fill_count_keeps_remainder_reserved(executor):
    order = place(executor)
    executor.apply_ws_fill("remote", order.order_id, "partiallyfilled", 4, 100)
    executor._process_exchange_order(order, {"status": "canceled", "filled": 0})
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert executor._total_exposure_usd() == 1000
    executor._process_exchange_order(order, {"status": "canceled", "filled": 4})
    assert order.status == OrderStatus.FILLED and executor._total_exposure_usd() == 400


def test_confirmed_exit_is_successful_even_if_cleanup_fails(executor):
    ex = executor
    ex._positions = {"A": ex.sign * 10}
    ex._position_avg_price = {"A": 100}
    svc = exit_service(ex)
    svc._cancel_exchange_stop.side_effect = RuntimeError("cleanup failed")
    side = "SELL" if ex.sign == 1 else "BUY"
    assert asyncio.run(svc._execute_exit_order("A", side, 10, 100))
    assert not svc._pending_exit_orders and ex.get_position("A") == 0


def test_kill_switch_does_not_cancel_native_protection_before_unconfirmed_exit(executor):
    ex = executor
    pending = place(ex)
    stop = ex.place_stop_order("A", "SELL", 10, 99)
    svc = LiveTradingService()
    svc.executor = ex
    svc._log_activity = Mock()
    svc._close_all_positions = AsyncMock()
    svc.get_status = Mock(return_value={})
    asyncio.run(svc.kill_switch())
    assert pending.status == OrderStatus.CANCELLED
    assert stop.status == OrderStatus.OPEN
    svc._close_all_positions.assert_awaited_once_with("kill_switch")
