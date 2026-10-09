"""Bound blocking work without releasing its ownership when a request cancels."""
import asyncio
import logging
from functools import partial

logger = logging.getLogger(__name__)


class SerializedWorker:
    """One admitted worker per owner/event loop; queued requests use no threads."""

    def __init__(self):
        self._slot = asyncio.Semaphore(1)
        self._abandoned = set()

    async def run(self, operation, *args, on_abandon=None, **kwargs):
        await self._slot.acquire()
        release_here = True
        try:
            loop = asyncio.get_running_loop()
            worker = loop.run_in_executor(None, partial(operation, *args, **kwargs))
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                # Future callbacks cannot be cancelled before a coroutine starts.
                # Keep ownership until the worker AND optional cleanup complete.
                self._abandoned.add(worker)
                worker.add_done_callback(partial(self._finish_abandoned, on_abandon))
                release_here = False
                raise
        finally:
            if release_here:
                self._slot.release()

    def _finish_abandoned(self, on_abandon, worker):
        self._abandoned.discard(worker)
        try:
            result = worker.result()
            if on_abandon is not None:
                cleanup = asyncio.get_running_loop().run_in_executor(None, on_abandon, result)
                self._abandoned.add(cleanup)
                cleanup.add_done_callback(self._finish_cleanup)
                return
        except asyncio.CancelledError:
            logger.error("Abandoned executor future was unexpectedly cancelled")
        except Exception:
            logger.exception("Cancelled request's worker or cleanup submission failed")
        self._slot.release()

    def _finish_cleanup(self, cleanup):
        self._abandoned.discard(cleanup)
        try:
            cleanup.result()
        except asyncio.CancelledError:
            logger.error("Abandoned cleanup future was unexpectedly cancelled")
        except Exception:
            logger.exception("Cancelled request's cleanup failed")
        finally:
            self._slot.release()
