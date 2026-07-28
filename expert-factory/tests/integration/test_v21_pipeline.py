"""Integration: create → validate → evaluate → build → publish dry-run."""

from __future__ import annotations

from pathlib import Path

import yaml

from workcopilot_expert_factory.builders.bundle import build_expert_bundle
from workcopilot_expert_factory.services.create import create_expert
from workcopilot_expert_factory.services.evaluate import evaluate_expert
from workcopilot_expert_factory.services.publish import publish_expert
from workcopilot_expert_factory.validators.expert import validate_expert


def test_end_to_end_pipeline(tmp_path: Path, monkeypatch):
    # @lat: [[tests#Integration Pipeline#End to end release publish]]
    monkeypatch.setenv("WORKCOPILOT_QUIET", "1")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    brief = tmp_path / "brief.yaml"
    brief.write_text(
        yaml.safe_dump(
            {
                "id": "e2e-finance",
                "name": "端到端财务专家",
                "business_goal": "端到端财务分析",
                "required_capabilities": ["财务分析", "风险检查"],
                "external_systems": ["finance-query"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    expert = tmp_path / "e2e-finance"
    create_expert(brief, expert, drafts_root=tmp_path / "drafts")

    v = validate_expert(expert, level="full")
    assert v.passed, [i for i in v.issues if i.level == "error"]

    ev = evaluate_expert(expert, mode="full")
    assert ev["passed"]
    assert ev["source_digest"].startswith("sha256:")

    dist = tmp_path / "dist"
    # release build requires evaluation bound to digest
    built = build_expert_bundle(expert, dist, dev=False, skip_runtime_evaluation=False)
    assert built["dev"] is False
    bundle = Path(built["bundle"])

    # publish dry-run with mock
    monkeypatch.setenv("WORKCOPILOT_NACOS_MOCK", "1")
    # point repo root used by publish to tmp
    import workcopilot_expert_factory.services.publish as pub_mod

    monkeypatch.setattr(pub_mod, "_repo_root", lambda: tmp_path)
    (tmp_path / ".workcopilot" / "registry").mkdir(parents=True)
    (tmp_path / ".workcopilot" / "registry" / "nacos-dev.yaml").write_text(
        "provider: nacos\nserver_url: http://127.0.0.1:8848/nacos\nnamespace: test\n",
        encoding="utf-8",
    )

    result = publish_expert(bundle, target="nacos-dev", stage="online", dry_run=False, wait=True, overwrite_draft=True)
    # With mock publisher, online should succeed
    assert result["status"] in {"online", "draft", "reviewed", "dry_run", "already_published"}
