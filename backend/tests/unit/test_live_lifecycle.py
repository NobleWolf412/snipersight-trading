"""Offline lifecycle ownership, shutdown recovery and snapshot contracts."""
import asyncio
from contextlib import suppress
from threading import Event
from types import SimpleNamespace as S
from unittest.mock import AsyncMock, Mock

import pytest

from backend.bot.live_trading_service import LiveTradingService, LiveBotStatus, LifecycleConflict
from backend.bot.executor.paper_executor import OrderStatus
from backend.data.adapters.phemex import PhemexAdapter
from backend.tests.unit.test_live_valuation_exposure import executor
from backend.tests.unit.test_live_acknowledgments import transport, place


def snapshot(**changes):
    return {"complete": True, "scope": "phemex:swap:USDT", "positions": [], "orders": [], **changes}


def service(ex):
    svc = LiveTradingService()
    svc.executor = ex
    svc.adapter = ex._adapter
    svc.adapter.fetch_account_snapshot = Mock(return_value=snapshot())
    svc.config = S(dry_run=False, testnet=True, to_dict=lambda: {})
    svc._phase = "running"
    svc._running = True
    svc.status = LiveBotStatus.RUNNING
    svc._get_active_positions = lambda: []
    svc._log_activity = Mock()
    svc._sync_closed_positions = AsyncMock()
    svc.position_manager = S(positions={}, get_open_positions=lambda: [], close_position=Mock())
    return svc


async def cleanup(svc):
    for task in (svc._shutdown_task, svc._ws_task, svc._monitor_task, svc._scan_task):
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def accepted(ex):
    ex = transport(ex)
    ex._adapter.create_order.side_effect = None
    ex._adapter.create_order.return_value = {"id": "remote", "status": "open", "filled": 0}
    ex._adapter.fetch_order.return_value = {"id": "remote", "status": "open", "filled": 0}
    ex._adapter.cancel_order.return_value = {"id": "remote", "status": "canceled", "filled": 0}
    return place(ex)


def test_stop_cancels_acknowledged_entry_and_reset_reobserves_account(executor):
    order = accepted(executor)
    svc = service(executor)
    svc._pending_plans[order.order_id] = S(symbol="A", direction=executor.side)

    async def run():
        result = await svc.stop()
        assert order.status == OrderStatus.CANCELLED
        assert result["lifecycle"]["phase"] == "stopped"
        assert result["lifecycle"]["account_state"] == "flat_confirmed"
        assert result["lifecycle"]["reset_allowed"]
        svc.adapter.fetch_account_snapshot.assert_called_once()
        observer = svc.adapter.fetch_account_snapshot
        await svc.reset()
        assert observer.call_count == 2
        assert svc.executor is None and svc._phase == "idle"
    asyncio.run(run())


def test_unknown_stop_preserves_recovery_identity_and_blocks_start_reset(executor):
    ex = transport(executor)
    order = place(ex)
    svc = service(ex)
    svc._pending_plans[order.order_id] = S(symbol="A", direction=ex.side)

    async def run():
        try:
            result = await svc.stop()
            task = svc._shutdown_task
            assert task and not task.done()
            assert result["pending_orders"][0]["status"] == "PENDING"
            assert result["lifecycle"]["recovery_required"]
            assert not result["lifecycle"]["reset_allowed"]
            assert not result["lifecycle"]["entry_admission_enabled"]
            for operation in (svc.reset(), svc.start(S())):
                with pytest.raises(LifecycleConflict):
                    await operation
            await asyncio.gather(svc.stop(), svc.kill_switch())
            assert svc._shutdown_task is task
            assert svc.status == LiveBotStatus.KILL_SWITCHED
            assert ex.get_order(order.order_id) is order
            assert place(ex).status == OrderStatus.REJECTED
            ex._adapter.create_order.assert_called_once()
            svc.adapter.fetch_account_snapshot.assert_not_called()
        finally:
            await cleanup(svc)
    asyncio.run(run())


