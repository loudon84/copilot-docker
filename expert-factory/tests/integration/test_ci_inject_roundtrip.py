from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from workcopilot_expert_factory.adapters.inject_runtime import inject_from_manifest
from workcopilot_expert_factory.adapters.schema_loader import validate_against
from workcopilot_expert_factory.builders.bundle import build_expert_bundle
from workcopilot_expert_factory.services.batch import list_v1_experts
from workcopilot_expert_factory.services.bind_check import bind_check
from workcopilot_expert_factory.services.evaluate import evaluate_expert

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "expert-templates"


def test_list_v1_experts_includes_five() -> None:
    experts = list_v1_experts(REPO)
    ids = {p.name for p in experts}
    assert {"writer", "finance", "sale", "bi-strategic-office", "ceo-strategic-office"} <= ids


def test_bind_check_bi_missing_env(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SQLBOT_MCP_URL=http://localhost\n", encoding="utf-8")
    result = bind_check(TEMPLATES / "bi-strategic-office", env)
    assert result["passed"] is False
    assert "SQLBOT_PASSWORD" in result["missing_env"]
    assert any(s["slot_id"] == "finance-query" for s in result["slots"])


def test_inject_from_manifest_excludes_docs(tmp_path: Path) -> None:
    data = tmp_path / "hermes"
    result = inject_from_manifest(
        template_dir=TEMPLATES / "writer",
        data_dir=data,
        base_dir=TEMPLATES / "base",
    )
    assert result["mode"] == "manifest-precise"
    assert (data / "SOUL.md").is_file() or any("SOUL" in c for c in result["copied"])
    assert not (data / "docs").exists()
    assert not (data / "evaluations").exists()
    assert not (data / "expert.yaml").exists()
    # skills should exist
    assert any((data / "skills").rglob("SKILL.md"))


def test_bundle_roundtrip_writer(tmp_path: Path) -> None:
    evaluate_expert(TEMPLATES / "writer", mode="static")
    out = tmp_path / "dist"
    built = build_expert_bundle(
        TEMPLATES / "writer",
        out,
        dev=False,
        skip_runtime_evaluation=False,
    )
    bundle = Path(built["bundle"])
    extract = tmp_path / "extracted"
    extract.mkdir()
    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
        assert "manifest/bundle.json" in names
        assert "manifest/expert.yaml" in names
        assert "manifest/checksums.sha256" in names
        assert any(n.startswith("runtime/") for n in names)
        for name in names:
            assert ".." not in name
            assert not name.startswith("/")
            assert not (len(name) > 1 and name[1] == ":")
        zf.extractall(extract)
    expert = yaml.safe_load((extract / "manifest" / "expert.yaml").read_text(encoding="utf-8"))
    errs = validate_against("expert-v1.schema.json", expert)
    assert errs == []
    checksums = (extract / "manifest" / "checksums.sha256").read_text(encoding="utf-8").strip()
    assert checksums
    evaluation = json.loads((extract / "manifest" / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation.get("skipped") is False
