from __future__ import annotations

import re
from datetime import date
from typing import List, Optional, Tuple

from finance_bi.catalog import SemanticCatalog
from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import (
    ErrorCode,
    FilterClause,
    FinanceBiError,
    OrderByClause,
    SemanticQuery,
)

_QUARTER_RE = re.compile(r"(20\d{2})\s*[Qq季]?\s*([1-4])")
_YEAR_RE = re.compile(r"(20\d{2})\s*年?")
_MARGIN_LT_RE = re.compile(r"毛利率\s*(?:低于|小于|<|<=)\s*(\d+(?:\.\d+)?)\s*%?")
_TOP_N_RE = re.compile(r"(?:前|top)\s*(\d+)", re.I)


def parse_quarter_range(text: str) -> Optional[Tuple[str, str]]:
    m = _QUARTER_RE.search(text.replace("第", ""))
    if not m:
        return None
    year = int(m.group(1))
    q = int(m.group(2))
    start_month = (q - 1) * 3 + 1
    start = date(year, start_month, 1)
    if q == 4:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, start_month + 3, 1)
    return start.isoformat(), end.isoformat()


class QueryPlanner:
    DEFAULT_DATASET = "ebs1_cux_ar_gp_details"

    def __init__(self, catalog: SemanticCatalog, config: FinanceBiConfig):
        self.catalog = catalog
        self.config = config

    def _resolve_dataset_id(self) -> str:
        preferred = self.DEFAULT_DATASET
        if preferred in self.catalog.datasets:
            return preferred
        if not self.catalog.datasets:
            raise FinanceBiError(ErrorCode.CATALOG_NOT_READY, "no datasets loaded")
        return next(iter(self.catalog.datasets))

    def _dataset_fields(self, dataset: dict) -> set[str]:
        return set((dataset.get("fields") or {}).keys())

    def _dimension_allowed(self, dataset: dict, dim: str) -> bool:
        if dim in (dataset.get("available_dimensions") or []):
            return True
        if dim in self._dataset_fields(dataset):
            return True
        return False

    def _pick_dimensions(self, text: str, dataset: dict) -> List[str]:
        candidates: List[str] = []
        if "品牌" in text:
            candidates.extend(["brand_name", "brand_code"])
        if "客户" in text:
            candidates.extend(["customer_name", "customer_code"])
        if "区域" in text or "销售区域" in text:
            candidates.extend(["sales_region", "com_first_layer"])
        if "主体" in text or "OU" in text.upper():
            candidates.append("ou_name")
        if "产品" in text:
            candidates.extend(["product_code", "product_name", "brand_name"])
        if not candidates:
            # Prefer brand/customer for GP detail; fall back to demo product dims
            candidates = ["brand_name", "customer_name", "product_code", "product_name"]

        out: List[str] = []
        for dim in candidates:
            if self._dimension_allowed(dataset, dim) and dim not in out:
                out.append(dim)
        return out

    def plan(self, question: str) -> SemanticQuery:
        text = str(question or "").strip()
        if not text:
            raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, "question is required")

        # Ambiguity: bare 「利润」 without 销售/毛利
        if (
            "利润" in text
            and "销售利润" not in text
            and "毛利" not in text
            and "毛利率" not in text
        ):
            raise FinanceBiError(
                ErrorCode.CLARIFICATION_REQUIRED,
                "利润口径不明确",
                {
                    "status": "clarification_required",
                    "questions": ["销售利润是指销售毛利还是经营利润？"],
                },
            )

        dataset_id = self._resolve_dataset_id()
        dataset = self.catalog.datasets[dataset_id]

        metrics: List[str] = []
        # detect metrics from aliases in text
        for alias, mid in sorted(
            self.catalog._alias_to_metric.items(), key=lambda x: -len(x[0])
        ):
            if alias and alias in text.lower():
                if mid not in metrics:
                    metrics.append(mid)

        if "毛利率" in text and "gross_margin" not in metrics:
            metrics.append("gross_margin")
        if any(k in text for k in ("销售利润", "毛利", "利润报表", "销售利润报表")):
            for mid in ("net_sales_amount", "gross_profit_amount", "gross_margin"):
                if mid not in metrics:
                    metrics.append(mid)
        if not metrics:
            metrics = ["net_sales_amount", "gross_profit_amount", "gross_margin"]

        for mid in metrics:
            if mid not in self.catalog.metrics:
                raise FinanceBiError(ErrorCode.METRIC_NOT_FOUND, f"metric not found: {mid}")
            if mid not in (dataset.get("available_metrics") or []):
                raise FinanceBiError(
                    ErrorCode.METRIC_NOT_FOUND,
                    f"metric {mid} not available on dataset {dataset_id}",
                )

        dimensions = self._pick_dimensions(text, dataset)
        for did in dimensions:
            if not self._dimension_allowed(dataset, did):
                raise FinanceBiError(
                    ErrorCode.DIMENSION_NOT_FOUND,
                    f"dimension {did} not available on dataset {dataset_id}",
                )

        filters: List[FilterClause] = []
        time_field = dataset.get("primary_time_field") or "posting_date"
        qrange = parse_quarter_range(text)
        if qrange:
            filters.append(FilterClause(field=time_field, operator="gte", value=qrange[0]))
            filters.append(FilterClause(field=time_field, operator="lt", value=qrange[1]))

        m = _MARGIN_LT_RE.search(text)
        if m:
            pct = float(m.group(1)) / 100.0
            filters.append(FilterClause(field="gross_margin", operator="lt", value=pct))
            if "gross_margin" not in metrics:
                metrics.append("gross_margin")

        entity_field = str(dataset.get("entity_field") or "entity_code")
        if "香港" in text or "HK01" in text.upper():
            filters.append(FilterClause(field=entity_field, operator="eq", value="HK01"))
        if "新加坡" in text or "SG01" in text.upper():
            filters.append(FilterClause(field=entity_field, operator="eq", value="SG01"))

        order_by: List[OrderByClause] = []
        if "毛利" in text or "利润" in text:
            order_by.append(OrderByClause(field="gross_profit_amount", direction="desc"))
        else:
            order_by.append(OrderByClause(field="net_sales_amount", direction="desc"))

        limit = self.config.default_limit
        top = _TOP_N_RE.search(text)
        if top:
            limit = min(int(top.group(1)), self.config.hard_limit)

        metric_versions = {
            mid: int(self.catalog.metrics[mid].get("version") or 1) for mid in metrics
        }

        return SemanticQuery(
            dataset=dataset_id,
            metrics=metrics,
            dimensions=dimensions,
            filters=filters,
            order_by=order_by,
            limit=limit,
            metric_versions=metric_versions,
            title=text[:120],
        )

    def apply_followup(self, base: SemanticQuery, instruction: str) -> SemanticQuery:
        text = str(instruction or "").strip()
        if not text:
            raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, "instruction is required")

        q = SemanticQuery.from_dict(base.to_dict())
        dataset = self.catalog.datasets[q.dataset]

        if "区域" in text or "销售区域" in text:
            region_dim = "sales_region" if self._dimension_allowed(dataset, "sales_region") else "com_first_layer"
            if region_dim not in q.dimensions and self._dimension_allowed(dataset, region_dim):
                q.dimensions.append(region_dim)
            if "只按" in text or "按销售区域拆分" in text:
                q.dimensions = [region_dim] if self._dimension_allowed(dataset, region_dim) else q.dimensions

        m = _MARGIN_LT_RE.search(text)
        if m:
            pct = float(m.group(1)) / 100.0
            q.filters = [f for f in q.filters if f.field != "gross_margin"]
            q.filters.append(FilterClause(field="gross_margin", operator="lt", value=pct))
            if "gross_margin" not in q.metrics:
                q.metrics.append("gross_margin")

        if "客户" in text:
            for d in ("customer_code", "customer_name"):
                if d not in q.dimensions and self._dimension_allowed(dataset, d):
                    q.dimensions.append(d)

        top = _TOP_N_RE.search(text)
        if top:
            q.limit = min(int(top.group(1)), self.config.hard_limit)

        q.title = f"{base.title} | {text}"[:160]
        q.metric_versions = {
            mid: int(self.catalog.metrics[mid].get("version") or 1) for mid in q.metrics
        }
        return q
