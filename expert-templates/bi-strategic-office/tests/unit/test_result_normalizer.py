#!/usr/bin/env python3
"""Unit tests for result normalizer."""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.client.mcp_client import QuestionResult
from sqlbot_adapter.normalizer.result_normalizer import normalize_question_result


def test_normalize_basic():
    result = QuestionResult(
        sql="SELECT product_name, profit FROM t",
        columns=[{"name": "product_name", "label": "产品"}, {"name": "profit", "type": "number"}],
        rows=[{"product_name": "A", "profit": 1.5}],
        title="demo",
        chat_id="secret-chat",
    )
    out = normalize_question_result(
        result,
        question="查询利润",
        datasource_key="finance-sales-profit",
        truncated=False,
    )
    d = out.to_dict()
    assert d["success"] is True
    assert d["query_id"].startswith("fbq_")
    assert d["meta"]["source"] == "sqlbot"
    assert d["columns"][0]["label"] == "产品"
    assert d["rows"][0]["profit"] == 1.5
    # chat_id must not appear in normalized payload
    assert "chat_id" not in str(d)
