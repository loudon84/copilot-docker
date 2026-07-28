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
    upstream_record_id: str = ""
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
        if "structuredContent" in data and data["structuredContent"] is not None:
            return unwrap_nested(data["structuredContent"], depth + 1, max_depth)
        if "content" in data and isinstance(data["content"], list):
            inner = unwrap_nested(data["content"], depth + 1, max_depth)
            if isinstance(inner, dict):
                merged = dict(inner)
                for k in ("chat_id", "access_token", "token", "sql", "record_id", "title", "success"):
                    if k in data and k not in merged:
                        merged[k] = data[k]
                if isinstance(merged.get("message"), str):
                    nested_msg = _try_json(merged["message"])
                    if isinstance(nested_msg, dict):
                        merged = {
                            **merged,
                            **nested_msg,
                            "message": nested_msg.get("message", merged["message"]),
                        }
                return merged
            return {"content": inner}

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


def _mcp_is_error(result: Any) -> bool:
    if result is None:
        return False
    if isinstance(result, dict):
        if result.get("isError") is True or result.get("is_error") is True:
            return True
    return bool(getattr(result, "isError", False) or getattr(result, "is_error", False))


def _content_error_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if content is None and isinstance(result, dict):
        content = result.get("content")
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if hasattr(block, "text"):
                parts.append(str(getattr(block, "text")))
            elif isinstance(block, dict) and block.get("text") is not None:
                parts.append(str(block["text"]))
            else:
                parts.append(str(block))
        return "\n".join(parts).strip()
    if content is not None:
        return str(content)
    return "MCP tool returned isError=true"


def extract_from_mcp_result(result: Any) -> Dict[str, Any]:
    """Normalize CallToolResult / dict into a plain dict. Raises on isError."""
    if result is None:
        return {}
    if _mcp_is_error(result):
        text = _content_error_text(result)
        nested = _try_json(text) if text else None
        msg = text
        if isinstance(nested, dict):
            msg = str(nested.get("message") or nested.get("error") or text)
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_TOOL_ERROR,
                msg or "SQLBot MCP Tool Error",
                source="sqlbot",
                details={"mcp_is_error": True},
            )
        raise SqlbotAdapterError(
            ErrorCode.SQLBOT_TOOL_ERROR,
            msg or "SQLBot MCP Tool Error",
            source="sqlbot",
            details={"mcp_is_error": True},
        )

    if isinstance(result, dict):
        return unwrap_nested(result)

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
    if d.get("success") is False:
        raise SqlbotAdapterError(
            ErrorCode.SQLBOT_AUTH_FAILED,
            str(d.get("message") or d.get("error") or "SQLBot 登录失败"),
            source="sqlbot",
        )
    token = d.get("access_token") or d.get("token")
    if not token and isinstance(d.get("data"), dict):
        token = d["data"].get("access_token") or d["data"].get("token")
    chat_id = d.get("chat_id") or d.get("id")
    if chat_id is None and isinstance(d.get("data"), dict):
        chat_id = d["data"].get("chat_id") or d["data"].get("id")
    expires_in = int(d.get("expires_in") or d.get("ttl") or 3600)
    if not token:
        raise SqlbotAdapterError(ErrorCode.SQLBOT_AUTH_FAILED, "SQLBot 登录失败：未返回 token")
    return {
        "access_token": str(token),
        "chat_id": str(chat_id) if chat_id is not None else "",
        "expires_in": expires_in,
        "raw": d,
    }


def _pick_rows_and_columns(d: Dict[str, Any], nested: Dict[str, Any]) -> tuple[List[Any], List[Any]]:
    """Preferred: top.data.fields + top.data.data; also columns/rows, fields/result."""
    columns: List[Any] = []
    rows: List[Any] = []

    data_block = d.get("data") if isinstance(d.get("data"), dict) else None
    if data_block is not None:
        if isinstance(data_block.get("fields"), list):
            columns = list(data_block["fields"])
        elif isinstance(data_block.get("columns"), list):
            columns = list(data_block["columns"])
        raw_rows = data_block.get("data")
        if isinstance(raw_rows, list):
            rows = list(raw_rows)
        elif isinstance(data_block.get("rows"), list):
            rows = list(data_block["rows"])
        elif isinstance(data_block.get("result"), list):
            rows = list(data_block["result"])

    if not columns:
        columns = nested.get("columns") or nested.get("fields") or d.get("columns") or d.get("fields") or []
    if not rows:
        rows = nested.get("rows") or nested.get("result") or d.get("rows") or d.get("result") or []
        if isinstance(rows, dict):
            rows = rows.get("rows") or rows.get("data") or []

    if not isinstance(rows, list):
        rows = []
    if not isinstance(columns, list):
        columns = []
    return columns, rows


