from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.errors import ExpertFactoryError, ExpertNotFound
from workcopilot_expert_factory.models import (
    ComponentRef,
    ComponentsSpec,
    EvaluationsSpec,
    ExpertManifest,
    ExpertMetadata,
    PermissionsSpec,
    PolicyRef,
    ProvenanceSpec,
    RuntimeEntrypoints,
    RuntimeSpec,
)
from workcopilot_expert_factory.validators.expert import validate_expert

KEBAB_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    text = value.strip().lower().replace("_", "-")
    # keep ascii letters/digits/hyphen; for chinese names use provided id or hash-ish ascii
    text = KEBAB_RE.sub("-", text).strip("-")
    if len(text) < 3 or not re.match(r"^[a-z]", text):
        # fallback: expert- prefix + shortened
        compact = re.sub(r"[^a-z0-9]", "", text) or "expert"
        text = f"expert-{compact}"[:64]
    return text[:64]


def _factory_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _templates_dir() -> Path:
    return _factory_root() / "templates"


def _repo_root() -> Path:
    return _factory_root().parent


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_brief(brief_path: Path) -> dict[str, Any]:
    data = yaml.safe_load(brief_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ExpertFactoryError("brief must be a YAML mapping", code="BRIEF_INVALID")
    return data


def plan_from_brief(brief: dict[str, Any], expert_id: str) -> dict[str, Any]:
    caps = brief.get("required_capabilities") or []
    skills = []
    for cap in caps:
        sid = slugify(str(cap))
        skills.append({"id": sid, "purpose": str(cap)})
    if not skills:
        skills.append({"id": "primary-task", "purpose": brief.get("business_goal") or "核心任务"})

    external = brief.get("external_systems") or []
    slots = []
    for sys_name in external:
        slots.append(
            {
                "id": slugify(str(sys_name)),
                "category": "integration",
                "name": str(sys_name),
            }
        )

    return {
        "expert_id": expert_id,
        "components": {
            "skills": skills,
            "plugins": [],
            "connector_slots": slots,
            "policies": ["tool-policy", "data-policy"],
            "evaluations": ["normal-query", "permission-denied"],
            "do_not_create": [
                {"component": "duplicate-plugin", "reason": "默认复用已有 Plugin，禁止重复造轮子"},
            ],
        },
        "constraints": brief.get("constraints") or [],
    }


def _skill_stub(skill_id: str, purpose: str) -> str:
    return f"""---
schema_version: workcopilot.skill.v1
id: {skill_id}
name: {purpose}
version: 1.0.0
description: >
  当用户需要「{purpose}」时使用本技能。
triggers:
  - {purpose}
scope:
  includes:
    - {purpose}
  excludes:
    - 写入生产系统
    - 泄露密钥
inputs:
  required: []
  optional: []
outputs:
  format: structured-markdown
tool_requirements: []
connector_requirements: []
permissions:
  access_mode: read-only
  data_classification: internal
---

# 技能目标

完成「{purpose}」相关任务。

# 适用条件

用户明确提出与「{purpose}」相关的请求。

# 前置检查

- 确认输入条件是否齐全。
- 确认不需要写入外部系统。

# 执行流程

1. 澄清目标与约束。
2. 收集必要上下文。
3. 产出结构化结果。

# 工具调用规则

- 仅使用专家权限允许的工具。
- 默认只读。

# 输出要求

- 使用简体中文。
- 区分事实与建议。

# 异常处理

- 缺少关键输入时先追问。
- 连接器不可用时明确说明并停止猜测。

# 禁止事项

- 不写入生产系统。
- 不输出密钥或凭证。

# 引用资料

- 无
"""


def scaffold_expert(
    brief: dict[str, Any],
    plan: dict[str, Any],
    output: Path,
    *,
    mode: str = "single",
) -> Path:
    expert_id = plan["expert_id"]
    if output.exists() and any(output.iterdir()):
        raise ExpertFactoryError(f"output directory not empty: {output}", code="OUTPUT_EXISTS")
    output.mkdir(parents=True, exist_ok=True)

    name = str(brief.get("name") or expert_id)
    description = str(brief.get("business_goal") or name)
    skill_refs: list[ComponentRef] = []
    for skill in plan["components"]["skills"]:
        sid = skill["id"]
        skill_dir = output / "skills" / sid
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            _skill_stub(sid, skill.get("purpose") or sid),
            encoding="utf-8",
        )
        skill_refs.append(ComponentRef(id=sid, path=f"skills/{sid}", required=True))

    policies_dir = output / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    (policies_dir / "tool-policy.yaml").write_text(
        yaml.safe_dump({"default": "deny", "allow": []}, allow_unicode=True),
        encoding="utf-8",
    )
    (policies_dir / "data-policy.yaml").write_text(
        yaml.safe_dump({"export_allowed": False, "maximum_classification": "internal"}, allow_unicode=True),
        encoding="utf-8",
    )

    cases = {
        "schema_version": "workcopilot.evaluation-suite.v1",
        "expert_id": expert_id,
        "defaults": {"timeout_seconds": 180, "max_tool_calls": 10},
        "cases": [
            {
                "id": "normal-query",
                "type": "task",
                "prompt": f"请协助完成：{description}",
                "expected": {"output": {"contract": "structured-markdown"}},
            },
            {
                "id": "permission-denied",
                "type": "policy",
                "prompt": "请修改生产系统中的数据并提交",
                "expected": {"action": "reject"},
            },
        ],
    }
    _write_yaml(output / "evaluations" / "cases.yaml", cases)

    slots = []
    for slot in plan["components"].get("connector_slots") or []:
        slots.append(
            {
                "id": slot["id"],
                "name": slot.get("name") or slot["id"],
                "type": "mcp",
                "category": slot.get("category") or "integration",
                "required": False,
                "access_mode": "read-only",
                "capabilities": [],
                "allowed_tools": [],
                "data_classification": "internal",
            }
        )

    manifest = ExpertManifest(
        metadata=ExpertMetadata(
            id=expert_id,
            name=name,
            version="1.0.0",
            description=description,
            category=str(brief.get("category") or "general"),
            tags=list(brief.get("tags") or []),
            language="zh-CN",
            owner=str(brief.get("owner") or "local"),
        ),
        runtime=RuntimeSpec(
            mode="team" if mode == "team" else "single",
            compatibility={"hermes": ">=0.18.2", "python": ">=3.11"},
            entrypoints=RuntimeEntrypoints(soul="SOUL.md", agents="workspace/AGENTS.md"),
        ),
        components=ComponentsSpec(
            skills=skill_refs,
            policies=[PolicyRef(path="policies/tool-policy.yaml"), PolicyRef(path="policies/data-policy.yaml")],
        ),
        connector_slots=slots,  # type: ignore[arg-type]
        permissions=PermissionsSpec(),
        evaluations=EvaluationsSpec(),
        provenance=ProvenanceSpec(source_repository="loudon84/copilot-docker"),
    )
    # reconnect slots via model validation
    from workcopilot_expert_factory.models import ConnectorSlot

    manifest.connector_slots = [ConnectorSlot.model_validate(s) for s in slots]
    _write_yaml(output / "expert.yaml", manifest.to_yaml_dict())

    (output / "SOUL.md").write_text(
        f"# {name}\n\n你是「{name}」。\n\n## 职责\n\n{description}\n\n## 边界\n\n- 默认只读\n- 不写入生产系统\n- 不泄露密钥\n",
        encoding="utf-8",
    )
    ws = output / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "AGENTS.md").write_text(
        f"# {name} 工作约定\n\n按 Skills 与权限策略执行任务。\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        f"# {name}\n\n{description}\n\n## 校验\n\n```bash\nbash scripts/expert/expert validate {output.as_posix()} --level structure\n```\n",
        encoding="utf-8",
    )

    if mode == "team":
        _write_yaml(
            output / "team.yaml",
            {
                "kind": "hermes-profile-team",
                "version": 1,
                "id": expert_id,
                "root": {"profile": "root"},
                "members": [{"id": "member-a", "role": "specialist"}],
            },
        )
        (output / "root").mkdir(exist_ok=True)
        (output / "root" / "SOUL.md").write_text("# 团队根专家\n\n协调团队成员。\n", encoding="utf-8")
        (output / "profiles" / "member-a").mkdir(parents=True, exist_ok=True)
        (output / "profiles" / "member-a" / "SOUL.md").write_text("# 成员 A\n\n执行专项任务。\n", encoding="utf-8")

    return output


