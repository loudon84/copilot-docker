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

# ---------------------------------------------------------------------------
# Time range extraction — STRICT
# 只允许从「日期/时间/日历」表述提取；禁止从单据号、客户编码等编号里猜年份/季度。
# 所有模式均要求两侧非字母数字边界，避免 101IN23120194 内嵌 2019+4。
# ---------------------------------------------------------------------------
_BOUND_L = r"(?<![A-Za-z0-9_])"
_BOUND_R = r"(?![A-Za-z0-9_])"
_YMD = r"(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])"
_ISO_RANGE_RE = re.compile(
    _BOUND_L + _YMD + r"\s*(?:[~～到至]|--+)\s*" + _YMD + _BOUND_R
)
_ISO_DATE_RE = re.compile(_BOUND_L + _YMD + _BOUND_R)
_CN_DATE_RE = re.compile(
    _BOUND_L + r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?" + _BOUND_R
)
_QUARTER_Q_RE = re.compile(_BOUND_L + r"(20\d{2})\s*[Qq]\s*([1-4])" + _BOUND_R)
_QUARTER_CN_RE = re.compile(
    _BOUND_L + r"(20\d{2})\s*年\s*第?\s*([1-4])\s*季度?" + _BOUND_R
)
_QUARTER_CN2_RE = re.compile(_BOUND_L + r"(20\d{2})\s*第\s*([1-4])\s*季度?" + _BOUND_R)
_CLEAR_TIME_RE = re.compile(
    r"(不限时间|不限期间|全部期间|全部时间|取消时间|去掉时间|移除时间|"
    r"无时间过滤|不要时间|忽略时间|clear\s*time|no\s*time\s*filter)",
    re.I,
)
_MARGIN_LT_RE = re.compile(r"毛利率\s*(?:低于|小于|<|<=)\s*(\d+(?:\.\d+)?)\s*%?")
_TOP_N_RE = re.compile(r"(?:前|top)\s*(\d+)", re.I)
_LIMIT_N_RE = re.compile(
    r"(?:只(?:需要|要)?返回|返回|只要|仅|只看|限制)\s*(\d+)\s*条|(?:明细)?\s*(\d+)\s*条(?:明细|数据|记录)?",
    re.I,
)
# 客户 XXX / 客户名称：XXX / 客户名 XXX
_CUSTOMER_RE = re.compile(
    r"(?:客户(?:名称|名)?|customer(?:\s*name)?)\s*[：:\s]+([^\s,，；;]+(?:[^\s,，；;]*[公司厂院社行店部中心集团有限责任股份]+)?)",
    re.I,
)
_CUSTOMER_INLINE_RE = re.compile(
    r"客户\s+([^\s,，；;]{2,80})",
)
# field=value / field='value' for known identity columns
_FIELD_EQ_RE = re.compile(
    r"(?i)\b(ar_trx_number|customer_code|customer_name|brand_name|brand_code|"
    r"ou_code|ou_name|product_code|product_name)\s*[=＝]\s*['\"]?([^'\"\s,，；;]+)['\"]?"
)
_TRX_LABEL_RE = re.compile(
    r"(?:单据号|单据|发票号|交易号|事务处理编号|发票编号|ar_trx_number|trx(?:\s*number)?)"
    r"\s*[：:=\s]+['\"]?([A-Za-z0-9_\-]+)['\"]?",
    re.I,
)
# e.g. 101IN26070199 / 101IN23120194
_TRX_BARE_RE = re.compile(r"\b(\d{2,4}[A-Z]{2}\d{6,})\b")


def _quarter_bounds(year: int, q: int) -> Tuple[str, str]:
    start_month = (q - 1) * 3 + 1
    start = date(year, start_month, 1)
    if q == 4:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, start_month + 3, 1)
    return start.isoformat(), end.isoformat()


def _ymd(y: str, m: str, d: str) -> str:
    return date(int(y), int(m), int(d)).isoformat()


