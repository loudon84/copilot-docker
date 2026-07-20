#!/usr/bin/env python3
"""Ensure hermes-finance-bi-plugin is opted into config.yaml plugins.enabled.

Hermes discovers user plugins under ~/.hermes/plugins/ but does NOT load them
until the plugin name appears in plugins.enabled (opt-in).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required", file=sys.stderr)
    raise SystemExit(2)

DEFAULT_PLUGIN = "hermes-finance-bi-plugin"
DEFAULT_TOOLSET = "finance-bi"


def ensure_enabled(config: dict[str, Any], plugin_name: str, toolset: str) -> dict[str, Any]:
    plugins = config.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        plugins = {}
        config["plugins"] = plugins

    enabled = plugins.get("enabled")
    if not isinstance(enabled, list):
        enabled = []
    # normalize and dedupe while preserving order
    seen: set[str] = set()
    new_enabled: list[str] = []
    for item in enabled:
        s = str(item).strip()
        if s and s not in seen:
            seen.add(s)
            new_enabled.append(s)
    if plugin_name not in seen:
        new_enabled.append(plugin_name)
    plugins["enabled"] = new_enabled

    disabled = plugins.get("disabled")
    if isinstance(disabled, list) and plugin_name in disabled:
        plugins["disabled"] = [x for x in disabled if str(x).strip() != plugin_name]

    # Append toolset to any existing platform_toolsets lists (do not create
    # a sparse map that would wipe default toolsets).
    platform_toolsets = config.get("platform_toolsets")
    if isinstance(platform_toolsets, dict):
        for _platform, tools in platform_toolsets.items():
            if isinstance(tools, list) and toolset not in tools:
                tools.append(toolset)

    return config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--plugin", default=DEFAULT_PLUGIN)
    parser.add_argument("--toolset", default=DEFAULT_TOOLSET)
    args = parser.parse_args()

    if not args.config.is_file():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 1

    data = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        print("ERROR: config must be a mapping", file=sys.stderr)
        return 1

    ensure_enabled(data, args.plugin, args.toolset)
    args.config.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"[bi] ensured plugins.enabled contains {args.plugin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
