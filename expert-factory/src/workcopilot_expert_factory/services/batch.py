from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable

import yaml

INFRA = frozenset({"base", "default"})
V1 = "workcopilot.expert.v1"


def repo_root_from_cwd() -> Path:
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "expert-templates").is_dir() and (candidate / "expert-factory").is_dir():
            return candidate
    return cwd


def templates_root(repo: Path | None = None) -> Path:
    return (repo or repo_root_from_cwd()) / "expert-templates"


def is_v1_expert(path: Path) -> bool:
    expert_yaml = path / "expert.yaml"
    if not expert_yaml.is_file():
        return False
    try:
        data = yaml.safe_load(expert_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    return isinstance(data, dict) and data.get("schema_version") == V1


def list_v1_experts(repo: Path | None = None) -> list[Path]:
    root = templates_root(repo)
    out: list[Path] = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in INFRA or child.name.startswith("."):
            continue
        if is_v1_expert(child):
            out.append(child)
    return out


def _git_diff_names(repo: Path, base_ref: str) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            cwd=str(repo),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []


def resolve_base_ref() -> str:
    env_base = os.environ.get("GITHUB_BASE_REF") or os.environ.get("EXPERT_FACTORY_BASE_REF")
    if env_base:
        # GITHUB_BASE_REF is branch name without origin/
        if not env_base.startswith("origin/") and "/" not in env_base:
            return f"origin/{env_base}"
        return env_base
    return "origin/master"


def list_changed_v1_experts(repo: Path | None = None, base_ref: str | None = None) -> list[Path]:
    root = repo or repo_root_from_cwd()
    base = base_ref or resolve_base_ref()
    names = _git_diff_names(root, base)
    ids: set[str] = set()
    for name in names:
        parts = name.split("/")
        if len(parts) >= 2 and parts[0] == "expert-templates":
            ids.add(parts[1])
    out: list[Path] = []
    for eid in sorted(ids):
        if eid in INFRA:
            continue
        path = templates_root(root) / eid
        if is_v1_expert(path):
            out.append(path)
    return out


def select_experts(
    *,
    all_experts: bool = False,
    changed: bool = False,
    paths: Iterable[Path] | None = None,
    repo: Path | None = None,
) -> list[Path]:
    if paths:
        return [Path(p).resolve() for p in paths]
    if changed:
        return list_changed_v1_experts(repo)
    if all_experts:
        return list_v1_experts(repo)
    return []
