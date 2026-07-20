#!/usr/bin/env python3
"""Deep-merge expert config.patch.yaml into instance config.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required", file=sys.stderr)
    sys.exit(2)


PRESERVE_TOP_LEVEL = ("model", "providers")


def deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})
    for key, value in (patch or {}).items():
        if key in PRESERVE_TOP_LEVEL and key in out:
            # never overwrite user model/providers from patch
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        elif (
            key == "enabled"
            and isinstance(value, list)
            and isinstance(out.get(key), list)
        ):
            # Union plugins.enabled (and similar allow-lists) instead of replace
            merged = list(out[key])
            for item in value:
                if item not in merged:
                    merged.append(item)
            out[key] = merged
        else:
            out[key] = value
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge config.patch.yaml into config.yaml")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--patch", required=True, help="Path to config.patch.yaml")
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Write merged result back to --config",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    patch_path = Path(args.patch)
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

    merged = deep_merge(config, patch)
    text = yaml.safe_dump(merged, allow_unicode=True, sort_keys=False)
    if args.inplace:
        config_path.write_text(text, encoding="utf-8")
        print(f"Merged {patch_path} -> {config_path}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
