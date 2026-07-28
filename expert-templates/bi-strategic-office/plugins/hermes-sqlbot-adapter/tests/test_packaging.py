"""Packaging / wheel subpackage smoke checks."""

from __future__ import annotations

from pathlib import Path

import sqlbot_adapter


def test_version():
    assert sqlbot_adapter.__version__ == "1.12.0"


def test_subpackages_importable():
    from sqlbot_adapter.client.mcp_client import SQLBotMCPClient
    from sqlbot_adapter.handlers.tools import finance_bi_ask
    from sqlbot_adapter.plugin import register
    from sqlbot_adapter.security.query_guard import guard_sql
    from sqlbot_adapter.session.session_store import SessionStore

    assert SQLBotMCPClient is not None
    assert callable(finance_bi_ask)
    assert callable(register)
    assert callable(guard_sql)
    assert SessionStore is not None


def test_pyproject_finds_subpackages():
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["sqlbot_adapter*"]' in text
    assert "hermes_agent.plugins" in text
