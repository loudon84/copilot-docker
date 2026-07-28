"""SQLite session store schema v3 with Fernet-encrypted tokens and migrations."""

from __future__ import annotations

import base64
import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Set

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.session.models import SCHEMA_VERSION, QueryRecord, SessionRecord

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


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
        query_retention_days: int = 90,
    ):
        self.db_path = str(db_path)
        self.ttl_seconds = int(ttl_seconds)
        self.query_retention_days = int(query_retention_days)
        self._fernet = _fernet_from_key(encryption_key)
        self._last_cleanup_day = ""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()
        self.cleanup_old_queries()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table: str) -> Set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(r[1]) for r in rows}

    @staticmethod
    def _add_column_if_missing(
        conn: sqlite3.Connection,
        table: str,
        column: str,
        decl: str,
        existing: Set[str],
    ) -> None:
        if column in existing:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        existing.add(column)

    def _read_schema_version(self, conn: sqlite3.Connection) -> int:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sqlbot_schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        row = conn.execute(
            "SELECT value FROM sqlbot_schema_meta WHERE key=?",
            ("schema_version",),
        ).fetchone()
        if row is None:
            # Infer from tables
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "sqlbot_sessions" not in tables:
                return 0
            cols = self._table_columns(conn, "sqlbot_sessions")
            if "last_upstream_record_id" in cols or "session_version" in cols:
                return 3
            if "last_payload_json" in cols:
                return 2
            return 1
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return 0

    def init_schema(self) -> None:
        with self._connect() as conn:
            try:
                conn.execute("BEGIN")
                version = self._read_schema_version(conn)

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
                        session_version INTEGER DEFAULT 3,
                        last_upstream_record_id TEXT,
                        last_response_mode TEXT,
                        last_error_code TEXT,
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
                        completed_at TEXT,
                        upstream_record_id TEXT,
                        query_payload_json TEXT,
                        title TEXT,
                        row_count INTEGER DEFAULT 0,
                        returned_row_count INTEGER DEFAULT 0,
                        truncated INTEGER DEFAULT 0,
                        request_id TEXT
                    )
                    """
                )

                sess_cols = self._table_columns(conn, "sqlbot_sessions")
                query_cols = self._table_columns(conn, "sqlbot_queries")

                # v1 -> v2 session columns
                for col, decl in [
                    ("last_query_id", "TEXT"),
                    ("last_sql", "TEXT"),
                    ("last_question", "TEXT"),
                    ("last_title", "TEXT"),
                    ("last_payload_json", "TEXT"),
                    ("token_expires_at", "TEXT"),
                ]:
                    self._add_column_if_missing(conn, "sqlbot_sessions", col, decl, sess_cols)

                # v2 -> v3
                for col, decl in [
                    ("session_version", "INTEGER DEFAULT 3"),
                    ("last_upstream_record_id", "TEXT"),
                    ("last_response_mode", "TEXT"),
                    ("last_error_code", "TEXT"),
                ]:
                    self._add_column_if_missing(conn, "sqlbot_sessions", col, decl, sess_cols)

                for col, decl in [
                    ("upstream_record_id", "TEXT"),
                    ("query_payload_json", "TEXT"),
                    ("title", "TEXT"),
                    ("row_count", "INTEGER DEFAULT 0"),
                    ("returned_row_count", "INTEGER DEFAULT 0"),
                    ("truncated", "INTEGER DEFAULT 0"),
                    ("request_id", "TEXT"),
                ]:
                    self._add_column_if_missing(conn, "sqlbot_queries", col, decl, query_cols)

                conn.execute(
                    "INSERT OR REPLACE INTO sqlbot_schema_meta(key, value) VALUES (?, ?)",
                    ("schema_version", str(SCHEMA_VERSION)),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

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

    def is_token_expired(self, rec: SessionRecord) -> bool:
        exp = _parse_iso(rec.token_expires_at)
        if exp is None:
            return False
        return _utcnow() > exp

    def get(
        self,
        *,
        profile_name: str,
        hermes_session_id: str,
        hermes_user_id: str,
        check_token: bool = True,
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
            exp = _parse_iso(rec.expires_at)
            if exp and _utcnow() > exp:
                self.reset(
                    profile_name=profile,
                    hermes_session_id=session_id,
                    hermes_user_id=user_id,
                )
                return None
        if check_token and self.is_token_expired(rec):
            return rec  # caller decides ask rebuild vs followup expire
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
        last_upstream_record_id: str = "",
        last_response_mode: str = "",
        last_error_code: str = "",
    ) -> SessionRecord:
        profile = profile_name or "default"
        session_id = hermes_session_id or "default"
        user_id = hermes_user_id or "local-cli"
        now = _utcnow()
        existing = self.get(
            profile_name=profile,
            hermes_session_id=session_id,
            hermes_user_id=user_id,
            check_token=False,
        )
        created_at = existing.created_at if existing else _iso(now)
        token_blob = (
            self.encrypt_token(access_token)
            if access_token
            else (existing.access_token_encrypted if existing else "")
        )
        if not token_blob and access_token == "":
            token_blob = existing.access_token_encrypted if existing else ""
        if not token_blob:
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_AUTH_FAILED,
                "无法保存空 Token",
            )
        chat_id = sqlbot_chat_id if sqlbot_chat_id != "" else (existing.sqlbot_chat_id if existing else "")
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
            session_version=SCHEMA_VERSION,
            last_upstream_record_id=last_upstream_record_id
            if last_upstream_record_id != ""
            else (existing.last_upstream_record_id if existing else ""),
            last_response_mode=last_response_mode
            if last_response_mode != ""
            else (existing.last_response_mode if existing else ""),
            last_error_code=last_error_code
            if last_error_code != ""
            else (existing.last_error_code if existing else ""),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sqlbot_sessions (
                    profile_name, hermes_session_id, hermes_user_id,
                    access_token_encrypted, sqlbot_chat_id,
                    workspace_id, datasource_id, token_expires_at,
                    created_at, updated_at, expires_at,
                    last_query_id, last_sql, last_question, last_title, last_payload_json,
                    session_version, last_upstream_record_id, last_response_mode, last_error_code
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                    last_payload_json=excluded.last_payload_json,
                    session_version=excluded.session_version,
                    last_upstream_record_id=excluded.last_upstream_record_id,
                    last_response_mode=excluded.last_response_mode,
                    last_error_code=excluded.last_error_code
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
                    rec.session_version,
                    rec.last_upstream_record_id,
                    rec.last_response_mode,
                    rec.last_error_code,
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
        upstream_record_id: str = "",
        query_payload_json: str = "",
        title: str = "",
        row_count: int = 0,
        returned_row_count: int = 0,
        truncated: bool = False,
        request_id: str = "",
    ) -> None:
        now = _iso(_utcnow())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sqlbot_queries (
                    query_id, profile_name, hermes_session_id, hermes_user_id,
                    question, generated_sql, datasource_id, workspace_id,
                    status, error_code, error_message, created_at, completed_at,
                    upstream_record_id, query_payload_json, title,
                    row_count, returned_row_count, truncated, request_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                    upstream_record_id,
                    (query_payload_json or "")[:20000],
                    (title or "")[:500],
                    int(row_count),
                    int(returned_row_count),
                    1 if truncated else 0,
                    request_id,
                ),
            )
            conn.commit()
        self.maybe_cleanup_queries()

    def get_query(
        self,
        *,
        query_id: str,
        profile_name: str,
        hermes_session_id: str,
        hermes_user_id: str,
    ) -> Optional[QueryRecord]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM sqlbot_queries
                WHERE query_id=? AND profile_name=? AND hermes_session_id=? AND hermes_user_id=?
                """,
                (
                    query_id,
                    profile_name or "default",
                    hermes_session_id or "default",
                    hermes_user_id or "local-cli",
                ),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_query(row)

    def cleanup_old_queries(self) -> int:
        days = max(int(self.query_retention_days), 1)
        cutoff = _iso(_utcnow() - timedelta(days=days))
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM sqlbot_queries WHERE created_at < ?",
                (cutoff,),
            )
            conn.commit()
            deleted = cur.rowcount
        self._last_cleanup_day = _utcnow().strftime("%Y%m%d")
        return int(deleted or 0)

    def maybe_cleanup_queries(self) -> None:
        day = _utcnow().strftime("%Y%m%d")
        if self._last_cleanup_day == day:
            return
        self.cleanup_old_queries()

    def access_token(self, rec: SessionRecord) -> str:
        return self.decrypt_token(rec.access_token_encrypted)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> SessionRecord:
        keys = set(row.keys())

        def g(name: str, default: str = "") -> str:
            if name not in keys:
                return default
            val = row[name]
            return default if val is None else str(val)

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
            last_query_id=g("last_query_id"),
            last_sql=g("last_sql"),
            last_question=g("last_question"),
            last_title=g("last_title"),
            last_payload_json=g("last_payload_json"),
            session_version=int(row["session_version"]) if "session_version" in keys and row["session_version"] is not None else SCHEMA_VERSION,
            last_upstream_record_id=g("last_upstream_record_id"),
            last_response_mode=g("last_response_mode"),
            last_error_code=g("last_error_code"),
        )

    @staticmethod
    def _row_to_query(row: sqlite3.Row) -> QueryRecord:
        keys = set(row.keys())

        def g(name: str, default: str = "") -> str:
            if name not in keys:
                return default
            val = row[name]
            return default if val is None else str(val)

        def gi(name: str, default: int = 0) -> int:
            if name not in keys or row[name] is None:
                return default
            try:
                return int(row[name])
            except (TypeError, ValueError):
                return default

        return QueryRecord(
            query_id=row["query_id"],
            profile_name=row["profile_name"],
            hermes_session_id=row["hermes_session_id"],
            hermes_user_id=row["hermes_user_id"],
            question=row["question"] or "",
            generated_sql=row["generated_sql"] or "",
            datasource_id=row["datasource_id"] or "",
            workspace_id=row["workspace_id"] or "",
            status=row["status"] or "",
            error_code=row["error_code"] or "",
            error_message=row["error_message"] or "",
            created_at=row["created_at"] or "",
            completed_at=row["completed_at"] or "",
            upstream_record_id=g("upstream_record_id"),
            query_payload_json=g("query_payload_json"),
            title=g("title"),
            row_count=gi("row_count"),
            returned_row_count=gi("returned_row_count"),
            truncated=gi("truncated"),
            request_id=g("request_id"),
        )
