#!/usr/bin/env python3
"""Unit tests for error mapping / json helpers (v1.11.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.contracts import (
    ErrorCode,
    SqlbotAdapterError,
    classify_sqlbot_failure,
    json_err,
    json_ok,
    map_http_error,
    scrub_secrets,
)


def test_map_http_error():
    assert map_http_error(401).code == ErrorCode.SQLBOT_AUTH_FAILED
    assert map_http_error(503).code == ErrorCode.SQLBOT_UNAVAILABLE


def test_detached_instance_error_mapping():
    err = classify_sqlbot_failure(
        message="execute sql failed",
        traceback_text="sqlalchemy.orm.exc.DetachedInstanceError: Instance is not bound",
        err_type="exec-sql-err",
    )
    assert err.code == ErrorCode.SQLBOT_DATASOURCE_SESSION_ERROR
    assert err.source == "sqlbot"
    assert err.retryable is False
    payload = json.loads(json_err(err))
    assert "DetachedInstanceError" not in json.dumps(payload)
    assert "traceback" not in json.dumps(payload).lower()


def test_json_err_and_scrub():
    err = SqlbotAdapterError(ErrorCode.FILTER_NOT_PRESERVED, "lost filter")
    payload = json.loads(json_err(err))
    assert payload["success"] is False
    assert payload["error"]["code"] == "FILTER_NOT_PRESERVED"

    dirty = {"access_token": "abc", "rows": [1], "password": "x", "ok": True}
    clean = scrub_secrets(dirty)
    assert "access_token" not in clean
    assert "password" not in clean
    assert clean["ok"] is True

    ok = json.loads(json_ok({"query_id": "fbq_1", "chat_id": "hidden"}))
    assert ok["success"] is True
    assert "chat_id" not in ok
