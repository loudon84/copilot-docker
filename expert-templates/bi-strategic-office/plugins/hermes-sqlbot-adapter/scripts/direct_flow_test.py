#!/usr/bin/env python3
"""Formal direct flow test — uses SQLBotMCPClient only (no duplicated MCP code)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from sqlbot_adapter.client.mcp_client import SQLBotMCPClient
from sqlbot_adapter.config import load_config
from sqlbot_adapter.errors import SqlbotAdapterError


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLBot direct flow via formal client")
    parser.add_argument("--question", default="查询应收交易编号 101IN26070199 的交易明细")
    parser.add_argument("--skip-question", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.is_configured():
        print("FAIL: missing config:", ", ".join(cfg.missing_required()))
        return 1

    client = SQLBotMCPClient(cfg)
    try:
        client.initialize_and_ping_sync()
        print("L1 OK: initialize/ping")
        started = client.start()
        _tok = str(started.get("access_token") or "")
        print("L2 OK: mcp_start chat_id present=", bool(started.get("chat_id")))
        # Do not print token
        ws = client.list_workspaces(access_token=_tok)
        print("L3 OK: workspaces count=", len(ws))
        ds = client.list_datasources(access_token=_tok)
        print("L4 OK: datasources count=", len(ds))
        if args.skip_question:
            return 0
        result = client.question(
            args.question,
            chat_id=str(started.get("chat_id") or ""),
            access_token=_tok,
        )
        if result.error:
            print(
                "L5 FAIL execution:",
                result.error.code.value,
                result.error.message,
            )
            if result.sql:
                print("sql_present=yes")
            return 2
        out = {
            "sql_present": bool(result.sql),
            "row_count": len(result.rows or []),
            "title": result.title,
        }
        print("L5 OK:", json.dumps(out, ensure_ascii=False))
        return 0
    except SqlbotAdapterError as exc:
        print(f"FAIL: {exc.code.value}: {exc.message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
