"""Result-level guards: detail-query filters and row limits."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple

from sqlbot_adapter.contracts import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.security.query_guard import ExplicitIdentifier, extract_explicit_identifiers

DETAIL_HINTS = re.compile(
    r"(明细|交易明细|凭证明细|detail|details|逐笔|行项目)",
    re.IGNORECASE,
)

DATE_RANGE_HINTS = re.compile(
    r"(20\d{2}[-/年]\d{1,2}|20\d{2}Q[1-4]|本月|本季|本周|上年|同比|环比|"
    r"\d{4}-\d{2}-\d{2}\s*[~到至\-]\s*\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

ENTITY_HINTS = re.compile(
    r"(客户|主体|OU|ou_code|品牌|区域|公司)",
    re.IGNORECASE,
)


def looks_like_detail_query(question: str) -> bool:
    return bool(DETAIL_HINTS.search(question or ""))


def has_effective_filter(question: str, identifiers: Sequence[ExplicitIdentifier] | None = None) -> bool:
    ids = list(identifiers) if identifiers is not None else extract_explicit_identifiers(question)
    if ids:
        return True
    text = question or ""
    if DATE_RANGE_HINTS.search(text):
        return True
    if ENTITY_HINTS.search(text) and re.search(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text):
        # Has entity keyword plus some substance — soft accept
        return True
    return False


def assert_detail_query_has_filter(
    question: str,
    identifiers: Sequence[ExplicitIdentifier] | None = None,
) -> None:
    if not looks_like_detail_query(question):
        return
    if has_effective_filter(question, identifiers):
        return
    raise SqlbotAdapterError(
        ErrorCode.DETAIL_QUERY_REQUIRES_FILTER,
        "明细查询缺少有效过滤（精确编号、日期范围、客户或主体）。",
    )


def truncate_rows(
    rows: List[Any],
    *,
    model_limit: int = 100,
    hard_limit: int = 500,
) -> Tuple[List[Any], bool, int]:
    """Return (rows_for_model, truncated, original_count)."""
    original = len(rows or [])
    limit = min(max(int(model_limit), 1), max(int(hard_limit), 1))
    if original > hard_limit:
        # Cap at hard limit for any in-memory processing before model slice
        rows = rows[:hard_limit]
    truncated = original > limit
    return list(rows[:limit]), truncated, original


def apply_result_guards(
    question: str,
    rows: List[Any],
    *,
    identifiers: Sequence[ExplicitIdentifier] | None = None,
    model_limit: int = 100,
    hard_limit: int = 500,
) -> Tuple[List[Any], bool, int, List[str]]:
    assert_detail_query_has_filter(question, identifiers)
    sliced, truncated, original = truncate_rows(
        rows, model_limit=model_limit, hard_limit=hard_limit
    )
    warnings: List[str] = []
    if truncated:
        warnings.append(
            f"结果已截断：原始 {original} 行，返回模型 {len(sliced)} 行（上限 {model_limit}）。"
        )
    if original > hard_limit:
        warnings.append(f"原始结果超过硬上限 {hard_limit}，已丢弃超出部分。")
    return sliced, truncated, original, warnings


def rows_as_dicts(rows: List[Any], columns: List[Any]) -> List[Dict[str, Any]]:
    """Normalize heterogeneous row payloads into list[dict]."""
    col_names: List[str] = []
    for c in columns or []:
        if isinstance(c, dict):
            col_names.append(str(c.get("name") or c.get("field") or c.get("label") or f"c{len(col_names)}"))
        else:
            col_names.append(str(c))

    out: List[Dict[str, Any]] = []
    for row in rows or []:
        if isinstance(row, dict):
            out.append(row)
        elif isinstance(row, (list, tuple)):
            item = {}
            for i, val in enumerate(row):
                key = col_names[i] if i < len(col_names) else f"c{i}"
                item[key] = val
            out.append(item)
        else:
            out.append({"value": row})
    return out
