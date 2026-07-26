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
    source = "gateway"
    if not session_id:
        if allow_cli_fallback:
            session_id = (env.get("SQLBOT_CLI_SESSION_ID") or "cli-session").strip()
            source = "cli"
        else:
            raise SqlbotAdapterError(
                ErrorCode.RUNTIME_CONTEXT_UNAVAILABLE,
                "无法获取 Hermes session_id，禁止回退到共享会话。",
            )
    if not user_id:
        if allow_cli_fallback or source == "cli":
            user_id = "local-cli"
            source = "cli"
        else:
            raise SqlbotAdapterError(
                ErrorCode.RUNTIME_CONTEXT_UNAVAILABLE,
                "无法获取 Hermes user_id，禁止回退到共享用户。",
            )
    return RuntimeContext(
        profile_name=profile,
        hermes_session_id=session_id,
        hermes_user_id=user_id,
        source=source,
        request_id=str(uuid.uuid4()),
    )
