#!/usr/bin/env python3
"""Deep-merge expert config.patch.yaml into instance config.yaml.

- Recursive dict merge
- List dedupe-union for plugins.enabled / toolsets (and nested enabled lists)
- Preserve top-level model / providers
- Atomic write + optional backup before merge
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required", file=sys.stderr)
    sys.exit(2)

PRESERVE_TOP_LEVEL = ("model", "providers")
LIST_UNION_KEYS = frozenset({"enabled", "toolsets", "disabled_toolsets"})


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base or {})
    for key, value in (patch or {}).items():
        if key in PRESERVE_TOP_LEVEL and key in out:
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        elif (
            key in LIST_UNION_KEYS
            and isinstance(value, list)
            and isinstance(out.get(key), list)
        ):
            merged = list(out[key])
            for item in value:
                if item not in merged:
                    merged.append(item)
            out[key] = merged
        else:
            out[key] = value
    return out


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        Path(tmp_name).replace(path)
    except Exception:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def backup_config(config_path: Path, backup_dir: Path | None = None) -> Path | None:
    if not config_path.is_file():
        return None
    if backup_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_dir = config_path.parent / ".backup" / ts
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / config_path.name
    shutil.copy2(config_path, dest)
    return dest


def merge_files(
    config_path: Path,
    patch_path: Path,
    *,
    inplace: bool = False,
    do_backup: bool = True,
) -> dict[str, Any]:
    if not patch_path.is_file():
        raise FileNotFoundError(f"patch not found: {patch_path}")
    if not config_path.is_file():
        raise FileNotFoundError(f"config not found: {config_path}")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    patch = yaml.safe_load(patch_path.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict) or not isinstance(patch, dict):
        raise ValueError("config/patch must be mapping")

    if do_backup and inplace:
        backup_config(config_path)

    merged = deep_merge(config, patch)
    text = yaml.safe_dump(merged, allow_unicode=True, sort_keys=False)
    if inplace:
        _atomic_write(config_path, text)
    return merged


def ensure_plugin_enabled(
    config: dict[str, Any],
    plugin_name: str = "hermes-finance-bi-plugin",
    toolset: str = "finance-bi",
) -> dict[str, Any]:
    """Ensure plugin is in plugins.enabled and toolset is in platform_toolsets lists."""
    plugins = config.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        plugins = {}
        config["plugins"] = plugins

    enabled = plugins.get("enabled")
    if not isinstance(enabled, list):
        enabled = []
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

    platform_toolsets = config.get("platform_toolsets")
    if isinstance(platform_toolsets, dict):
        for _platform, tools in platform_toolsets.items():
            if isinstance(tools, list) and toolset not in tools:
                tools.append(toolset)

    # Also union into top-level toolsets if present
    toolsets = config.get("toolsets")
    if isinstance(toolsets, list) and toolset not in toolsets:
        toolsets.append(toolset)

    return config


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge config.patch.yaml into config.yaml"
    )
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--patch", required=True, help="Path to config.patch.yaml")
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Write merged result back to --config",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup before inplace write",
    )
    parser.add_argument(
        "--enable-plugin",
        default="",
        help="Also ensure this plugin name is in plugins.enabled",
    )
    parser.add_argument(
        "--enable-toolset",
        default="finance-bi",
        help="Toolset to append when --enable-plugin is set",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    patch_path = Path(args.patch)

    try:
        if not patch_path.is_file():
            print(f"SKIP: patch not found: {patch_path}")
            return 0
        if not config_path.is_file():
            print(f"ERROR: config not found: {config_path}", file=sys.stderr)
            return 1

        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        patch = yaml.safe_load(patch_path.read_text(encoding="utf-8")) or {}
        if not isinstance(config, dict) or not isinstance(patch, dict):
            print("ERROR: config/patch must be mapping", file=sys.stderr)
            return 1

        if args.inplace and not args.no_backup:
            backup_config(config_path)

        merged = deep_merge(config, patch)
        if args.enable_plugin:
            ensure_plugin_enabled(merged, args.enable_plugin, args.enable_toolset)

        text = yaml.safe_dump(merged, allow_unicode=True, sort_keys=False)
        if args.inplace:
            _atomic_write(config_path, text)
            print(f"Merged {patch_path} -> {config_path}")
        else:
            sys.stdout.write(text)
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