def test_reset_cannot_interleave_with_task_cancellation(executor):
    svc = service(transport(executor))

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()

        async def monitor():
            try:
                await asyncio.Event().wait()
            finally:
                entered.set()
                await release.wait()

        svc._monitor_task = asyncio.create_task(monitor())
        await asyncio.sleep(0)
        stopping = asyncio.create_task(svc.stop())
        await entered.wait()
        with pytest.raises(LifecycleConflict):
            await svc.reset()
        assert svc.executor is executor
        release.set()
        await stopping
        await svc._shutdown_task
        assert svc._phase == "stopped"
    asyncio.run(run())


@pytest.mark.parametrize("bad", [None, {}, snapshot(complete=False), snapshot(orders=None),
                                    snapshot(positions=[{}]), snapshot(positions=[{"symbol": "A", "contracts": float("nan")}]),
                                    snapshot(scope="spot"), snapshot(orders=[{}])])
def test_incomplete_snapshot_cannot_confirm_flat_or_reset(executor, bad):
    svc = service(transport(executor))
    svc.adapter.fetch_account_snapshot.return_value = bad

    async def run():
        try:
            result = await svc.stop()
            assert result["lifecycle"]["account_state"] == "unknown"
            assert not result["lifecycle"]["reset_allowed"]
            with pytest.raises(LifecycleConflict):
                await svc.reset()
        finally:
            await cleanup(svc)
    asyncio.run(run())


def test_foreign_exposure_is_visible_and_not_liquidated(executor):
    svc = service(transport(executor))
    svc.adapter.fetch_account_snapshot.return_value = snapshot(
        positions=[{"symbol": "FOREIGN", "contracts": 3}], orders=[{"id": "foreign-stop", "symbol": "FOREIGN"}])

    async def run():
        try:
            status = (await svc.kill_switch())["lifecycle"]
            assert status["account_state"] == "exposure_present"
            assert status["unmanaged_symbols"] == ["FOREIGN"]
            assert status["account_open_orders"][0]["exchange_id"] == "foreign-stop"
            assert not status["reset_allowed"]
            executor._adapter.create_order.assert_not_called()
            executor._adapter.cancel_order.assert_not_called()
        finally:
            await cleanup(svc)
    asyncio.run(run())


def test_caller_cancel_does_not_cancel_supervisor_or_block_event_loop(executor):
    svc = service(transport(executor))
    entered, release = Event(), Event()

    def observe():
        entered.set()
        assert release.wait(3)
        return snapshot()
    svc.adapter.fetch_account_snapshot.side_effect = observe

    async def run():
        caller = asyncio.create_task(svc.stop())
        while not entered.is_set():
            await asyncio.sleep(.001)
        caller.cancel()
        with suppress(asyncio.CancelledError):
            await caller
        assert svc._shutdown_task and not svc._shutdown_task.done()
        assert svc.get_status()["lifecycle"]["phase"] == "recovering"
        release.set()
        await svc._shutdown_task
    asyncio.run(run())


def test_execution_update_invalidates_flat_snapshot(executor):
    svc = service(transport(executor))
    order = place(executor)

    def observe():
        executor._submission_unknown(order, "late update")
        return snapshot()
    svc.adapter.fetch_account_snapshot.side_effect = observe
    with pytest.raises(ValueError, match="changed"):
        asyncio.run(svc._observe_account())
    assert svc._account_state == "unknown"


def test_shutdown_adopts_cancellation_fill_before_attempting_exit(executor):
    order = accepted(executor)
    executor._adapter.cancel_order.return_value = {"status": "canceled", "filled": 4, "average": 100}
    svc = service(executor)
    plan = S(symbol="A", direction="LONG" if executor.sign == 1 else "SHORT")
    svc._pending_plans[order.order_id] = plan
    events = []

    async def adopt(oid, p, price, quantity):
        events.append(("adopt", quantity))
        svc._clear_pending_entry(oid)
    async def close(reason):
        events.append(("close", executor.get_position("A")))
    svc._open_filled_entry = adopt
    svc._close_all_positions = close
    svc._shutdown_reason = "session_stopped"
    svc._shutdown_step()
    assert events == [("adopt", 4), ("close", 4 * executor.sign)]


def test_freeze_during_leverage_setup_blocks_entry_transport(executor):
    ex = transport(executor)
    ex._leverage_confirmed.clear()
    ex._adapter.set_margin_mode = Mock()
    ex._adapter.set_leverage = Mock(side_effect=lambda *args: ex.set_entry_admission(False))
    order = place(ex)
    assert order.status == OrderStatus.REJECTED
    ex._adapter.create_order.assert_not_called()


