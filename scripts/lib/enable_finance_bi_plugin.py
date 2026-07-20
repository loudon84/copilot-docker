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
    changed_platforms: list[str] = []
    platform_toolsets = config.get("platform_toolsets")
    if isinstance(platform_toolsets, dict):
        for platform, tools in platform_toolsets.items():
            if isinstance(tools, list) and toolset not in tools:
                tools.append(toolset)
                changed_platforms.append(str(platform))

    config["_bi_enable_meta"] = {
        "plugin": plugin_name,
        "toolset": toolset,
        "platform_toolsets_updated": changed_platforms,
    }
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
    meta = data.pop("_bi_enable_meta", {})
    args.config.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"[bi] ensured plugins.enabled contains {args.plugin}")
    updated = meta.get("platform_toolsets_updated") or []
    if updated:
        print(f"[bi] appended {args.toolset} to platform_toolsets: {', '.join(updated)}")
    elif isinstance(data.get("platform_toolsets"), dict) and data["platform_toolsets"]:
        print(f"[bi] platform_toolsets already include {args.toolset} (or no list entries)")
    else:
        print("[bi] no platform_toolsets map present (plugin enable alone is enough if Hermes uses defaults)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
