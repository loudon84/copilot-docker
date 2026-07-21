#!/usr/bin/env python3
"""Manage finance-bi/package-state.yaml for the expert package."""

from __future__ import annotations

import argparse
import hashlib
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

DEFAULT_STATE_REL = Path("finance-bi") / "package-state.yaml"


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


def compute_package_hash(package_root: Path) -> str:
    """Stable content hash over VERSION + expert.yaml + plugin.yaml + requirements."""
    parts: list[bytes] = []
    for rel in (
        "VERSION",
        "expert.yaml",
        "plugins/hermes-finance-bi-plugin/plugin.yaml",
        "plugins/hermes-finance-bi-plugin/requirements.txt",
    ):
        p = package_root / rel
        if p.is_file():
            parts.append(p.read_bytes())
    if not parts:
        return ""
    h = hashlib.sha256()
    for chunk in parts:
        h.update(chunk)
    return h.hexdigest()


def build_state(
    *,
    expert_id: str = "bi-strategic-office",
    expert_version: str = "1.10.0",
    plugin_id: str = "hermes-finance-bi-plugin",
    plugin_version: str | None = None,
    semantic_catalog_version: str | None = None,
    package_source: str = "expert-templates/bi-strategic-office",
    package_hash: str = "",
    installed_at: str | None = None,
) -> dict[str, Any]:
    version = expert_version
    return {
        "expert_id": expert_id,
        "expert_version": version,
        "plugin": {
            "id": plugin_id,
            "version": plugin_version or version,
        },
        "semantic_catalog_version": semantic_catalog_version or version,
        "installed_at": installed_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "package_source": package_source,
        "package_hash": package_hash,
    }


def read_state(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return None
    return data


def write_state(path: Path, state: dict[str, Any]) -> None:
    # Never write secrets
    text = yaml.safe_dump(state, allow_unicode=True, sort_keys=False)
    if any(
        k in text.lower()
        for k in ("password", "secret", "api_key", "dsn=", "passwd")
    ):
        raise ValueError("refusing to write package-state containing secret-like keys")
    _atomic_write(path, text)


def write_success_state(
    data_dir: Path,
    package_root: Path,
    *,
    expert_version: str | None = None,
) -> Path:
    version_file = package_root / "VERSION"
    version = expert_version or (
        version_file.read_text(encoding="utf-8").strip()
        if version_file.is_file()
        else "1.10.0"
    )
    plugin_yaml = package_root / "plugins" / "hermes-finance-bi-plugin" / "plugin.yaml"
    plugin_version = version
    if plugin_yaml.is_file():
        pdata = yaml.safe_load(plugin_yaml.read_text(encoding="utf-8")) or {}
        if isinstance(pdata, dict) and pdata.get("version"):
            plugin_version = str(pdata["version"])

    state = build_state(
        expert_version=version,
        plugin_version=plugin_version,
        semantic_catalog_version=version,
        package_hash=compute_package_hash(package_root),
    )
    out = data_dir / DEFAULT_STATE_REL
    write_state(out, state)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Read/write package-state.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write", help="Write success package-state")
    p_write.add_argument("--data-dir", required=True)
    p_write.add_argument("--package-root", required=True)
    p_write.add_argument("--version", default="")

    p_read = sub.add_parser("read", help="Read package-state")
    p_read.add_argument("--data-dir", required=True)

    args = parser.parse_args()
    try:
        if args.cmd == "write":
            path = write_success_state(
                Path(args.data_dir),
                Path(args.package_root),
                expert_version=args.version or None,
            )
            print(f"Wrote {path}")
            return 0
        if args.cmd == "read":
            path = Path(args.data_dir) / DEFAULT_STATE_REL
            state = read_state(path)
            if state is None:
                print("NO_STATE")
                return 1
            print(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), end="")
            return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
