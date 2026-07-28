"""Normalize SQLBot MCP responses into the finance-bi contract."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlbot_adapter.client.mcp_client import QuestionResult
from sqlbot_adapter.contracts import NormalizedResult, scrub_secrets
from sqlbot_adapter.security.result_guard import rows_as_dicts

TZ_CN = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(TZ_CN).isoformat(timespec="seconds")


def _normalize_columns(columns: List[Any], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if columns:
        for c in columns:
            if isinstance(c, dict):
                name = str(c.get("name") or c.get("field") or c.get("label") or "")
                label = str(c.get("label") or c.get("title") or name)
                ctype = str(c.get("type") or c.get("data_type") or "string")
                if name:
                    out.append({"name": name, "label": label, "type": ctype})
            else:
                name = str(c)
                out.append({"name": name, "label": name, "type": "string"})
    if not out and rows:
        for key in rows[0].keys():
            out.append({"name": str(key), "label": str(key), "type": "string"})
    return out


def new_query_id() -> str:
    return f"fbq_{uuid.uuid4().hex[:12]}"


def normalize_question_result(
    result: QuestionResult,
    *,
    question: str,
    datasource_key: str = "",
    datasource_name: str = "",
    query_id: str = "",
    rows: Optional[List[Dict[str, Any]]] = None,
    columns: Optional[List[Any]] = None,
    truncated: bool = False,
    original_row_count: Optional[int] = None,
    warnings: Optional[List[str]] = None,
    include_chart: bool = False,
    include_summary: bool = True,
    request_id: str = "",
    upstream_record_id: str = "",
) -> NormalizedResult:
    cols_src = columns if columns is not None else result.columns
    dict_rows = rows if rows is not None else rows_as_dicts(result.rows, cols_src)
    col_defs = _normalize_columns(cols_src, dict_rows)
    qid = query_id or new_query_id()
    row_count = original_row_count if original_row_count is not None else len(dict_rows)
    upstream = upstream_record_id or getattr(result, "upstream_record_id", "") or ""

    payload = NormalizedResult(
        success=True,
        query_id=qid,
        upstream_record_id=str(upstream) if upstream else "",
        title=result.title or question[:80],
        datasource={
            "key": datasource_key or "",
            "name": datasource_name or datasource_key or "",
        },
        query={
            "question": question,
            "sql": result.sql or "",
            "filters": list(result.filters or []),
            "row_count": row_count,
            "returned_row_count": len(dict_rows),
            "truncated": bool(truncated),
        },
        columns=col_defs,
        rows=dict_rows,
        chart=result.chart if include_chart else None,
        summary=result.summary if include_summary else None,
        warnings=list(warnings or []),
        meta={
            "generated_at": _now_iso(),
            "source": "sqlbot",
            "request_id": request_id or "",
        },
    )
    scrubbed = scrub_secrets(payload.to_dict())
    return NormalizedResult(**scrubbed)
