"""Result-level guards: row/column/byte limits (postflight)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence, Tuple

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.security.query_guard import ExplicitIdentifier
from sqlbot_adapter.security.question_guard import (
    has_effective_filter,
    looks_like_detail_query,
)


def assert_detail_query_has_filter(
    question: str,
    identifiers: Sequence[ExplicitIdentifier] | None = None,
    *,
    business_identifiers: list | None = None,
) -> None:
    if not looks_like_detail_query(question):
        return
    if has_effective_filter(question, identifiers, business_identifiers=business_identifiers):
        return
    raise SqlbotAdapterError(
        ErrorCode.DETAIL_QUERY_REQUIRES_FILTER,
        "明细查询缺少有效过滤（精确编号、日期范围、客户或主体）。",
    )


def truncate_rows(
    rows: List[Any],
    *,
    model_limit: int = 100,
    hard_limit: int = 1000,
) -> Tuple[List[Any], bool, int, List[str]]:
    """Return (rows_for_model, truncated, original_count, warnings).

    Over hard_limit: truncate to hard_limit (do not discard entire result).
    """
    original = len(rows or [])
    warnings: List[str] = []
    hard = max(int(hard_limit), 1)
    model = max(int(model_limit), 1)
    working = list(rows or [])
    if original > hard:
        working = working[:hard]
        warnings.append(
            f"结果超过硬上限 {hard} 行（实际 {original}），已截断到硬上限。"
        )
        original_reported = original
    else:
        original_reported = original
    limit = min(model, hard)
    truncated = len(working) > limit or original > limit
    sliced = working[:limit]
    if truncated and not any("硬上限" in w for w in warnings):
        warnings.append(
            f"结果已截断：原始 {original_reported} 行，返回模型 {len(sliced)} 行（上限 {model}）。"
        )
    return sliced, truncated, original_reported, warnings


def truncate_columns(
    columns: List[Any],
    rows: List[Dict[str, Any]],
    *,
    max_columns: int = 50,
) -> Tuple[List[Any], List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    limit = max(int(max_columns), 1)
    if len(columns or []) <= limit:
        return list(columns or []), list(rows or []), warnings
    kept_cols = list(columns[:limit])
    names: List[str] = []
    for c in kept_cols:
        if isinstance(c, dict):
            names.append(str(c.get("name") or c.get("field") or c.get("label") or ""))
        else:
            names.append(str(c))
    names = [n for n in names if n]
    new_rows: List[Dict[str, Any]] = []
    for row in rows or []:
        if isinstance(row, dict):
            new_rows.append({k: row[k] for k in names if k in row})
        else:
            new_rows.append(row)
    warnings.append(f"列数超过上限 {limit}，已保留前 {limit} 列（原始 {len(columns)} 列）。")
    return kept_cols, new_rows, warnings


def enforce_byte_limit(
    rows: List[Dict[str, Any]],
    *,
    max_bytes: int = 2_000_000,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    limit = max(int(max_bytes), 1)
    payload = json.dumps(rows, ensure_ascii=False, default=str)
    if len(payload.encode("utf-8")) <= limit:
        return rows, warnings
    # Binary-search shrink
    lo, hi = 0, len(rows)
    best: List[Dict[str, Any]] = []
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = rows[:mid]
        size = len(json.dumps(candidate, ensure_ascii=False, default=str).encode("utf-8"))
        if size <= limit:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    warnings.append(
        f"结果 JSON 超过字节上限 {limit}，已进一步截断行数至 {len(best)}。"
    )
    return best, warnings


def apply_result_guards(
    question: str,
    rows: List[Any],
    *,
    columns: List[Any] | None = None,
    identifiers: Sequence[ExplicitIdentifier] | None = None,
    model_limit: int = 100,
    hard_limit: int = 1000,
    max_columns: int = 50,
    max_bytes: int = 2_000_000,
    business_identifiers: list | None = None,
    skip_detail_check: bool = False,
) -> Tuple[List[Any], List[Any], bool, int, List[str]]:
    """Return (sliced_rows, columns, truncated, original_count, warnings)."""
    if not skip_detail_check:
        assert_detail_query_has_filter(
            question, identifiers, business_identifiers=business_identifiers
        )
    warnings: List[str] = []
    cols = list(columns or [])
    dict_rows = rows if rows and isinstance(rows[0], dict) else list(rows or [])

    cols, dict_rows, col_warn = truncate_columns(cols, dict_rows, max_columns=max_columns)
    warnings.extend(col_warn)

    sliced, truncated, original, row_warn = truncate_rows(
        dict_rows, model_limit=model_limit, hard_limit=hard_limit
    )
    warnings.extend(row_warn)

    sliced, byte_warn = enforce_byte_limit(sliced, max_bytes=max_bytes)
    if byte_warn:
        truncated = True
        warnings.extend(byte_warn)

    return sliced, cols, truncated, original, warnings


def rows_as_dicts(rows: List[Any], columns: List[Any]) -> List[Dict[str, Any]]:
    """Normalize heterogeneous row payloads into list[dict]."""
    col_names: List[str] = []
    for c in columns or []:
        if isinstance(c, dict):
            col_names.append(
                str(c.get("name") or c.get("field") or c.get("label") or f"c{len(col_names)}")
            )
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
