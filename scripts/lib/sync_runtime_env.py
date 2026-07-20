#!/usr/bin/env python3
"""Merge runtime keys from source into target .env (Hermes gateway reads HERMES_HOME/.env)."""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

SYNC_KEYS = (
    "HERMES_PROFILE",
    "HERMES_HOME",
    "HERMES_CONFIG_PATH",
    "API_SERVER_ENABLED",
    "API_SERVER_KEY",
    "API_SERVER_HOST",
    "API_SERVER_PORT",
    "API_SERVER_MODEL_NAME",
    "API_SERVER_CORS_ORIGINS",
    "GATEWAY_ALLOW_ALL_USERS",
    "HINDSIGHT_MODE",
    "HINDSIGHT_API_URL",
    "HINDSIGHT_BANK_ID",
    "GBRAIN_ENABLED",
    "GBRAIN_COMMAND",
    "GBRAIN_HOME",
    "GBRAIN_VAULT",
    "FINANCE_BI_DSN",
    "FINANCE_BI_DIALECT",
    "FINANCE_BI_CATALOG_PATH",
    "FINANCE_BI_POLICY_PATH",
    "FINANCE_BI_ALLOWED_SCHEMAS",
    "FINANCE_BI_ALLOWED_ENTITIES",
    "FINANCE_BI_DEFAULT_CURRENCY",
    "FINANCE_BI_TIMEZONE",
    "FINANCE_BI_QUERY_TIMEOUT_SECONDS",
    "FINANCE_BI_DEFAULT_LIMIT",
    "FINANCE_BI_HARD_LIMIT",
    "FINANCE_BI_STATE_DB",
    "FINANCE_BI_EXPORT_DIR",
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value
    return values


def merge_env_file(target: Path, updates: dict[str, str]) -> list[str]:
    lines = target.read_text(encoding="utf-8").splitlines() if target.is_file() else []
    seen: set[str] = set()
    out: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key, _, _ = line.partition("=")
            key = key.strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)

    for key in SYNC_KEYS:
        if key in updates and key not in seen:
            out.append(f"{key}={updates[key]}")

    target.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(out)
    if text and not text.endswith("\n"):
        text += "\n"
    target.write_text(text, encoding="utf-8")
    return sorted(k for k in updates if k in SYNC_KEYS)


def collect_updates(source_env: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if source_env is not None:
        values.update(parse_env_file(source_env))
    for key in SYNC_KEYS:
        if key in os.environ:
            values[key] = os.environ[key]
    return {k: values[k] for k in SYNC_KEYS if k in values and values[k] != ""}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Hermes runtime .env for gateway")
    parser.add_argument("--target", required=True, help="Target .env path (e.g. data/hermes/.env)")
    parser.add_argument(
        "--source",
        help="Source instances/<profile>/.env (host mode). Container mode uses process env.",
    )
    args = parser.parse_args()

    target = Path(args.target)
    source = Path(args.source) if args.source else None
    updates = collect_updates(source)
    if not updates:
        print(f"[sync-runtime-env] WARN: no runtime keys to sync -> {target}")
        return 0

    merged = merge_env_file(target, updates)
    print(f"[sync-runtime-env] synced {len(merged)} key(s) -> {target}")
    for key in merged:
        if key == "API_SERVER_KEY":
            print(f"[sync-runtime-env]   {key}=***")
        else:
            print(f"[sync-runtime-env]   {key}={updates[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
