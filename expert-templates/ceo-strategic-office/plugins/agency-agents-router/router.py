#!/usr/bin/env python3
"""Minimal Agency Agents Router — search / view / load prompt for delegate_task."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parent / "catalog.json"
PROMPTS = Path(__file__).resolve().parent / "prompts"


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def cmd_search(args: argparse.Namespace) -> int:
    q = (args.query or "").lower()
    hits = []
    for agent in load_catalog().get("agents", []):
        blob = " ".join(
            [
                agent.get("id", ""),
                agent.get("name", ""),
                agent.get("summary", ""),
                " ".join(agent.get("tags", [])),
            ]
        ).lower()
        if not q or q in blob:
            hits.append(agent)
    print(json.dumps({"ok": True, "agents": hits}, ensure_ascii=False, indent=2))
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    for agent in load_catalog().get("agents", []):
        if agent["id"] == args.agent_id:
            print(json.dumps({"ok": True, "agent": agent}, ensure_ascii=False, indent=2))
            return 0
    print(json.dumps({"ok": False, "error": f"unknown agent: {args.agent_id}"}))
    return 1


def cmd_load_prompt(args: argparse.Namespace) -> int:
    path = PROMPTS / f"{args.agent_id}.md"
    if not path.is_file():
        agent = None
        for a in load_catalog().get("agents", []):
            if a["id"] == args.agent_id:
                agent = a
                break
        if not agent:
            print(json.dumps({"ok": False, "error": f"unknown agent: {args.agent_id}"}))
            return 1
        prompt = (
            f"You are an ephemeral specialist: {agent['name']}.\n"
            f"{agent['summary']}\n"
            "Stay within the task boundary. Do not request credentials. "
            "Do not write permanent memory or team-shared files. "
            "Return a concise, evidence-labeled answer for the calling Profile."
        )
        print(
            json.dumps(
                {"ok": True, "agent_id": args.agent_id, "prompt": prompt},
                ensure_ascii=False,
            )
        )
        return 0
    print(
        json.dumps(
            {
                "ok": True,
                "agent_id": args.agent_id,
                "prompt": path.read_text(encoding="utf-8"),
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Agency Agents Router")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query", nargs="?", default="")
    s.set_defaults(func=cmd_search)
    v = sub.add_parser("view")
    v.add_argument("agent_id")
    v.set_defaults(func=cmd_view)
    l = sub.add_parser("load-prompt")
    l.add_argument("agent_id")
    l.set_defaults(func=cmd_load_prompt)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
