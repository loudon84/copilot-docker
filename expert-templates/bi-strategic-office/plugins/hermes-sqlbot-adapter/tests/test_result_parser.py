"""Unit tests for result_parser (v1.12 protocol)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sqlbot_adapter.client.result_parser import (
    extract_from_mcp_result,
    parse_question_result,
)
from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_success_top_level_sql_and_data_data():
    data = _load("mcp_question_success.json")
    parsed = parse_question_result(data)
    assert parsed.error is None
    assert "SELECT" in parsed.sql
    assert parsed.title
    assert parsed.upstream_record_id == "60"
    assert parsed.columns == ["detail_id", "ar_trx_number"]
    assert len(parsed.rows) == 1
    assert parsed.rows[0]["ar_trx_number"] == "101IN26070194"


def test_parse_success_false():
    data = _load("mcp_question_exec_error.json")
    parsed = parse_question_result(data)
    assert parsed.error is not None
    assert parsed.error.code == ErrorCode.SQLBOT_EXECUTION_FAILED


def test_extract_is_error():
    data = _load("mcp_tool_is_error.json")

    class Fake:
        isError = True
        content = data["content"]

    with pytest.raises(SqlbotAdapterError) as ei:
        extract_from_mcp_result(Fake())
    assert ei.value.code == ErrorCode.SQLBOT_TOOL_ERROR


def test_message_embedded_json_error():
    data = _load("mcp_message_embedded_error.json")
    # unwrap happens in extract; parse on unwrapped
    from sqlbot_adapter.client.result_parser import unwrap_nested

    unwrapped = unwrap_nested(data)
    parsed = parse_question_result(unwrapped)
    assert parsed.error is not None
    assert parsed.error.code in {
        ErrorCode.SQLBOT_EXECUTION_FAILED,
        ErrorCode.SQLBOT_DATASOURCE_SESSION_ERROR,
    }
