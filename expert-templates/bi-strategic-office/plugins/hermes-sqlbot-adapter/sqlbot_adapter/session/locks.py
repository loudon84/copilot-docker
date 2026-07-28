"""In-process session locks for serial ask/followup per Hermes session."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Dict, Iterator


class SessionLockManager:
    """Process-local RLock keyed by profile/session/user."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: Dict[str, threading.RLock] = {}

    @staticmethod
    def make_key(profile_name: str, hermes_session_id: str, hermes_user_id: str) -> str:
        return f"{profile_name or 'default'}/{hermes_session_id or ''}/{hermes_user_id or ''}"

    def _get_lock(self, key: str) -> threading.RLock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._locks[key] = lock
            return lock

    @contextmanager
    def acquire(
        self,
        profile_name: str,
        hermes_session_id: str,
        hermes_user_id: str,
    ) -> Iterator[None]:
        lock = self._get_lock(self.make_key(profile_name, hermes_session_id, hermes_user_id))
        lock.acquire()
        try:
            yield
        finally:
            lock.release()


_GLOBAL_LOCKS = SessionLockManager()


def get_session_locks() -> SessionLockManager:
    return _GLOBAL_LOCKS