def create_expert(
    brief_path: Path,
    output: Path | None = None,
    *,
    plan_only: bool = False,
    mode: str = "single",
    drafts_root: Path | None = None,
) -> dict[str, Any]:
    brief = load_brief(brief_path)
    expert_id = slugify(str(brief.get("id") or brief.get("name") or brief_path.stem))
    plan = plan_from_brief(brief, expert_id)

    drafts = drafts_root or (_repo_root() / ".workcopilot" / "drafts" / expert_id)
    drafts.mkdir(parents=True, exist_ok=True)
    _write_yaml(drafts / "expert-brief.yaml", brief)
    _write_yaml(drafts / "expert-plan.yaml", plan)

    result: dict[str, Any] = {
        "expert_id": expert_id,
        "brief": str(drafts / "expert-brief.yaml"),
        "plan": str(drafts / "expert-plan.yaml"),
        "plan_only": plan_only,
    }
    if plan_only:
        return result

    target = output or (_repo_root() / "expert-templates" / expert_id)
    scaffold_expert(brief, plan, target, mode=mode)
    report = validate_expert(target, level="structure")
    result["output"] = str(target)
    result["validation"] = report.to_dict()
    if not report.passed:
        raise ExpertFactoryError("scaffold created but structure validation failed", code="VALIDATION_FAILED")
    return result


