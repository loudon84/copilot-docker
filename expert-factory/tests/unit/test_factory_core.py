from __future__ import annotations

import json
from pathlib import Path

import yaml

from workcopilot_expert_factory.adapters.schema_loader import load_schema, validate_against
from workcopilot_expert_factory.builders.bundle import build_expert_bundle
from workcopilot_expert_factory.models import ExpertManifest
from workcopilot_expert_factory.services.create import create_expert, customize_expert, slugify
from workcopilot_expert_factory.validators.expert import validate_expert

REPO = Path(__file__).resolve().parents[3]
FACTORY = REPO / "expert-factory"
TEMPLATES = REPO / "expert-templates"


def test_schemas_load() -> None:
    for name in (
        "expert-v1.schema.json",
        "skill-v1.schema.json",
        "connector-slot-v1.schema.json",
        "evaluation-suite-v1.schema.json",
        "expert-bundle-v1.schema.json",
    ):
        schema = load_schema(name)
        assert "$schema" in schema


def test_writer_manifest_validates() -> None:
    data = yaml.safe_load((TEMPLATES / "writer" / "expert.yaml").read_text(encoding="utf-8"))
    errors = validate_against("expert-v1.schema.json", data)
    assert errors == []
    manifest = ExpertManifest.model_validate(data)
    assert manifest.metadata.id == "writer"


def test_validate_writer_full() -> None:
    report = validate_expert(TEMPLATES / "writer", level="full")
    assert report.passed
    assert not report.legacy


def test_validate_bi_is_v1() -> None:
    report = validate_expert(TEMPLATES / "bi-strategic-office", level="structure")
    assert not report.legacy
    assert report.passed


def test_secret_scan_detects_env(tmp_path: Path) -> None:
    expert = tmp_path / "secret-expert"
    # minimal copy from writer skeleton via create
    brief = tmp_path / "brief.yaml"
    brief.write_text(
        yaml.safe_dump(
            {
                "id": "secret-expert",
                "name": "密钥测试专家",
                "business_goal": "测试密钥扫描",
                "required_capabilities": ["基础问答"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    create_expert(brief, expert, drafts_root=tmp_path / "drafts")
    (expert / ".env").write_text("PASSWORD=supersecret123\n", encoding="utf-8")
    report = validate_expert(expert, level="security")
    assert not report.passed
    assert any(i.code == "SECRET_DETECTED" for i in report.issues)


def test_create_and_customize(tmp_path: Path) -> None:
    brief = tmp_path / "brief.yaml"
    brief.write_text(
        yaml.safe_dump(
            {
                "id": "demo-expert-aa",
                "name": "演示专家",
                "business_goal": "演示创建与定制",
                "required_capabilities": ["演示任务"],
                "external_systems": [],
                "constraints": ["只读"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "demo-expert-aa"
    result = create_expert(brief, out, drafts_root=tmp_path / "drafts")
    assert Path(result["output"]).is_dir()
    assert (out / "expert.yaml").is_file()
    report = validate_expert(out, level="full")
    assert report.passed

    derived = tmp_path / "demo-expert-aa-custom"
    custom = customize_expert(out, derived, notes="测试定制")
    assert (derived / "docs" / "customization-report.md").is_file()
    data = yaml.safe_load((derived / "expert.yaml").read_text(encoding="utf-8"))
    assert data["provenance"]["derived_from"]["expert_id"] == "demo-expert-aa"
    assert (out / "expert.yaml").read_text(encoding="utf-8")  # source untouched path exists
    assert custom["validation"]["passed"]


def test_build_writer_bundle(tmp_path: Path) -> None:
    out = tmp_path / "dist"
    result = build_expert_bundle(TEMPLATES / "writer", out, dev=True, skip_runtime_evaluation=True)
    bundle = Path(result["bundle"])
    assert bundle.is_file()
    assert bundle.suffixes[-2:] == [".expert", ".bundle"] or bundle.name.endswith(".expert.bundle")
    assert result["payload_digest"].startswith("sha256:")


def test_slugify() -> None:
    assert slugify("Hello World") == "hello-world"
    assert len(slugify("a")) >= 3
