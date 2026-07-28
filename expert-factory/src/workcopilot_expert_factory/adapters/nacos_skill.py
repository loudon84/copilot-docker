"""Adapter helpers for Nacos Skill packages."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.builders.nacos_package import build_skill_zip_bytes

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.DOTALL)


def skill_frontmatter(skill_dir: Path) -> dict[str, Any]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return {}
    text = skill_md.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {"id": skill_dir.name, "version": "1.0.0"}
    return yaml.safe_load(m.group(1)) or {}


def pack_skill(skill_dir: Path) -> tuple[bytes, dict[str, Any]]:
    meta = skill_frontmatter(skill_dir)
    sid = meta.get("id") or skill_dir.name
    version = meta.get("version") or "1.0.0"
    return build_skill_zip_bytes(skill_dir, sid, version), {"id": sid, "version": version, **meta}
