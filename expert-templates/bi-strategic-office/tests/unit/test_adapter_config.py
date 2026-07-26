#!/usr/bin/env python3
"""Unit tests for AdapterConfig (v1.11.1)."""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.config import load_config


def test_load_config_defaults():
    cfg = load_config({})
    assert cfg.request_timeout_seconds == 120
    assert cfg.connect_timeout_seconds == 15
    assert cfg.model_result_rows == 100
    assert cfg.max_result_rows == 500
    assert cfg.verify_ssl is True
    assert cfg.is_configured() is False
    assert "SQLBOT_MCP_URL" in cfg.missing_required()
    assert "SQLBOT_SESSION_ENCRYPTION_KEY" in cfg.missing_required()


def test_load_config_required():
    cfg = load_config(
        {
            "SQLBOT_MCP_URL": "http://sqlbot:8001/mcp",
            "SQLBOT_USERNAME": "u",
            "SQLBOT_PASSWORD": "p",
            "SQLBOT_WORKSPACE_ID": "ws1",
            "SQLBOT_DEFAULT_DATASOURCE_ID": "ds1",
            "SQLBOT_SESSION_ENCRYPTION_KEY": "enc-key",
            "SQLBOT_DATASOURCE_ALIASES": "finance-ar:ds_ar,finance-sales:ds_sales",
            "SQLBOT_VERIFY_SSL": "false",
            "SQLBOT_MODEL_RESULT_ROWS": "50",
        }
    )
    assert cfg.is_configured()
    assert cfg.verify_ssl is False
    assert cfg.model_result_rows == 50
    assert cfg.session_encryption_key == "enc-key"
    assert cfg.resolve_datasource_id("finance-ar") == "ds_ar"
    assert cfg.resolve_datasource_id("") == "ds1"
    assert cfg.resolve_datasource_id("unknown") == "ds1"
