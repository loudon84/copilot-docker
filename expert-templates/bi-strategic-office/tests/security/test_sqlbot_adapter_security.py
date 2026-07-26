#!/usr/bin/env python3
"""Security tests specific to SQLBot adapter guards and secret scrubbing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = PACKAGE_ROOT / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.contracts import ErrorCode, SqlbotAdapterError, json_ok, scrub_secrets
from sqlbot_adapter.security.query_guard import assert_readonly_sql, guard_sql
from sqlbot_adapter.session.session_store import SessionStore


def test_password_and_token_not_in_tool_result():
    payload = {
        "success": True,
        "access_token": "should-not-leak",
        "password": "secret",
        "chat_id": "chat-1",
        "rows": [{"a": 1}],
    }
    text = json_ok(payload)
    assert "should-not-leak" not in text
    assert "secret" not in text
    assert "chat-1" not in text
    data = json.loads(text)
    assert data["rows"] == [{"a": 1}]


def test_drop_table_rejected():
    with pytest.raises(SqlbotAdapterError) as ei:
        assert_readonly_sql("DROP TABLE ar_transactions")
    assert ei.value.code == ErrorCode.UNSAFE_SQL


def test_filter_loss_blocks_rows():
    with pytest.raises(SqlbotAdapterError) as ei:
        guard_sql(
            "查询凭证号101IN26070199的交易明细",
            "SELECT TOP 10 * FROM ar_transactions",
        )
    assert ei.value.code == ErrorCode.FILTER_NOT_PRESERVED


def test_sessions_isolated(tmp_path: Path):
    store = SessionStore(str(tmp_path / "s.db"), encryption_key="k")
    store.upsert(
        profile_name="p",
        hermes_session_id="s1",
        hermes_user_id="u1",
        sqlbot_chat_id="chat-s1",
        access_token="tok1",
    )
    store.upsert(
        profile_name="p",
        hermes_session_id="s2",
        hermes_user_id="u1",
        sqlbot_chat_id="chat-s2",
        access_token="tok2",
    )
    a = store.get(profile_name="p", hermes_session_id="s1", hermes_user_id="u1")
    b = store.get(profile_name="p", hermes_session_id="s2", hermes_user_id="u1")
    assert a and b
    assert a.sqlbot_chat_id != b.sqlbot_chat_id
    assert store.access_token(a) != store.access_token(b)


def test_scrub_nested_secrets():
    cleaned = scrub_secrets({"meta": {"token": "x", "ok": 1}, "authorization": "Bearer x"})
    assert "token" not in cleaned["meta"]
    assert cleaned["meta"]["ok"] == 1
    assert "authorization" not in cleaned


def test_encryption_key_required(tmp_path: Path):
    with pytest.raises(SqlbotAdapterError) as ei:
        SessionStore(str(tmp_path / "x.db"), encryption_key="  ")
    assert ei.value.code == ErrorCode.SQLBOT_NOT_CONFIGURED
