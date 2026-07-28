"""Preflight question guard — runs before SQLBot MCP submission."""

from __future__ import annotations

import re
from typing import Sequence

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.security.query_guard import ExplicitIdentifier, extract_explicit_identifiers

MUTATION_HINTS = re.compile(
    r"(修改|删除|创建表|删表|drop\s+table|truncate|insert\s+into|update\s+\w+\s+set|"
    r"exec(ute)?\s+|调用存储过程|存储过程)",
    re.IGNORECASE,
)

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
    r"(客户|主体|OU|ou_code|品牌|区域|公司|部门)",
    re.IGNORECASE,
)


def looks_like_detail_query(question: str) -> bool:
    return bool(DETAIL_HINTS.search(question or ""))


def has_effective_filter(
    question: str,
    identifiers: Sequence[ExplicitIdentifier] | None = None,
    *,
    business_identifiers: list | None = None,
) -> bool:
    ids = (
        list(identifiers)
        if identifiers is not None
        else extract_explicit_identifiers(question, business_identifiers=business_identifiers)
    )
    if ids:
        return True
    text = question or ""
    if DATE_RANGE_HINTS.search(text):
        return True
    if ENTITY_HINTS.search(text) and re.search(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text):
        return True
    return False


def preflight_question_guard(
    question: str,
    *,
    max_chars: int = 2000,
    business_identifiers: list | None = None,
    require_datasource_ok: bool = True,
) -> None:
    q = (question or "").strip()
    if not q:
        raise SqlbotAdapterError(ErrorCode.INVALID_ARGUMENT, "question 不能为空")
    if len(q) > max(int(max_chars), 1):
        raise SqlbotAdapterError(
            ErrorCode.INVALID_ARGUMENT,
            f"问题长度超过上限 {max_chars} 字符",
        )
    if MUTATION_HINTS.search(q):
        raise SqlbotAdapterError(
            ErrorCode.UNSAFE_SQL,
            "禁止要求修改、删除、创建表或执行存储过程。",
        )
    if looks_like_detail_query(q) and not has_effective_filter(
        q, business_identifiers=business_identifiers
    ):
        raise SqlbotAdapterError(
            ErrorCode.DETAIL_QUERY_REQUIRES_FILTER,
            "明细查询缺少有效过滤（精确编号、日期范围、客户或主体）。",
        )
