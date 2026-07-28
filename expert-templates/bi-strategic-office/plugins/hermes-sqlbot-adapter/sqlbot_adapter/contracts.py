"""Shared contracts / result shapes for SQLBot Adapter."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from sqlbot_adapter.errors import (  # noqa: F401
    ErrorCode,
    SqlbotAdapterError,
    classify_sqlbot_failure,
    json_err,
    json_ok,
    map_http_error,
    scrub_secrets,
)


@dataclass
class NormalizedResult:
    success: bool = True
    query_id: str = ""
    upstream_record_id: str = ""
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
