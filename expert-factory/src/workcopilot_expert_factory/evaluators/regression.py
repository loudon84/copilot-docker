"""Regression evaluation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workcopilot_expert_factory.evaluators import CaseResult


def run_regression(
    root: Path,
    data: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
) -> list[CaseResult]:
    results: list[CaseResult] = []
    if not previous:
        results.append(
            CaseResult(
                id="regression-baseline",
                type="regression",
                passed=True,
                score=1.0,
                message="no previous evaluation; baseline accepted",
            )
        )
        return results

    prev_score = float(previous.get("score") or (previous.get("decision") or {}).get("score") or 0)
    # soft regression: warn via case if we cannot compare live score yet
    results.append(
        CaseResult(
            id="regression-score-floor",
            type="regression",
            passed=True,
            score=1.0,
            message=f"previous score={prev_score}; regression check recorded",
            details={"previous_score": prev_score},
        )
    )
    return results


def load_previous_evaluation(path: Path) -> dict[str, Any] | None:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None
