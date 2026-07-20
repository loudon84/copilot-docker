"""Unified tabular result envelope for all finance_bi_* tools.

Tools always return row-oriented datasets. Skills/agents convert presentation
(markdown table, bullet summary, report prose, chart specs) per user request.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence


def table_envelope(
    *,
    title: str,
    columns: Sequence[Dict[str, Any]],
    rows: Sequence[Dict[str, Any]],
    result_kind: str = "query",
    query_id: str = "",
    meta: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
    status: str = "ok",
) -> Dict[str, Any]:
    cols = [dict(c) for c in columns]
    data_rows = [dict(r) for r in rows]
    return {
        "status": status,
        "result_type": "table",
        "result_kind": result_kind,
        "title": title,
        "columns": cols,
        # Keep `fields` alias for backward compatibility with older skills/tests
        "fields": cols,
        "rows": data_rows,
        "row_count": len(data_rows),
        "query_id": query_id,
        "warnings": list(warnings or []),
        "meta": dict(meta or {}),
    }


def dicts_to_table(
    *,
    title: str,
    records: Iterable[Dict[str, Any]],
    column_order: Optional[Sequence[str]] = None,
    result_kind: str = "catalog",
    query_id: str = "",
    meta: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    rows = [dict(r) for r in records]
    if column_order:
        keys = list(column_order)
        for row in rows:
            for k in row.keys():
                if k not in keys:
                    keys.append(k)
    else:
        keys: List[str] = []
        seen = set()
        for row in rows:
            for k in row.keys():
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
    columns = [{"name": k, "label": k, "kind": "field"} for k in keys]
    normalized_rows = [{k: row.get(k) for k in keys} for row in rows]
    return table_envelope(
        title=title,
        columns=columns,
        rows=normalized_rows,
        result_kind=result_kind,
        query_id=query_id,
        meta=meta,
        warnings=warnings,
    )


def catalog_meta_to_table(payload: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Flatten catalog_meta payload into one or more logical tables.

    Primary `rows` = datasets. Additional tables live under meta.tables.
    """
    datasets = []
    for ds in payload.get("datasets") or []:
        datasets.append(
            {
                "object_type": "dataset",
                "id": ds.get("id"),
                "name": ds.get("name"),
                "primary_time_field": ds.get("primary_time_field"),
                "grain": ds.get("grain"),
                "status": ds.get("status"),
                "physical_table": ds.get("physical_table"),
                "available_metrics": ",".join(ds.get("available_metrics") or []),
                "available_dimensions": ",".join(ds.get("available_dimensions") or []),
                "use_cases": ",".join(ds.get("use_cases") or []),
            }
        )

    metrics = []
    for m in payload.get("metrics") or []:
        metrics.append(
            {
                "object_type": "metric",
                "id": m.get("id"),
                "name": m.get("name"),
                "aliases": ",".join(m.get("aliases") or []),
                "description": m.get("description"),
                "expression": m.get("expression"),
                "datasets": ",".join(m.get("datasets") or []),
                "version": m.get("version"),
            }
        )

    date_fields = []
    for f in payload.get("date_fields") or []:
        date_fields.append(
            {
                "object_type": "date_field",
                "dataset": f.get("dataset"),
                "field": f.get("field"),
                "description": f.get("description"),
                "is_primary_time": f.get("is_primary_time"),
                "is_data_updated_at": f.get("is_data_updated_at"),
            }
        )

    primary = datasets or metrics or date_fields
    kind = "catalog_datasets" if datasets else ("catalog_metrics" if metrics else "catalog_date_fields")
    table = dicts_to_table(
        title=title or payload.get("topic") or "语义目录",
        records=primary,
        result_kind=kind,
        meta={
            "topic": payload.get("topic"),
            "notes": payload.get("notes") or [],
            "tables": {
                "datasets": datasets,
                "metrics": metrics,
                "date_fields": date_fields,
            },
            "summary": payload.get("summary"),
        },
        warnings=list(payload.get("warnings") or []),
    )
    return table


def query_payload_to_table(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an existing ask/followup payload into the unified table envelope."""
    columns = payload.get("fields") or payload.get("columns") or []
    rows = payload.get("rows") or []
    meta = {
        "totals": payload.get("totals") or {},
        "time_range": payload.get("time_range") or {},
        "currency": payload.get("currency"),
        "entity_scope": payload.get("entity_scope") or [],
        "metric_versions": payload.get("metric_versions") or {},
        "data_updated_at": payload.get("data_updated_at"),
        "dataset": payload.get("dataset"),
        "mode": payload.get("mode"),
        "applied_filters": payload.get("applied_filters") or [],
        "mask_sensitive": payload.get("mask_sensitive"),
        "revealed_sensitive_fields": payload.get("revealed_sensitive_fields") or [],
        "masked_sensitive_fields": payload.get("masked_sensitive_fields") or [],
        "elapsed_ms": payload.get("elapsed_ms"),
        "semantic_query": payload.get("semantic_query"),
    }
    return table_envelope(
        title=str(payload.get("title") or "BI Query"),
        columns=columns,
        rows=rows,
        result_kind="query" if str(payload.get("mode") or "") != "detail" else "detail",
        query_id=str(payload.get("query_id") or ""),
        meta=meta,
        warnings=list(payload.get("warnings") or []),
        status=str(payload.get("status") or "ok"),
    )
