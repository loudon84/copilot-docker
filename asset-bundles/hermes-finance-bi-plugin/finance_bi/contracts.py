from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ErrorCode(str, Enum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    CATALOG_NOT_READY = "CATALOG_NOT_READY"
    METRIC_NOT_FOUND = "METRIC_NOT_FOUND"
    DIMENSION_NOT_FOUND = "DIMENSION_NOT_FOUND"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    QUERY_POLICY_VIOLATION = "QUERY_POLICY_VIOLATION"
    ACCESS_DENIED = "ACCESS_DENIED"
    QUERY_TOO_EXPENSIVE = "QUERY_TOO_EXPENSIVE"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    DATASOURCE_UNAVAILABLE = "DATASOURCE_UNAVAILABLE"
    QUERY_NOT_FOUND = "QUERY_NOT_FOUND"
    EXPORT_FAILED = "EXPORT_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class FinanceBiError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.code.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class FilterClause:
    field: str
    operator: str
    value: Any


@dataclass
class OrderByClause:
    field: str
    direction: str = "desc"


@dataclass
class SemanticQuery:
    dataset: str
    metrics: List[str]
    dimensions: List[str] = field(default_factory=list)
    filters: List[FilterClause] = field(default_factory=list)
    order_by: List[OrderByClause] = field(default_factory=list)
    limit: int = 200
    metric_versions: Dict[str, int] = field(default_factory=dict)
    title: str = ""
    # aggregate = GROUP BY + SUM; detail = row-level lines (no GROUP BY)
    mode: str = "aggregate"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "metrics": list(self.metrics),
            "dimensions": list(self.dimensions),
            "filters": [asdict(f) for f in self.filters],
            "order_by": [asdict(o) for o in self.order_by],
            "limit": self.limit,
            "metric_versions": dict(self.metric_versions),
            "title": self.title,
            "mode": self.mode or "aggregate",
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticQuery":
        return cls(
            dataset=data["dataset"],
            metrics=list(data.get("metrics") or []),
            dimensions=list(data.get("dimensions") or []),
            filters=[FilterClause(**f) for f in data.get("filters") or []],
            order_by=[OrderByClause(**o) for o in data.get("order_by") or []],
            limit=int(data.get("limit") or 200),
            metric_versions=dict(data.get("metric_versions") or {}),
            title=str(data.get("title") or ""),
            mode=str(data.get("mode") or "aggregate"),
        )
