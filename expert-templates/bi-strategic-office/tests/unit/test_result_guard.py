#!/usr/bin/env python3
"""Unit tests for result_guard (v1.11.1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.contracts import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.security.result_guard import apply_result_guards, truncate_rows


def test_truncate_rows():
    rows = [{"i": i} for i in range(250)]
    sliced, truncated, original = truncate_rows(rows, model_limit=100, hard_limit=500)
    assert original == 250
    assert truncated is True
    assert len(sliced) == 100


def test_hard_limit_result_too_large():
    rows = [{"i": i} for i in range(501)]
    with pytest.raises(SqlbotAdapterError) as ei:
        truncate_rows(rows, model_limit=100, hard_limit=500)
    assert ei.value.code == ErrorCode.RESULT_TOO_LARGE


def test_detail_requires_filter():
    with pytest.raises(SqlbotAdapterError) as ei:
        apply_result_guards("查询交易明细", [{"a": 1}])
    assert ei.value.code == ErrorCode.DETAIL_QUERY_REQUIRES_FILTER


def test_detail_with_id_ok():
    rows, truncated, original, warnings = apply_result_guards(
        "查询凭证号101IN26070199的交易明细",
        [{"a": 1}],
    )
    assert len(rows) == 1
    assert truncated is False
    assert original == 1
