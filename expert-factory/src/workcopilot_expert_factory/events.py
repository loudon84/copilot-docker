"""Structured observability events (PRD v2.1 §21)."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator


SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "secret",
        "api_key",
        "apikey",
        "nacos_password",
        "nacos_username",
        "private_key",
        "cookie",
    }
)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if str(k).lower() in SENSITIVE_KEYS or any(s in str(k).lower() for s in ("password", "token", "secret")):
                out[k] = "***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


@dataclass
class ExpertEvent:
    event: str
    trace_id: str
    status: str = "success"
    expert_id: str | None = None
    version: str | None = None
    bundle_digest: str | None = None
    target: str | None = None
    namespace: str | None = None
    duration_ms: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {k: v for k, v in asdict(self).items() if k != "extras" and v is not None}
        if self.extras:
            data.update(_redact(self.extras))
        return data


_active_trace: str | None = None


def new_trace_id(explicit: str | None = None) -> str:
    global _active_trace
    _active_trace = explicit or f"trace_{uuid.uuid4().hex[:16]}"
    return _active_trace


def current_trace_id() -> str:
    return _active_trace or new_trace_id()


def emit(event: str, *, status: str = "success", **kwargs: Any) -> ExpertEvent:
    """Emit a structured event to stderr (JSON line). Never logs secrets."""
    quiet = os.environ.get("WORKCOPILOT_QUIET", "").lower() in {"1", "true", "yes"}
    ev = ExpertEvent(
        event=event,
        trace_id=str(kwargs.pop("trace_id", None) or current_trace_id()),
        status=status,
        expert_id=kwargs.pop("expert_id", None),
        version=kwargs.pop("version", None),
        bundle_digest=kwargs.pop("bundle_digest", None),
        target=kwargs.pop("target", None),
        namespace=kwargs.pop("namespace", None),
        duration_ms=kwargs.pop("duration_ms", None),
        extras=kwargs,
    )
    if not quiet:
        line = json.dumps(ev.to_dict(), ensure_ascii=False)
        print(line, file=sys.stderr)
    return ev


@contextmanager
def timed_event(event_base: str, **kwargs: Any) -> Iterator[dict[str, Any]]:
    """Emit started + completed/failed around a block."""
    started = time.perf_counter()
    emit(f"{event_base}.started", status="started", **kwargs)
    ctx: dict[str, Any] = dict(kwargs)
    try:
        yield ctx
        duration_ms = int((time.perf_counter() - started) * 1000)
        emit(f"{event_base}.completed", status="success", duration_ms=duration_ms, **{**kwargs, **ctx})
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started) * 1000)
        emit(
            f"{event_base}.failed",
            status="failed",
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            error_code=getattr(exc, "code", None),
            **{**kwargs, **ctx},
        )
        raise
