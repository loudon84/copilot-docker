"""Discover reusable skills/plugins/tools across expert-templates."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.DOTALL)


def _parse_skill(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    meta: dict[str, Any] = {}
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
    skill_id = meta.get("id") or path.parent.name
    return {
        "type": "skill",
        "id": skill_id,
        "name": meta.get("name") or skill_id,
        "description": (meta.get("description") or "")[:200],
        "triggers": meta.get("triggers") or [],
        "source": str(path.parent).replace("\\", "/"),
        "kind": meta.get("kind"),
    }


def scan_component_catalog(templates_root: Path) -> dict[str, Any]:
    skills: list[dict[str, Any]] = []
    plugins: list[dict[str, Any]] = []
    tools: list[dict[str, Any]] = []

    if not templates_root.is_dir():
        return {"skills": skills, "plugins": plugins, "tools": tools}

    for expert_dir in sorted(p for p in templates_root.iterdir() if p.is_dir()):
        for skill_md in expert_dir.rglob("SKILL.md"):
            if any(x in skill_md.parts for x in (".git", "node_modules", ".backup")):
                continue
            # skip factory skills inside templates accidentally
            try:
                entry = _parse_skill(skill_md)
            except OSError:
                continue
            if entry:
                entry["expert"] = expert_dir.name
                skills.append(entry)

        plugins_dir = expert_dir / "plugins"
        if plugins_dir.is_dir():
            for child in plugins_dir.iterdir():
                if child.is_dir() and ((child / "plugin.yaml").is_file() or (child / "SKILL.md").is_file()):
                    plugins.append(
                        {
                            "type": "plugin",
                            "id": child.name,
                            "source": str(child).replace("\\", "/"),
                            "expert": expert_dir.name,
                        }
                    )

        tools_dir = expert_dir / "tools"
        if tools_dir.is_dir():
            for child in tools_dir.iterdir():
                if child.is_dir() or child.suffix in {".py", ".js", ".ts"}:
                    tools.append(
                        {
                            "type": "tool",
                            "id": child.stem if child.is_file() else child.name,
                            "source": str(child).replace("\\", "/"),
                            "expert": expert_dir.name,
                        }
                    )

    return {"skills": skills, "plugins": plugins, "tools": tools}


def find_reusable(
    catalog: dict[str, Any],
    capability: str,
) -> dict[str, Any] | None:
    needle = capability.lower()
    tokens = set(re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", needle))
    best = None
    best_score = 0
    for skill in catalog.get("skills") or []:
        hay = " ".join(
            [
                str(skill.get("id") or ""),
                str(skill.get("name") or ""),
                str(skill.get("description") or ""),
                " ".join(skill.get("triggers") or []),
            ]
        ).lower()
        score = sum(1 for t in tokens if t and t in hay)
        if score > best_score:
            best_score = score
            best = skill
    if best_score >= 2 or (best_score >= 1 and len(tokens) <= 2):
        return best
    return None
