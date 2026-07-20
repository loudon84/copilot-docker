from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from finance_bi.catalog import SemanticCatalog
from finance_bi.compiler import SqlCompiler
from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import ErrorCode, FinanceBiError, SemanticQuery
from finance_bi.executor import QueryExecutor
from finance_bi.export import export_result
from finance_bi.planner import QueryPlanner
from finance_bi.policy import SqlPolicy
from finance_bi.repository import QueryRepository
from finance_bi.results import normalize_result, validate_result_payload


class FinanceBiService:
    def __init__(self, config: Optional[FinanceBiConfig] = None):
        self.config = config or FinanceBiConfig.from_env()
        self.catalog = SemanticCatalog(Path(self.config.catalog_path)).load()
        self.planner = QueryPlanner(self.catalog, self.config)
        self.compiler = SqlCompiler(self.catalog, self.config)
        self.policy = SqlPolicy(self.catalog, self.config)
        self.executor = QueryExecutor(self.config)
        self.repo = QueryRepository(self.config)

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "datasets": len(self.catalog.datasets),
            "metrics": len(self.catalog.metrics),
            "dimensions": len(self.catalog.dimensions),
            "dialect": self.config.dialect,
            "dsn_configured": bool(self.config.dsn),
        }

    def ask(self, question: str, output_mode: str = "table_and_summary", session_id: str = "") -> Dict[str, Any]:
        semantic = self.planner.plan(question)
        return self._run(semantic, session_id=session_id, output_mode=output_mode)

    def followup(
        self,
        base_query_id: str,
        instruction: str,
        session_id: str = "",
        output_mode: str = "table_and_summary",
    ) -> Dict[str, Any]:
        base = self.repo.get_query(base_query_id)
        semantic = self.planner.apply_followup(base["semantic_query"], instruction)
        return self._run(semantic, session_id=session_id, output_mode=output_mode)

    def explain(self, query_id: str = "", topic: str = "", metric: str = "") -> Dict[str, Any]:
        if query_id:
            stored = self.repo.get_query(query_id)
            semantic: SemanticQuery = stored["semantic_query"]
            metric_info = []
            for mid in semantic.metrics:
                m = self.catalog.metrics.get(mid) or {}
                metric_info.append(
                    {
                        "id": mid,
                        "name": m.get("name"),
                        "description": m.get("description"),
                        "expression": m.get("expression"),
                        "version": m.get("version"),
                    }
                )
            ds = self.catalog.datasets.get(semantic.dataset) or {}
            return {
                "status": "ok",
                "query_id": query_id,
                "dataset": {
                    "id": semantic.dataset,
                    "name": ds.get("name"),
                    "primary_time_field": ds.get("primary_time_field"),
                    "grain": ds.get("grain"),
                },
                "metrics": metric_info,
                "filters": semantic.to_dict()["filters"],
                "currency": self.config.default_currency,
                "sql_compiled": stored.get("sql_text"),
            }

        if metric:
            mid = self.catalog.resolve_metric(metric) or metric
            m = self.catalog.metrics.get(mid)
            if not m:
                raise FinanceBiError(ErrorCode.METRIC_NOT_FOUND, f"metric not found: {metric}")
            return {"status": "ok", "metric": {"id": mid, **m}}

        if topic:
            return {"status": "ok", "catalog": self.catalog.search(topic)}

        raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, "provide query_id, metric, or topic")

    def catalog_search(self, query: str = "", kind: str = "all") -> Dict[str, Any]:
        return {"status": "ok", **self.catalog.search(query, kind=kind)}

    def validate(self, query_id: str) -> Dict[str, Any]:
        # Re-run to obtain fresh normalized payload for checks
        stored = self.repo.get_query(query_id)
        payload = self._run(stored["semantic_query"], session_id=stored.get("session_id") or "", reuse_id=query_id)
        return validate_result_payload(payload, self.catalog)

    def export(self, query_id: str, fmt: str = "csv") -> Dict[str, Any]:
        stored = self.repo.get_query(query_id)
        payload = self._run(
            stored["semantic_query"],
            session_id=stored.get("session_id") or "",
            reuse_id=query_id,
        )
        columns = [f["name"] for f in payload.get("fields") or []]
        rows = payload.get("rows") or []
        # export uses masked rows already — for formal export re-fetch unmasked? PRD says mask sensitive in audit;
        # export of current result uses normalized (masked) rows for customer fields.
        return export_result(
            config=self.config,
            query_id=query_id,
            columns=columns,
            rows=rows,
            fmt=fmt,
        )

    def _run(
        self,
        semantic: SemanticQuery,
        session_id: str = "",
        output_mode: str = "table_and_summary",
        reuse_id: str = "",
    ) -> Dict[str, Any]:
        sql, warnings = self.compiler.compile(semantic)
        tables, cols = self.policy.allowed_objects_for_dataset(semantic.dataset)
        sql = self.policy.validate(sql, tables, cols)

        query_id = reuse_id or self.repo.create_query(semantic, sql, session_id=session_id)
        if reuse_id and not query_id:
            query_id = reuse_id

        try:
            columns, rows, elapsed_ms = self.executor.execute(sql)
            payload = normalize_result(
                catalog=self.catalog,
                config=self.config,
                query_id=query_id,
                semantic=semantic,
                columns=columns,
                rows=rows,
                warnings=warnings,
                elapsed_ms=elapsed_ms,
            )
            payload["output_mode"] = output_mode
            self.repo.audit(
                query_id=query_id,
                session_id=session_id,
                semantic=semantic,
                sql_text=sql,
                fields=columns,
                entity_scope=payload.get("entity_scope") or [],
                elapsed_ms=elapsed_ms,
                row_count=len(rows),
                status="ok",
            )
            return payload
        except FinanceBiError as exc:
            self.repo.audit(
                query_id=query_id,
                session_id=session_id,
                semantic=semantic,
                sql_text=sql,
                fields=[],
                entity_scope=list(self.config.allowed_entities),
                elapsed_ms=0,
                row_count=0,
                status="error",
                error_code=exc.code.value,
            )
            raise


_SERVICE: Optional[FinanceBiService] = None


def get_service() -> FinanceBiService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = FinanceBiService()
    return _SERVICE


def reset_service(config: Optional[FinanceBiConfig] = None) -> FinanceBiService:
    global _SERVICE
    _SERVICE = FinanceBiService(config=config) if config else FinanceBiService()
    return _SERVICE


def json_ok(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def json_err(exc: BaseException) -> str:
    if isinstance(exc, FinanceBiError):
        return json.dumps(exc.to_dict(), ensure_ascii=False)
    return json.dumps(
        {
            "status": "error",
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": "internal error",
            "details": {"reason": type(exc).__name__},
        },
        ensure_ascii=False,
    )
