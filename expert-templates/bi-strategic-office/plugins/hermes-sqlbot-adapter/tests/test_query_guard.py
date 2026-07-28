"""query_guard / question_guard unit tests."""

from __future__ import annotations

import pytest

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.security.query_guard import (
    assert_readonly_sql,
    extract_explicit_identifiers,
    guard_sql,
)
from sqlbot_adapter.security.question_guard import preflight_question_guard


def test_extract_trx_number_glued():
    ids = extract_explicit_identifiers("查询销售利润报表交易凭证编号101IN26070194的数据")
    assert any(i.value == "101IN26070194" for i in ids)


def test_extract_ar_label():
    ids = extract_explicit_identifiers("查询应收交易编号 101IN26070199 的交易明细")
    assert any(i.value == "101IN26070199" for i in ids)


def test_tsql_top_allowed():
    assert_readonly_sql("SELECT TOP 10 ar_trx_number FROM t WHERE ar_trx_number = 'A'", dialect="tsql")


def test_select_into_rejected():
    with pytest.raises(SqlbotAdapterError) as ei:
        assert_readonly_sql("SELECT * INTO #tmp FROM t", dialect="tsql")
    assert ei.value.code == ErrorCode.UNSAFE_SQL


def test_dml_rejected():
    with pytest.raises(SqlbotAdapterError):
        assert_readonly_sql("DELETE FROM t WHERE id=1", dialect="tsql")


def test_identifier_must_be_in_predicate():
    q = "查询交易凭证编号101IN26070194的数据"
    sql_ok = "SELECT ar_trx_number FROM t WHERE ar_trx_number = '101IN26070194'"
    guard_sql(q, sql_ok, dialect="tsql")

    sql_bad = "SELECT '101IN26070194' AS note, ar_trx_number FROM t"
    with pytest.raises(SqlbotAdapterError) as ei:
        guard_sql(q, sql_bad, dialect="tsql")
    assert ei.value.code == ErrorCode.FILTER_NOT_PRESERVED


def test_preflight_detail_requires_filter():
    with pytest.raises(SqlbotAdapterError) as ei:
        preflight_question_guard("查询全部交易明细")
    assert ei.value.code == ErrorCode.DETAIL_QUERY_REQUIRES_FILTER


def test_preflight_mutation_blocked():
    with pytest.raises(SqlbotAdapterError):
        preflight_question_guard("请删除这张表的数据")
