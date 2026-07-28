from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.errors import ExpertFactoryError, ExpertNotFound


def _copy_path(src: Path, dst: Path) -> None:
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                ".pytest_cache",
                "*.egg-info",
                "tests",
                ".git",
            ),
        )
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    else:
        raise ExpertFactoryError(f"source missing: {src}", code="COMPONENT_MISSING")


def inject_from_manifest(
    *,
    template_dir: Path | str,
    data_dir: Path | str,
    base_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Copy base + v1 manifest runtime assets into Hermes data dir (precise inject)."""
    tpl = Path(template_dir).resolve()
    dest = Path(data_dir).resolve()
    if not tpl.is_dir():
        raise ExpertNotFound(f"template not found: {tpl}")

    expert_yaml = tpl / "expert.yaml"
    if not expert_yaml.is_file():
        raise ExpertFactoryError("missing expert.yaml", code="EXPERT_SCHEMA_INVALID")
    data = yaml.safe_load(expert_yaml.read_text(encoding="utf-8")) or {}
    if data.get("schema_version") != "workcopilot.expert.v1":
        raise ExpertFactoryError("inject_from_manifest requires v1 manifest", code="LEGACY_EXPERT")
    if (data.get("runtime") or {}).get("mode") == "team":
        raise ExpertFactoryError("team mode must use inject-expert-team.sh", code="TEAM_LAYOUT")

    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    if base_dir:
        base = Path(base_dir).resolve()
        if base.is_dir():
            for item in base.iterdir():
                if item.name.startswith("."):
                    continue
                _copy_path(item, dest / item.name)
                copied.append(f"base:{item.name}")

    entry = (data.get("runtime") or {}).get("entrypoints") or {}
    for key in ("soul", "agents", "config_patch"):
        rel = entry.get(key)
        if not rel:
            continue
        src = tpl / rel
        _copy_path(src, dest / Path(rel))
        copied.append(str(Path(rel)).replace("\\", "/"))
        if key == "soul":
            mem = src.parent / "memories"
            if mem.is_dir():
                rel_mem = mem.relative_to(tpl)
                _copy_path(mem, dest / rel_mem)
                copied.append(str(rel_mem).replace("\\", "/"))

    components = data.get("components") or {}
    for kind in ("skills", "tools", "plugins"):
        for item in components.get(kind) or []:
            if not isinstance(item, dict):
                continue
            rel = item.get("path")
            if not rel:
                continue
            _copy_path(tpl / rel, dest / Path(rel))
            copied.append(str(Path(rel)).replace("\\", "/"))

    for item in components.get("policies") or []:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        if not rel:
            continue
        _copy_path(tpl / rel, dest / Path(rel))
        copied.append(str(Path(rel)).replace("\\", "/"))

    for optional in ("workspace", "memories", "obsidian-vault", "policies", "connectors"):
        src = tpl / optional
        if not src.exists():
            continue
        marker = optional
        if any(c == marker or c.startswith(marker + "/") for c in copied):
            continue
        _copy_path(src, dest / optional)
        copied.append(optional)

    return {
        "expert_id": (data.get("metadata") or {}).get("id"),
        "template": str(tpl),
        "data_dir": str(dest),
        "copied": sorted(set(copied)),
        "mode": "manifest-precise",
    }
