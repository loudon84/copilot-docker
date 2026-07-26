"""SQLite session store: Hermes session <-> SQLBot chat_id mapping."""

from __future__ import annotations

import base64
import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _encrypt_token(token: str, key_material: str) -> str:
    """Lightweight reversible obfuscation (not a KMS). Avoid plain text on disk."""
    if not token:
        return ""
    key = hashlib.sha256((key_material or "sqlbot-adapter").encode("utf-8")).digest()
    raw = token.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    return base64.urlsafe_b64encode(xored).decode("ascii")


def _decrypt_token(blob: str, key_material: str) -> str:
    if not blob:
        return ""
    key = hashlib.sha256((key_material or "sqlbot-adapter").encode("utf-8")).digest()
    try:
        raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    except Exception:
        return ""
    plain = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    return plain.decode("utf-8", errors="ignore")


@dataclass
class SessionRecord:
    hermes_profile: str
    hermes_session_id: str
    hermes_user_id: str
    sqlbot_chat_id: str = ""
    sqlbot_workspace_id: str = ""
    sqlbot_datasource_id: str = ""
    token_encrypted: str = ""
    token_expires_at: float = 0.0
    last_query_id: str = ""
    last_sql: str = ""
    last_question: str = ""
    last_title: str = ""
    last_payload_json: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    expires_at: float = 0.0

    def access_token(self, key_material: str) -> str:
        return _decrypt_token(self.token_encrypted, key_material)