def parse_time_range(text: str) -> Optional[Tuple[str, str]]:
    """Extract [start, end) only from explicit date/calendar formats.

    Allowed:
      - ISO: 2026-04-01~2026-06-30 / 2026/04/01 到 2026/06/30
      - Single ISO date → that day [d, d+1)
      - CN date: 2026年4月1日
      - Calendar quarter: 2026Q2 / 2026年第2季度 / 2026第2季度

    Forbidden:
      - Guessing year/quarter from invoice/customer/product codes
      - Loose digit runs without date separators or Q/年/月/日/季 markers
    """
    raw = str(text or "")
    if not raw.strip():
        return None

    m = _ISO_RANGE_RE.search(raw)
    if m:
        start = _ymd(m.group(1), m.group(2), m.group(3))
        end = _ymd(m.group(4), m.group(5), m.group(6))
        # normalize to [start, end) — if end is a calendar day, use next day when equal
        if end <= start:
            # treat as inclusive end-of-day → next day exclusive
            y, mo, d = (int(x) for x in end.split("-"))
            end = date(y, mo, d).fromordinal(date(y, mo, d).toordinal() + 1).isoformat()
        else:
            # inclusive end date in NL → exclusive upper bound = end + 1 day
            y, mo, d = (int(x) for x in end.split("-"))
            end = date.fromordinal(date(y, mo, d).toordinal() + 1).isoformat()
        return start, end

    m = _CN_DATE_RE.search(raw)
    if m:
        start = _ymd(m.group(1), m.group(2), m.group(3))
        y, mo, d = (int(x) for x in start.split("-"))
        end = date.fromordinal(date(y, mo, d).toordinal() + 1).isoformat()
        return start, end

    m = _ISO_DATE_RE.search(raw)
    if m:
        start = _ymd(m.group(1), m.group(2), m.group(3))
        y, mo, d = (int(x) for x in start.split("-"))
        end = date.fromordinal(date(y, mo, d).toordinal() + 1).isoformat()
        return start, end

    for pat in (_QUARTER_Q_RE, _QUARTER_CN_RE, _QUARTER_CN2_RE):
        m = pat.search(raw)
        if m:
            year, q = int(m.group(1)), int(m.group(2))
            if 1 <= q <= 4 and 2000 <= year <= 2100:
                return _quarter_bounds(year, q)
    return None


def parse_quarter_range(text: str) -> Optional[Tuple[str, str]]:
    """Backward-compatible alias → parse_time_range (strict date/calendar only)."""
    return parse_time_range(text)


def wants_clear_time_range(text: str) -> bool:
    return bool(_CLEAR_TIME_RE.search(text or ""))

def extract_customer_name(text: str) -> Optional[str]:
    """Extract a customer name filter value from natural language."""
    for pattern in (_CUSTOMER_RE, _CUSTOMER_INLINE_RE):
        m = pattern.search(text)
        if not m:
            continue
        name = (m.group(1) or "").strip().strip("\"'“”‘’")
        # drop trailing intent words accidentally captured
        for stop in ("交易", "统计", "明细", "汇总", "查询", "的", "相关"):
            if name.endswith(stop) and len(name) > len(stop) + 1:
                name = name[: -len(stop)].strip()
        if len(name) >= 2 and name not in ("名称", "列表", "有哪些"):
            return name
    return None


def extract_limit(text: str, default: int, hard: int) -> int:
    top = _TOP_N_RE.search(text)
    if top:
        return min(int(top.group(1)), hard)
    m = _LIMIT_N_RE.search(text)
    if m:
        n = m.group(1) or m.group(2)
        if n:
            return min(int(n), hard)
    return default


def extract_field_eq_filters(text: str) -> List[Tuple[str, str]]:
    """Extract field=value equality filters from NL / semi-structured text."""
    out: List[Tuple[str, str]] = []
    seen = set()
    for m in _FIELD_EQ_RE.finditer(text or ""):
        field = (m.group(1) or "").strip().lower()
        value = (m.group(2) or "").strip().strip("\"'“”‘’")
        if field and value and (field, value) not in seen:
            seen.add((field, value))
            out.append((field, value))
    return out


def extract_trx_number(text: str) -> Optional[str]:
    """Extract AR transaction / invoice number (always scan bare invoice tokens)."""
    raw = text or ""
    for field, value in extract_field_eq_filters(raw):
        if field == "ar_trx_number" and value:
            return value
    m = _TRX_LABEL_RE.search(raw)
    if m:
        return (m.group(1) or "").strip()
    # Always accept invoice-shaped tokens — do not require 单据/过滤 keywords
    m = _TRX_BARE_RE.search(raw)
    if m:
        return m.group(1)
    return None


