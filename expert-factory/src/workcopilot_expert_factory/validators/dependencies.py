"""Dependency / supply-chain validation (PRD §13.7)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workcopilot_expert_factory.validators.expert import ValidationReport

UNBOUNDED_RE = re.compile(r"^[A-Za-z0-9_.\-]+\s*>=\s*[^,<\s]+$")
DENY_LICENSES = frozenset({"GPL-3.0", "AGPL-3.0", "SSPL-1.0"})


def _parse_req_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # strip extras
    line = line.split(";")[0].strip()
    m = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)$", line)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def validate_dependencies(
    root: Path,
    report: ValidationReport,
    *,
    release_mode: bool = False,
) -> None:
    req_files = [
        root / "requirements.txt",
        root / "python-requirements.txt",
        root / "dependencies" / "python-requirements.txt",
    ]
    # plugin requirements
    for path in root.rglob("requirements.txt"):
        if "node_modules" in path.parts or ".git" in path.parts:
            continue
        req_files.append(path)

    seen: set[str] = set()
    for req_path in req_files:
        if not req_path.is_file():
            continue
        rel = str(req_path.relative_to(root)).replace("\\", "/")
        try:
            lines = req_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            parsed = _parse_req_line(line)
            if not parsed:
                continue
            name, spec = parsed
            key = name.lower()
            if key in seen:
                report.add("warning", "E_DEPENDENCY_INVALID", f"duplicate dependency: {name}", rel)
            seen.add(key)
            if release_mode and (not spec or UNBOUNDED_RE.match(f"{name}{spec}") or spec.startswith(">=")):
                if not any(op in spec for op in ("==", "~=", "<=", "<", ",")):
                    report.add(
                        "error",
                        "E_DEPENDENCY_INVALID",
                        f"release mode forbids unbounded pin: {name}{spec}",
                        rel,
                    )

    # undeclared network: connector slots without network permission
    expert_yaml = root / "expert.yaml"
    if expert_yaml.is_file():
        import yaml

        data = yaml.safe_load(expert_yaml.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            slots = [s.get("id") for s in (data.get("connector_slots") or []) if isinstance(s, dict)]
            net = ((data.get("permissions") or {}).get("network") or {}).get("connector_slots") or []
            for sid in slots:
                if sid and sid not in net:
                    report.add(
                        "warning",
                        "E_DEPENDENCY_INVALID",
                        f"connector slot {sid} not listed in permissions.network.connector_slots",
                    )


def collect_dependency_manifest(root: Path) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    for name in ("python-requirements.txt", "requirements.txt", "npm-global.txt", "system-packages.txt"):
        path = root / name
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                parsed = _parse_req_line(line)
                if parsed:
                    components.append(
                        {
                            "type": "library",
                            "name": parsed[0],
                            "version": parsed[1] or "unspecified",
                            "purl": f"pkg:pypi/{parsed[0].lower()}" if "npm" not in name else f"pkg:npm/{parsed[0]}",
                        }
                    )
    return {"components": components}
