"""Dedicated background event loop for MCP async calls (sync Hermes handlers)."""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import threading
from concurrent.futures import Future
from typing import Any, Coroutine, TypeVar

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError

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
    """Submit coroutine to the bridge loop; block until done. Cancel on timeout."""
    loop = _ensure_loop()
    fut: Future[T] = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError as exc:
        fut.cancel()
        try:
            # Give the event loop a brief window to honour cancellation.
            fut.result(timeout=2.0)
        except (concurrent.futures.CancelledError, concurrent.futures.TimeoutError, Exception):
            pass
        raise SqlbotAdapterError(
            ErrorCode.SQLBOT_TIMEOUT,
            f"SQLBot 请求超时（{timeout}s），已取消后台协程。",
            source="adapter",
            retryable=True,
        ) from exc
    except concurrent.futures.CancelledError as exc:
        raise SqlbotAdapterError(
            ErrorCode.SQLBOT_TIMEOUT,
            "SQLBot 请求已取消。",
            source="adapter",
            retryable=True,
        ) from exc


def shutdown_bridge() -> None:
    global _loop, _thread
    with _lock:
        if _loop is None:
            return
        loop = _loop

        def _cancel_all() -> None:
            for task in asyncio.all_tasks(loop):
                task.cancel()
            loop.stop()

        loop.call_soon_threadsafe(_cancel_all)
        if _thread is not None:
            _thread.join(timeout=5)
        _loop = None
        _thread = None


atexit.register(shutdown_bridge)
