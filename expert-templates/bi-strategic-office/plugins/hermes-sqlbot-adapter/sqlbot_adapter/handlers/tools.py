"""finance_bi_* tool handlers — always return JSON strings."""

from __future__ import annotations

from sqlbot_adapter.contracts import json_err, json_ok
from sqlbot_adapter.handlers.service import get_service


def finance_bi_ask(
    question: str = "",
    datasource_key: str = "",
    response_mode: str = "data_and_summary",
    session_id: str = "",
    user_id: str = "",
    **_: object,
) -> str:
    try:
        return json_ok(
            get_service().ask(
                question,
                datasource_key=datasource_key,
                response_mode=response_mode,
                session_id=session_id,
                user_id=user_id,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_followup(
    instruction: str = "",
    session_id: str = "",
    user_id: str = "",
    response_mode: str = "data_and_summary",
    **_: object,
) -> str:
    try:
        return json_ok(
            get_service().followup(
                instruction,
                session_id=session_id,
                user_id=user_id,
                response_mode=response_mode,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_explain(
    query_id: str = "",
    session_id: str = "",
    user_id: str = "",
    **_: object,
) -> str:
    try:
        return json_ok(
            get_service().explain(
                query_id=query_id,
                session_id=session_id,
                user_id=user_id,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_reset(
    session_id: str = "",
    user_id: str = "",
    **_: object,
) -> str:
    try:
        return json_ok(get_service().reset(session_id=session_id, user_id=user_id))
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)
