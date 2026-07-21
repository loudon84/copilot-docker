#!/usr/bin/env python3
"""Validate expert package manifest and required layout."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required", file=sys.stderr)
    sys.exit(2)

SECRET_PATTERNS = [
    re.compile(r"(?i)password\s*[:=]\s*\S+"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*\S+"),
    re.compile(r"(?i)secret\s*[:=]\s*\S+"),
    re.compile(r"(?i)mssql\+pymssql://[^:]+:[^@]+@"),
    re.compile(r"(?i)postgres(?:ql)?://[^:]+:[^@]+@"),
]

FORBIDDEN_NAMES = {
    ".env",
    "finance_bi.db",
    "doctor_probe.db",
}


def _fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)
    print(f"FAIL: {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"PASS: {msg}")


def validate_package(package_root: Path) -> int:
    errors: list[str] = []
    root = package_root.resolve()

    required_files = [
        "expert.yaml",
        "VERSION",
        "runtime/SOUL.md",
        "runtime/memories/MEMORY.md",
        "runtime/config.patch.yaml",
        "plugins/hermes-finance-bi-plugin/plugin.yaml",
        "plugins/hermes-finance-bi-plugin/requirements.txt",
        "bin/install.sh",
        "bin/post-start.sh",
        "bin/update.sh",
        "bin/validate.sh",
        "bin/doctor.sh",
        "bin/test.sh",
        "bin/sync-semantic-catalog.sh",
    ]
    for rel in required_files:
        if (root / rel).is_file():
            _ok(f"exists {rel}")
        else:
            _fail(f"missing {rel}", errors)

    required_dirs = [
        "runtime/skills",
        "runtime/semantic",
        "runtime/policies",
        "plugins/hermes-finance-bi-plugin",
        "lib",
        "tests",
    ]
    for rel in required_dirs:
        if (root / rel).is_dir():
            _ok(f"dir {rel}")
        else:
            _fail(f"missing dir {rel}", errors)

    # Parse YAML manifests
    for rel in ("expert.yaml", "runtime/config.patch.yaml", "plugins/hermes-finance-bi-plugin/plugin.yaml"):
        path = root / rel
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if data is None or not isinstance(data, (dict, list)):
                _fail(f"YAML empty/invalid: {rel}", errors)
            else:
                _ok(f"YAML parse {rel}")
        except Exception as exc:
            _fail(f"YAML parse error {rel}: {exc}", errors)

    # VERSION content
    version_path = root / "VERSION"
    if version_path.is_file():
        ver = version_path.read_text(encoding="utf-8").strip()
        if re.match(r"^\d+\.\d+\.\d+", ver):
            _ok(f"VERSION={ver}")
        else:
            _fail(f"VERSION not semver-like: {ver!r}", errors)

    # expert.yaml consistency
    manifest_path = root / "expert.yaml"
    if manifest_path.is_file():
        try:
            manifest: Any = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            expert = manifest.get("expert") if isinstance(manifest, dict) else None
            if not isinstance(expert, dict) or expert.get("id") != "bi-strategic-office":
                _fail("expert.yaml expert.id must be bi-strategic-office", errors)
            else:
                _ok("expert.id=bi-strategic-office")
        except Exception as exc:
            _fail(f"expert.yaml read error: {exc}", errors)

    # Forbidden runtime/secrets in package (scan package source-of-truth only;
    # skip transitional root copies like legacy config.yaml / GUIDE.md)
    SCAN_PREFIXES = ("runtime/", "plugins/", "bin/", "lib/", "expert.yaml", "VERSION")
    SKIP_PREFIXES = ("docs/", "prd/", "tests/", "skills/", "semantic/", "policies/", "memories/", "workspace/")

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if "__pycache__" in parts or ".git" in parts:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        name = path.name
        if name in FORBIDDEN_NAMES or name.endswith(".db"):
            if name == ".env" or name.endswith(".db"):
                _fail(f"forbidden file in package: {rel}", errors)
                continue

        if any(rel.startswith(p) or rel == p.rstrip("/") for p in SKIP_PREFIXES):
            continue
        if not any(rel.startswith(p) or rel == p.rstrip("/") for p in SCAN_PREFIXES):
            # transitional root files (legacy config.yaml, GUIDE.md, SOUL.md copies)
            continue
        if rel.endswith("README.md") or rel.endswith("CHANGELOG.md"):
            continue

        if path.suffix.lower() in {".md", ".txt", ".yaml", ".yml", ".py", ".sh", ".toml"}:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pat in SECRET_PATTERNS:
                m = pat.search(text)
                if not m:
                    continue
                snippet = m.group(0)
                if "PASSWORD" in snippet.upper() or "changeme" in snippet.lower():
                    continue
                if re.search(r"(?i)password\s*:\s*$", snippet):
                    continue
                # Placeholder / local stub values
                if re.search(
                    r"(?i)(your_|xxx|example|placeholder|<|\blocal\b|\bnone\b|\bnull\b|\btest\b)",
                    snippet,
                ):
                    continue
                _fail(f"possible secret in {rel}: {snippet[:60]}", errors)
                break

    if errors:
        print(f"validate_manifest: FAILED ({len(errors)} errors)", file=sys.stderr)
        return 1
    print("validate_manifest: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate bi-strategic-office package")
    parser.add_argument(
        "--package-root",
        default="",
        help="Package root (default: parent of lib/)",
    )
    args = parser.parse_args()
    if args.package_root:
        root = Path(args.package_root)
    else:
        root = Path(__file__).resolve().parents[1]
    return validate_package(root)


if __name__ == "__main__":
    raise SystemExit(main())