class SessionStore:
    def __init__(self, db_path: str, *, key_material: str = "", ttl_seconds: int = 86400):
        self.db_path = str(db_path)
        self.key_material = key_material or "sqlbot-adapter"
        self.ttl_seconds = int(ttl_seconds)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sqlbot_sessions (
                    hermes_profile TEXT NOT NULL,
                    hermes_session_id TEXT NOT NULL,
                    hermes_user_id TEXT NOT NULL,
                    sqlbot_chat_id TEXT,
                    sqlbot_workspace_id TEXT,
                    sqlbot_datasource_id TEXT,
                    token_encrypted TEXT,
                    token_expires_at REAL,
                    last_query_id TEXT,
                    last_sql TEXT,
                    last_question TEXT,
                    last_title TEXT,
                    last_payload_json TEXT,
                    created_at REAL,
                    updated_at REAL,
                    expires_at REAL,
                    PRIMARY KEY (hermes_profile, hermes_session_id, hermes_user_id)
                )
                """
            )
            conn.commit()

    def get(
        self,
        *,
        hermes_profile: str,
        hermes_session_id: str,
        hermes_user_id: str = "",
    ) -> Optional[SessionRecord]:
        profile = hermes_profile or "default"
        session_id = hermes_session_id or "default"
        user_id = hermes_user_id or "anonymous"
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM sqlbot_sessions
                WHERE hermes_profile=? AND hermes_session_id=? AND hermes_user_id=?
                """,
                (profile, session_id, user_id),
            ).fetchone()
        if row is None:
            return None
        rec = self._row_to_record(row)
        if rec.expires_at and time.time() > rec.expires_at:
            self.reset(
                hermes_profile=profile,
                hermes_session_id=session_id,
                hermes_user_id=user_id,
            )
            return None
        return rec

    def upsert(
        self,
        *,
        hermes_profile: str,
        hermes_session_id: str,
        hermes_user_id: str = "",
        sqlbot_chat_id: str = "",
        sqlbot_workspace_id: str = "",
        sqlbot_datasource_id: str = "",
        access_token: str = "",
        token_expires_at: float = 0.0,
        last_query_id: str = "",
        last_sql: str = "",
        last_question: str = "",
        last_title: str = "",
        last_payload_json: str = "",
    ) -> SessionRecord:
        profile = hermes_profile or "default"
        session_id = hermes_session_id or "default"
        user_id = hermes_user_id or "anonymous"
        now = time.time()
        existing = self.get(
            hermes_profile=profile,
            hermes_session_id=session_id,
            hermes_user_id=user_id,
        )
        created_at = existing.created_at if existing else now
        token_blob = (
            _encrypt_token(access_token, self.key_material)
            if access_token
            else (existing.token_encrypted if existing else "")
        )
        if not access_token and existing:
            token_expires_at = token_expires_at or existing.token_expires_at
        expires_at = now + self.ttl_seconds
        rec = SessionRecord(
            hermes_profile=profile,
            hermes_session_id=session_id,
            hermes_user_id=user_id,
            sqlbot_chat_id=sqlbot_chat_id or (existing.sqlbot_chat_id if existing else ""),
            sqlbot_workspace_id=sqlbot_workspace_id
            or (existing.sqlbot_workspace_id if existing else ""),
            sqlbot_datasource_id=sqlbot_datasource_id
            or (existing.sqlbot_datasource_id if existing else ""),
            token_encrypted=token_blob,
            token_expires_at=token_expires_at
            or (existing.token_expires_at if existing else 0.0),
            last_query_id=last_query_id or (existing.last_query_id if existing else ""),
            last_sql=last_sql if last_sql != "" else (existing.last_sql if existing else ""),
            last_question=last_question
            if last_question != ""
            else (existing.last_question if existing else ""),
            last_title=last_title if last_title != "" else (existing.last_title if existing else ""),
            last_payload_json=last_payload_json
            if last_payload_json != ""
            else (existing.last_payload_json if existing else ""),
            created_at=created_at,
            updated_at=now,
            expires_at=expires_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sqlbot_sessions (
                    hermes_profile, hermes_session_id, hermes_user_id,
                    sqlbot_chat_id, sqlbot_workspace_id, sqlbot_datasource_id,
                    token_encrypted, token_expires_at, last_query_id,
                    last_sql, last_question, last_title, last_payload_json,
                    created_at, updated_at, expires_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(hermes_profile, hermes_session_id, hermes_user_id)
                DO UPDATE SET
                    sqlbot_chat_id=excluded.sqlbot_chat_id,
                    sqlbot_workspace_id=excluded.sqlbot_workspace_id,
                    sqlbot_datasource_id=excluded.sqlbot_datasource_id,
                    token_encrypted=excluded.token_encrypted,
                    token_expires_at=excluded.token_expires_at,
                    last_query_id=excluded.last_query_id,
                    last_sql=excluded.last_sql,
                    last_question=excluded.last_question,
                    last_title=excluded.last_title,
                    last_payload_json=excluded.last_payload_json,
                    updated_at=excluded.updated_at,
                    expires_at=excluded.expires_at
                """,
                (
                    rec.hermes_profile,
                    rec.hermes_session_id,
                    rec.hermes_user_id,
                    rec.sqlbot_chat_id,
                    rec.sqlbot_workspace_id,
                    rec.sqlbot_datasource_id,
                    rec.token_encrypted,
                    rec.token_expires_at,
                    rec.last_query_id,
                    rec.last_sql,
                    rec.last_question,
                    rec.last_title,
                    rec.last_payload_json,
                    rec.created_at,
                    rec.updated_at,
                    rec.expires_at,
                ),
            )
            conn.commit()
        return rec

    def reset(
        self,
        *,
        hermes_profile: str,
        hermes_session_id: str,
        hermes_user_id: str = "",
    ) -> bool:
        profile = hermes_profile or "default"
        session_id = hermes_session_id or "default"
        user_id = hermes_user_id or "anonymous"
        with self._connect() as conn:
            cur = conn.execute(
                """
                DELETE FROM sqlbot_sessions
                WHERE hermes_profile=? AND hermes_session_id=? AND hermes_user_id=?
                """,
                (profile, session_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            hermes_profile=row["hermes_profile"],
            hermes_session_id=row["hermes_session_id"],
            hermes_user_id=row["hermes_user_id"],
            sqlbot_chat_id=row["sqlbot_chat_id"] or "",
            sqlbot_workspace_id=row["sqlbot_workspace_id"] or "",
            sqlbot_datasource_id=row["sqlbot_datasource_id"] or "",
            token_encrypted=row["token_encrypted"] or "",
            token_expires_at=float(row["token_expires_at"] or 0),
            last_query_id=row["last_query_id"] or "",
            last_sql=row["last_sql"] or "",
            last_question=row["last_question"] or "",
            last_title=row["last_title"] or "",
            last_payload_json=row["last_payload_json"] or "",
            created_at=float(row["created_at"] or 0),
            updated_at=float(row["updated_at"] or 0),
            expires_at=float(row["expires_at"] or 0),
        )