def test_stale_generation_callback_cannot_mutate_new_session(executor):
    svc = service(executor)
    svc._generation = 2
    task = S(cancelled=lambda: False, exception=lambda: RuntimeError("old"), get_name=lambda: "old")
    svc._task_done_callback(task, 1)
    assert svc._phase == "running" and svc._running
    svc._task_done_callback(task, 2)
    assert svc._phase == "recovering" and not svc._running
    assert not executor.recovery_snapshot()["entry_admission_enabled"]


def adapter_fixture():
    ad = object.__new__(PhemexAdapter)
    ad.default_type = "swap"
    ad.supports_trading = lambda: True
    markets = {s: {"id": s, "symbol": s, "swap": True, "settle": "USDT"} for s in ("A", "B")}
    ad.exchange = S(load_markets=Mock(return_value=markets),
                    privateGetGOrdersActiveList=Mock(return_value={"code": 0, "data": {"rows": []}}),
                    privateGetGAccountsAccountPositions=Mock(return_value={"code": 0, "data": {"account": {"currency": "USDT"}, "positions": []}}),
                    parse_order=lambda row, market: row, parse_position=lambda row, market: row)
    return ad


def test_account_snapshot_queries_every_contract_and_includes_conditional_orders():
    ad = adapter_fixture()
    ad.exchange.privateGetGOrdersActiveList.side_effect = [
        {"code": 0, "data": {"total": 1, "rows": [{"id": "stop", "symbol": "A", "type": "stop", "status": "open"}]}},
        {"code": 0, "data": []},
    ]
    result = ad.fetch_account_snapshot()
    assert result["complete"] and result["orders"][0]["id"] == "stop"
    assert [c.args[0]["symbol"] for c in ad.exchange.privateGetGOrdersActiveList.call_args_list] == ["A", "B"]


@pytest.mark.parametrize("body", [{}, {"rows": [], "total": 1}, {"rows": None}, {"rows": [None]},
                                  {"rows": [], "nextCursor": "more"}, {"rows": [], "total": False}])
def test_account_snapshot_rejects_missing_or_truncated_rows(body):
    ad = adapter_fixture()
    ad.exchange.privateGetGOrdersActiveList.return_value = {"code": 0, "data": body}
    with pytest.raises(ValueError):
        ad.fetch_account_snapshot()


def test_partial_exit_stays_open_without_duplicate_exit_or_reset(executor):
    svc = service(transport(executor))
    pos = S(position_id="p", symbol="A", direction="LONG" if executor.sign == 1 else "SHORT",
            quantity=10, remaining_quantity=10, entry_price=100)
    svc.position_manager.get_open_positions = lambda: [pos]
    svc._cancel_exchange_stop = AsyncMock()
    svc._cancel_exchange_tp = AsyncMock()
    svc._cancel_exchange_trailing = AsyncMock()

    async def run():
        try:
            await svc.stop()
            oid = svc._pending_exit_orders['A']
            executor._adapter.fetch_order_by_client_id.side_effect = None
            executor._adapter.fetch_order_by_client_id.return_value = {
                'id': 'partial', 'clientOrderId': oid, 'status': 'canceled', 'filled': 4, 'average': 100}
            await asyncio.to_thread(svc._shutdown_step)
            executor._adapter.create_order.assert_called_once()
            svc.position_manager.close_position.assert_not_called()
            svc._cancel_exchange_stop.assert_not_called()
            assert svc.get_status()['lifecycle']['recovery_required']
            assert not svc.get_status()['lifecycle']['reset_allowed']
        finally:
            await cleanup(svc)
    asyncio.run(run())


def test_resume_supervisor_reuses_inflight_worker(executor):
    svc = service(transport(executor))
    entered, release = Event(), Event()
    calls = []

    def slow_step():
        calls.append(1)
        entered.set()
        assert release.wait(3)
    svc._shutdown_step = slow_step

    async def run():
        await svc.stop()
        assert entered.is_set()
        worker = svc._shutdown_step_task
        svc._shutdown_task.cancel()
        with suppress(asyncio.CancelledError):
            await svc._shutdown_task
        await svc.stop()
        assert svc._shutdown_step_task is worker
        release.set()
        await svc._shutdown_task
        assert len(calls) == 1 and svc._phase == 'stopped'
    asyncio.run(run())


