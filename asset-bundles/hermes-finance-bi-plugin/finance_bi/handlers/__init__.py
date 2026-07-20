from __future__ import annotations

import json
import re
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
from finance_bi.table_result import (
    catalog_meta_to_table,
    dicts_to_table,
    query_payload_to_table,
    table_envelope,
)

_META_ASK_RE = re.compile(
    r"(有哪些数据集|哪些数据集|数据集有哪些|列出.*字段|与日期有关|日期有关|日期字段|"
    r"时间字段|语义目录|可用指标|可用维度|检查.*报表|报表.*数据集)",
    re.I,
)


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
        prod = self.catalog.production_datasets()
        return {
            "status": "ok",
            "datasets": len(self.catalog.datasets),
            "production_datasets": list(prod.keys()),
            "metrics": len(self.catalog.metrics),
            "metric_ids": sorted(self.catalog.metrics.keys()),
            "dimensions": len(self.catalog.dimensions),
            "dialect": self.config.dialect,
            "dsn_configured": bool(self.config.dsn),
            "catalog_path": str(self.config.catalog_path),
            "load_warnings": list(getattr(self.catalog, "load_warnings", None) or []),
        }

    def _is_meta_question(self, question: str) -> bool:
        text = str(question or "")
        if _META_ASK_RE.search(text):
            return True
        # 纯目录探查：问报表有什么，但没有明确聚合/排名意图
        if any(k in text for k in ("数据集", "字段", "目录")) and not any(
            k in text for k in ("汇总", "排名", "前", "多少钱", "按品牌", "按客户", "同比", "环比")
        ):
            return True
        return False

    def ask(self, question: str, output_mode: str = "table", session_id: str = "") -> Dict[str, Any]:
        # output_mode kept for API compatibility; tools always return result_type=table.
        _ = output_mode
        text = str(question or "").strip()
        if self._is_meta_question(text):
            payload = self.catalog.describe_report_catalog(text)
            payload["summary"] = (
                f"找到 {len(payload.get('datasets') or [])} 个数据集，"
                f"{len(payload.get('date_fields') or [])} 个日期相关字段；"
                "本结果来自语义目录，未查询业务库。"
            )
            table = catalog_meta_to_table(payload, title=text[:120] or "语义目录")
            table["meta"]["session_id"] = session_id
            table["meta"]["mode"] = "catalog_meta"
            return table
        semantic = self.planner.plan(text)
        return self._run(semantic, session_id=session_id)

    def followup(
        self,
        base_query_id: str,
        instruction: str,
        session_id: str = "",
        output_mode: str = "table",
    ) -> Dict[str, Any]:
        _ = output_mode
        base_query_id = str(base_query_id or "").strip()
        instruction = str(instruction or "").strip()
        if not base_query_id:
            raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, "base_query_id is required")
        base = self.repo.get_query(base_query_id)
        semantic = self.planner.apply_followup(base["semantic_query"], instruction)
        return self._run(semantic, session_id=session_id)

    def explain(self, query_id: str = "", topic: str = "", metric: str = "") -> Dict[str, Any]:
        query_id = str(query_id or "").strip()
        topic = str(topic or "").strip()
        metric = str(metric or "").strip()

        if query_id:
            stored = self.repo.get_query(query_id)
            semantic: SemanticQuery = stored["semantic_query"]
            metric_info = []
            for mid in semantic.metrics:
                m = self.catalog.metrics.get(mid) or {}
                metric_info.append(
                    {
                        "object_type": "metric",
                        "id": mid,
                        "name": m.get("name"),
                        "description": m.get("description"),
                        "expression": m.get("expression"),
                        "version": m.get("version"),
                    }
                )
            ds = self.catalog.datasets.get(semantic.dataset) or {}
            date_fields = [
                {
                    "object_type": "date_field",
                    "dataset": semantic.dataset,
                    "field": f.get("field") if isinstance(f, dict) else f,
                    "description": f.get("description") if isinstance(f, dict) else "",
                    "is_primary_time": f.get("is_primary_time") if isinstance(f, dict) else None,
                }
                for f in (self.catalog.date_fields(semantic.dataset) or [])
            ]
            table = dicts_to_table(
                title=f"explain:{query_id}",
                records=metric_info or [{"object_type": "dataset", "id": semantic.dataset}],
                result_kind="explain_query",
                query_id=query_id,
                meta={
                    "dataset": {
                        "id": semantic.dataset,
                        "name": ds.get("name"),
                        "primary_time_field": ds.get("primary_time_field"),
                        "grain": ds.get("grain"),
                    },
                    "filters": semantic.to_dict()["filters"],
                    "date_fields": date_fields,
                    "currency": self.config.default_currency,
                    "sql_compiled": stored.get("sql_text"),
                    "tables": {"metrics": metric_info, "date_fields": date_fields},
                },
            )
            return table

        if metric:
            mid = self.catalog.resolve_metric(metric) or metric
            m = self.catalog.metrics.get(mid)
            if not m:
                raise FinanceBiError(ErrorCode.METRIC_NOT_FOUND, f"metric not found: {metric}")
            row = {"object_type": "metric", "id": mid, **{k: m.get(k) for k in m.keys()}}
            # Flatten list-ish fields for tabular display
            for key in ("aliases", "datasets", "dimensions"):
                if isinstance(row.get(key), list):
                    row[key] = ",".join(str(x) for x in row[key])
            return dicts_to_table(
                title=f"metric:{mid}",
                records=[row],
                result_kind="explain_metric",
                meta={"metric_id": mid},
            )

        if topic:
            if any(k in topic for k in ("报表", "数据集", "日期", "字段", "利润", "毛利", "目录")):
                return catalog_meta_to_table(
                    self.catalog.describe_report_catalog(topic), title=topic[:120]
                )
            search = self.catalog.search(topic)
            return catalog_meta_to_table(
                {
                    "topic": topic,
                    "datasets": search.get("datasets") or [],
                    "metrics": search.get("metrics") or [],
                    "date_fields": search.get("date_fields") or [],
                    "notes": [],
                },
                title=topic[:120] or "catalog search",
            )

        return catalog_meta_to_table(
            self.catalog.describe_report_catalog("销售利润报表"),
            title="销售利润报表",
        )

    def catalog_search(self, query: str = "", kind: str = "all") -> Dict[str, Any]:
        query = str(query or "").strip()
        kind = str(kind or "all").strip().lower()
        known_kinds = {
            "all",
            "datasets",
            "metrics",
            "dimensions",
            "date_fields",
            "fields",
        }
        # LLM often puts the search term into `kind` (e.g. kind=毛利, query="")
        if kind not in known_kinds:
            if not query:
                query = kind
            kind = "all"

        if kind in {"date_fields", "fields"} or any(k in query for k in ("日期", "时间字段")):
            payload = self.catalog.search(query, kind="date_fields", include_demo=False)
            if not payload.get("date_fields"):
                payload["date_fields"] = self.catalog.date_fields()
            if not payload.get("datasets"):
                payload["datasets"] = [
                    {
                        "id": ds_id,
                        "name": ds.get("name"),
                        "primary_time_field": ds.get("primary_time_field"),
                        "status": ds.get("status") or "active",
                    }
                    for ds_id, ds in self.catalog.production_datasets().items()
                ] or [
                    {
                        "id": ds_id,
                        "name": ds.get("name"),
                        "primary_time_field": ds.get("primary_time_field"),
                        "status": ds.get("status") or "active",
                    }
                    for ds_id, ds in self.catalog.datasets.items()
                ]
            table = catalog_meta_to_table(
                {
                    "topic": query or "date_fields",
                    "datasets": payload.get("datasets") or [],
                    "metrics": payload.get("metrics") or [],
                    "date_fields": payload.get("date_fields") or [],
                    "notes": [],
                },
                title=query[:120] or "date_fields",
            )
            # Prefer date_fields as primary rows when that was the ask
            date_rows = (table.get("meta") or {}).get("tables", {}).get("date_fields") or []
            if date_rows:
                return dicts_to_table(
                    title=query[:120] or "date_fields",
                    records=date_rows,
                    result_kind="catalog_date_fields",
                    meta={
                        **(table.get("meta") or {}),
                        "mode": "date_fields",
                    },
                )
            table["meta"]["mode"] = "date_fields"
            return table

        if any(k in query for k in ("销售利润", "利润报表", "毛利报表", "数据集")):
            table = catalog_meta_to_table(self.catalog.describe_report_catalog(query), title=query[:120])
            table["meta"]["mode"] = "catalog_meta"
            return table

        if any(k in query for k in ("毛利", "利润", "销售", "gross", "margin", "profit")):
            table = catalog_meta_to_table(self.catalog.describe_report_catalog(query), title=query[:120])
            table["meta"]["mode"] = "catalog_meta"
            return table

        payload = self.catalog.search(query, kind=kind, include_demo=False)
        empty = not any(payload.get(k) for k in ("datasets", "metrics", "dimensions", "date_fields"))
        if empty:
            table = catalog_meta_to_table(
                self.catalog.describe_report_catalog(query or "销售利润报表"),
                title=query[:120] or "销售利润报表",
            )
            table["meta"]["mode"] = "catalog_meta"
            table["meta"]["recovered_from_empty_search"] = True
            table["meta"]["original_query"] = query
            table["meta"]["original_kind"] = kind
            return table

        # Flatten mixed search hits into rows
        rows: list = []
        for ds in payload.get("datasets") or []:
            rows.append({"object_type": "dataset", **ds})
        for m in payload.get("metrics") or []:
            item = {"object_type": "metric", **m}
            for key in ("aliases", "datasets"):
                if isinstance(item.get(key), list):
                    item[key] = ",".join(str(x) for x in item[key])
            rows.append(item)
        for d in payload.get("dimensions") or []:
            rows.append({"object_type": "dimension", **d})
        for f in payload.get("date_fields") or []:
            rows.append({"object_type": "date_field", **f})
        return dicts_to_table(
            title=query[:120] or "catalog_search",
            records=rows,
            result_kind="catalog_search",
            meta={
                "mode": "search",
                "tables": {
                    "datasets": payload.get("datasets") or [],
                    "metrics": payload.get("metrics") or [],
                    "dimensions": payload.get("dimensions") or [],
                    "date_fields": payload.get("date_fields") or [],
                },
            },
        )

    def validate(self, query_id: str) -> Dict[str, Any]:
        stored = self.repo.get_query(query_id)
        payload = self._run(stored["semantic_query"], session_id=stored.get("session_id") or "", reuse_id=query_id)
        report = validate_result_payload(payload, self.catalog)
        checks = report.get("checks") or {}
        rows = [{"check": k, "value": v, "ok": bool(v) if isinstance(v, bool) else True} for k, v in checks.items()]
        return table_envelope(
            title=f"validate:{query_id}",
            columns=[
                {"name": "check", "label": "check", "kind": "field"},
                {"name": "value", "label": "value", "kind": "field"},
                {"name": "ok", "label": "ok", "kind": "field"},
            ],
            rows=rows,
            result_kind="validate",
            query_id=query_id,
            meta={
                "passed": report.get("passed"),
                "checks": checks,
            },
            warnings=list(report.get("warnings") or []),
        )

    def export(self, query_id: str, fmt: str = "csv") -> Dict[str, Any]:
        stored = self.repo.get_query(query_id)
        payload = self._run(
            stored["semantic_query"],
            session_id=stored.get("session_id") or "",
            reuse_id=query_id,
        )
        columns = [f["name"] for f in payload.get("fields") or payload.get("columns") or []]
        rows = payload.get("rows") or []
        exported = export_result(
            config=self.config,
            query_id=query_id,
            columns=columns,
            rows=rows,
            fmt=fmt,
        )
        # File export is not a data table; keep path metadata but preserve row_count.
        return {
            **exported,
            "result_type": "export",
            "result_kind": "file",
            "columns": [{"name": c, "label": c, "kind": "field"} for c in columns],
            "fields": [{"name": c, "label": c, "kind": "field"} for c in columns],
            "rows": [],
            "meta": {
                "path": exported.get("path"),
                "format": exported.get("format") or fmt,
                "source_row_count": exported.get("row_count") or len(rows),
                "query_id": query_id,
            },
        }

    def _run(
        self,
        semantic: SemanticQuery,
        session_id: str = "",
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
            table = query_payload_to_table(payload)
            table["meta"]["session_id"] = session_id
            self.repo.audit(
                query_id=query_id,
                session_id=session_id,
                semantic=semantic,
                sql_text=sql,
                fields=columns,
                entity_scope=(table.get("meta") or {}).get("entity_scope") or [],
                elapsed_ms=elapsed_ms,
                row_count=len(rows),
                status="ok",
            )
            return table
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
            "details": {"reason": type(exc).__name__, "detail": str(exc)},
        },
        ensure_ascii=False,
    )
