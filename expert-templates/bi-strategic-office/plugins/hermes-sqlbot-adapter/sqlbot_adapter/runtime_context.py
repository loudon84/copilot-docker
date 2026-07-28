"""Extract Hermes runtime context — never accept session/user from model args."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError


@dataclass
class RuntimeContext:
    profile_name: str
    hermes_session_id: str
    hermes_user_id: str
    source: str = "gateway"
    request_id: str = ""
    task_id: str = ""
    tool_call_id: str = ""


def _get(obj: Any, *names: str) -> str:
    if obj is None:
        return ""
    for name in names:
        if isinstance(obj, dict) and obj.get(name):
            return str(obj.get(name))
        if hasattr(obj, name):
            val = getattr(obj, name)
            if val:
                return str(val)
    return ""


def resolve_runtime_context(
    *,
    hermes_ctx: Any = None,
    environ: Optional[dict] = None,
    allow_cli_fallback: bool = True,
) -> RuntimeContext:
    """
    Priority: hermes_ctx kwargs > explicit RuntimeContext > CLI env.

    Gateway must obtain session_id; never fall back to fixed shared cli-session.
    Without user_id, isolate by session_id (never shared local-cli).
    CLI requires explicit SQLBOT_CLI_SESSION_ID.
    """
    env = environ if environ is not None else os.environ
    profile = (
        _get(hermes_ctx, "profile", "profile_name", "hermes_profile")
        or (env.get("HERMES_PROFILE") or "").strip()
        or "default"
    )
    session_id = (
        _get(hermes_ctx, "session_id", "hermes_session_id", "conversation_id")
        or (env.get("HERMES_SESSION_ID") or "").strip()
    )
    user_id = (
        _get(hermes_ctx, "user_id", "hermes_user_id", "platform_user_id")
        or (env.get("HERMES_USER_ID") or "").strip()
    )
    task_id = _get(hermes_ctx, "task_id") or (env.get("HERMES_TASK_ID") or "").strip()
    tool_call_id = (
        _get(hermes_ctx, "tool_call_id") or (env.get("HERMES_TOOL_CALL_ID") or "").strip()
    )
    request_id = (
        _get(hermes_ctx, "request_id")
        or (env.get("HERMES_REQUEST_ID") or "").strip()
        or str(uuid.uuid4())
    )

    has_gateway_hints = bool(
        hermes_ctx is not None
        or (env.get("HERMES_SESSION_ID") or "").strip()
        or (env.get("HERMES_GATEWAY") or "").strip().lower() in {"1", "true", "yes"}
    )
    source = "gateway" if has_gateway_hints or not allow_cli_fallback else "cli"

    if not session_id:
        if source == "gateway" or not allow_cli_fallback:
            raise SqlbotAdapterError(
                ErrorCode.RUNTIME_CONTEXT_UNAVAILABLE,
                "无法获取 Hermes session_id，禁止回退到共享会话。",
            )
        cli_session = (env.get("SQLBOT_CLI_SESSION_ID") or "").strip()
        if not cli_session:
            raise SqlbotAdapterError(
                ErrorCode.RUNTIME_CONTEXT_UNAVAILABLE,
                "CLI 模式必须显式设置 SQLBOT_CLI_SESSION_ID。",
            )
        session_id = cli_session
        source = "cli"

    if not user_id:
        # Isolate by session — never share a fixed local-cli identity across sessions.
        user_id = f"session:{session_id}"
        if source != "gateway":
            source = "cli"

    return RuntimeContext(
        profile_name=profile,
        hermes_session_id=session_id,
        hermes_user_id=user_id,
        source=source,
        request_id=request_id,
        task_id=task_id,
        tool_call_id=tool_call_id,
    )
