"""Cancellation controls responses, not the lifetime of synchronous work."""
import asyncio
import threading
from unittest.mock import Mock

import pytest

from backend.shared.async_worker import SerializedWorker


@pytest.mark.parametrize("late_failure", [False, True])
def test_async_worker_cancellation_keeps_admission_and_observes_late_result(late_failure, caplog, monkeypatch):
    async def scenario():
        loop = asyncio.get_running_loop()
        submit = loop.run_in_executor
        submissions = []
        def tracked(pool, operation, *args):
            submissions.append(operation)
            return submit(pool, operation, *args)
        monkeypatch.setattr(loop, "run_in_executor", tracked)
        gate = SerializedWorker()
        entered, release = threading.Event(), threading.Event()
        def blocking():
            entered.set()
            assert release.wait(3)
            if late_failure:
                raise ValueError("late fixture failure")
            return 1
        operation = Mock(return_value=2)
        first = asyncio.create_task(gate.run(blocking))
        try:
            while not entered.is_set():
                await asyncio.sleep(.001)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            # Ownership is attached to the physical future, not a cancellable task.
            assert len(gate._abandoned) == 1
            waiters = [asyncio.create_task(gate.run(operation)) for _ in range(20)]
            await asyncio.sleep(.02)
            assert not operation.called and len(submissions) == 1
            waiters[0].cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiters[0]
        finally:
            release.set()
        assert await asyncio.gather(*waiters[1:]) == [2] * 19
        assert operation.call_count == 19
        if late_failure:
            assert "late fixture failure" in caplog.text
    asyncio.run(scenario())


def test_async_worker_cancelled_creation_cleanup_keeps_admission():
    async def scenario():
        gate = SerializedWorker()
        entered, release, cleaning, cleaned = [threading.Event() for _ in range(4)]
        def load():
            entered.set()
            assert release.wait(3)
            return "created-session"
        def cleanup(value):
            assert value == "created-session"
            cleaning.set()
            assert cleaned.wait(3)
        next_operation = Mock(return_value="next")
        first = asyncio.create_task(gate.run(load, on_abandon=cleanup))
        second = None
        try:
            while not entered.is_set():
                await asyncio.sleep(.001)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            release.set()
            while not cleaning.is_set():
                await asyncio.sleep(.001)
            second = asyncio.create_task(gate.run(next_operation))
            await asyncio.sleep(.02)
            assert not next_operation.called
        finally:
            release.set()
            cleaned.set()
        assert await second == "next"
    asyncio.run(scenario())


def test_async_worker_releases_admission_after_synchronous_failure():
    async def scenario():
        gate = SerializedWorker()
        with pytest.raises(ValueError, match="fixture"):
            await gate.run(Mock(side_effect=ValueError("fixture")))
        assert await gate.run(lambda: 3) == 3
    asyncio.run(scenario())


def test_async_worker_cleanup_survives_a_drain_cancelled_before_first_step(monkeypatch):
    async def scenario():
        gate = SerializedWorker()
        entered, release = threading.Event(), threading.Event()
        create_task = asyncio.create_task
        def cancel_unstarted_drain(coro, **kwargs):
            task = create_task(coro, **kwargs)
            if coro.cr_code.co_name == "_drain":
                task.cancel()
            return task
        monkeypatch.setattr(asyncio, "create_task", cancel_unstarted_drain)
        def load():
            entered.set()
            assert release.wait(3)
            return "session"
        cleanup = Mock()
        task = asyncio.create_task(gate.run(load, on_abandon=cleanup))
        try:
            while not entered.is_set():
                await asyncio.sleep(.001)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        assert await asyncio.wait_for(gate.run(lambda: "next"), timeout=1) == "next"
        cleanup.assert_called_once_with("session")
    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["submission", "execution"])
def test_async_worker_cleanup_failure_is_logged_and_releases_admission(monkeypatch, caplog, failure):
    async def scenario():
        gate = SerializedWorker()
        entered, release = threading.Event(), threading.Event()
        def load():
            entered.set()
            assert release.wait(3)
            return "session"
        cleanup = Mock(side_effect=RuntimeError("cleanup fixture failed"))
        loop = asyncio.get_running_loop()
        submit = loop.run_in_executor
        def controlled(pool, fn, *args):
            if fn is cleanup and failure == "submission":
                raise RuntimeError("cleanup submission fixture failed")
            return submit(pool, fn, *args)
        monkeypatch.setattr(loop, "run_in_executor", controlled)
        task = asyncio.create_task(gate.run(load, on_abandon=cleanup))
        try:
            while not entered.is_set():
                await asyncio.sleep(.001)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        assert await asyncio.wait_for(gate.run(lambda: "next"), timeout=1) == "next"
        assert "fixture failed" in caplog.text
        assert not gate._abandoned
    asyncio.run(scenario())
