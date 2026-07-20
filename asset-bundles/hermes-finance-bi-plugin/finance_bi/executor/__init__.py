from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import ErrorCode, FinanceBiError

_ENGINE_CACHE: Dict[str, Any] = {}


class QueryExecutor:
    def __init__(self, config: FinanceBiConfig):
        self.config = config

    def execute(self, sql: str) -> Tuple[List[str], List[Dict[str, Any]], float]:
        if not self.config.dsn and self.config.dialect != "sqlite":
            raise FinanceBiError(
                ErrorCode.DATASOURCE_UNAVAILABLE,
                "FINANCE_BI_DSN is not configured",
            )
        try:
            from sqlalchemy import create_engine, text
        except ImportError as exc:
            raise FinanceBiError(
                ErrorCode.INTERNAL_ERROR,
                "sqlalchemy is required",
            ) from exc

        dsn = self.config.dsn
        connect_args: Dict[str, Any] = {}
        if self.config.dialect == "sqlite" and dsn.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        elif self.config.is_mssql:
            # SQL Server 2012 + pymssql：固定 TDS 7.0
            connect_args = {
                "tds_version": "7.0",
                "timeout": int(self.config.query_timeout_seconds),
                "login_timeout": 15,
                "charset": "utf8",
            }

        try:
            engine = _ENGINE_CACHE.get(dsn)
            if engine is None:
                engine = create_engine(
                    dsn,
                    pool_pre_ping=True,
                    pool_size=2,
                    max_overflow=2,
                    connect_args=connect_args,
                )
                _ENGINE_CACHE[dsn] = engine
        except Exception as exc:  # noqa: BLE001
            raise FinanceBiError(
                ErrorCode.DATASOURCE_UNAVAILABLE,
                "failed to create database engine",
                {"reason": type(exc).__name__},
            ) from exc

        started = time.perf_counter()
        try:
            with engine.connect() as conn:
                if self.config.dialect == "postgresql":
                    with conn.begin():
                        conn.execute(
                            text(
                                f"SET LOCAL statement_timeout = {int(self.config.query_timeout_seconds) * 1000}"
                            )
                        )
                        try:
                            conn.execute(text("SET TRANSACTION READ ONLY"))
                        except Exception:  # noqa: BLE001
                            pass
                        result = conn.execute(text(sql))
                        keys = list(result.keys())
                        rows = [dict(zip(keys, row)) for row in result.fetchall()]
                elif self.config.is_mssql:
                    # pymssql treats '%' as bind placeholder — escape when SQL has no bound params
                    safe_sql = sql.replace("%", "%%")
                    conn.execute(
                        text(
                            f"SET LOCK_TIMEOUT {int(self.config.query_timeout_seconds) * 1000}"
                        )
                    )
                    conn.commit()
                    with conn.begin():
                        result = conn.execute(text(safe_sql))
                        keys = list(result.keys())
                        rows = [dict(zip(keys, row)) for row in result.fetchall()]
                else:
                    with conn.begin():
                        result = conn.execute(text(sql))
                        keys = list(result.keys())
                        rows = [dict(zip(keys, row)) for row in result.fetchall()]
        except FinanceBiError:
            raise
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "timeout" in msg or "canceling statement" in msg or "lock request" in msg:
                raise FinanceBiError(ErrorCode.QUERY_TIMEOUT, "query timed out") from exc
            raise FinanceBiError(
                ErrorCode.DATASOURCE_UNAVAILABLE,
                "query execution failed",
                {"reason": type(exc).__name__, "detail": str(exc)[:500]},
            ) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if len(rows) > self.config.hard_limit:
            raise FinanceBiError(ErrorCode.QUERY_TOO_EXPENSIVE, "result exceeds hard limit")
        return keys, rows, elapsed_ms

    def probe_readonly(self) -> Dict[str, Any]:
        if not self.config.dsn:
            return {"ok": False, "reason": "DSN empty"}
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(self.config.dsn, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                if self.config.dialect == "postgresql":
                    try:
                        conn.execute(text("CREATE TEMP TABLE finance_bi_write_probe(id int)"))
                        return {"ok": False, "reason": "write succeeded; account may not be readonly"}
                    except Exception:  # noqa: BLE001
                        return {"ok": True, "readonly": True}
                if self.config.is_mssql:
                    try:
                        conn.execute(text("SELECT 1 INTO #finance_bi_write_probe"))
                        return {"ok": False, "reason": "write succeeded; account may not be readonly"}
                    except Exception:  # noqa: BLE001
                        return {"ok": True, "readonly": True}
                return {"ok": True, "readonly": "unknown"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": type(exc).__name__}
