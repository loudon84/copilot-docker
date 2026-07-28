"""Handler compatibility and config/datasource tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from sqlbot_adapter.config import AdapterConfig, load_config
from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.handlers.tools import normalize_handler_params, finance_bi_ask
from sqlbot_adapter.runtime_context import resolve_runtime_context


def test_normalize_params_dict():
    payload, runtime = normalize_handler_params(
        {"question": "q1", "datasource_key": "sales_profit"},
        {"session_id": "s1", "user_id": "u1"},
    )
    assert payload["question"] == "q1"
    assert "session_id" not in payload
    assert runtime["session_id"] == "s1"


def test_normalize_kwargs_compat():
    payload, runtime = normalize_handler_params(
        None,
        {"question": "q2", "session_id": "s2"},
    )
    assert payload["question"] == "q2"
    assert runtime["session_id"] == "s2"


def test_unknown_datasource_key():
    cfg = AdapterConfig(
        default_datasource_id="1",
        datasource_aliases={"sales_profit": "1"},
    )
    assert cfg.resolve_datasource_id("") == "1"
    assert cfg.resolve_datasource_id("sales_profit") == "1"
    with pytest.raises(SqlbotAdapterError) as ei:
        cfg.resolve_datasource_id("unknown_ds")
    assert ei.value.code == ErrorCode.INVALID_DATASOURCE_KEY


def test_int_env_validation():
    with pytest.raises(SqlbotAdapterError):
        load_config({"SQLBOT_MAX_RESULT_ROWS": "abc"})


def test_runtime_context_cli_requires_explicit_session():
    with pytest.raises(SqlbotAdapterError):
        resolve_runtime_context(hermes_ctx=None, environ={}, allow_cli_fallback=True)


def test_runtime_context_gateway_no_shared_fallback():
    with pytest.raises(SqlbotAdapterError):
        resolve_runtime_context(
            hermes_ctx=None,
            environ={"HERMES_GATEWAY": "true"},
            allow_cli_fallback=False,
        )


def test_runtime_isolates_user_by_session():
    ctx = resolve_runtime_context(
        hermes_ctx={"session_id": "abc"},
        environ={},
        allow_cli_fallback=True,
    )
    assert ctx.hermes_session_id == "abc"
    assert ctx.hermes_user_id == "session:abc"


def test_finance_bi_ask_params_dict():
    fake = MagicMock()
    fake.ask.return_value = {"success": True, "query_id": "fbq_x"}
    with patch("sqlbot_adapter.handlers.tools.get_service", return_value=fake):
        out = finance_bi_ask(
            {"question": "hello", "datasource_key": ""},
            session_id="sess-1",
            user_id="user-1",
        )
    data = json.loads(out)
    assert data["success"] is True
    fake.ask.assert_called_once()
    kwargs = fake.ask.call_args
    assert kwargs.args[0] == "hello"
    assert kwargs.kwargs["hermes_ctx"]["session_id"] == "sess-1"
