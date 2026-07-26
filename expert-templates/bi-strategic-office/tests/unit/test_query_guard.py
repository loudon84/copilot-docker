#!/usr/bin/env python3
"""Unit tests for query_guard."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.contracts import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.security.query_guard import (
    assert_readonly_sql,
    extract_explicit_identifiers,
    guard_sql,
)


def test_readonly_select_ok():
    assert_readonly_sql("SELECT a FROM t WHERE id = 1")
    assert_readonly_sql("WITH x AS (SELECT 1 AS n) SELECT * FROM x")


def test_reject_drop_and_multistmt():
    with pytest.raises(SqlbotAdapterError) as ei:
        assert_readonly_sql("DROP TABLE t")
    assert ei.value.code == ErrorCode.UNSAFE_SQL

    with pytest.raises(SqlbotAdapterError):
        assert_readonly_sql("SELECT 1; DELETE FROM t")


def test_identifier_preserved():
    q = "查询凭证号101IN26070199的交易明细"
    ids = extract_explicit_identifiers(q)
    assert any(i.value == "101IN26070199" for i in ids)
    guard_sql(q, "SELECT * FROM ar WHERE ar_trx_number = '101IN26070199'")


def test_identifier_missing_raises():
    q = "查询凭证号101IN26070199的交易明细"
    with pytest.raises(SqlbotAdapterError) as ei:
        guard_sql(q, "SELECT TOP 10 * FROM ar")
    assert ei.value.code == ErrorCode.FILTER_NOT_PRESERVED
