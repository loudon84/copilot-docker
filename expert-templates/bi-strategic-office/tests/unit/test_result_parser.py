#!/usr/bin/env python3
"""Unit tests for result_parser nested JSON / DetachedInstanceError."""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.client.result_parser import parse_question_result, unwrap_nested
from sqlbot_adapter.errors import ErrorCode


def test_unwrap_nested_message_json():
    outer = {
        "content": [
            {
                "type": "text",
                "text": '{"message": "{\\"type\\": \\"exec-sql-err\\", \\"message\\": \\"DetachedInstanceError: x\\"}"}',
            }
        ]
    }
    data = unwrap_nested(outer)
    assert isinstance(data, dict)


def test_parse_detached_instance():
    payload = {
        "sql": "SELECT 1",
        "message": {
            "type": "exec-sql-err",
            "message": "sqlalchemy.orm.exc.DetachedInstanceError: Instance is not bound to a Session",
        },
    }
    parsed = parse_question_result(payload)
    assert parsed.sql == "SELECT 1"
    assert parsed.error is not None
    assert parsed.error.code == ErrorCode.SQLBOT_DATASOURCE_SESSION_ERROR
