"""Error codes and exceptions for hermes-sqlbot-adapter (v1.11.1)."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    SQLBOT_NOT_CONFIGURED = "SQLBOT_NOT_CONFIGURED"
    SQLBOT_TRANSPORT_ERROR = "SQLBOT_TRANSPORT_ERROR"
    SQLBOT_INITIALIZE_FAILED = "SQLBOT_INITIALIZE_FAILED"
    SQLBOT_MCP_TOOL_UNAVAILABLE = "SQLBOT_MCP_TOOL_UNAVAILABLE"
    SQLBOT_AUTH_FAILED = "SQLBOT_AUTH_FAILED"
    SQLBOT_SESSION_EXPIRED = "SQLBOT_SESSION_EXPIRED"
    SQLBOT_WORKSPACE_NOT_FOUND = "SQLBOT_WORKSPACE_NOT_FOUND"
    SQLBOT_DATASOURCE_NOT_FOUND = "SQLBOT_DATASOURCE_NOT_FOUND"
    SQLBOT_QUERY_GENERATION_FAILED = "SQLBOT_QUERY_GENERATION_FAILED"
    SQLBOT_EXECUTION_FAILED = "SQLBOT_EXECUTION_FAILED"
    SQLBOT_DATASOURCE_SESSION_ERROR = "SQLBOT_DATASOURCE_SESSION_ERROR"
    SQLBOT_RESPONSE_INVALID = "SQLBOT_RESPONSE_INVALID"
    SQLBOT_UNAVAILABLE = "SQLBOT_UNAVAILABLE"
    FILTER_NOT_PRESERVED = "FILTER_NOT_PRESERVED"
    UNSAFE_SQL = "UNSAFE_SQL"
    DETAIL_QUERY_REQUIRES_FILTER = "DETAIL_QUERY_REQUIRES_FILTER"
    RESULT_TOO_LARGE = "RESULT_TOO_LARGE"
    QUERY_CONTEXT_NOT_FOUND = "QUERY_CONTEXT_NOT_FOUND"
    RUNTIME_CONTEXT_UNAVAILABLE = "RUNTIME_CONTEXT_UNAVAILABLE"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Errors that may retry once (transport / initialize only)
RETRYABLE = frozenset(
    {
        ErrorCode.SQLBOT_TRANSPORT_ERROR,
        ErrorCode.SQLBOT_INITIALIZE_FAILED,
    }
)


class SqlbotAdapterError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        source: str = "adapter",
        retryable: bool | None = None,
        traceback_text: str = "",
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.source = source
        self.retryable = RETRYABLE.__contains__(code) if retryable is None else bool(retryable)
        self.traceback_text = traceback_text or ""

    def to_dict(self) -> Dict[str, Any]:
        err: Dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "source": self.source,
        }
        # Never put traceback into tool result
        if self.details:
            safe = {k: v for k, v in self.details.items() if k.lower() not in {"traceback", "access_token", "password", "token"}}
            if safe:
                err["details"] = safe
        return {"success": False, "error": err}


def classify_sqlbot_failure(
    message: str = "",
    traceback_text: str = "",
    err_type: str = "",
) -> SqlbotAdapterError:
    """Map SQLBot nested execution errors to adapter error codes."""
    blob = "\n".join([message or "", traceback_text or "", err_type or ""])
    lower = blob.lower()

    if "detachedinstanceerror" in lower or "detached instance" in lower:
        return SqlbotAdapterError(
            ErrorCode.SQLBOT_DATASOURCE_SESSION_ERROR,
            "SQLBot 已生成 SQL，但数据源会话失效，查询未执行。",
            source="sqlbot",
            retryable=False,
            traceback_text=traceback_text,
        )
    if err_type in {"exec-sql-err", "execute_sql_failed"} or "execute sql failed" in lower:
        return SqlbotAdapterError(
            ErrorCode.SQLBOT_EXECUTION_FAILED,
            "SQLBot 执行查询失败。",
            source="sqlbot",
            retryable=False,
            traceback_text=traceback_text,
            details={"sqlbot_type": err_type} if err_type else None,
        )
    if "auth" in lower or "login" in lower or "unauthorized" in lower:
        return SqlbotAdapterError(
            ErrorCode.SQLBOT_AUTH_FAILED,
            "SQLBot 登录失败。",
            source="sqlbot",
            retryable=False,
        )
    if "workspace" in lower and ("not found" in lower or "不存在" in message):
        return SqlbotAdapterError(
            ErrorCode.SQLBOT_WORKSPACE_NOT_FOUND,
            "工作空间不存在。",
            source="sqlbot",
            retryable=False,
        )
    if "datasource" in lower and ("not found" in lower or "不存在" in message):
        return SqlbotAdapterError(
            ErrorCode.SQLBOT_DATASOURCE_NOT_FOUND,
            "数据源不存在。",
            source="sqlbot",
            retryable=False,
        )
    return SqlbotAdapterError(
        ErrorCode.SQLBOT_EXECUTION_FAILED,
        message or "SQLBot 查询失败。",
        source="sqlbot",
        retryable=False,
        traceback_text=traceback_text,
    )


SENSITIVE_KEYS = frozenset(
    {
        "password",
        "access_token",
        "token",
        "chat_id",
        "sqlbot_chat_id",
        "username",
        "passwd",
        "authorization",
        "refresh_token",
        "traceback",
        "sqlbot_session_encryption_key",
    }
)


def scrub_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in SENSITIVE_KEYS:
                continue
            out[k] = scrub_secrets(v)
        return out
    if isinstance(obj, list):
        return [scrub_secrets(x) for x in obj]
    return obj


def json_ok(payload: Dict[str, Any]) -> str:
    data = scrub_secrets(dict(payload))
    if "success" not in data:
        data["success"] = True
    return json.dumps(data, ensure_ascii=False, default=str)


def json_err(exc: BaseException) -> str:
    if isinstance(exc, SqlbotAdapterError):
        return json.dumps(scrub_secrets(exc.to_dict()), ensure_ascii=False, default=str)
    return json.dumps(
        scrub_secrets(
            SqlbotAdapterError(
                ErrorCode.INTERNAL_ERROR,
                f"{type(exc).__name__}: {exc}",
            ).to_dict()
        ),
        ensure_ascii=False,
        default=str,
    )


def map_http_error(status_code: int, message: str = "") -> SqlbotAdapterError:
    """Map HTTP-ish status to adapter errors (compat / transport probes)."""
    code = int(status_code or 0)
    if code in {401, 403}:
        return SqlbotAdapterError(
            ErrorCode.SQLBOT_AUTH_FAILED,
            message or "SQLBot 认证失败",
            source="sqlbot",
            retryable=False,
        )
    if code in {404}:
        return SqlbotAdapterError(
            ErrorCode.SQLBOT_UNAVAILABLE,
            message or "SQLBot MCP 端点不存在",
            source="sqlbot",
            retryable=False,
        )
    if code >= 500 or code in {408, 429}:
        return SqlbotAdapterError(
            ErrorCode.SQLBOT_UNAVAILABLE,
            message or f"SQLBot 不可用 (HTTP {code})",
            source="sqlbot",
            retryable=True,
        )
    return SqlbotAdapterError(
        ErrorCode.SQLBOT_TRANSPORT_ERROR,
        message or f"SQLBot HTTP 错误 {code}",
        source="sqlbot",
        retryable=True,
    )