def _strip_time_filters(filters: List[FilterClause], time_field: str) -> List[FilterClause]:
    return [
        f
        for f in filters
        if not (
            f.field == time_field
            and str(f.operator or "").lower() in {"gte", "gt", "lte", "lt", "<=", ">=", ">", "<", "eq", "="}
        )
    ]


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

    def _is_detail_request(self, text: str) -> bool:
        if extract_trx_number(text) or extract_field_eq_filters(text):
            return True
        return any(
            k in text
            for k in (
                "明细",
                "明细数据",
                "交易明细",
                "行明细",
                "流水",
                "逐笔",
                "原始行",
            )
        )

    def _upsert_eq_filter(self, filters: List[FilterClause], field: str, value: str) -> List[FilterClause]:
        out = [f for f in filters if f.field != field]
        out.append(FilterClause(field=field, operator="eq", value=value))
        return out

    def _apply_identity_filters(
        self, text: str, dataset: dict, filters: List[FilterClause]
    ) -> List[FilterClause]:
        """Apply trx / field=value filters into SQL WHERE (not in-memory on prior rows)."""
        for field, value in extract_field_eq_filters(text):
            if self._dimension_allowed(dataset, field):
                filters = self._upsert_eq_filter(filters, field, value)
        trx = extract_trx_number(text)
        if trx and self._dimension_allowed(dataset, "ar_trx_number"):
            # Avoid double-add if already from field=eq
            if not any(f.field == "ar_trx_number" and str(f.value) == trx for f in filters):
                filters = self._upsert_eq_filter(filters, "ar_trx_number", trx)
        return filters

    def _pick_dimensions(self, text: str, dataset: dict, *, detail: bool, has_customer_filter: bool) -> List[str]:
        candidates: List[str] = []
        if detail:
            # Detail lines: identity + time + key attrs
            candidates.extend(
                [
                    "customer_name",
                    "customer_code",
                    "brand_name",
                    "transaction_date",
                    "ar_trx_number",
                    "ar_fin_due_date",
                ]
            )
        else:
            if "品牌" in text:
                candidates.extend(["brand_name", "brand_code"])
            if "客户" in text and not has_customer_filter:
                candidates.extend(["customer_name", "customer_code"])
            if has_customer_filter:
                # Already filtered to one customer — break by brand by default
                candidates.extend(["brand_name", "brand_code"])
            if "区域" in text or "销售区域" in text:
                candidates.extend(["sales_region", "com_first_layer"])
            if "主体" in text or "OU" in text.upper():
                candidates.append("ou_name")
            if "产品" in text:
                candidates.extend(["product_code", "product_name", "brand_name"])
            if not candidates:
                candidates = ["brand_name", "customer_name", "product_code", "product_name"]

        out: List[str] = []
        for dim in candidates:
            if self._dimension_allowed(dataset, dim) and dim not in out:
                out.append(dim)
        # Detail mode needs at least one column
        if detail and not out:
            for dim in ("customer_name", "brand_name", "transaction_date"):
                if self._dimension_allowed(dataset, dim):
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
            and "交易" not in text
            and "明细" not in text
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
        detail = self._is_detail_request(text)
        customer_name = extract_customer_name(text)

        metrics: List[str] = []
        for alias, mid in sorted(
            self.catalog._alias_to_metric.items(), key=lambda x: -len(x[0])
        ):
            if alias and alias in text.lower():
                if mid not in metrics:
                    metrics.append(mid)

        if "毛利率" in text and "gross_margin" not in metrics:
            metrics.append("gross_margin")
        if any(k in text for k in ("销售利润", "毛利", "利润报表", "销售利润报表", "交易统计", "交易")):
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

        dimensions = self._pick_dimensions(
            text, dataset, detail=detail, has_customer_filter=bool(customer_name)
        )
        for did in dimensions:
            if not self._dimension_allowed(dataset, did):
                raise FinanceBiError(
                    ErrorCode.DIMENSION_NOT_FOUND,
                    f"dimension {did} not available on dataset {dataset_id}",
                )

        filters: List[FilterClause] = []
        time_field = str(dataset.get("primary_time_field") or "posting_date")

        # Time ONLY from explicit date/calendar phrases → applied on primary_time_field
        if wants_clear_time_range(text):
            filters = _strip_time_filters(filters, time_field)
        else:
            trange = parse_time_range(text)
            if trange:
                filters.append(FilterClause(field=time_field, operator="gte", value=trange[0]))
                filters.append(FilterClause(field=time_field, operator="lt", value=trange[1]))

        m = _MARGIN_LT_RE.search(text)
        if m:
            pct = float(m.group(1)) / 100.0
            filters.append(FilterClause(field="gross_margin", operator="lt", value=pct))
            if "gross_margin" not in metrics:
                metrics.append("gross_margin")

        if customer_name and self._dimension_allowed(dataset, "customer_name"):
            filters.append(
                FilterClause(field="customer_name", operator="contains", value=customer_name)
            )

        # Identity codes (trx/customer_code) are NOT time sources
        filters = self._apply_identity_filters(text, dataset, filters)
        has_identity = any(
            f.field in {"ar_trx_number", "customer_code"} and f.operator in {"eq", "="}
            for f in filters
        )
        if has_identity:
            detail = True
            dimensions = self._pick_dimensions(
                text, dataset, detail=True, has_customer_filter=bool(customer_name)
            )

        entity_field = str(dataset.get("entity_field") or "entity_code")
        if "香港" in text or "HK01" in text.upper():
            filters.append(FilterClause(field=entity_field, operator="eq", value="HK01"))
        if "新加坡" in text or "SG01" in text.upper():
            filters.append(FilterClause(field=entity_field, operator="eq", value="SG01"))

        order_by: List[OrderByClause] = []
        if detail and self._dimension_allowed(dataset, "transaction_date"):
            order_by.append(OrderByClause(field="transaction_date", direction="desc"))
        elif "毛利" in text or "利润" in text:
            order_by.append(OrderByClause(field="gross_profit_amount", direction="desc"))
        else:
            order_by.append(OrderByClause(field="net_sales_amount", direction="desc"))

        # Precise identity lookup: do not inherit a stale "10 rows" default unless asked
        if has_identity:
            default_limit = self.config.default_limit
        else:
            default_limit = 10 if detail else self.config.default_limit
        limit = extract_limit(text, default_limit, self.config.hard_limit)

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
            mode="detail" if detail else "aggregate",
        )

    def apply_followup(self, base: SemanticQuery, instruction: str) -> SemanticQuery:
        text = str(instruction or "").strip()
        if not text:
            raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, "instruction is required")

        q = SemanticQuery.from_dict(base.to_dict())
        dataset = self.catalog.datasets[q.dataset]

        if self._is_detail_request(text):
            q.mode = "detail"
            q.dimensions = self._pick_dimensions(
                text,
                dataset,
                detail=True,
                has_customer_filter=any(f.field == "customer_name" for f in q.filters),
            )
            if self._dimension_allowed(dataset, "transaction_date"):
                q.order_by = [OrderByClause(field="transaction_date", direction="desc")]

        customer_name = extract_customer_name(text)
        if customer_name and self._dimension_allowed(dataset, "customer_name"):
            q.filters = [f for f in q.filters if f.field != "customer_name"]
            q.filters.append(
                FilterClause(field="customer_name", operator="contains", value=customer_name)
            )

        time_field = str(dataset.get("primary_time_field") or "posting_date")

        # New conditions become SQL WHERE on the full table — not a filter over prior TOP N rows
        before = [(f.field, f.operator, f.value) for f in q.filters]
        q.filters = self._apply_identity_filters(text, dataset, list(q.filters))
        after = [(f.field, f.operator, f.value) for f in q.filters]
        has_identity = any(
            f.field == "ar_trx_number" or (
                f.operator in {"eq", "="}
                and f.field in {"customer_code", "brand_code", "product_code", "ou_code"}
            )
            for f in q.filters
        )
        identity_added = after != before and has_identity
        if has_identity and (identity_added or extract_trx_number(text)):
            q.mode = "detail"
            q.dimensions = self._pick_dimensions(
                text,
                dataset,
                detail=True,
                has_customer_filter=any(f.field == "customer_name" for f in q.filters),
            )
            if not _LIMIT_N_RE.search(text) and not _TOP_N_RE.search(text):
                q.limit = self.config.default_limit

        # Time updates: only explicit clear / date-calendar phrases (never from codes)
        if wants_clear_time_range(text):
            q.filters = _strip_time_filters(q.filters, time_field)
        else:
            trange = parse_time_range(text)
            if trange:
                q.filters = _strip_time_filters(q.filters, time_field)
                q.filters.append(FilterClause(field=time_field, operator="gte", value=trange[0]))
                q.filters.append(FilterClause(field=time_field, operator="lt", value=trange[1]))

        if "区域" in text or "销售区域" in text:
            region_dim = (
                "sales_region"
                if self._dimension_allowed(dataset, "sales_region")
                else "com_first_layer"
            )
            if region_dim not in q.dimensions and self._dimension_allowed(dataset, region_dim):
                q.dimensions.append(region_dim)
            if "只按" in text or "按销售区域拆分" in text:
                q.dimensions = (
                    [region_dim] if self._dimension_allowed(dataset, region_dim) else q.dimensions
                )

        m = _MARGIN_LT_RE.search(text)
        if m:
            pct = float(m.group(1)) / 100.0
            q.filters = [f for f in q.filters if f.field != "gross_margin"]
            q.filters.append(FilterClause(field="gross_margin", operator="lt", value=pct))
            if "gross_margin" not in q.metrics:
                q.metrics.append("gross_margin")

        if "客户" in text and not customer_name:
            for d in ("customer_code", "customer_name"):
                if d not in q.dimensions and self._dimension_allowed(dataset, d):
                    q.dimensions.append(d)

        q.limit = extract_limit(text, q.limit or self.config.default_limit, self.config.hard_limit)

        q.title = f"{base.title} | {text}"[:160]
        q.metric_versions = {
            mid: int(self.catalog.metrics[mid].get("version") or 1) for mid in q.metrics
        }
        return q
