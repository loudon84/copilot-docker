from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class CheckResult:
    id: str
    dimension: str
    passed: bool
    weight: float
    message: str
    gate: bool = False  # security gate: failure fails whole eval


@dataclass
class CaseResult:
    id: str
    type: str
    passed: bool
    score: float
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationReport:
    expert_id: str
    version: str
    mode: str
    passed: bool
    score: float
    minimum_score: float
    security_gates_passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    cases: list[CaseResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expert_id": self.expert_id,
            "version": self.version,
            "mode": self.mode,
            "passed": self.passed,
            "score": round(self.score, 4),
            "minimum_score": self.minimum_score,
            "security_gates_passed": self.security_gates_passed,
            "summary": self.summary,
            "checks": [
                {
                    "id": c.id,
                    "dimension": c.dimension,
                    "passed": c.passed,
                    "weight": c.weight,
                    "message": c.message,
                    "gate": c.gate,
                }
                for c in self.checks
            ],
            "cases": [
                {
                    "id": c.id,
                    "type": c.type,
                    "passed": c.passed,
                    "score": c.score,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.cases
            ],
        }


WEIGHTS = {
    "task": 0.30,
    "skill": 0.15,
    "tool": 0.15,
    "output": 0.15,
    "permission": 0.15,
    "exception": 0.10,
}
