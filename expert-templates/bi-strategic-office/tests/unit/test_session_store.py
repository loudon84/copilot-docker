#!/usr/bin/env python3
"""Unit tests for SessionStore schema v2 + Fernet."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.session.session_store import SessionStore


def test_session_upsert_get_reset(tmp_path: Path):
    db = tmp_path / "sessions.db"
    store = SessionStore(str(db), encryption_key="test-key", ttl_seconds=3600)
    store.upsert(
        profile_name="p1",
        hermes_session_id="s1",
        hermes_user_id="u1",
        sqlbot_chat_id="chat-aaa",
        access_token="tok-secret",
        last_query_id="fbq_1",
        last_sql="SELECT 1",
        last_question="q",
    )
    rec = store.get(profile_name="p1", hermes_session_id="s1", hermes_user_id="u1")
    assert rec is not None
    assert rec.sqlbot_chat_id == "chat-aaa"
    assert store.access_token(rec) == "tok-secret"
    assert "tok-secret" not in (rec.access_token_encrypted or "")

    other = store.get(profile_name="p1", hermes_session_id="s2", hermes_user_id="u1")
    assert other is None

    assert store.reset(profile_name="p1", hermes_session_id="s1", hermes_user_id="u1")
    assert store.get(profile_name="p1", hermes_session_id="s1", hermes_user_id="u1") is None


def test_session_ttl_expiry(tmp_path: Path):
    db = tmp_path / "ttl.db"
    store = SessionStore(str(db), encryption_key="k", ttl_seconds=1)
    store.upsert(
        profile_name="p",
        hermes_session_id="s",
        hermes_user_id="u",
        sqlbot_chat_id="c1",
        access_token="tok",
    )
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            "UPDATE sqlbot_sessions SET expires_at=?",
            ("2000-01-01T00:00:00Z",),
        )
        conn.commit()
    assert store.get(profile_name="p", hermes_session_id="s", hermes_user_id="u") is None


def test_missing_encryption_key_fails():
    with pytest.raises(SqlbotAdapterError) as ei:
        SessionStore(":memory:", encryption_key="")
    assert ei.value.code == ErrorCode.SQLBOT_NOT_CONFIGURED
