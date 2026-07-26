"""Parse SQLBot MCP tool results (nested JSON, TextContent, fences)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError, classify_sqlbot_failure

FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


@dataclass
class ParsedQuestion:
    raw: Dict[str, Any] = field(default_factory=dict)
    sql: str = ""
    columns: List[Any] = field(default_factory=list)
    rows: List[Any] = field(default_factory=list)
    chart: Any = None
    summary: Any = None
    title: str = ""
    chat_id: str = ""
    access_token: str = ""
    filters: List[Any] = field(default_factory=list)
    error: Optional[SqlbotAdapterError] = None


def _try_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = FENCE_RE.search(text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                return None
        return None


def unwrap_nested(data: Any, depth: int = 0, max_depth: int = 3) -> Dict[str, Any]:
    """Recursively unwrap MCP TextContent / message-embedded JSON (max 3 layers)."""
    if depth > max_depth:
        return data if isinstance(data, dict) else {"value": data}

    if data is None:
        return {}

    if isinstance(data, str):
        parsed = _try_json(data)
        if parsed is None:
            return {"text": data}
        return unwrap_nested(parsed, depth + 1, max_depth)

    if isinstance(data, list):
        # MCP content blocks
        texts: List[str] = []
        for block in data:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text") is not None:
                    texts.append(str(block["text"]))
                elif "text" in block:
                    texts.append(str(block["text"]))
            elif hasattr(block, "text"):
                texts.append(str(getattr(block, "text")))
            else:
                texts.append(str(block))
        joined = "\n".join(texts).strip()
        if joined:
            return unwrap_nested(joined, depth + 1, max_depth)
        return {"items": data}

    if isinstance(data, dict):
        # structuredContent / result wrappers
        if "structuredContent" in data and data["structuredContent"] is not None:
            return unwrap_nested(data["structuredContent"], depth + 1, max_depth)
        if "content" in data and isinstance(data["content"], list):
            inner = unwrap_nested(data["content"], depth + 1, max_depth)
            # merge top-level keys that are useful
            if isinstance(inner, dict):
                merged = dict(inner)
                for k in ("chat_id", "access_token", "token", "sql"):
                    if k in data and k not in merged:
                        merged[k] = data[k]
                # message may itself be JSON
                if isinstance(merged.get("message"), str):
                    nested_msg = _try_json(merged["message"])
                    if isinstance(nested_msg, dict):
                        merged = {**merged, **nested_msg, "message": nested_msg.get("message", merged["message"])}
                return merged
            return {"content": inner}

        # message field embeds JSON error
        msg = data.get("message")
        if isinstance(msg, str):
            nested = _try_json(msg)
            if isinstance(nested, dict):
                out = dict(data)
                out.update(nested)
                if "message" in nested:
                    out["message"] = nested["message"]
                return unwrap_nested(out, depth + 1, max_depth)

        return data

    return {"value": data}


def extract_from_mcp_result(result: Any) -> Dict[str, Any]:
    """Normalize CallToolResult / dict into a plain dict."""
    if result is None:
        return {}
    if isinstance(result, dict):
        return unwrap_nested(result)
    # mcp CallToolResult-like
    content = getattr(result, "content", None)
    structured = getattr(result, "structuredContent", None)
    payload: Dict[str, Any] = {}
    if structured is not None:
        payload = unwrap_nested(structured)
    elif content is not None:
        payload = unwrap_nested(content)
    else:
        payload = unwrap_nested(result)
    if not isinstance(payload, dict):
        return {"data": payload}
    return payload


def parse_start_result(data: Dict[str, Any]) -> Dict[str, Any]:
    d = unwrap_nested(data) if not isinstance(data, dict) else data
    if not isinstance(d, dict):
        d = {}
    token = d.get("access_token") or d.get("token")
    if not token and isinstance(d.get("data"), dict):
        token = d["data"].get("access_token") or d["data"].get("token")
    chat_id = d.get("chat_id") or d.get("id")
    if chat_id is None and isinstance(d.get("data"), dict):
        chat_id = d["data"].get("chat_id") or d["data"].get("id")
    expires_in = int(d.get("expires_in") or d.get("ttl") or 3600)
    if not token:
        raise SqlbotAdapterError(ErrorCode.SQLBOT_AUTH_FAILED, "SQLBot 登录失败：未返回 access_token")
    return {
        "access_token": str(token),
        "chat_id": str(chat_id) if chat_id is not None else "",
        "expires_in": expires_in,
        "raw": d,
    }


def parse_question_result(data: Dict[str, Any]) -> ParsedQuestion:
    d = data if isinstance(data, dict) else unwrap_nested(data)
    if not isinstance(d, dict):
        raise SqlbotAdapterError(ErrorCode.SQLBOT_RESPONSE_INVALID, "SQLBot 返回结构无法解析")

    # Nested error in message (string JSON or dict)
    err_type = str(d.get("type") or "")
    traceback_text = str(d.get("traceback") or "")
    raw_message = d.get("message")
    message = ""
    nested_err: Dict[str, Any] = {}
    if isinstance(raw_message, dict):
        nested_err = dict(raw_message)
        message = str(nested_err.get("message") or "")
        err_type = str(nested_err.get("type") or err_type)
        traceback_text = str(nested_err.get("traceback") or traceback_text)
    else:
        message = str(raw_message or "")

    if (
        err_type in {"exec-sql-err", "execute_sql_failed"}
        or "Execute SQL Failed" in message
        or "DetachedInstanceError" in message
        or "DetachedInstanceError" in traceback_text
        or traceback_text
    ):
        nested = {**d, **nested_err}
        if isinstance(raw_message, str):
            maybe = _try_json(raw_message)
            if isinstance(maybe, dict):
                nested = {**nested, **maybe}
                message = str(nested.get("message") or message)
                traceback_text = str(nested.get("traceback") or traceback_text)
                err_type = str(nested.get("type") or err_type)
        err = classify_sqlbot_failure(message, traceback_text, err_type)
        sql = str(
            nested.get("sql")
            or nested.get("query_sql")
            or (nested.get("query") or {}).get("sql")
            or d.get("sql")
            or ""
        )
        return ParsedQuestion(
            raw=d,
            sql=sql,
            chat_id=str(nested.get("chat_id") or d.get("chat_id") or ""),
            error=err,
        )

    nested = d.get("data") if isinstance(d.get("data"), dict) else d
    sql = str(
        nested.get("sql")
        or nested.get("query_sql")
        or (nested.get("query") or {}).get("sql")
        or ""
    )
    columns = nested.get("columns") or nested.get("fields") or []
    rows = nested.get("rows") or nested.get("result") or []
    if isinstance(rows, dict):
        rows = rows.get("rows") or []
    if not isinstance(rows, list):
        rows = []
    if not isinstance(columns, list):
        columns = []

    # Soft failure: error key without rows
    if nested.get("error") and not rows and not sql:
        raise SqlbotAdapterError(
            ErrorCode.SQLBOT_QUERY_GENERATION_FAILED,
            str(nested.get("error")),
            source="sqlbot",
        )

    return ParsedQuestion(
        raw=d,
        sql=sql,
        columns=columns,
        rows=rows,
        chart=nested.get("chart"),
        summary=nested.get("summary") or nested.get("answer"),
        title=str(nested.get("title") or nested.get("name") or ""),
        chat_id=str(nested.get("chat_id") or d.get("chat_id") or ""),
        access_token=str(nested.get("access_token") or d.get("access_token") or ""),
        filters=list(nested.get("filters") or []) if isinstance(nested.get("filters"), list) else [],
    )
