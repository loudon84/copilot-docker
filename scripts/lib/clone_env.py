#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

# @lat: [[decisions#Design Decisions#Create-Only Instance Capability Clone]]
# These values define B's identity and MUST always remain unique to B.
HARD_PROTECTED = {
    "HERMES_PROFILE",
    "HERMES_WEBUI_PORT",
    "HERMES_GATEWAY_PORT",
    "HERMES_WEBUI_PASSWORD",
    "API_SERVER_KEY",
    "API_SERVER_MODEL_NAME",
    "HINDSIGHT_BANK_ID",
}

SECRET_RE = re.compile(
    r"(?:^|_)(?:API_?KEY|KEY|TOKEN|PASSWORD|PASS|SECRET|CREDENTIAL|PRIVATE_?KEY)(?:$|_)",
    re.IGNORECASE,
)


def parse_env(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value
    return lines, values


# @lat: [[runtime#Runtime Deployment#Instance Capability Clone#Target Env Identity Merge]]
def rewrite_target(
    target_lines: list[str],
    target_values: dict[str, str],
    source_values: dict[str, str],
    copy_secrets: bool,
) -> list[str]:
    merged = dict(target_values)

    # Copy runtime/build/capability configuration from A into B, but never
    # overwrite B identity. Secret-like values are opt-in.
    for key, value in source_values.items():
        if key in HARD_PROTECTED:
            continue
        if SECRET_RE.search(key) and not copy_secrets:
            continue
        merged[key] = value

    # Preserve target file order/comments, then append source-only keys.
    output: list[str] = []
    seen: set[str] = set()

    for line in target_lines:
        if "=" not in line or line.lstrip().startswith("#"):
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in merged:
            output.append(f"{key}={merged[key]}")
            seen.add(key)
        else:
            output.append(line)

    source_only = [k for k in merged if k not in seen]
    if source_only:
        output.append("")
        output.append("# Cloned non-instance runtime settings")
        for key in sorted(source_only):
            output.append(f"{key}={merged[key]}")

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge A runtime env into clean B env")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--copy-secrets", action="store_true")
    args = parser.parse_args()

    target_lines, target_values = parse_env(args.target)
    _, source_values = parse_env(args.source)

    result = rewrite_target(
        target_lines,
        target_values,
        source_values,
        args.copy_secrets,
    )
    args.target.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
