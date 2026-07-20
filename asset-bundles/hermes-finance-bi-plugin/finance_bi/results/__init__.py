from __future__ import annotations

from typing import Any, Dict, List, Set

from finance_bi.catalog import SemanticCatalog
from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import SemanticQuery
from finance_bi.text_codec import repair_row_strings


def _filtered_sensitive_fields(semantic: SemanticQuery, sensitive: Set[str]) -> Set[str]:
    """Fields already constrained by the query — safe to show in clear for operator UX."""
    out: Set[str] = set()
    for flt in semantic.filters:
        if flt.field in sensitive and str(flt.operator or "").lower() in {
            "eq",
            "=",
            "==",
            "like",
            "contains",
            "ilike",
            "in",
        }:
            out.add(flt.field)
    return out


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

    sensitive: Set[str] = {
        d
        for d, meta in catalog.dimensions.items()
        if meta.get("sensitive") and d in columns
    }
    reveal = (
        _filtered_sensitive_fields(semantic, sensitive)
        if config.reveal_filtered_sensitive
        else set()
    )
    mask_fields = set() if not config.mask_sensitive else (sensitive - reveal)

    out_rows = []
    for row in rows:
        item = repair_row_strings(dict(row))
        for key in mask_fields:
            if key in item and item[key] is not None:
                val = str(item[key])
                item[key] = val[:2] + "***" if len(val) > 2 else "***"
        out_rows.append(item)

    warn = list(warnings)
    if mask_fields:
        warn.append(
            "sensitive_fields_masked="
            + ",".join(sorted(mask_fields))
            + "; set FINANCE_BI_MASK_SENSITIVE=false to show full values"
        )
    if reveal:
        warn.append(
            "sensitive_fields_revealed_due_to_filter=" + ",".join(sorted(reveal))
        )

    totals: Dict[str, Any] = {}
    for mid in semantic.metrics:
        metric = catalog.metrics.get(mid) or {}
        if metric.get("aggregation") == "sum":
            totals[mid] = sum(float(r.get(mid) or 0) for r in rows)
        elif metric.get("compute_after_aggregate") or metric.get("aggregation") == "ratio":
            if mid == "gross_margin":
                sales = sum(float(r.get("net_sales_amount") or 0) for r in rows)
                profit = sum(float(r.get("gross_profit_amount") or 0) for r in rows)
                totals[mid] = (profit / sales) if sales else None

    time_range = {}
    applied_filters = []
    for flt in semantic.filters:
        applied_filters.append(
            {"field": flt.field, "operator": flt.operator, "value": flt.value}
        )
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
        "rows": out_rows,
        "totals": totals,
        "time_range": time_range,
        "currency": config.default_currency,
        "entity_scope": entity_scope,
        "metric_versions": semantic.metric_versions,
        "data_updated_at": None,
        "warnings": warn,
        "elapsed_ms": round(elapsed_ms, 2),
        "row_count": len(rows),
        "dataset": semantic.dataset,
        "mode": semantic.mode,
        "applied_filters": applied_filters,
        "mask_sensitive": bool(config.mask_sensitive),
        "revealed_sensitive_fields": sorted(reveal),
        "masked_sensitive_fields": sorted(mask_fields),
        "semantic_query": semantic.to_dict(),
    }


def validate_result_payload(payload: Dict[str, Any], catalog: SemanticCatalog) -> Dict[str, Any]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    warnings = list(payload.get("warnings") or [])
    time_range = payload.get("time_range") or meta.get("time_range")
    entity_scope = payload.get("entity_scope") or meta.get("entity_scope")
    currency = payload.get("currency") if "currency" in payload else meta.get("currency")
    metric_versions = payload.get("metric_versions") or meta.get("metric_versions")
    checks = {
        "has_time_range": bool(time_range),
        "has_entity_scope": bool(entity_scope),
        "has_currency": bool(currency),
        "has_metric_versions": bool(metric_versions),
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
