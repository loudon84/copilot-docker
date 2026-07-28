from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.adapters.schema_loader import validate_against
from workcopilot_expert_factory.evaluators import CheckResult
from workcopilot_expert_factory.validators.expert import _parse_frontmatter


V1 = "workcopilot.expert.v1"


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run_static_checks(root: Path, data: dict[str, Any]) -> list[CheckResult]:
    checks: list[CheckResult] = []
    components = data.get("components") or {}
    skills = components.get("skills") or []
    slots = data.get("connector_slots") or []
    perms = data.get("permissions") or {}
    tools_perm = perms.get("tools") or {}

    # permissions default deny
    if tools_perm.get("default") == "deny":
        checks.append(
            CheckResult("perm-default-deny", "permission", True, 1.0, "tools.default=deny")
        )
    else:
        checks.append(
            CheckResult(
                "perm-default-deny",
                "permission",
                False,
                1.0,
                "tools.default must be deny",
                gate=True,
            )
        )

    # skill frontmatter + sections + triggers
    trigger_ok = 0
    tool_map_ok = 0
    prohibit_ok = 0
    skill_total = 0
    for item in skills:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        if not rel:
            continue
        skill_md = root / rel / "SKILL.md"
        skill_total += 1
        if not skill_md.is_file():
            checks.append(
                CheckResult(
                    f"skill-missing-{item.get('id')}",
                    "skill",
                    False,
                    1.0,
                    f"missing {rel}/SKILL.md",
                    gate=False,
                )
            )
            continue
        text = skill_md.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        if not meta or meta.get("schema_version") != "workcopilot.skill.v1":
            checks.append(
                CheckResult(
                    f"skill-schema-{item.get('id')}",
                    "skill",
                    False,
                    1.0,
                    "missing workcopilot.skill.v1",
                )
            )
            continue
        triggers = meta.get("triggers") or []
        if triggers:
            trigger_ok += 1
        req_tools = set(meta.get("tool_requirements") or [])
        allow = set((tools_perm.get("allow") or []))
        deny = set((tools_perm.get("deny") or []))
        if not req_tools or req_tools.issubset(allow) or not allow:
            # empty allow with only deny is ok for read-only experts without tools
            if req_tools and allow and not req_tools.issubset(allow):
                if req_tools & deny:
                    checks.append(
                        CheckResult(
                            f"tool-deny-conflict-{item.get('id')}",
                            "tool",
                            False,
                            1.0,
                            f"skill requires denied tools: {sorted(req_tools & deny)}",
                            gate=True,
                        )
                    )
                else:
                    tool_map_ok += 0
            else:
                tool_map_ok += 1
        else:
            tool_map_ok += 1
        if "# 禁止事项" in body:
            prohibit_ok += 1
        # connector requirements must be declared slots
        for cid in meta.get("connector_requirements") or []:
            if not any(isinstance(s, dict) and s.get("id") == cid for s in slots):
                checks.append(
                    CheckResult(
                        f"connector-undeclared-{cid}",
                        "exception",
                        False,
                        1.0,
                        f"skill requires undeclared connector slot {cid}",
                        gate=True,
                    )
                )

    if skill_total:
        checks.append(
            CheckResult(
                "triggers-coverage",
                "skill",
                trigger_ok == skill_total,
                1.0,
                f"skills with triggers: {trigger_ok}/{skill_total}",
            )
        )
        checks.append(
            CheckResult(
                "tool-mapping",
                "tool",
                tool_map_ok >= max(1, skill_total // 2),
                1.0,
                f"skills with ok tool mapping: {tool_map_ok}/{skill_total}",
            )
        )
        checks.append(
            CheckResult(
                "prohibit-sections",
                "permission",
                prohibit_ok == skill_total,
                1.0,
                f"skills with 禁止事项: {prohibit_ok}/{skill_total}",
            )
        )
    else:
        checks.append(CheckResult("skills-present", "skill", False, 1.0, "no skills declared"))

    # evaluation suite
    suite_rel = (data.get("evaluations") or {}).get("suite") or "evaluations/cases.yaml"
    suite_path = root / suite_rel
    if suite_path.is_file():
        suite = _load(suite_path)
        errs = validate_against("evaluation-suite-v1.schema.json", suite)
        checks.append(
            CheckResult(
                "eval-suite-schema",
                "task",
                not errs,
                1.0,
                "ok" if not errs else "; ".join(errs)[:200],
            )
        )
        cases = suite.get("cases") or []
        types = {c.get("type") for c in cases if isinstance(c, dict)}
        checks.append(
            CheckResult(
                "eval-suite-coverage",
                "task",
                "task" in types and ("policy" in types or "security" in types),
                1.0,
                f"case types: {sorted(t for t in types if t)}",
            )
        )
    else:
        checks.append(
            CheckResult("eval-suite-missing", "task", False, 1.0, f"missing {suite_rel}")
        )

    # output contract: at least structured-markdown mentioned in skills
    out_ok = False
    for item in skills:
        if not isinstance(item, dict):
            continue
        skill_md = root / (item.get("path") or "") / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta, _ = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        if meta and (meta.get("outputs") or {}).get("format"):
            out_ok = True
            break
    checks.append(
        CheckResult(
            "output-contract",
            "output",
            out_ok or not skills,
            1.0,
            "skills declare outputs.format" if out_ok else "no outputs.format found",
        )
    )

    # connector slots shape
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        sid = slot.get("id", "?")
        if slot.get("access_mode") == "read-only" or slot.get("required") is not None:
            checks.append(
                CheckResult(
                    f"slot-{sid}",
                    "exception",
                    True,
                    0.5,
                    f"connector slot {sid} declared",
                )
            )

    return checks
