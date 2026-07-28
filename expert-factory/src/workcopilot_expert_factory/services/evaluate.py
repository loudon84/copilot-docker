from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from workcopilot_expert_factory import __version__
from workcopilot_expert_factory.digest import compute_json_digest, compute_source_digest, git_commit, iter_source_files
from workcopilot_expert_factory.errors import ExpertFactoryError, ExpertNotFound, ValidationFailed
from workcopilot_expert_factory.evaluators import CaseResult, CheckResult
from workcopilot_expert_factory.evaluators.cases import run_cases
from workcopilot_expert_factory.evaluators.hermes_runtime import run_hermes_runtime_harness
from workcopilot_expert_factory.evaluators.regression import load_previous_evaluation, run_regression
from workcopilot_expert_factory.evaluators.runtime_smoke import run_runtime_smoke
from workcopilot_expert_factory.evaluators.scenario import run_scenario_cases
from workcopilot_expert_factory.evaluators.scoring import aggregate
from workcopilot_expert_factory.evaluators.security import run_security_adversarial
from workcopilot_expert_factory.evaluators.static import run_static_checks
from workcopilot_expert_factory.models import (
    EvaluationCost,
    EvaluationDecision,
    EvaluationReportV2,
    EvaluationRuntimeInfo,
    EvaluationSource,
)
from workcopilot_expert_factory.validators.expert import validate_expert

EvalMode = Literal["static", "runtime", "full"]


def _repo_root(expert_root: Path) -> Path:
    if expert_root.parent.name == "expert-templates":
        return expert_root.parent.parent
    return expert_root.parent


def results_dir(expert_id: str, version: str, repo: Path) -> Path:
    return repo / "evaluations" / "results" / expert_id / version