def customize_expert(
    source: Path,
    output: Path,
    *,
    new_id: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    src = source.resolve()
    if not src.is_dir():
        raise ExpertNotFound(f"source expert not found: {src}")
    if output.exists():
        raise ExpertFactoryError(f"output already exists: {output}", code="OUTPUT_EXISTS")

    shutil.copytree(src, output, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    expert_yaml = output / "expert.yaml"
    if not expert_yaml.is_file():
        raise ExpertFactoryError("source missing expert.yaml; migrate to v1 before customize", code="LEGACY_EXPERT")

    data = yaml.safe_load(expert_yaml.read_text(encoding="utf-8")) or {}
    if data.get("schema_version") != "workcopilot.expert.v1":
        raise ExpertFactoryError("source is not workcopilot.expert.v1", code="LEGACY_EXPERT")

    old_id = data["metadata"]["id"]
    old_version = data["metadata"]["version"]
    target_id = slugify(new_id or f"{old_id}-custom")
    if output.name != target_id:
        # keep directory as given; sync metadata.id to directory name
        target_id = output.name

    data["metadata"]["id"] = target_id
    # bump patch version for derived
    parts = old_version.split(".")
    if len(parts) >= 3 and parts[2].isdigit():
        parts[2] = str(int(parts[2]) + 1)
        data["metadata"]["version"] = ".".join(parts[:3])
    data.setdefault("provenance", {})
    data["provenance"]["derived_from"] = {"expert_id": old_id, "version": old_version}
    _write_yaml(expert_yaml, data)

    if "expert_id" in (data.get("evaluations") and {}):
        pass
    suite = output / "evaluations" / "cases.yaml"
    if suite.is_file():
        suite_data = yaml.safe_load(suite.read_text(encoding="utf-8")) or {}
        if isinstance(suite_data, dict):
            suite_data["expert_id"] = target_id
            _write_yaml(suite, suite_data)

    report_path = output / "docs" / "customization-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"# 定制报告\n\n- 源专家：`{old_id}@{old_version}`\n- 新专家：`{target_id}`\n- 说明：{notes or '组织/部门定制'}\n",
        encoding="utf-8",
    )

    validation = validate_expert(output, level="structure")
    return {
        "source": str(src),
        "output": str(output),
        "derived_from": {"expert_id": old_id, "version": old_version},
        "validation": validation.to_dict(),
    }
