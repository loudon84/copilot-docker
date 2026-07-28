"""Plan Expert components with reuse decisions and risk notes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from workcopilot_expert_factory.planners.component_catalog import find_reusable, scan_component_catalog


def _slugify(value: str) -> str:
    text = value.strip().lower().replace("_", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(text) < 3 or not re.match(r"^[a-z]", text):
        compact = re.sub(r"[^a-z0-9]", "", text) or "skill"
        text = f"skill-{compact}"[:64]
    return text[:64]


def plan_expert(
    brief: dict[str, Any],
    *,
    expert_id: str,
    templates_root: Path | None = None,
) -> dict[str, Any]:
    catalog = scan_component_catalog(templates_root) if templates_root else {"skills": [], "plugins": [], "tools": []}

    reusable: list[dict[str, Any]] = []
    new_components: list[dict[str, Any]] = []
    skills: list[dict[str, Any]] = []

    for cap in brief.get("required_capabilities") or []:
        hit = find_reusable(catalog, str(cap))
        if hit:
            reusable.append(
                {
                    "type": "skill",
                    "id": hit["id"],
                    "source": hit["source"],
                    "decision": "reuse",
                    "for_capability": cap,
                }
            )
            skills.append(
                {
                    "id": hit["id"],
                    "purpose": str(cap),
                    "reuse_from": hit["source"],
                    "kind": hit.get("kind") or "procedural",
                }
            )
        else:
            sid = _slugify(str(cap))
            new_components.append(
                {
                    "type": "skill",
                    "id": sid,
                    "reason": "当前仓库无对应能力",
                    "for_capability": cap,
                }
            )
            skills.append({"id": sid, "purpose": str(cap), "kind": "procedural"})

    if not skills:
        skills.append(
            {
                "id": "primary-task",
                "purpose": brief.get("business_goal") or "核心任务",
                "kind": "general",
            }
        )
        new_components.append({"type": "skill", "id": "primary-task", "reason": "默认主技能"})

    slots = []
    for sys_name in brief.get("external_systems") or []:
        slots.append({"id": _slugify(str(sys_name)), "category": "integration", "name": str(sys_name)})

    risks = []
    if any(s.get("reuse_from") for s in skills) and any(not s.get("reuse_from") for s in skills):
        risks.append("部分能力复用已有 Skill，部分新建；需检查职责重叠")
    if slots:
        risks.append("存在外部系统依赖，需声明 Connector Slot 且默认只读")
    for c in brief.get("constraints") or []:
        risks.append(f"约束: {c}")

    return {
        "expert_id": expert_id,
        "business_goal": brief.get("business_goal"),
        "role_boundary": brief.get("constraints") or ["默认只读", "不写入生产", "不泄露密钥"],
        "inputs": ["用户业务问题", "可选上下文附件"],
        "outputs": ["结构化 Markdown 报告"],
        "components": {
            "skills": skills,
            "plugins": [],
            "connector_slots": slots,
            "policies": ["tool-policy", "data-policy"],
            "evaluations": ["normal-query", "normal-query-2", "missing-input", "permission-denied", "prompt-injection"],
            "do_not_create": [
                {"component": "duplicate-plugin", "reason": "默认复用已有 Plugin，禁止重复造轮子"},
            ],
        },
        "reusable_components": reusable,
        "new_components": new_components,
        "risks": risks,
        "unsupported": ["生产 Secret 绑定", "在线审批", "跨组织交易"],
        "constraints": brief.get("constraints") or [],
    }
