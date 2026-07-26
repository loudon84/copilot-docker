"""Dedicated background event loop for MCP async calls (sync Hermes handlers)."""

from __future__ import annotations

import asyncio
import atexit
import threading
from concurrent.futures import Future
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    with _lock:
        if _loop is not None and _loop.is_running():
            return _loop

        loop = asyncio.new_event_loop()

        def _runner() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(target=_runner, name="sqlbot-mcp-async-bridge", daemon=True)
        t.start()
        _loop = loop
        _thread = t
        return loop


def run_coro(coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
    """Submit coroutine to the bridge loop; block until done. Never uses asyncio.run()."""
    loop = _ensure_loop()
    fut: Future[T] = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result(timeout=timeout)


def shutdown_bridge() -> None:
    global _loop, _thread
    with _lock:
        if _loop is None:
            return
        loop = _loop
        loop.call_soon_threadsafe(loop.stop)
        if _thread is not None:
            _thread.join(timeout=5)
        _loop = None
        _thread = None


atexit.register(shutdown_bridge)
