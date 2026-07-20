from __future__ import annotations

from typing import Any, Dict, List, Optional

from finance_bi.catalog import SemanticCatalog
from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import SemanticQuery


def normalize_result(
    *,
    catalog: SemanticCatalog,
    config: FinanceBiConfig,
    query_id: str,
    semantic: SemanticQuery,
    columns: List[str],
    rows: List[Dict[str, Any]],
    warnings: List[str],
    elapsed_ms: float,
) -> Dict[str, Any]:
    dataset = catalog.datasets[semantic.dataset]
    field_defs = []
    for col in columns:
        metric = catalog.metrics.get(col)
        dim = catalog.dimensions.get(col)
        if metric:
            field_defs.append(
                {
                    "name": col,
                    "label": metric.get("name") or col,
                    "kind": "metric",
                    "format": metric.get("format"),
                    "version": metric.get("version"),
                }
            )
        elif dim:
            field_defs.append(
                {
                    "name": col,
                    "label": dim.get("name") or col,
                    "kind": "dimension",
                    "sensitive": bool(dim.get("sensitive")),
                }
            )
        else:
            field_defs.append({"name": col, "label": col, "kind": "field"})

    # mask sensitive dimensions in output rows for default table view
    masked_rows = []
    sensitive = {
        d
        for d, meta in catalog.dimensions.items()
        if meta.get("sensitive") and d in columns
    }
    for row in rows:
        item = dict(row)
        for key in sensitive:
            if key in item and item[key] is not None:
                val = str(item[key])
                item[key] = val[:2] + "***" if len(val) > 2 else "***"
        masked_rows.append(item)

    totals: Dict[str, Any] = {}
    for mid in semantic.metrics:
        metric = catalog.metrics.get(mid) or {}
        if metric.get("aggregation") == "sum":
            totals[mid] = sum(float(r.get(mid) or 0) for r in rows)
        elif metric.get("compute_after_aggregate") or metric.get("aggregation") == "ratio":
            # recompute from sum components when possible
            if mid == "gross_margin":
                sales = sum(float(r.get("net_sales_amount") or 0) for r in rows)
                profit = sum(float(r.get("gross_profit_amount") or 0) for r in rows)
                totals[mid] = (profit / sales) if sales else None

    time_range = {}
    for flt in semantic.filters:
        if flt.field == dataset.get("primary_time_field"):
            if flt.operator in ("gte", ">="):
                time_range["gte"] = flt.value
            if flt.operator in ("lt", "<"):
                time_range["lt"] = flt.value

    entity_scope = list(config.allowed_entities)
    for flt in semantic.filters:
        if flt.field == (dataset.get("entity_field") or "entity_code") and flt.operator in (
            "eq",
            "=",
        ):
            entity_scope = [str(flt.value)]

    return {
        "status": "ok",
        "query_id": query_id,
        "title": semantic.title or "BI Query",
        "fields": field_defs,
        "rows": masked_rows,
        "totals": totals,
        "time_range": time_range,
        "currency": config.default_currency,
        "entity_scope": entity_scope,
        "metric_versions": semantic.metric_versions,
        "data_updated_at": None,
        "warnings": warnings,
        "elapsed_ms": round(elapsed_ms, 2),
        "row_count": len(rows),
        "dataset": semantic.dataset,
        "semantic_query": semantic.to_dict(),
    }


def validate_result_payload(payload: Dict[str, Any], catalog: SemanticCatalog) -> Dict[str, Any]:
    warnings = list(payload.get("warnings") or [])
    checks = {
        "has_time_range": bool(payload.get("time_range")),
        "has_entity_scope": bool(payload.get("entity_scope")),
        "has_currency": bool(payload.get("currency")),
        "has_metric_versions": bool(payload.get("metric_versions")),
        "row_count": payload.get("row_count", 0),
    }
    if not checks["has_time_range"]:
        warnings.append("time_range missing")
    if not checks["has_entity_scope"]:
        warnings.append("entity_scope missing")
    nullish = 0
    for row in payload.get("rows") or []:
        for v in row.values():
            if v is None:
                nullish += 1
    if nullish:
        warnings.append(f"null_cell_count={nullish}")
    return {
        "status": "ok",
        "query_id": payload.get("query_id"),
        "checks": checks,
        "warnings": warnings,
        "passed": len([w for w in warnings if "missing" in w]) == 0,
    }
