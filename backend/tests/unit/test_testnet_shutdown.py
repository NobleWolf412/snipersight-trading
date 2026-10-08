"""Testnet shutdown must confirm the actual exit before local closure."""
import asyncio
from unittest.mock import AsyncMock
from types import SimpleNamespace as S
import pytest
from backend.bot.paper_trading_service import PaperTradingService
from backend.bot.paper_trading_service import PaperBotStatus
from backend.bot.executor.position_manager import PositionManager, PositionState, PositionStatus


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('confirmed', [False, True])
def test_testnet_shutdown_needs_confirmed_exit(direction, confirmed):
    svc = PaperTradingService()
    svc.executor = S(_accounting=True, get_open_entry_orders=lambda: [])
    svc._execute_exit_order = AsyncMock(return_value=confirmed)
    svc._sync_closed_positions = AsyncMock()
    svc._price_cache['BTC/USDT:USDT'] = 100.
    svc.position_manager = PositionManager(price_fetcher=lambda _:100.)
    pos = PositionState('position','BTC/USDT:USDT',direction,100.,10.,10.,90. if direction=='LONG' else 110.,[])
    svc.position_manager.positions[pos.position_id] = pos
    asyncio.run(svc._close_all_positions('session_stopped'))
    svc._execute_exit_order.assert_awaited_once_with('BTC/USDT:USDT','SELL' if direction=='LONG' else 'BUY',10.,100.)
    assert pos.remaining_quantity == (0 if confirmed else 10.)
    assert pos.status == (PositionStatus.CLOSED if confirmed else PositionStatus.OPEN)


def test_repeated_testnet_stop_retries_pending_exit_without_resuming_scans():
    svc = PaperTradingService()
    svc.status = PaperBotStatus.STOPPED
    svc.executor = S(_accounting=True, get_open_entry_orders=lambda: [], recovery_snapshot=lambda: {},
                     set_entry_admission=lambda enabled: None)
    svc._execute_exit_order = AsyncMock(side_effect=[False, True])
    svc._sync_closed_positions = AsyncMock()
    svc.get_status = lambda: {'status':svc.status.value}
    svc.position_manager = PositionManager(price_fetcher=lambda _:100.)
    pos = PositionState('position','BTC/USDT:USDT','LONG',100.,10.,10.,90.,[])
    svc.position_manager.positions[pos.position_id] = pos
    asyncio.run(svc.stop())
    assert pos.remaining_quantity == 10
    asyncio.run(svc.stop())
    assert pos.remaining_quantity == 0
    assert not svc._running and svc.status == PaperBotStatus.STOPPED
    assert svc._execute_exit_order.await_count == 2


def test_testnet_transport_exception_is_unconfirmed_exit():
    svc = PaperTradingService()
    svc.executor = S(_accounting=True)
    svc._execute_testnet_exit = AsyncMock(side_effect=RuntimeError('network unavailable'))
    assert not asyncio.run(svc._execute_exit_order('BTC/USDT:USDT','SELL',10,100))
