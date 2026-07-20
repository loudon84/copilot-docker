from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import ErrorCode, FinanceBiError, SemanticQuery


class QueryRepository:
    def __init__(self, config: FinanceBiConfig):
        self.config = config
        self.db_path = Path(config.state_db)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS queries (
                  query_id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  semantic_query TEXT NOT NULL,
                  sql_text TEXT,
                  dataset TEXT,
                  metric_versions TEXT,
                  session_id TEXT,
                  title TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  query_id TEXT,
                  created_at TEXT NOT NULL,
                  session_id TEXT,
                  semantic_query TEXT,
                  sql_text TEXT,
                  dataset TEXT,
                  fields TEXT,
                  entity_scope TEXT,
                  elapsed_ms REAL,
                  row_count INTEGER,
                  status TEXT,
                  error_code TEXT
                );
                """
            )

    def create_query(
        self,
        semantic: SemanticQuery,
        sql_text: str,
        session_id: str = "",
    ) -> str:
        query_id = f"biq_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO queries(query_id, created_at, semantic_query, sql_text, dataset,
                                    metric_versions, session_id, title)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    now,
                    json.dumps(semantic.to_dict(), ensure_ascii=False),
                    sql_text,
                    semantic.dataset,
                    json.dumps(semantic.metric_versions, ensure_ascii=False),
                    session_id,
                    semantic.title,
                ),
            )
        self.cleanup()
        return query_id

    def get_query(self, query_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM queries WHERE query_id = ?", (query_id,)
            ).fetchone()
        if not row:
            raise FinanceBiError(ErrorCode.QUERY_NOT_FOUND, f"query not found: {query_id}")
        created = datetime.fromisoformat(row["created_at"])
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created > timedelta(days=self.config.retain_days):
            raise FinanceBiError(ErrorCode.QUERY_NOT_FOUND, f"query expired: {query_id}")
        return {
            "query_id": row["query_id"],
            "created_at": row["created_at"],
            "semantic_query": SemanticQuery.from_dict(json.loads(row["semantic_query"])),
            "sql_text": row["sql_text"],
            "dataset": row["dataset"],
            "metric_versions": json.loads(row["metric_versions"] or "{}"),
            "session_id": row["session_id"],
            "title": row["title"],
        }

    def audit(
        self,
        *,
        query_id: str,
        session_id: str,
        semantic: SemanticQuery,
        sql_text: str,
        fields: list,
        entity_scope: list,
        elapsed_ms: float,
        row_count: int,
        status: str,
        error_code: str = "",
    ) -> None:
        # Do not store result rows or credentials
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log(
                  query_id, created_at, session_id, semantic_query, sql_text, dataset,
                  fields, entity_scope, elapsed_ms, row_count, status, error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    datetime.now(timezone.utc).isoformat(),
                    session_id,
                    json.dumps(semantic.to_dict(), ensure_ascii=False),
                    sql_text,
                    semantic.dataset,
                    json.dumps(fields, ensure_ascii=False),
                    json.dumps(entity_scope, ensure_ascii=False),
                    elapsed_ms,
                    row_count,
                    status,
                    error_code,
                ),
            )

    def cleanup(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.config.retain_days)).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM queries WHERE created_at < ?", (cutoff,))
            conn.execute("DELETE FROM audit_log WHERE created_at < ?", (cutoff,))
