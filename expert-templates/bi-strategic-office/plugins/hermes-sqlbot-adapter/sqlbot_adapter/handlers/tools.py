"""finance_bi_* tool handlers — always return JSON strings."""

from __future__ import annotations

from sqlbot_adapter.errors import json_err, json_ok
from sqlbot_adapter.service import get_service


def finance_bi_ask(
    question: str = "",
    datasource_key: str = "",
    response_mode: str = "data_and_summary",
    **_: object,
) -> str:
    try:
        return json_ok(
            get_service().ask(
                question,
                datasource_key=datasource_key,
                response_mode=response_mode,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_followup(
    instruction: str = "",
    response_mode: str = "data_and_summary",
    **_: object,
) -> str:
    try:
        return json_ok(
            get_service().followup(
                instruction,
                response_mode=response_mode,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_explain(query_id: str = "", **_: object) -> str:
    try:
        return json_ok(get_service().explain(query_id=query_id))
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_reset(**_: object) -> str:
    try:
        return json_ok(get_service().reset())
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)