def parse_question_result(data: Dict[str, Any]) -> ParsedQuestion:
    d = data if isinstance(data, dict) else unwrap_nested(data)
    if not isinstance(d, dict):
        raise SqlbotAdapterError(ErrorCode.SQLBOT_RESPONSE_INVALID, "SQLBot 返回结构无法解析")

    # Explicit failure markers
    if d.get("success") is False:
        err = classify_sqlbot_failure(
            str(d.get("message") or d.get("error") or "SQLBot 查询失败"),
            str(d.get("traceback") or ""),
            str(d.get("type") or ""),
        )
        return ParsedQuestion(raw=d, error=err)

    code = d.get("code")
    if code is not None and str(code) not in {"0", "None", ""} and code != 0:
        return ParsedQuestion(
            raw=d,
            error=SqlbotAdapterError(
                ErrorCode.SQLBOT_EXECUTION_FAILED,
                str(d.get("message") or f"SQLBot 返回错误码 {code}"),
                source="sqlbot",
            ),
        )

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
        or (traceback_text and err_type)
        or d.get("error")
        and not d.get("sql")
        and d.get("success") is not True
    ):
        nested = {**d, **nested_err}
        if isinstance(raw_message, str):
            maybe = _try_json(raw_message)
            if isinstance(maybe, dict):
                nested = {**nested, **maybe}
                message = str(nested.get("message") or message)
                traceback_text = str(nested.get("traceback") or traceback_text)
                err_type = str(nested.get("type") or err_type)
        if err_type or traceback_text or "Execute SQL Failed" in message or "DetachedInstanceError" in message:
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
                upstream_record_id=str(nested.get("record_id") or d.get("record_id") or ""),
                error=err,
            )

    nested = d.get("data") if isinstance(d.get("data"), dict) else d
    # Prefer top-level sql/title/record_id (verified SQLBot protocol)
    sql = str(
        d.get("sql")
        or nested.get("sql")
        or nested.get("query_sql")
        or (nested.get("query") or {}).get("sql")
        or ""
    )
    columns, rows = _pick_rows_and_columns(d, nested if isinstance(nested, dict) else {})

    if nested.get("error") and not rows and not sql:
        raise SqlbotAdapterError(
            ErrorCode.SQLBOT_QUERY_GENERATION_FAILED,
            str(nested.get("error")),
            source="sqlbot",
        )

    title = str(d.get("title") or nested.get("title") or nested.get("name") or "")
    record_id = d.get("record_id")
    if record_id is None:
        record_id = nested.get("record_id")
    upstream_record_id = str(record_id) if record_id is not None else ""

    chart = d.get("chart")
    if chart is None:
        chart = nested.get("chart")
    summary = d.get("summary") or d.get("answer")
    if summary is None:
        summary = nested.get("summary") or nested.get("answer")

    # Success integrity: when success=true, require sql + fields list + data list
    if d.get("success") is True:
        if not sql:
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_RESPONSE_INVALID,
                "SQLBot 成功响应缺少 sql 字段",
                source="sqlbot",
            )
        data_block = d.get("data")
        if not isinstance(data_block, dict):
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_RESPONSE_INVALID,
                "SQLBot 成功响应缺少 data 对象",
                source="sqlbot",
            )
        if not isinstance(data_block.get("fields"), list) and not columns:
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_RESPONSE_INVALID,
                "SQLBot 成功响应缺少 fields 列表",
                source="sqlbot",
            )
        if not isinstance(data_block.get("data"), list) and not isinstance(rows, list):
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_RESPONSE_INVALID,
                "SQLBot 成功响应缺少 data.data 行列表",
                source="sqlbot",
            )

    return ParsedQuestion(
        raw=d,
        sql=sql,
        columns=columns,
        rows=rows,
        chart=chart,
        summary=summary,
        title=title,
        chat_id=str(nested.get("chat_id") or d.get("chat_id") or ""),
        access_token=str(nested.get("access_token") or nested.get("token") or d.get("token") or ""),
        upstream_record_id=upstream_record_id,
        filters=list(nested.get("filters") or []) if isinstance(nested.get("filters"), list) else [],
    )
