#!/usr/bin/env python3
"""Check expert SOUL/AGENT(S)/SKILL docs for forbidden control chars; optionally require CJK body."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DOC_NAMES = frozenset({"SOUL.md", "AGENT.md", "AGENTS.md", "SKILL.md"})
SKIP_ZH_TEMPLATES = frozenset({"base", "default"})
ALLOWED_CTRL = frozenset({9, 10, 13})  # tab, LF, CR
ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff", "\u00ad")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n?", re.DOTALL)


def iter_doc_files(template_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in template_dir.rglob("*")
        if path.is_file() and path.name in DOC_NAMES
    )


def find_control_issues(data: bytes) -> list[str]:
    issues: list[str] = []
    for i, byte in enumerate(data):
        if byte < 32 and byte not in ALLOWED_CTRL:
            ctx = data[max(0, i - 12) : i + 16]
            issues.append(f"offset {i}: U+{byte:04X} near {ctx!r}")
            if len(issues) >= 8:
                break
    return issues


def find_zero_width_issues(text: str) -> list[str]:
    return [
        f"contains zero-width/BOM char U+{ord(ch):04X}"
        for ch in ZERO_WIDTH
        if ch in text
    ]


def body_for_cjk_check(text: str) -> str:
    body = FRONTMATTER_RE.sub("", text, count=1)
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    return body.strip()


def check_file(path: Path) -> tuple[list[str], list[str]]:
    """Return (hard_failures, soft_warnings)."""
    data = path.read_bytes()
    hard = find_control_issues(data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"not valid UTF-8: {exc}"], []
    hard.extend(find_zero_width_issues(text))
    soft: list[str] = []
    body = body_for_cjk_check(text)
    if body and not CJK_RE.search(body):
        soft.append(
            "body has no CJK; descriptive text must be Simplified Chinese "
            "(identifiers like finance_bi_ask may stay English)"
        )
    return hard, soft


def main() -> int:
    # Avoid mojibake on Windows consoles when printing Chinese hints.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template_dir", type=Path, help="Path to expert-templates/<id>")
    parser.add_argument(
        "--require-zh",
        action="store_true",
        help="Fail when descriptive body has no CJK (default: warn only)",
    )
    args = parser.parse_args()
    template_dir = args.template_dir.resolve()
    if not template_dir.is_dir():
        print(f"FAIL: template dir not found: {template_dir}", file=sys.stderr)
        return 1

    template_id = template_dir.name
    check_zh = template_id not in SKIP_ZH_TEMPLATES
    files = iter_doc_files(template_dir)
    if not files:
        print(f"FAIL: no SOUL.md / AGENT.md / AGENTS.md / SKILL.md under {template_dir}")
        return 1

    failed = False
    for path in files:
        rel = path.relative_to(template_dir)
        hard, soft = check_file(path)
        if not check_zh:
            soft = []
        if hard:
            failed = True
            print(f"FAIL: {rel}")
            for issue in hard:
                print(f"  - {issue}")
            continue
        if soft and args.require_zh:
            failed = True
            print(f"FAIL: {rel}")
            for issue in soft:
                print(f"  - {issue}")
            continue
        if soft:
            print(f"WARN: {rel}")
            for issue in soft:
                print(f"  - {issue}")
        else:
            print(f"PASS: {rel}")

    if failed:
        print(
            "HINT: forbid Form Feed (U+000C) and other control/zero-width chars; "
            "descriptive text must be Simplified Chinese; tool ids may stay English "
            "(e.g. finance_bi_ask)."
        )
        return 1
    print(f"OK: expert doc chars for {template_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
