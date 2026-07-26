"""SQLite session store schema v2 with Fernet-encrypted tokens."""

from __future__ import annotations

import base64
import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.session.models import SCHEMA_VERSION, SessionRecord

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fernet_from_key(key_material: str) -> "Fernet":
    if Fernet is None:
        raise SqlbotAdapterError(
            ErrorCode.SQLBOT_NOT_CONFIGURED,
            "缺少 cryptography，无法加密 Token",
        )
    if not (key_material or "").strip():
        raise SqlbotAdapterError(
            ErrorCode.SQLBOT_NOT_CONFIGURED,
            "缺少 SQLBOT_SESSION_ENCRYPTION_KEY，禁止明文存储 Token",
        )
    raw = key_material.strip().encode("utf-8")
    # Accept raw Fernet key or derive from passphrase
    try:
        if len(raw) == 44:
            return Fernet(raw)
    except Exception:
        pass
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class SessionStore:
    def __init__(
        self,
        db_path: str,
        *,
        encryption_key: str,
        ttl_seconds: int = 86400,
    ):
        self.db_path = str(db_path)
        self.ttl_seconds = int(ttl_seconds)
        self._fernet = _fernet_from_key(encryption_key)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sqlbot_sessions (
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
                CREATE TABLE IF NOT EXISTS sqlbot_queries (
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
                """
                CREATE TABLE IF NOT EXISTS sqlbot_schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO sqlbot_schema_meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            conn.commit()

    def encrypt_token(self, token: str) -> str:
        if not token:
            return ""
        return self._fernet.encrypt(token.encode("utf-8")).decode("ascii")

    def decrypt_token(self, blob: str) -> str:
        if not blob:
            return ""
        try:
            return self._fernet.decrypt(blob.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_SESSION_EXPIRED,
                "会话 Token 解密失败，请重新登录。",
            ) from exc

    def get(
        self,
        *,
        profile_name: str,
        hermes_session_id: str,
        hermes_user_id: str,
    ) -> Optional[SessionRecord]:
        profile = profile_name or "default"
        session_id = hermes_session_id or "default"
        user_id = hermes_user_id or "local-cli"
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM sqlbot_sessions
                WHERE profile_name=? AND hermes_session_id=? AND hermes_user_id=?
                """,
                (profile, session_id, user_id),
            ).fetchone()
        if row is None:
            return None
        rec = self._row_to_record(row)
        if rec.expires_at:
            try:
                exp = datetime.strptime(rec.expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                if _utcnow() > exp:
                    self.reset(
                        profile_name=profile,
                        hermes_session_id=session_id,
                        hermes_user_id=user_id,
                    )
                    return None
            except ValueError:
                pass
        return rec

    def upsert(
        self,
        *,
        profile_name: str,
        hermes_session_id: str,
        hermes_user_id: str,
        access_token: str = "",
        sqlbot_chat_id: str = "",
        workspace_id: str = "",
        datasource_id: str = "",
        token_expires_at: str = "",
        last_query_id: str = "",
        last_sql: str = "",
        last_question: str = "",
        last_title: str = "",
        last_payload_json: str = "",
    ) -> SessionRecord:
        profile = profile_name or "default"
        session_id = hermes_session_id or "default"
        user_id = hermes_user_id or "local-cli"
        now = _utcnow()
        existing = self.get(
            profile_name=profile,
            hermes_session_id=session_id,
            hermes_user_id=user_id,
        )
        created_at = existing.created_at if existing else _iso(now)
        token_blob = (
            self.encrypt_token(access_token)
            if access_token
            else (existing.access_token_encrypted if existing else "")
        )
        if not token_blob and access_token == "":
            # allow empty only when existing has token
            token_blob = existing.access_token_encrypted if existing else ""
        if not token_blob:
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_AUTH_FAILED,
                "无法保存空 Token",
            )
        chat_id = sqlbot_chat_id or (existing.sqlbot_chat_id if existing else "")
        if not chat_id:
            chat_id = ""
        expires_at = _iso(now + timedelta(seconds=self.ttl_seconds))
        rec = SessionRecord(
            profile_name=profile,
            hermes_session_id=session_id,
            hermes_user_id=user_id,
            access_token_encrypted=token_blob,
            sqlbot_chat_id=str(chat_id),
            workspace_id=workspace_id or (existing.workspace_id if existing else ""),
            datasource_id=datasource_id or (existing.datasource_id if existing else ""),
            token_expires_at=token_expires_at
            or (existing.token_expires_at if existing else ""),
            created_at=created_at,
            updated_at=_iso(now),
            expires_at=expires_at,
            last_query_id=last_query_id or (existing.last_query_id if existing else ""),
            last_sql=last_sql if last_sql != "" else (existing.last_sql if existing else ""),
            last_question=last_question
            if last_question != ""
            else (existing.last_question if existing else ""),
            last_title=last_title if last_title != "" else (existing.last_title if existing else ""),
            last_payload_json=last_payload_json
            if last_payload_json != ""
            else (existing.last_payload_json if existing else ""),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sqlbot_sessions (
                    profile_name, hermes_session_id, hermes_user_id,
                    access_token_encrypted, sqlbot_chat_id,
                    workspace_id, datasource_id, token_expires_at,
                    created_at, updated_at, expires_at,
                    last_query_id, last_sql, last_question, last_title, last_payload_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(profile_name, hermes_session_id, hermes_user_id)
                DO UPDATE SET
                    access_token_encrypted=excluded.access_token_encrypted,
                    sqlbot_chat_id=excluded.sqlbot_chat_id,
                    workspace_id=excluded.workspace_id,
                    datasource_id=excluded.datasource_id,
                    token_expires_at=excluded.token_expires_at,
                    updated_at=excluded.updated_at,
                    expires_at=excluded.expires_at,
                    last_query_id=excluded.last_query_id,
                    last_sql=excluded.last_sql,
                    last_question=excluded.last_question,
                    last_title=excluded.last_title,
                    last_payload_json=excluded.last_payload_json
                """,
                (
                    rec.profile_name,
                    rec.hermes_session_id,
                    rec.hermes_user_id,
                    rec.access_token_encrypted,
                    rec.sqlbot_chat_id,
                    rec.workspace_id,
                    rec.datasource_id,
                    rec.token_expires_at,
                    rec.created_at,
                    rec.updated_at,
                    rec.expires_at,
                    rec.last_query_id,
                    rec.last_sql,
                    rec.last_question,
                    rec.last_title,
                    rec.last_payload_json,
                ),
            )
            conn.commit()
        return rec

    def reset(
        self,
        *,
        profile_name: str,
        hermes_session_id: str,
        hermes_user_id: str,
    ) -> bool:
        profile = profile_name or "default"
        session_id = hermes_session_id or "default"
        user_id = hermes_user_id or "local-cli"
        with self._connect() as conn:
            cur = conn.execute(
                """
                DELETE FROM sqlbot_sessions
                WHERE profile_name=? AND hermes_session_id=? AND hermes_user_id=?
                """,
                (profile, session_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def record_query(
        self,
        *,
        query_id: str,
        profile_name: str,
        hermes_session_id: str,
        hermes_user_id: str,
        question: str,
        generated_sql: str = "",
        datasource_id: str = "",
        workspace_id: str = "",
        status: str = "ok",
        error_code: str = "",
        error_message: str = "",
    ) -> None:
        now = _iso(_utcnow())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sqlbot_queries (
                    query_id, profile_name, hermes_session_id, hermes_user_id,
                    question, generated_sql, datasource_id, workspace_id,
                    status, error_code, error_message, created_at, completed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    query_id,
                    profile_name or "default",
                    hermes_session_id or "default",
                    hermes_user_id or "local-cli",
                    (question or "")[:2000],
                    (generated_sql or "")[:8000],
                    datasource_id,
                    workspace_id,
                    status,
                    error_code,
                    (error_message or "")[:2000],
                    now,
                    now,
                ),
            )
            conn.commit()

    def access_token(self, rec: SessionRecord) -> str:
        return self.decrypt_token(rec.access_token_encrypted)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> SessionRecord:
        keys = set(row.keys())
        return SessionRecord(
            profile_name=row["profile_name"],
            hermes_session_id=row["hermes_session_id"],
            hermes_user_id=row["hermes_user_id"],
            access_token_encrypted=row["access_token_encrypted"] or "",
            sqlbot_chat_id=str(row["sqlbot_chat_id"] or ""),
            workspace_id=row["workspace_id"] or "",
            datasource_id=row["datasource_id"] or "",
            token_expires_at=row["token_expires_at"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
            expires_at=row["expires_at"] or "",
            last_query_id=(row["last_query_id"] if "last_query_id" in keys else "") or "",
            last_sql=(row["last_sql"] if "last_sql" in keys else "") or "",
            last_question=(row["last_question"] if "last_question" in keys else "") or "",
            last_title=(row["last_title"] if "last_title" in keys else "") or "",
            last_payload_json=(row["last_payload_json"] if "last_payload_json" in keys else "")
            or "",
        )
