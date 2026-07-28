"""finance_bi_* tool handlers — always return JSON strings."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from sqlbot_adapter.errors import json_err, json_ok
from sqlbot_adapter.service import get_service

RUNTIME_KEYS = frozenset(
    {
        "session_id",
        "hermes_session_id",
        "conversation_id",
        "user_id",
        "hermes_user_id",
        "platform_user_id",
        "profile",
        "profile_name",
        "hermes_profile",
        "task_id",
        "tool_call_id",
        "request_id",
        "hermes_ctx",
    }
)

BUSINESS_KEYS = frozenset(
    {
        "question",
        "instruction",
        "datasource_key",
        "response_mode",
        "query_id",
    }
)


def normalize_handler_params(
    params: Dict[str, Any] | None,
    runtime_kwargs: Mapping[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Split tool business params from Hermes runtime kwargs.

    1. First positional arg as dict -> business params from that dict.
    2. Keyword args still supported for tests / direct calls.
    3. Runtime fields never mix into business payload.
    """
    payload: Dict[str, Any] = {}
    runtime: Dict[str, Any] = {}

    if isinstance(params, Mapping):
        for k, v in params.items():
            if k in RUNTIME_KEYS:
                runtime[k] = v
            else:
                payload[k] = v
    elif params is not None:
        # Compatibility: some callers may pass question as first positional string
        payload["question"] = params

    for k, v in runtime_kwargs.items():
        if k in RUNTIME_KEYS or k == "hermes_ctx":
            runtime[k] = v
        elif k in BUSINESS_KEYS and k not in payload:
            payload[k] = v
        elif k not in payload and k not in RUNTIME_KEYS:
            # Unknown keys treated as business only if not runtime-like
            payload[k] = v

    hermes_ctx = runtime.get("hermes_ctx")
    if hermes_ctx is None:
        hermes_ctx = {k: v for k, v in runtime.items() if k != "hermes_ctx"}
    return payload, hermes_ctx if isinstance(hermes_ctx, (dict, Mapping)) or hermes_ctx else runtime


def finance_bi_ask(params: dict | None = None, **runtime_kwargs: Any) -> str:
    try:
        payload, hermes_ctx = normalize_handler_params(params, runtime_kwargs)
        return json_ok(
            get_service().ask(
                str(payload.get("question") or ""),
                datasource_key=str(payload.get("datasource_key") or ""),
                response_mode=str(payload.get("response_mode") or "data_and_summary"),
                hermes_ctx=hermes_ctx,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_followup(params: dict | None = None, **runtime_kwargs: Any) -> str:
    try:
        payload, hermes_ctx = normalize_handler_params(params, runtime_kwargs)
        return json_ok(
            get_service().followup(
                str(payload.get("instruction") or ""),
                response_mode=str(payload.get("response_mode") or "data_and_summary"),
                hermes_ctx=hermes_ctx,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_explain(params: dict | None = None, **runtime_kwargs: Any) -> str:
    try:
        payload, hermes_ctx = normalize_handler_params(params, runtime_kwargs)
        return json_ok(
            get_service().explain(
                query_id=str(payload.get("query_id") or ""),
                hermes_ctx=hermes_ctx,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_reset(params: dict | None = None, **runtime_kwargs: Any) -> str:
    try:
        _, hermes_ctx = normalize_handler_params(params if params is not None else {}, runtime_kwargs)
        return json_ok(get_service().reset(hermes_ctx=hermes_ctx))
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)
