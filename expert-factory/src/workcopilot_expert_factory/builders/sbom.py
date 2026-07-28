"""CycloneDX-compatible SBOM generator for Expert Bundle."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workcopilot_expert_factory.digest import sha256_file
from workcopilot_expert_factory.validators.dependencies import collect_dependency_manifest


def build_cyclonedx_sbom(
    expert_root: Path,
    *,
    expert_id: str,
    expert_version: str,
    files: list[Path],
) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    deps = collect_dependency_manifest(expert_root)
    for dep in deps.get("components") or []:
        components.append(
            {
                "type": dep.get("type") or "library",
                "name": dep["name"],
                "version": dep.get("version") or "unspecified",
                "purl": dep.get("purl"),
            }
        )

    for path in files:
        rel = path.relative_to(expert_root).as_posix()
        components.append(
            {
                "type": "file",
                "name": rel,
                "version": expert_version,
                "hashes": [{"alg": "SHA-256", "content": sha256_file(path)}],
            }
        )

    # plugins as components
    plugins_dir = expert_root / "plugins"
    if plugins_dir.is_dir():
        for plugin_yaml in plugins_dir.rglob("plugin.yaml"):
            components.append(
                {
                    "type": "application",
                    "name": plugin_yaml.parent.name,
                    "version": expert_version,
                    "description": "hermes plugin",
                }
            )

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type": "application",
                "name": expert_id,
                "version": expert_version,
                "bom-ref": f"expert:{expert_id}@{expert_version}",
            },
            "tools": [{"vendor": "WorkCopilot", "name": "expert-factory", "version": "2.1.0"}],
        },
        "components": components,
    }


def write_sbom_json(path: Path, bom: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bom, ensure_ascii=False, indent=2), encoding="utf-8")
