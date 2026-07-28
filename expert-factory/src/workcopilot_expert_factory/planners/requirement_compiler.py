"""Compile Markdown PRD / natural language requirements into Expert Brief."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from workcopilot_expert_factory.errors import BriefInvalid


HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
BULLET_RE = re.compile(r"^[\-\*]\s+(.+)$", re.MULTILINE)


def _slugify(value: str) -> str:
    text = value.strip().lower().replace("_", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(text) < 3 or not re.match(r"^[a-z]", text):
        compact = re.sub(r"[^a-z0-9]", "", text) or "expert"
        text = f"expert-{compact}"[:64]
    return text[:64]


def compile_requirements_markdown(text: str, *, default_id: str | None = None) -> dict[str, Any]:
    if not text or not text.strip():
        raise BriefInvalid("requirements document is empty")

    title = None
    for match in HEADING_RE.finditer(text):
        if len(match.group(1)) <= 2:
            title = match.group(2).strip()
            break
    if not title:
        title = (text.strip().splitlines()[0] or "未命名专家")[:80]

    bullets = [m.group(1).strip() for m in BULLET_RE.finditer(text)]
    capabilities: list[str] = []
    external: list[str] = []
    constraints: list[str] = []

    section = "general"
    for line in text.splitlines():
        h = HEADING_RE.match(line)
        if h:
            heading = h.group(2).lower()
            if any(k in heading for k in ("能力", "capability", "skill", "功能")):
                section = "capabilities"
            elif any(k in heading for k in ("外部", "系统", "connector", "集成")):
                section = "external"
            elif any(k in heading for k in ("约束", "禁止", "边界", "constraint")):
                section = "constraints"
            elif any(k in heading for k in ("目标", "职责", "goal", "定位")):
                section = "goal"
            else:
                section = "general"
            continue
        m = re.match(r"^[\-\*]\s+(.+)$", line)
        if not m:
            continue
        item = m.group(1).strip()
        if section == "capabilities":
            capabilities.append(item)
        elif section == "external":
            external.append(item)
        elif section == "constraints":
            constraints.append(item)

    if not capabilities:
        # fallback: first few bullets as capabilities
        capabilities = bullets[:5] or [f"完成「{title}」相关任务"]

    # goal paragraph
    goal = title
    goal_match = re.search(r"(?:业务目标|目标|职责)[：:]\s*(.+)", text)
    if goal_match:
        goal = goal_match.group(1).strip()

    expert_id = default_id or _slugify(title)
    return {
        "id": expert_id,
        "name": title,
        "business_goal": goal,
        "required_capabilities": capabilities,
        "external_systems": external,
        "constraints": constraints,
        "category": "general",
        "tags": [],
        "owner": "local",
        "source": "requirements-markdown",
    }


def compile_requirements_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BriefInvalid(f"requirements file not found: {path}")
    text = path.read_text(encoding="utf-8")
    return compile_requirements_markdown(text, default_id=_slugify(path.stem))