def test_api_reset_awaits_guard_and_returns_conflict_without_app_import():
    import ast
    from pathlib import Path
    from fastapi import HTTPException
    source = Path(__file__).resolve().parents[2] / 'api_server.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'reset_live_trading')
    node.decorator_list = []
    svc = S(reset=AsyncMock(side_effect=LifecycleConflict('unresolved exit')))
    ns = dict(get_live_trading_service=lambda: svc, HTTPException=HTTPException, LifecycleConflict=LifecycleConflict)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), ns)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(ns['reset_live_trading']())
    assert caught.value.status_code == 409 and caught.value.detail == 'unresolved exit'
    svc.reset.assert_awaited_once()


def test_startup_transition_rejects_overlapping_lifecycle_commands(executor):
    svc = LiveTradingService()

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        async def setup(config):
            svc.executor = executor
            entered.set()
            await release.wait()
            return {'status': 'running'}
        svc._start_session = setup
        from backend.shared.config.live_trading_config import LiveTradingConfig
        first = asyncio.create_task(svc.start(LiveTradingConfig()))
        await asyncio.wait_for(entered.wait(), timeout=3)
        for command in (svc.start(S()), svc.reset(), svc.stop(), svc.kill_switch()):
            with pytest.raises(LifecycleConflict):
                await command
        assert svc._phase == 'starting'
        release.set()
        await first
        assert svc._phase == 'running' and not svc._lifecycle_busy
    asyncio.run(run())


def test_reset_refuses_new_external_exposure_after_previous_flatness(executor):
    svc = service(transport(executor))
    async def run():
        await svc.stop()
        assert svc._phase == 'stopped'
        svc.adapter.fetch_account_snapshot.return_value = snapshot(positions=[{'symbol': 'A', 'contracts': 1}])
        with pytest.raises(LifecycleConflict, match='exposure remains'):
            await svc.reset()
        assert svc.executor is executor
        assert svc.get_status()['lifecycle']['recovery_required']
    asyncio.run(run())


@pytest.mark.parametrize('state', ['New', 'Untriggered', 'PartiallyFilled'])
def test_snapshot_uses_installed_ccxt_order_parser_without_network(state):
    import ccxt
    ad = adapter_fixture()
    client = ccxt.phemex()
    market = {'id': 'BTCUSDT', 'symbol': 'BTC/USDT:USDT', 'type': 'swap', 'swap': True,
              'spot': False, 'linear': True, 'inverse': False, 'contract': True,
              'settle': 'USDT', 'settleId': 'USDT', 'base': 'BTC', 'quote': 'USDT',
              'baseId': 'BTC', 'quoteId': 'USDT', 'contractSize': 1,
              'precision': {'price': .1, 'amount': .001}, 'info': {}}
    client.set_markets([market])
    client.load_markets = Mock(return_value={market['symbol']: market})
    client.privateGetGOrdersActiveList = Mock(return_value={'code': 0, 'data': {'rows': [{
        'orderID': 'conditional', 'clOrdID': 'original', 'symbol': 'BTCUSDT', 'ordStatus': state,
        'orderType': 'Stop', 'side': 'Sell', 'orderQtyRq': '0.01', 'cumQtyRq': '0',
        'leavesQtyRq': '0.01', 'priceRp': '0', 'stopPxRp': '50000', 'reduceOnly': True,
    }]}})
    client.privateGetGAccountsAccountPositions = ad.exchange.privateGetGAccountsAccountPositions
    ad.exchange = client
    result = ad.fetch_account_snapshot()
    assert result['orders'][0]['id'] == 'conditional'
    assert result['orders'][0]['status'] == 'open'
    assert result['orders'][0]['symbol'] == market['symbol']


@pytest.mark.parametrize('qty', [None, True, -1, float('nan')])
def test_adapter_rejects_unusable_position_quantities(qty):
    ad = adapter_fixture()
    ad.exchange.privateGetGAccountsAccountPositions.return_value['data']['positions'] = [{'symbol': 'A', 'contracts': qty}]
    with pytest.raises(ValueError, match='quantity'):
        ad.fetch_account_snapshot()