def load_latest_evaluation(expert_root: Path) -> dict[str, Any] | None:
    expert_yaml = expert_root / "expert.yaml"
    if not expert_yaml.is_file():
        return None
    data = yaml.safe_load(expert_yaml.read_text(encoding="utf-8")) or {}
    if data.get("schema_version") != "workcopilot.expert.v1":
        return None
    expert_id = data["metadata"]["id"]
    version = data["metadata"]["version"]
    path = results_dir(expert_id, version, _repo_root(expert_root)) / "evaluation.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_expert(
    path: Path | str,
    *,
    mode: EvalMode = "full",
    runtime_profile: str | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    root = Path(path).resolve()
    if not root.is_dir():
        raise ExpertNotFound(f"expert directory not found: {root}")

    vreport = validate_expert(root, level="full")
    if vreport.legacy:
        raise ValidationFailed("cannot evaluate legacy expert; migrate to workcopilot.expert.v1 first")
    if not vreport.passed:
        raise ValidationFailed(
            "validate failed before evaluate: "
            + "; ".join(i.message for i in vreport.issues if i.level == "error")[:400]
        )

    data = yaml.safe_load((root / "expert.yaml").read_text(encoding="utf-8")) or {}
    expert_id = data["metadata"]["id"]
    version = data["metadata"]["version"]
    minimum = float((data.get("evaluations") or {}).get("minimum_score") or 0.9)
    source_digest = compute_source_digest(root, iter_source_files(root))
    commit = git_commit(root)

    checks: list[CheckResult] = []
    cases: list[CaseResult] = []
    runtime_results: list[dict[str, Any]] = []
    fixture_digest = None
    cost = EvaluationCost()

    checks.append(
        CheckResult(
            id="schema",
            dimension="output",
            passed=True,
            weight=1.0,
            message="schema validated before evaluate",
            gate=True,
        )
    )
    checks.append(
        CheckResult(
            id="source-digest",
            dimension="output",
            passed=bool(source_digest),
            weight=1.0,
            message=f"source_digest={source_digest}",
            gate=True,
        )
    )

    if mode in {"static", "full"}:
        checks.extend(run_static_checks(root, data))
        cases.extend(run_cases(root, data))
        cases.extend(run_scenario_cases(root, data, live=False))
        sec_checks, sec_cases = run_security_adversarial(root, data)
        checks.extend(sec_checks)
        cases.extend(sec_cases)
        soul = root / "SOUL.md"
        has_cite = False
        if soul.is_file():
            has_cite = "引用" in soul.read_text(encoding="utf-8", errors="ignore")
        checks.append(
            CheckResult(
                id="citation-grounding",
                dimension="citation",
                passed=True,
                weight=1.0,
                message="citation dimension covered" if has_cite else "citation dimension static coverage",
            )
        )
        if not any(c.dimension == "tool" for c in checks):
            checks.append(
                CheckResult(
                    id="tool-policy-present",
                    dimension="tool",
                    passed=(root / "policies" / "tool-policy.yaml").is_file(),
                    weight=1.0,
                    message="tool-policy.yaml present",
                )
            )

    if mode in {"runtime", "full"}:
        checks.extend(
            run_runtime_smoke(
                root,
                data,
                timeout=timeout,
                runtime_profile=runtime_profile,
            )
        )
        h_checks, runtime_results, fixtures = run_hermes_runtime_harness(root, data, timeout=timeout)
        checks.extend(h_checks)
        fixture_digest = compute_json_digest(fixtures.digest_payload())
        cost.tool_calls = len(fixtures.calls)
        cost.duration_ms = sum(int(r.get("duration_ms") or 0) for r in runtime_results)
        if runtime_results:
            cases.append(
                CaseResult(
                    id="runtime-task",
                    type="task",
                    passed=bool(runtime_results[0].get("reply")),
                    score=1.0 if runtime_results[0].get("reply") else 0.0,
                    message=f"hermes runtime mode={runtime_results[0].get('mode')}",
                )
            )

    if mode == "full":
        prev = load_previous_evaluation(results_dir(expert_id, version, _repo_root(root)) / "evaluation.json")
        cases.extend(run_regression(root, data, previous=prev))

    report = aggregate(
        expert_id=expert_id,
        version=version,
        mode=mode,
        minimum_score=minimum,
        checks=checks,
        cases=cases,
    )
    payload = report.to_dict()
    payload["validated"] = True
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["expert_path"] = str(root)
    payload["source_digest"] = source_digest
    payload["git_commit"] = commit
    payload["factory_version"] = __version__
    payload["fixture_digest"] = fixture_digest
    payload["schema_version"] = "workcopilot.evaluation-report.v2"
    payload["source"] = {
        "expert_id": expert_id,
        "expert_version": version,
        "source_digest": source_digest,
        "git_commit": commit,
    }
    payload["runtime"] = {
        "engine": "hermes",
        "hermes_version": None,
        "model": runtime_profile,
        "connector_fixture_set": "default",
    }
    payload["cost"] = {
        "input_tokens": cost.input_tokens,
        "output_tokens": cost.output_tokens,
        "tool_calls": cost.tool_calls,
        "duration_ms": cost.duration_ms,
    }
    payload["decision"] = {
        "passed": payload["passed"],
        "score": payload["score"],
        "gate_failures": payload.get("summary", {}).get("gate_failures") or [],
    }
    payload["results"] = {
        "static": mode in {"static", "full"},
        "runtime": mode in {"runtime", "full"},
        "security": mode in {"static", "full"},
        "regression": mode == "full",
        "runtime_samples": runtime_results[:3],
    }

    v2 = EvaluationReportV2(
        source=EvaluationSource(
            expert_id=expert_id,
            expert_version=version,
            source_digest=source_digest,
            git_commit=commit,
        ),
        runtime=EvaluationRuntimeInfo(model=runtime_profile, connector_fixture_set="default"),
        results=payload["results"],
        cost=cost,
        decision=EvaluationDecision(
            passed=payload["passed"],
            score=payload["score"],
            gate_failures=payload["decision"]["gate_failures"],
        ),
        factory_version=__version__,
        fixture_digest=fixture_digest,
        generated_at=payload["generated_at"],
    )

    out = results_dir(expert_id, version, _repo_root(root))
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "evaluation.v2.json").write_text(
        json.dumps(v2.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = [
        f"# Evaluation Report: {expert_id}@{version}",
        "",
        f"- mode: `{mode}`",
        f"- source_digest: `{source_digest}`",
        f"- passed: **{payload['passed']}**",
        f"- score: `{payload['score']}` (minimum `{minimum}`)",
        f"- security_gates_passed: `{payload['security_gates_passed']}`",
        "",
        "## Checks",
        "",
    ]
    for c in payload["checks"]:
        mark = "PASS" if c["passed"] else "FAIL"
        gate = " [GATE]" if c.get("gate") else ""
        md.append(f"- [{mark}] `{c['id']}` ({c['dimension']}){gate}: {c['message']}")
    md.extend(["", "## Cases", ""])
    for c in payload["cases"]:
        mark = "PASS" if c["passed"] else "FAIL"
        md.append(f"- [{mark}] `{c['id']}` ({c['type']}) score={c['score']}: {c['message']}")
    (out / "evaluation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    payload["report_json"] = str(out / "evaluation.json")
    payload["report_md"] = str(out / "evaluation.md")

    if not payload["security_gates_passed"]:
        err = ExpertFactoryError("security gate failed", code="E_SECURITY_GATE_FAILED")
        err.exit_code = 4
        err.payload = payload
        raise err
    if not payload["passed"]:
        err = ExpertFactoryError(
            f"evaluation failed score={payload['score']} < {minimum} or cases failed",
            code="E_EVALUATION_FAILED",
        )
        err.exit_code = 1
        err.payload = payload
        raise err
    return payload
