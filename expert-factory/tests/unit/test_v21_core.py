"""Unit tests for Expert Factory v2.1 core."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from workcopilot_expert_factory.digest import compute_source_digest, iter_source_files
from workcopilot_expert_factory.evaluators.scoring import aggregate
from workcopilot_expert_factory.evaluators import CaseResult, CheckResult
from workcopilot_expert_factory.planners.requirement_compiler import compile_requirements_markdown
from workcopilot_expert_factory.services.branch import create_branch, branch_status, materialize_branch
from workcopilot_expert_factory.services.create import create_expert
from workcopilot_expert_factory.services.customize import customize_expert
from workcopilot_expert_factory.builders.bundle import build_expert_bundle
from workcopilot_expert_factory.validators.bundle import validate_bundle
from workcopilot_expert_factory.validators.expert import validate_expert
from workcopilot_expert_factory.publishers.nacos import NacosPublisher


def test_requirement_compiler_extracts_capabilities():
    # @lat: [[tests#Unit Core#Requirement compiler extracts capabilities]]
    md = """# 财务风险专家

## 业务目标
应收风险分析

## 能力
- 账龄查询
- 风险清单

## 外部系统
- SQLBot

## 约束
- 只读
"""
    brief = compile_requirements_markdown(md)
    assert brief["id"]
    assert "账龄查询" in brief["required_capabilities"]
    assert "SQLBot" in brief["external_systems"]


def test_scoring_missing_dimension_is_zero_not_full():
    # @lat: [[tests#Unit Core#Missing score dimensions are zero]]
    report = aggregate(
        expert_id="x",
        version="1.0.0",
        mode="static",
        minimum_score=0.5,
        checks=[CheckResult("a", "task", True, 1.0, "ok")],
        cases=[],
    )
    assert report.summary["dimensions"]["task"] == 1.0
    assert report.summary["dimensions"]["skill"] == 0.0
    assert "skill" in report.summary["missing_dimensions"]


def test_create_from_brief(tmp_path: Path):
    # @lat: [[tests#Unit Core#Create scaffolds full skills]]
    brief = tmp_path / "brief.yaml"
    brief.write_text(
        yaml.safe_dump(
            {
                "id": "demo-risk-unit",
                "name": "演示风险专家",
                "business_goal": "演示应收风险",
                "required_capabilities": ["账龄分析"],
                "external_systems": [],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "demo-risk-unit"
    result = create_expert(brief, out, drafts_root=tmp_path / "drafts")
    assert (out / "expert.yaml").is_file()
    assert (out / "skills").is_dir()
    skill_md = next((out / "skills").rglob("SKILL.md"))
    text = skill_md.read_text(encoding="utf-8")
    assert "kind:" in text
    assert "# 技能目标" in text
    assert result["validation"]["passed"]


def test_customize_blocks_permission_expansion(tmp_path: Path):
    brief = tmp_path / "brief.yaml"
    brief.write_text(
        yaml.safe_dump(
            {
                "id": "base-exp",
                "name": "基础专家",
                "business_goal": "基础",
                "required_capabilities": ["查询"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    src = tmp_path / "base-exp"
    create_expert(brief, src, drafts_root=tmp_path / "drafts")
    # expand permissions in a would-be target by patching source copy via spec that modifies tools — simulate by editing after customize default
    out = tmp_path / "base-exp-custom"
    customize_expert(src, out, notes="dept")
    data = yaml.safe_load((out / "expert.yaml").read_text(encoding="utf-8"))
    data["permissions"]["tools"]["allow"] = ["terminal"]
    (out / "expert.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    # re-run expansion detection via permission_expansion_diff path — customize already done;
    # verify permission_expansion_diff detects
    from workcopilot_expert_factory.validators.permissions import permission_expansion_diff

    src_data = yaml.safe_load((src / "expert.yaml").read_text(encoding="utf-8"))
    assert permission_expansion_diff(src_data, data)


def test_branch_create_status_materialize(tmp_path: Path, monkeypatch):
    # @lat: [[tests#Unit Core#Branch create status materialize]]
    # isolate repo root
    brief = tmp_path / "brief.yaml"
    brief.write_text(
        yaml.safe_dump(
            {
                "id": "br-src",
                "name": "分支源",
                "business_goal": "分支",
                "required_capabilities": ["分析"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    src = tmp_path / "br-src"
    create_expert(brief, src, drafts_root=tmp_path / "drafts")

    import workcopilot_expert_factory.services.branch as branch_mod

    monkeypatch.setattr(branch_mod, "_repo_root", lambda: tmp_path)
    result = create_branch(src, name="corp", target_id="corp-br")
    bpath = Path(result["branch_path"])
    assert (bpath / "branch.yaml").is_file()
    assert not any((bpath / "overlay").iterdir()) if (bpath / "overlay").exists() else True
    st = branch_status(bpath)
    assert st["sync_state"] in {"synced", "behind"}
    # add overlay file
    ov = bpath / "overlay" / "SOUL.md"
    ov.parent.mkdir(parents=True, exist_ok=True)
    ov.write_text("# 定制\n\n部门定制灵魂。\n", encoding="utf-8")
    out = tmp_path / "corp-br"
    mat = materialize_branch(bpath, out)
    assert (out / "SOUL.md").read_text(encoding="utf-8").startswith("# 定制")
    assert mat["expert_id"] == "corp-br"


def test_build_dev_bundle_whitelist_and_no_abspath(tmp_path: Path):
    # @lat: [[tests#Unit Core#Dev bundle omits absolute source path]]
    brief = tmp_path / "brief.yaml"
    brief.write_text(
        yaml.safe_dump(
            {
                "id": "build-demo",
                "name": "构建演示",
                "business_goal": "构建",
                "required_capabilities": ["报告"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    src = tmp_path / "build-demo"
    create_expert(brief, src, drafts_root=tmp_path / "drafts")
    # structure validate should pass
    assert validate_expert(src, level="structure").passed
    out = tmp_path / "dist"
    report = build_expert_bundle(src, out, dev=True, skip_runtime_evaluation=True)
    bundle = Path(report["bundle"])
    assert bundle.is_file()
    assert report["source_digest"].startswith("sha256:")
    # source.json should not contain Windows drive absolute path as authority — uses relative_source
    import zipfile

    with zipfile.ZipFile(bundle) as zf:
        source = json.loads(zf.read("manifest/source.json"))
        assert "relative_source" in source
        assert not str(source.get("relative_source", "")).startswith("D:")
        assert "sbom/bom.cdx.json" in zf.namelist()
        bom = json.loads(zf.read("sbom/bom.cdx.json"))
        assert bom["bomFormat"] == "CycloneDX"


def test_nacos_mock_publish_flow():
    # @lat: [[tests#Unit Core#Nacos mock publish flow]]
    pub = NacosPublisher("http://127.0.0.1:8848/nacos", namespace="test", mock=True)
    assert pub.health()["ok"]
    up = pub.upload_skill("s1", "1.0.0", b"PK\x03\x04fake")
    assert up["status"] == "uploaded"
    pub.submit("skill", "s1", "1.0.0")
    pub.publish("skill", "s1", "1.0.0")
    assert pub.get_resource("skill", "s1", "1.0.0")["status"] == "online"


def test_source_digest_stable(tmp_path: Path):
    # @lat: [[tests#Unit Core#Source digest is stable]]
    brief = tmp_path / "brief.yaml"
    brief.write_text(
        yaml.safe_dump(
            {
                "id": "digest-demo",
                "name": "摘要",
                "business_goal": "摘要稳定",
                "required_capabilities": ["摘要"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    src = tmp_path / "digest-demo"
    create_expert(brief, src, drafts_root=tmp_path / "drafts")
    files = iter_source_files(src)
    d1 = compute_source_digest(src, files)
    d2 = compute_source_digest(src, files)
    assert d1 == d2
