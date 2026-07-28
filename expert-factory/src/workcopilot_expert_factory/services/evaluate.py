from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from workcopilot_expert_factory.errors import ExpertFactoryError, ExpertNotFound, ValidationFailed
from workcopilot_expert_factory.evaluators.cases import run_cases
from workcopilot_expert_factory.evaluators.runtime_smoke import run_runtime_smoke
from workcopilot_expert_factory.evaluators.scoring import aggregate
from workcopilot_expert_factory.evaluators.static import run_static_checks
from workcopilot_expert_factory.validators.expert import validate_expert

EvalMode = Literal["static", "runtime", "full"]


def _repo_root(expert_root: Path) -> Path:
    if expert_root.parent.name == "expert-templates":
        return expert_root.parent.parent
    return expert_root.parent


def results_dir(expert_id: str, version: str, repo: Path) -> Path:
    return repo / "evaluations" / "results" / expert_id / version


def load_latest_evaluation(expert_root: Path) -> dict[str, Any] | None:
    data = yaml.safe_load((expert_root / "expert.yaml").read_text(encoding="utf-8")) or {}
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

    checks = []
    cases = []
    if mode in {"static", "full"}:
        checks.extend(run_static_checks(root, data))
        cases.extend(run_cases(root, data))
    if mode in {"runtime", "full"}:
        checks.extend(
            run_runtime_smoke(
                root,
                data,
                timeout=timeout,
                runtime_profile=runtime_profile,
            )
        )

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

    out = results_dir(expert_id, version, _repo_root(root))
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = [
        f"# Evaluation Report: {expert_id}@{version}",
        "",
        f"- mode: `{mode}`",
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
        err = ExpertFactoryError("security gate failed", code="SECURITY_GATE_FAILED")
        err.exit_code = 4
        err.payload = payload  # type: ignore[attr-defined]
        raise err
    if not payload["passed"]:
        err = ExpertFactoryError(
            f"evaluation failed score={payload['score']} < {minimum} or cases failed",
            code="EVALUATION_FAILED",
        )
        err.exit_code = 1
        err.payload = payload  # type: ignore[attr-defined]
        raise err
    return payload
