from __future__ import annotations

from finance_bi.contracts import FinanceBiError
from finance_bi.handlers import get_service, json_err, json_ok


def finance_bi_ask(question: str = "", output_mode: str = "table_and_summary", session_id: str = "", **_: object) -> str:
    try:
        return json_ok(get_service().ask(question, output_mode=output_mode, session_id=session_id))
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_followup(
    base_query_id: str = "",
    instruction: str = "",
    session_id: str = "",
    output_mode: str = "table_and_summary",
    **_: object,
) -> str:
    try:
        return json_ok(
            get_service().followup(
                base_query_id,
                instruction,
                session_id=session_id,
                output_mode=output_mode,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_explain(query_id: str = "", topic: str = "", metric: str = "", **_: object) -> str:
    try:
        return json_ok(get_service().explain(query_id=query_id, topic=topic, metric=metric))
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_catalog_search(
    query: str = "",
    kind: str = "all",
    q: str = "",
    keyword: str = "",
    search: str = "",
    text: str = "",
    **kwargs: object,
) -> str:
    """Search semantic catalog. Tolerates common LLM argument mix-ups."""
    try:
        # Hermes/LLM sometimes put the search term in `kind`, or use alias keys.
        raw_query = query or q or keyword or search or text or kwargs.get("query") or ""
        raw_kind = kind or kwargs.get("kind") or "all"
        if isinstance(raw_query, (list, tuple)):
            raw_query = " ".join(str(x) for x in raw_query)
        if isinstance(raw_kind, (list, tuple)):
            raw_kind = str(raw_kind[0]) if raw_kind else "all"
        return json_ok(
            get_service().catalog_search(query=str(raw_query or ""), kind=str(raw_kind or "all"))
        )
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_validate_result(query_id: str = "", **_: object) -> str:
    try:
        return json_ok(get_service().validate(query_id))
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


def finance_bi_export_result(query_id: str = "", format: str = "csv", **_: object) -> str:
    try:
        return json_ok(get_service().export(query_id, fmt=format))
    except Exception as exc:  # noqa: BLE001
        return json_err(exc)


# Avoid unused import lint for FinanceBiError re-export clarity
_ = FinanceBiError
