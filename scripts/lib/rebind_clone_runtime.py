#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def replace_instance_tokens(value: Any, source: str, target: str) -> Any:
    if isinstance(value, str):
        # Runtime-critical source namespace replacement only. Do not replace a
        # bare source name in arbitrary prompts/text.
        value = value.replace(f"hermes-{source}", f"hermes-{target}")
        return value
    if isinstance(value, list):
        return [replace_instance_tokens(v, source, target) for v in value]
    if isinstance(value, dict):
        return {
            k: replace_instance_tokens(v, source, target)
            for k, v in value.items()
        }
    return value


def expected_bank(target_instance: str, profile_id: str | None) -> str:
    if profile_id:
        return f"hermes-{target_instance}-{profile_id}"
    return f"hermes-{target_instance}"


# @lat: [[runtime#Runtime Deployment#Instance Capability Clone#Hindsight Namespace Rebind]]
def rebind_config(
    path: Path,
    source_instance: str,
    target_instance: str,
    hindsight_api_url: str,
    profile_id: str | None,
    verify_only: bool,
) -> None:
    data = load_yaml(path)
    data = replace_instance_tokens(data, source_instance, target_instance)

    memory = data.setdefault("memory", {})
    if not isinstance(memory, dict):
        memory = {}
        data["memory"] = memory

    bank = expected_bank(target_instance, profile_id)

    if verify_only:
        actual = memory.get("bank_id")
        if actual != bank:
            raise SystemExit(
                f"ERROR: {path}: memory.bank_id={actual!r}, expected {bank!r}"
            )
        serialized = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        if f"hermes-{source_instance}" in serialized:
            raise SystemExit(
                f"ERROR: {path}: source Hindsight namespace still present"
            )
        return

    memory["provider"] = memory.get("provider", "hindsight")
    memory["mode"] = memory.get("mode", "local_external")
    memory["api_url"] = hindsight_api_url
    memory["bank_id"] = bank

    dump_yaml(path, data)


def rebind_team_yaml(
    path: Path,
    source_instance: str,
    target_instance: str,
    verify_only: bool,
) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    rebound = text.replace(f"hermes-{source_instance}", f"hermes-{target_instance}")
    if verify_only:
        if f"hermes-{source_instance}" in rebound:
            raise SystemExit(f"ERROR: {path}: source namespace still present")
        return
    if rebound != text:
        path.write_text(rebound, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebind cloned Hermes runtime identity")
    parser.add_argument("--hermes-root", required=True, type=Path)
    parser.add_argument("--source-instance", required=True)
    parser.add_argument("--target-instance", required=True)
    parser.add_argument("--hindsight-api-url", required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    root = args.hermes_root
    root_config = root / "config.yaml"
    if not root_config.exists():
        raise SystemExit(f"ERROR: root config missing: {root_config}")

    rebind_config(
        root_config,
        args.source_instance,
        args.target_instance,
        args.hindsight_api_url,
        None,
        args.verify_only,
    )
    rebind_team_yaml(
        root / "team.yaml",
        args.source_instance,
        args.target_instance,
        args.verify_only,
    )

    profiles_root = root / "profiles"
    if profiles_root.is_dir():
        for profile_dir in sorted(profiles_root.iterdir(), key=lambda p: p.name):
            if not profile_dir.is_dir():
                continue
            config = profile_dir / "config.yaml"
            if not config.exists():
                continue
            rebind_config(
                config,
                args.source_instance,
                args.target_instance,
                args.hindsight_api_url,
                profile_dir.name,
                args.verify_only,
            )

    print("runtime rebind verification OK" if args.verify_only else "runtime rebind OK")


if __name__ == "__main__":
    main()
