from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.errors import ExpertFactoryError, ExpertNotFound

ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _load_env_keys(env_file: Path) -> set[str]:
    keys: set[str] = set()
    if not env_file.is_file():
        return keys
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = ENV_LINE.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def _slot_examples(expert_root: Path) -> dict[str, dict[str, Any]]:
    connectors = expert_root / "connectors"
    out: dict[str, dict[str, Any]] = {}
    if not connectors.is_dir():
        return out
    for path in connectors.glob("*.example.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict) and data.get("id"):
            out[str(data["id"])] = data
    return out


def bind_check(expert_path: Path | str, env_file: Path | str | None = None) -> dict[str, Any]:
    root = Path(expert_path).resolve()
    if not root.is_dir():
        raise ExpertNotFound(f"expert directory not found: {root}")
    expert_yaml = root / "expert.yaml"
    if not expert_yaml.is_file():
        raise ExpertFactoryError("missing expert.yaml", code="EXPERT_SCHEMA_INVALID")
    data = yaml.safe_load(expert_yaml.read_text(encoding="utf-8")) or {}
    if data.get("schema_version") != "workcopilot.expert.v1":
        raise ExpertFactoryError("bind-check requires workcopilot.expert.v1", code="LEGACY_EXPERT")

    slots = data.get("connector_slots") or []
    examples = _slot_examples(root)
    env_path = Path(env_file) if env_file else None
    present = _load_env_keys(env_path) if env_path else set()

    results = []
    missing_total: list[str] = []
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        sid = str(slot.get("id") or "")
        example = examples.get(sid) or {}
        env_map = example.get("env") or example.get("env_keys") or {}
        # env can be dict field->ENV_KEY or list of ENV_KEY
        required_env: list[str] = []
        if isinstance(env_map, dict):
            required_env = [str(v) for v in env_map.values() if v]
        elif isinstance(env_map, list):
            required_env = [str(v) for v in env_map]
        else:
            auth = slot.get("auth") or {}
            required_env = [
                f"{sid.upper().replace('-', '_')}_{f.upper()}"
                for f in (auth.get("required_fields") or [])
            ]

        if env_path:
            missing = [k for k in required_env if k not in present]
            if missing:
                missing_total.extend(missing)
            status = "ok" if not missing else "missing"
        else:
            missing = []
            status = "unchecked"
        results.append(
            {
                "slot_id": sid,
                "required": bool(slot.get("required", True)),
                "example": str((root / "connectors" / f"{sid}.example.yaml").relative_to(root))
                if (root / "connectors" / f"{sid}.example.yaml").is_file()
                else None,
                "required_env": required_env,
                "missing_env": missing,
                "status": status,
            }
        )

    return {
        "expert_id": (data.get("metadata") or {}).get("id"),
        "env_file": str(env_path) if env_path else None,
        "slots": results,
        "missing_env": sorted(set(missing_total)),
        "passed": not missing_total if env_path else True,
    }
