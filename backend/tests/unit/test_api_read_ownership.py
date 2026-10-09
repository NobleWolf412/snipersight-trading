"""Actual route bodies, isolated from credential-loading application bootstrap."""
import ast
import asyncio
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as S
from typing import Optional
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, Query


@pytest.fixture(autouse=True)
def fresh_replay_dispatcher(monkeypatch):
    from backend.routers import replay
    from backend.shared.async_worker import SerializedWorker
    monkeypatch.setattr(replay, "_replay_worker", SerializedWorker())


def regime_handler(reader):
    source = Path(__file__).resolve().parents[2] / "api_server.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_market_regime")
    node.decorator_list = []
    scanner = Mock()
    scanner._detect_global_regime.side_effect = AssertionError("display borrowed scanner engine")
    namespace = dict(Optional=Optional, Query=Query, HTTPException=HTTPException,
                     logger=Mock(), REGIME_CACHE=S(get=lambda _: None), orchestrator=scanner,
                     market_regime_service=reader)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "regime-route-fixture", "exec"), namespace)
    return namespace["get_market_regime"], scanner


def test_api_read_ownership_regime_does_not_borrow_scanner_engine():
    reader = S(get_global=AsyncMock(return_value={"composite": "fixture"}))
    handler, scanner = regime_handler(reader)
    result = asyncio.run(handler(symbol=None))
    assert result == {"composite": "fixture"}
    scanner._detect_global_regime.assert_not_called()
    reader.get_global.assert_awaited_once()


@pytest.mark.parametrize("operation", ["create", "status", "step", "jump", "delete"])
def test_api_read_ownership_replay_operations_leave_event_loop_responsive(monkeypatch, operation):
    from backend.routers import replay
    from backend.engine.replay_engine import StepResult
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    session = S(session_id="s", symbol="BTC/USDT", mode_name="stealth", total_bars=1,
                tf_step="1h", window_start=now, window_end=now, bar_timestamps=[now], step_index=0)
    step = StepResult(0, now, now, {})
    entered, release, expired = threading.Event(), threading.Event(), threading.Event()
    def block(value):
        entered.set()
        assert release.wait(2)
        return value
    engine = S(load_session=lambda **_: block(session), get_session=lambda _: block(session),
               session_status=lambda _: block(dict(session_id="s", symbol="BTC/USDT", mode="stealth",
                                                    current_index=0, total_bars=1, tf_step="1h")),
               step=lambda *a, **k: block(step), jump_to_next_signal=lambda *a, **k: block((step, 1)),
               end_session=lambda _: block(True))
    monkeypatch.setattr(replay, "_engine_or_500", lambda: engine)
    async def scenario():
        calls = {
            "create": lambda: replay.create_session(replay.CreateSessionRequest(
                symbol="BTC/USDT", mode="stealth", window_start=now, window_end=now)),
            "status": lambda: replay.get_session_status("s"),
            "step": lambda: replay.step_session("s", replay.StepRequest()),
            "jump": lambda: replay.jump_to_next_signal("s", replay.JumpToSignalRequest()),
            "delete": lambda: replay.delete_session("s"),
        }
        def watchdog():
            expired.set()
            release.set()
        timer = threading.Timer(.5, watchdog)
        timer.start()
        task = asyncio.create_task(calls[operation]())
        try:
            await asyncio.sleep(.05)
            assert entered.is_set()
            assert not expired.is_set(), "route blocked the event loop until watchdog release"
        finally:
            release.set()
            timer.cancel()
            await task
    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["create", "step"])
def test_api_read_ownership_cancelled_replay_retains_worker_and_cleans_orphan(monkeypatch, operation):
    from backend.routers import replay
    from backend.tests.unit.test_replay_navigation_state import fixture_engine
    engine, session = fixture_engine()
    entered, release = threading.Event(), threading.Event()
    compute = engine._compute_step
    def blocked_compute(session, index):
        entered.set()
        assert release.wait(3)
        return compute(session, index)
    def load(**kwargs):
        entered.set()
        assert release.wait(3)
        return session
    engine._compute_step = blocked_compute
    engine.load_session = load
    end_session = Mock(wraps=engine.end_session)
    engine.end_session = end_session
    monkeypatch.setattr(replay, "_engine_or_500", lambda: engine)
    async def scenario():
        if operation == "create":
            call = replay.create_session(replay.CreateSessionRequest(
                symbol=session.symbol, mode="stealth", window_start=session.window_start, window_end=session.window_end))
        else:
            call = replay.step_session("session", replay.StepRequest())
        first = asyncio.create_task(call)
        try:
            while not entered.is_set():
                await asyncio.sleep(.001)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            following = asyncio.create_task(replay.get_session_status("session"))
            await asyncio.sleep(.02)
            assert not following.done() and not end_session.called
        finally:
            release.set()
        if operation == "create":
            with pytest.raises(HTTPException) as caught:
                await following
            assert caught.value.status_code == 404
            end_session.assert_called_once_with("session")
        else:
            assert (await following).current_index == 0
            assert session.step_index == 0  # cancellation does not roll back work
    asyncio.run(scenario())
