from __future__ import annotations

from workcopilot_expert_factory.evaluators import WEIGHTS, CaseResult, CheckResult, EvaluationReport


def aggregate(
    *,
    expert_id: str,
    version: str,
    mode: str,
    minimum_score: float,
    checks: list[CheckResult],
    cases: list[CaseResult],
) -> EvaluationReport:
    # security gates
    gate_fails = [c for c in checks if c.gate and not c.passed]
    security_ok = len(gate_fails) == 0

    # dimension scores from checks
    dim_scores: dict[str, list[float]] = {k: [] for k in WEIGHTS}
    for c in checks:
        if c.weight <= 0:
            continue
        dim = c.dimension if c.dimension in dim_scores else "exception"
        dim_scores.setdefault(dim, [])
        dim_scores[dim].append(1.0 if c.passed else 0.0)

    # cases contribute to task / permission / exception
    for case in cases:
        val = case.score if case.passed else 0.0
        if case.type in {"task", "smoke"}:
            dim_scores["task"].append(val)
        elif case.type in {"policy", "security"}:
            dim_scores["permission"].append(val)
        elif case.type == "resilience":
            dim_scores["exception"].append(val)
        else:
            dim_scores["task"].append(val)

    score = 0.0
    detail = {}
    for dim, weight in WEIGHTS.items():
        vals = dim_scores.get(dim) or []
        part = sum(vals) / len(vals) if vals else 1.0  # missing dim = neutral full
        detail[dim] = round(part, 4)
        score += weight * part

    passed = security_ok and score >= minimum_score and all(c.passed for c in cases if c.type in {"policy", "security"})
    # require all security/policy cases pass; other cases fold into score
    if any(not c.passed for c in cases if c.type in {"policy", "security"}):
        passed = False

    return EvaluationReport(
        expert_id=expert_id,
        version=version,
        mode=mode,
        passed=passed,
        score=score,
        minimum_score=minimum_score,
        security_gates_passed=security_ok,
        checks=checks,
        cases=cases,
        summary={
            "dimensions": detail,
            "gate_failures": [c.id for c in gate_fails],
            "case_pass": sum(1 for c in cases if c.passed),
            "case_total": len(cases),
        },
    )
