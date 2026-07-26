#!/usr/bin/env python3
"""MCP connection test: initialize + ping (no login)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from sqlbot_adapter.client.mcp_client import SQLBotMCPClient
from sqlbot_adapter.config import load_config
from sqlbot_adapter.errors import SqlbotAdapterError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-tools", action="store_true")
    args = parser.parse_args()
    cfg = load_config()
    if not cfg.mcp_url:
        print("FAIL: SQLBOT_MCP_URL missing")
        return 1
    client = SQLBotMCPClient(cfg)
    try:
        client.initialize_and_ping_sync()
        print("OK: MCP initialize/ping")
    except SqlbotAdapterError as exc:
        print(f"FAIL: {exc.code.value}: {exc.message}")
        return 1
    if args.list_tools:
        names = client.list_tools_names_sync()
        if names:
            print("tools:", ", ".join(names))
        else:
            print("WARN: tools/list empty or incompatible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
