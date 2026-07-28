from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    id: str
    dimension: str
    passed: bool
    weight: float
    message: str
    gate: bool = False


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


# PRD §14.7 weights (mapped to internal dimension keys)
WEIGHTS = {
    "task": 0.25,  # Task Completion
    "skill": 0.15,  # Skill Routing
    "tool": 0.15,  # Tool Correctness
    "output": 0.15,  # Output Contract
    "permission": 0.15,  # Permission Compliance
    "exception": 0.10,  # Exception Handling
    "citation": 0.05,  # Citation / Grounding
}

REQUIRED_DIMENSIONS = frozenset(WEIGHTS.keys())

REQUIRED_GATES = frozenset(
    {
        "schema",
        "secret",
        "permission-default-deny",
        "forbidden-tool",
        "prompt-injection",
        "source-digest",
        "runtime-smoke",
        "runtime-task",
    }
)
