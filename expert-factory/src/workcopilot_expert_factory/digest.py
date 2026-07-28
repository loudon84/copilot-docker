"""Canonical digests for Expert Source / Evaluation / Bundle payload."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Iterable

# Whitelist roots / files that participate in Source Digest and Release Bundle.
RUNTIME_WHITELIST_FILES = frozenset(
    {
        "expert.yaml",
        "SOUL.md",
        "AGENT.md",
        "AGENTS.md",
        "config.patch.yaml",
        "team.yaml",
        "README.md",
        "VERSION",
        "package.yaml",
        "requirements.txt",
        "python-requirements.txt",
        "npm-global.txt",
        "system-packages.txt",
        "package.json",
        "package-lock.json",
        "pyproject.toml",
    }
)

RUNTIME_WHITELIST_DIRS = frozenset(
    {
        "root",
        "profiles",
        "workspace",
        "skills",
        "tools",
        "plugins",
        "mcp",
        "policies",
        "skill-bundles",
        "gbrain",
        "connectors",
        "docs",
        "evaluations",
        "runtime",
        "bin",
        "lib",
        "shared",
        "config",
    }
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".env",
        "__pycache__",
        ".pytest_cache",
        "sessions",
        "logs",
        "webui",
        "node_modules",
        ".workcopilot",
        "dist",
        ".venv",
        "venv",
        "memories",
        "obsidian-vault",
        "hindsight",
        "prd",
        "tests",
    }
)


def git_commit(root: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def source_date_epoch() -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH", "0")
    try:
        epoch = int(raw)
    except ValueError:
        epoch = 0
    return epoch if epoch > 0 else 315532800  # 1980-01-01


def is_whitelisted_relative(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    if not parts or parts[0] in SKIP_DIR_NAMES:
        return False
    if any(p in SKIP_DIR_NAMES for p in parts):
        return False
    name = parts[-1]
    if name.endswith(".pyc") or name == ".env":
        return False
    if len(parts) == 1:
        return name in RUNTIME_WHITELIST_FILES or name.endswith(".yaml") or name.endswith(".yml")
    top = parts[0]
    if top not in RUNTIME_WHITELIST_DIRS:
        return False
    # evaluations: only cases.yaml (and fixtures), not results
    if top == "evaluations":
        if "results" in parts:
            return False
        return name.endswith((".yaml", ".yml", ".json", ".md"))
    return True


def iter_source_files(expert_root: Path) -> list[Path]:
    files: list[Path] = []
    root = expert_root.resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if is_whitelisted_relative(rel):
            files.append(path)
    return files


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_source_digest(expert_root: Path, files: Iterable[Path] | None = None) -> str:
    """
    Source Digest over release-related files:
    relative-path NUL file-content, sorted by normalized path.
    """
    root = expert_root.resolve()
    paths = list(files) if files is not None else iter_source_files(root)
    hasher = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
    return f"sha256:{hasher.hexdigest()}"


def compute_json_digest(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256_bytes(raw)}"
