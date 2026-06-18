#!/usr/bin/env python3
"""Merge Hermes runtime sections (memory / MCP / curator / security / terminal) into config.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "ERROR: PyYAML 未安装。请执行: sudo apt-get install -y python3-yaml",
        file=sys.stderr,
    )
    raise SystemExit(1)


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def deep_update(target: dict, patch: dict) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value


def runtime_patch(
    profile: str,
    hindsight_api_url: str,
    hindsight_bank_id: str,
    gbrain_enabled: bool = True,
    gbrain_command: str = "/usr/local/bin/gbrain",
) -> dict:
    bank_id = hindsight_bank_id or f"hermes-{profile}"
    return {
        "memory": {
            "provider": "hindsight",
            "mode": "local_external",
            "api_url": hindsight_api_url,
            "bank_id": bank_id,
        },
        "mcp_servers": {
            "workspace": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "/data/hermes/workspace",
                ],
                "enabled": True,
                "tools": {"resources": True, "prompts": False},
            },
            "obsidian_vault": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "/data/hermes/obsidian-vault",
                ],
                "enabled": True,
                "tools": {"resources": True, "prompts": False},
            },
            "gbrain": {
                "command": gbrain_command,
                "args": [],
                "enabled": gbrain_enabled,
                "tools": {"resources": True, "prompts": False},
            },
        },
        "auxiliary": {
            "curator": {
                "enabled": True,
                "interval_days": 7,
                "archive_unused_after_days": 45,
                "protect_bundled_skills": True,
                "protect_hub_skills": True,
            }
        },
        "security": {
            "website_blocklist": {
                "enabled": True,
                "domains": ["169.254.169.254"],
            }
        },
        "terminal": {
            "backend": "docker",
            "docker_forward_env": [],
            "env_passthrough": [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--hindsight-api-url", default="http://hindsight.superic.com:8888")
    parser.add_argument("--hindsight-bank-id", default="")
    parser.add_argument("--gbrain-enabled", default="1")
    parser.add_argument("--gbrain-command", default="/usr/local/bin/gbrain")
    args = parser.parse_args()

    gbrain_enabled = args.gbrain_enabled not in ("0", "false", "False")
    data = load_yaml(args.config)
    patch = runtime_patch(
        args.profile,
        args.hindsight_api_url,
        args.hindsight_bank_id,
        gbrain_enabled=gbrain_enabled,
        gbrain_command=args.gbrain_command,
    )
    deep_update(data, patch)

    args.config.parent.mkdir(parents=True, exist_ok=True)
    args.config.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"OK: runtime sections patched → {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
