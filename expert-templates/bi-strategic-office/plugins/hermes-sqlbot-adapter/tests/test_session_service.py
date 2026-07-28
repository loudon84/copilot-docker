"""Session store migration, token expiry, ask/followup semantics."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sqlbot_adapter.client.mcp_client import QuestionResult
from sqlbot_adapter.config import AdapterConfig
from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.service import SQLBotService
from sqlbot_adapter.session.models import SCHEMA_VERSION
from sqlbot_adapter.session.session_store import SessionStore


def _fernet_key() -> str:
    digest = hashlib.sha256(b"test-sqlbot-key").digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def _cfg(db: str, audit: str) -> AdapterConfig:
    return AdapterConfig(
        mcp_url="http://example/sse",
        username="u",
        password="p",
        workspace_id="1",
        default_datasource_id="1",
        session_encryption_key=_fernet_key(),
        state_db=db,
        audit_dir=audit,
        datasource_aliases={"sales_profit": "1"},
    )


def test_schema_v2_to_v3_migration(tmp_path: Path):
    db = tmp_path / "s.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE sqlbot_sessions (
                profile_name TEXT NOT NULL,
                hermes_session_id TEXT NOT NULL,
                hermes_user_id TEXT NOT NULL,
                access_token_encrypted TEXT NOT NULL,
                sqlbot_chat_id TEXT NOT NULL,
                workspace_id TEXT,
                datasource_id TEXT,
                token_expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_query_id TEXT,
                last_sql TEXT,
                last_question TEXT,
                last_title TEXT,
                last_payload_json TEXT,
                PRIMARY KEY (profile_name, hermes_session_id, hermes_user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE sqlbot_queries (
                query_id TEXT PRIMARY KEY,
                profile_name TEXT NOT NULL,
                hermes_session_id TEXT NOT NULL,
                hermes_user_id TEXT NOT NULL,
                question TEXT NOT NULL,
                generated_sql TEXT,
                datasource_id TEXT,
                workspace_id TEXT,
                status TEXT NOT NULL,
                error_code TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE TABLE sqlbot_schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO sqlbot_schema_meta(key, value) VALUES ('schema_version', '2')"
        )
        conn.commit()

    store = SessionStore(str(db), encryption_key=_fernet_key())
    with sqlite3.connect(db) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(sqlbot_sessions)")}
        assert "last_upstream_record_id" in cols
        assert "session_version" in cols
        ver = conn.execute(
            "SELECT value FROM sqlbot_schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert int(ver) == SCHEMA_VERSION


def test_token_expired_flag(tmp_path: Path):
    store = SessionStore(str(tmp_path / "t.db"), encryption_key=_fernet_key())
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    store.upsert(
        profile_name="p",
        hermes_session_id="s",
        hermes_user_id="u",
        access_token="tok",
        sqlbot_chat_id="9",
        token_expires_at=past,
    )
    rec = store.get(profile_name="p", hermes_session_id="s", hermes_user_id="u")
    assert rec is not None
    assert store.is_token_expired(rec)


def test_ask_replaces_chat_and_followup_reuses(tmp_path: Path):
    cfg = _cfg(str(tmp_path / "a.db"), str(tmp_path / "audit"))
    svc = SQLBotService(cfg)
    client = MagicMock()
    svc.client = client

    client.start.side_effect = [
        {"access_token": "t1", "chat_id": "100", "expires_in": 3600},
        {"access_token": "t2", "chat_id": "200", "expires_in": 3600},
    ]

    def _ok_result(chat: str):
        return QuestionResult(
            sql="SELECT ar_trx_number FROM t WHERE ar_trx_number = '101IN26070194'",
            columns=["ar_trx_number"],
            rows=[{"ar_trx_number": "101IN26070194"}],
            title="ok",
            chat_id=chat,
            upstream_record_id="60",
            raw={"success": True},
        )

    client.question.side_effect = [
        _ok_result("100"),
        _ok_result("100"),
        _ok_result("200"),
    ]

    ctx_a = {"session_id": "sess-a", "user_id": "user-a", "profile": "default"}
    out1 = svc.ask(
        "查询交易凭证编号101IN26070194的数据",
        datasource_key="sales_profit",
        hermes_ctx=ctx_a,
    )
    assert out1["success"] is True
    assert out1["upstream_record_id"] == "60"
    assert "chat_id" not in json.dumps(out1)

    out2 = svc.followup("只保留销售额", hermes_ctx=ctx_a)
    assert out2["success"] is True
    # followup must reuse chat 100
    assert client.question.call_args_list[1].kwargs["chat_id"] == "100"

    out3 = svc.ask(
        "查询交易凭证编号101IN26070194的数据",
        datasource_key="sales_profit",
        hermes_ctx=ctx_a,
    )
    assert out3["success"] is True
    assert client.start.call_count == 2
    assert client.question.call_args_list[2].kwargs["chat_id"] == "200"


def test_two_sessions_isolated(tmp_path: Path):
    cfg = _cfg(str(tmp_path / "b.db"), str(tmp_path / "audit2"))
    svc = SQLBotService(cfg)
    client = MagicMock()
    svc.client = client
    client.start.side_effect = [
        {"access_token": "ta", "chat_id": "11", "expires_in": 3600},
        {"access_token": "tb", "chat_id": "22", "expires_in": 3600},
    ]
    client.question.side_effect = [
        QuestionResult(
            sql="SELECT ar_trx_number FROM t WHERE ar_trx_number = '101IN26070194'",
            columns=["ar_trx_number"],
            rows=[{"ar_trx_number": "101IN26070194"}],
            title="a",
            chat_id="11",
            upstream_record_id="1",
        ),
        QuestionResult(
            sql="SELECT ar_trx_number FROM t WHERE ar_trx_number = '101IN26070194'",
            columns=["ar_trx_number"],
            rows=[{"ar_trx_number": "101IN26070194"}],
            title="b",
            chat_id="22",
            upstream_record_id="2",
        ),
    ]
    svc.ask(
        "查询交易凭证编号101IN26070194的数据",
        hermes_ctx={"session_id": "A", "user_id": "u"},
    )
    svc.ask(
        "查询交易凭证编号101IN26070194的数据",
        hermes_ctx={"session_id": "B", "user_id": "u"},
    )
    sa = svc.store.get(profile_name="default", hermes_session_id="A", hermes_user_id="u")
    sb = svc.store.get(profile_name="default", hermes_session_id="B", hermes_user_id="u")
    assert sa is not None and sb is not None
    assert sa.sqlbot_chat_id == "11"
    assert sb.sqlbot_chat_id == "22"


def test_followup_token_expired(tmp_path: Path):
    cfg = _cfg(str(tmp_path / "c.db"), str(tmp_path / "audit3"))
    svc = SQLBotService(cfg)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    svc.store.upsert(
        profile_name="default",
        hermes_session_id="s",
        hermes_user_id="u",
        access_token="tok",
        sqlbot_chat_id="9",
        token_expires_at=past,
    )
    with pytest.raises(SqlbotAdapterError) as ei:
        svc.followup("继续", hermes_ctx={"session_id": "s", "user_id": "u"})
    assert ei.value.code == ErrorCode.SQLBOT_SESSION_EXPIRED


def test_explain_from_history(tmp_path: Path):
    cfg = _cfg(str(tmp_path / "d.db"), str(tmp_path / "audit4"))
    svc = SQLBotService(cfg)
    svc.store.upsert(
        profile_name="default",
        hermes_session_id="s",
        hermes_user_id="u",
        access_token="tok",
        sqlbot_chat_id="9",
        last_query_id="fbq_recent",
        last_sql="SELECT 1",
        last_question="q",
        last_title="t",
    )
    svc.store.record_query(
        query_id="fbq_old",
        profile_name="default",
        hermes_session_id="s",
        hermes_user_id="u",
        question="old q",
        generated_sql="SELECT 2",
        title="old title",
        upstream_record_id="99",
        query_payload_json=json.dumps({"query": {"filters": []}, "columns": []}),
    )
    out = svc.explain(query_id="fbq_old", hermes_ctx={"session_id": "s", "user_id": "u"})
    assert out["query_id"] == "fbq_old"
    assert out["query"]["sql"] == "SELECT 2"
    assert out["upstream_record_id"] == "99"
    assert out["rows"] == []
