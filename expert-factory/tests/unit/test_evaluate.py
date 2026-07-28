from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from workcopilot_expert_factory.builders.bundle import build_expert_bundle
from workcopilot_expert_factory.errors import ValidationFailed
from workcopilot_expert_factory.evaluators.scoring import aggregate
from workcopilot_expert_factory.evaluators import CheckResult, CaseResult
from workcopilot_expert_factory.services.evaluate import evaluate_expert, results_dir

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "expert-templates"


def test_scoring_security_gate_blocks() -> None:
    report = aggregate(
        expert_id="x",
        version="1.0.0",
        mode="static",
        minimum_score=0.5,
        checks=[
            CheckResult("g", "permission", False, 1.0, "deny missing", gate=True),
            CheckResult("ok", "task", True, 1.0, "ok"),
        ],
        cases=[CaseResult("c1", "task", True, 1.0, "ok")],
    )
    assert not report.security_gates_passed
    assert not report.passed


def test_evaluate_writer_static() -> None:
    result = evaluate_expert(TEMPLATES / "writer", mode="static")
    assert result["passed"]
    assert Path(result["report_json"]).is_file()


def test_build_release_requires_evaluation(tmp_path: Path) -> None:
    # use a disposable copy of a mini scaffold would be heavy; assert gate on missing eval for a fake path
    # Instead: temporarily rename evaluation dir if present is invasive.
    # Build writer --release should succeed after evaluate above.
    out = tmp_path / "dist"
    # ensure evaluation exists
    evaluate_expert(TEMPLATES / "writer", mode="static")
    result = build_expert_bundle(TEMPLATES / "writer", out, dev=False, skip_runtime_evaluation=False)
    assert Path(result["bundle"]).is_file()
    # open zip and check evaluation not skipped
    import zipfile

    with zipfile.ZipFile(result["bundle"]) as zf:
        data = json.loads(zf.read("manifest/evaluation.json"))
    assert data.get("skipped") is False
    assert data.get("passed") is True


def test_build_release_fails_without_eval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import workcopilot_expert_factory.builders.bundle as bundle_mod

    monkeypatch.setattr(bundle_mod, "load_latest_evaluation", lambda _root: None)
    with pytest.raises(ValidationFailed):
        build_expert_bundle(TEMPLATES / "sale", tmp_path / "dist", dev=False, skip_runtime_evaluation=False)


def test_five_experts_static_evaluate() -> None:
    for name in ("writer", "finance", "sale", "bi-strategic-office", "ceo-strategic-office"):
        report_path = TEMPLATES / name / "expert.yaml"
        data = yaml.safe_load(report_path.read_text(encoding="utf-8"))
        assert data.get("schema_version") == "workcopilot.expert.v1"
        result = evaluate_expert(TEMPLATES / name, mode="static")
        assert result["passed"], name
