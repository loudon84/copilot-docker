#!/usr/bin/env python3
"""Unit tests for SessionStore."""

from __future__ import annotations

import sys
import time
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.session.session_store import SessionStore


def test_session_upsert_get_reset(tmp_path: Path):
    db = tmp_path / "sessions.db"
    store = SessionStore(str(db), key_material="test-key", ttl_seconds=3600)
    store.upsert(
        hermes_profile="p1",
        hermes_session_id="s1",
        hermes_user_id="u1",
        sqlbot_chat_id="chat-aaa",
        access_token="tok-secret",
        token_expires_at=time.time() + 3600,
        last_query_id="fbq_1",
        last_sql="SELECT 1",
        last_question="q",
    )
    rec = store.get(hermes_profile="p1", hermes_session_id="s1", hermes_user_id="u1")
    assert rec is not None
    assert rec.sqlbot_chat_id == "chat-aaa"
    assert rec.access_token("test-key") == "tok-secret"
    assert "tok-secret" not in (rec.token_encrypted or "")

    # Isolation
    other = store.get(hermes_profile="p1", hermes_session_id="s2", hermes_user_id="u1")
    assert other is None

    assert store.reset(hermes_profile="p1", hermes_session_id="s1", hermes_user_id="u1")
    assert store.get(hermes_profile="p1", hermes_session_id="s1", hermes_user_id="u1") is None


def test_session_ttl_expiry(tmp_path: Path):
    db = tmp_path / "ttl.db"
    store = SessionStore(str(db), key_material="k", ttl_seconds=1)
    store.upsert(
        hermes_profile="p",
        hermes_session_id="s",
        hermes_user_id="u",
        sqlbot_chat_id="c1",
    )
    # Force expiry
    import sqlite3

    with sqlite3.connect(str(db)) as conn:
        conn.execute("UPDATE sqlbot_sessions SET expires_at=?", (time.time() - 10,))
        conn.commit()
    assert store.get(hermes_profile="p", hermes_session_id="s", hermes_user_id="u") is None
