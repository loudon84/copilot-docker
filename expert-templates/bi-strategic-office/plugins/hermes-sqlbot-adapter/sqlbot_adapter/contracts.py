"""Contracts, error codes, and JSON helpers for SQLBot Adapter."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ErrorCode(str, Enum):
    SQLBOT_NOT_CONFIGURED = "SQLBOT_NOT_CONFIGURED"
    SQLBOT_UNAVAILABLE = "SQLBOT_UNAVAILABLE"
    SQLBOT_AUTH_FAILED = "SQLBOT_AUTH_FAILED"
    WORKSPACE_NOT_FOUND = "WORKSPACE_NOT_FOUND"
    DATASOURCE_NOT_FOUND = "DATASOURCE_NOT_FOUND"
    QUERY_CONTEXT_NOT_FOUND = "QUERY_CONTEXT_NOT_FOUND"
    QUERY_GENERATION_FAILED = "QUERY_GENERATION_FAILED"
    QUERY_EXECUTION_FAILED = "QUERY_EXECUTION_FAILED"
    FILTER_NOT_PRESERVED = "FILTER_NOT_PRESERVED"
    UNSAFE_SQL = "UNSAFE_SQL"
    DETAIL_QUERY_REQUIRES_FILTER = "DETAIL_QUERY_REQUIRES_FILTER"
    RESULT_TOO_LARGE = "RESULT_TOO_LARGE"
    SQLBOT_RESPONSE_INVALID = "SQLBOT_RESPONSE_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"


class SqlbotAdapterError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": False,
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
            },
        }


@dataclass
class NormalizedColumn:
    name: str
    label: str = ""
    type: str = "string"

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "label": self.label or self.name, "type": self.type}


@dataclass
class NormalizedResult:
    success: bool = True
    query_id: str = ""
    title: str = ""
    datasource: Dict[str, Any] = field(default_factory=dict)
    query: Dict[str, Any] = field(default_factory=dict)
    columns: List[Dict[str, Any]] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    chart: Any = None
    summary: Any = None
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    }
)


def scrub_secrets(obj: Any) -> Any:
    """Recursively remove sensitive keys from structures returned to the model."""
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


def json_ok(payload: Dict[str, Any] | NormalizedResult) -> str:
    data = payload.to_dict() if isinstance(payload, NormalizedResult) else dict(payload)
    data = scrub_secrets(data)
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
    msg = message or f"SQLBot HTTP {status_code}"
    if status_code in (401, 403):
        return SqlbotAdapterError(ErrorCode.SQLBOT_AUTH_FAILED, "SQLBot 登录失败或 Token 无效")
    if status_code == 404:
        if "workspace" in msg.lower():
            return SqlbotAdapterError(ErrorCode.WORKSPACE_NOT_FOUND, "工作空间不存在")
        if "datasource" in msg.lower() or "data_source" in msg.lower():
            return SqlbotAdapterError(ErrorCode.DATASOURCE_NOT_FOUND, "数据源不存在")
        return SqlbotAdapterError(ErrorCode.SQLBOT_UNAVAILABLE, msg)
    if status_code >= 500:
        return SqlbotAdapterError(ErrorCode.SQLBOT_UNAVAILABLE, "SQLBot 服务不可访问")
    return SqlbotAdapterError(ErrorCode.SQLBOT_RESPONSE_INVALID, msg)
