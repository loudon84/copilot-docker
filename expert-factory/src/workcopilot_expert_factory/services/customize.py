"""Structured customize-expert (PRD §11)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.errors import ExpertFactoryError, ExpertNotFound, PermissionExpansion
from workcopilot_expert_factory.validators.expert import validate_expert
from workcopilot_expert_factory.validators.permissions import permission_expansion_diff


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _apply_terminology(text: str, mapping: dict[str, str]) -> str:
    out = text
    for src, dst in mapping.items():
        out = out.replace(src, dst)
    return out


def customize_expert(
    source: Path,
    output: Path,
    *,
    new_id: str | None = None,
    notes: str | None = None,
    spec_path: Path | None = None,
    allow_permission_expansion: bool = False,
) -> dict[str, Any]:
    src = source.resolve()
    if not src.is_dir():
        raise ExpertNotFound(f"source expert not found: {src}")
    if output.exists():
        raise ExpertFactoryError(f"output already exists: {output}", code="OUTPUT_EXISTS")

    spec: dict[str, Any] = {}
    if spec_path:
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
        if not isinstance(spec, dict):
            raise ExpertFactoryError("customize spec must be a mapping", code="E_PLAN_INVALID")

    shutil.copytree(src, output, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    expert_yaml = output / "expert.yaml"
    if not expert_yaml.is_file():
        raise ExpertFactoryError("source missing expert.yaml; migrate to v1 before customize", code="LEGACY_EXPERT")

    data = yaml.safe_load(expert_yaml.read_text(encoding="utf-8")) or {}
    if data.get("schema_version") != "workcopilot.expert.v1":
        raise ExpertFactoryError("source is not workcopilot.expert.v1", code="LEGACY_EXPERT")

    source_snapshot = yaml.safe_load((src / "expert.yaml").read_text(encoding="utf-8")) or {}
    old_id = data["metadata"]["id"]
    old_version = data["metadata"]["version"]

    target_meta = (spec.get("target") or {})
    target_id = target_meta.get("expert_id") or new_id or f"{old_id}-custom"
    target_id = str(target_id)
    if output.name != target_id:
        target_id = output.name

    data["metadata"]["id"] = target_id
    if target_meta.get("version"):
        data["metadata"]["version"] = str(target_meta["version"])
    else:
        parts = old_version.split(".")
        if len(parts) >= 3 and parts[2].isdigit():
            parts[2] = str(int(parts[2]) + 1)
            data["metadata"]["version"] = ".".join(parts[:3])

    changes = spec.get("changes") or {}
    component_diff: list[str] = []

    # terminology replacements in markdown docs
    terminology = changes.get("terminology") or {}
    if terminology:
        for path in output.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".yaml", ".yml"}:
                continue
            if path.name == "expert.yaml":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            new_text = _apply_terminology(text, {str(k): str(v) for k, v in terminology.items()})
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                component_diff.append(f"terminology updated: {path.relative_to(output).as_posix()}")

    # skill instruction appends
    for item in (changes.get("skills") or {}).get("modify") or []:
        sid = item.get("id")
        instructions = item.get("instructions") or ""
        if not sid:
            continue
        # find skill
        for skill_md in output.rglob("SKILL.md"):
            if skill_md.parent.name == sid or f"/{sid}/" in skill_md.as_posix():
                text = skill_md.read_text(encoding="utf-8")
                if instructions and instructions not in text:
                    text = text.rstrip() + f"\n\n## 定制补充\n\n{instructions}\n"
                    skill_md.write_text(text, encoding="utf-8")
                    component_diff.append(f"skill modified: {sid}")
                break

    # policy data_scope note
    if changes.get("policies"):
        pol = output / "policies" / "data-policy.yaml"
        if pol.is_file():
            pol_data = yaml.safe_load(pol.read_text(encoding="utf-8")) or {}
            pol_data["customization"] = changes["policies"]
            _write_yaml(pol, pol_data)
            component_diff.append("policies updated")

    # outputs template copy hint
    if (changes.get("outputs") or {}).get("template"):
        component_diff.append(f"output template requested: {changes['outputs']['template']}")

    data.setdefault("provenance", {})
    data["provenance"]["derived_from"] = {"expert_id": old_id, "version": old_version}
    _write_yaml(expert_yaml, data)

    # permission expansion check against source
    expansions = permission_expansion_diff(source_snapshot, data)
    high_risk = False
    if expansions and not allow_permission_expansion:
        # revert output? leave dir but fail
        raise PermissionExpansion(
            "permission expansion detected: " + "; ".join(expansions),
            payload={"expansions": expansions},
        )
    if expansions and allow_permission_expansion:
        high_risk = True
        data.setdefault("release", {})
        data["release"]["publishable"] = False
        data["release"]["permission_expansion_unapproved"] = True
        _write_yaml(expert_yaml, data)

    suite = output / "evaluations" / "cases.yaml"
    if suite.is_file():
        suite_data = yaml.safe_load(suite.read_text(encoding="utf-8")) or {}
        if isinstance(suite_data, dict):
            suite_data["expert_id"] = target_id
            cases = list(suite_data.get("cases") or [])
            # add regression case when skills modified
            if any("skill modified" in x for x in component_diff):
                cases.append(
                    {
                        "id": "customize-regression",
                        "type": "regression",
                        "prompt": f"回归验证定制专家 {target_id} 的核心只读任务",
                        "expected": {"output": {"contract": "structured-markdown"}},
                    }
                )
                suite_data["cases"] = cases
            _write_yaml(suite, suite_data)

    docs = output / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "customization-report.md").write_text(
        f"""# 定制报告

- 源专家：`{old_id}@{old_version}`
- 新专家：`{target_id}`
- 说明：{notes or (spec.get('notes') if spec else None) or '组织/部门定制'}
- 权限扩大：{'是（已显式允许，禁止自动发布）' if high_risk else '否'}

## 变更摘要

{chr(10).join(f'- {x}' for x in component_diff) or '- （仅元数据派生）'}
""",
        encoding="utf-8",
    )
    (docs / "permission-diff.md").write_text(
        "# 权限差异\n\n"
        + ("\n".join(f"- {x}" for x in expansions) if expansions else "- 无权限扩大\n"),
        encoding="utf-8",
    )
    (docs / "component-diff.md").write_text(
        "# 组件差异\n\n" + ("\n".join(f"- {x}" for x in component_diff) or "- 无组件变更\n"),
        encoding="utf-8",
    )

    validation = validate_expert(output, level="structure")
    return {
        "source": str(src),
        "output": str(output),
        "derived_from": {"expert_id": old_id, "version": old_version},
        "permission_expansions": expansions,
        "high_risk": high_risk,
        "component_diff": component_diff,
        "validation": validation.to_dict(),
    }
