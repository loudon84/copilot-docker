#!/usr/bin/env python3
"""Parse and validate Hermes profile-team manifests (PRD v1.8)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print(
        "ERROR: PyYAML 未安装。请执行: sudo apt-get install -y python3-yaml",
        file=sys.stderr,
    )
    raise SystemExit(1)

PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
ALLOWED_KIND = "hermes-profile-team"
ALLOWED_VERSION = 1


class ManifestError(Exception):
    """Structured validation failure."""

    def __init__(self, message: str, field: str = "") -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}" if field else message)


def _require_dict(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        raise ManifestError("must be a mapping", field)
    return value


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError("must be a non-empty string", field)
    return value.strip()


def _require_list(value: Any, field: str) -> list:
    if not isinstance(value, list):
        raise ManifestError("must be a list", field)
    return value


def _is_safe_relative(path: str) -> bool:
    p = Path(path)
    if p.is_absolute():
        return False
    parts = p.parts
    return ".." not in parts and not any(part.startswith("/") for part in parts)


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise ManifestError(f"file not found: {path}", "team.yaml")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ManifestError("root must be a YAML mapping", "team.yaml")
    return loaded


def validate_manifest(
    data: dict,
    *,
    template_root: Path | None = None,
    hermes_home: Path | None = None,
) -> dict:
    """Validate and return a normalized copy of the manifest."""
    kind = data.get("kind")
    if kind != ALLOWED_KIND:
        raise ManifestError(f"must be '{ALLOWED_KIND}', got {kind!r}", "kind")

    version = data.get("version")
    if version != ALLOWED_VERSION:
        raise ManifestError(f"must be {ALLOWED_VERSION}, got {version!r}", "version")

    team_id = _require_str(data.get("id"), "id")
    name = _require_str(data.get("name"), "name")

    root = _require_dict(data.get("root"), "root")
    root_profile = _require_str(root.get("profile"), "root.profile")
    if root_profile != "default":
        raise ManifestError("must be 'default'", "root.profile")
    root_template = _require_str(root.get("template"), "root.template")
    root_role = _require_str(root.get("role", "chief-of-staff"), "root.role")
    root_orchestrator = bool(root.get("orchestrator", True))

    if template_root is not None:
        root_dir = template_root / root_template
        if not root_dir.is_dir():
            raise ManifestError(f"directory not found: {root_dir}", "root.template")

    members_raw = _require_list(data.get("members"), "members")
    members: list[dict] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(members_raw):
        field = f"members[{i}]"
        member = _require_dict(item, field)
        mid = _require_str(member.get("id"), f"{field}.id")
        if not PROFILE_ID_RE.match(mid):
            raise ManifestError(
                "must match ^[a-z][a-z0-9-]{0,62}$ (Hermes Profile ID)",
                f"{field}.id",
            )
        if mid in seen_ids:
            raise ManifestError(f"duplicate member id '{mid}'", f"{field}.id")
        seen_ids.add(mid)
        template = _require_str(member.get("template"), f"{field}.template")
        role = _require_str(member.get("role", "permanent-advisor"), f"{field}.role")
        if template_root is not None:
            member_dir = template_root / template
            if not member_dir.is_dir():
                raise ManifestError(
                    f"directory not found: {member_dir}",
                    f"{field}.template",
                )
        members.append({"id": mid, "template": template, "role": role})

    orchestration = _require_dict(data.get("orchestration"), "orchestration")
    engine = _require_str(orchestration.get("engine"), "orchestration.engine")
    if engine != "kanban":
        raise ManifestError("must be 'kanban'", "orchestration.engine")
    board = _require_str(orchestration.get("board"), "orchestration.board")
    dispatch_in_gateway = bool(orchestration.get("dispatch_in_gateway", True))
    dispatch_interval = orchestration.get("dispatch_interval_seconds", 30)
    if not isinstance(dispatch_interval, int) or dispatch_interval < 1:
        raise ManifestError(
            "must be a positive integer",
            "orchestration.dispatch_interval_seconds",
        )

    dynamic = _require_dict(data.get("dynamic_experts", {}), "dynamic_experts")
    shared = _require_dict(data.get("shared_context"), "shared_context")
    host_rel = _require_str(
        shared.get("host_relative_path"), "shared_context.host_relative_path"
    )
    if not _is_safe_relative(host_rel):
        raise ManifestError(
            "must be a relative path without '..'",
            "shared_context.host_relative_path",
        )
    container_path = _require_str(
        shared.get("container_path"), "shared_context.container_path"
    )
    if not container_path.startswith("/data/hermes/"):
        raise ManifestError(
            "must start with /data/hermes/",
            "shared_context.container_path",
        )
    if hermes_home is not None:
        resolved_shared = (hermes_home / host_rel).resolve()
        hermes_resolved = hermes_home.resolve()
        try:
            resolved_shared.relative_to(hermes_resolved)
        except ValueError as exc:
            raise ManifestError(
                "shared context path escapes Hermes Home",
                "shared_context.host_relative_path",
            ) from exc

    mode = _require_str(shared.get("mode", "read-only"), "shared_context.mode")
    memory = _require_dict(data.get("memory", {}), "memory")
    governance = _require_dict(data.get("governance", {}), "governance")

    return {
        "kind": ALLOWED_KIND,
        "version": ALLOWED_VERSION,
        "id": team_id,
        "name": name,
        "root": {
            "profile": "default",
            "template": root_template,
            "role": root_role,
            "orchestrator": root_orchestrator,
        },
        "members": members,
        "orchestration": {
            "engine": "kanban",
            "board": board,
            "dispatch_in_gateway": dispatch_in_gateway,
            "dispatch_interval_seconds": dispatch_interval,
        },
        "dynamic_experts": dynamic,
        "shared_context": {
            "host_relative_path": host_rel,
            "container_path": container_path,
            "mode": mode,
        },
        "memory": memory,
        "governance": governance,
    }


def resolve_manifest(
    data: dict,
    *,
    instance: str,
    template_root: Path | None = None,
    hermes_home: Path | None = None,
) -> dict:
    validated = validate_manifest(
        data, template_root=template_root, hermes_home=hermes_home
    )
    bank_pattern = validated.get("memory", {}).get(
        "hindsight_bank_pattern", "hermes-__INSTANCE__-__PROFILE__"
    )
    if not isinstance(bank_pattern, str):
        bank_pattern = "hermes-__INSTANCE__-__PROFILE__"

    def bank_for(profile_id: str) -> str:
        return bank_pattern.replace("__INSTANCE__", instance).replace(
            "__PROFILE__", profile_id
        )

    resolved = dict(validated)
    resolved["instance"] = instance
    resolved["banks"] = {
        "default": bank_for("default"),
        **{m["id"]: bank_for(m["id"]) for m in validated["members"]},
    }
    resolved["profile_homes"] = {
        "default": "/data/hermes",
        **{
            m["id"]: f"/data/hermes/profiles/{m['id']}"
            for m in validated["members"]
        },
    }
    return resolved


def emit_json(payload: Any, *, ok: bool = True, error: str | None = None) -> None:
    out: dict[str, Any] = {"ok": ok}
    if error:
        out["error"] = error
    if isinstance(payload, dict):
        out.update(payload)
    else:
        out["data"] = payload
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.team_yaml)
    template_root = Path(args.template_root) if args.template_root else path.parent
    try:
        data = load_manifest(path)
        validated = validate_manifest(data, template_root=template_root)
        emit_json({"manifest": validated})
        return 0
    except ManifestError as exc:
        emit_json({}, ok=False, error=str(exc))
        return 1


def cmd_resolve(args: argparse.Namespace) -> int:
    path = Path(args.team_yaml)
    template_root = Path(args.template_root) if args.template_root else path.parent
    hermes_home = Path(args.hermes_home) if args.hermes_home else None
    try:
        data = load_manifest(path)
        resolved = resolve_manifest(
            data,
            instance=args.instance,
            template_root=template_root,
            hermes_home=hermes_home,
        )
        emit_json({"manifest": resolved})
        return 0
    except ManifestError as exc:
        emit_json({}, ok=False, error=str(exc))
        return 1


def cmd_list_members(args: argparse.Namespace) -> int:
    path = Path(args.team_yaml)
    template_root = Path(args.template_root) if args.template_root else path.parent
    try:
        data = load_manifest(path)
        validated = validate_manifest(data, template_root=template_root)
        members = [
            {"id": "default", "role": validated["root"]["role"], "kind": "root"},
            *[
                {"id": m["id"], "role": m["role"], "kind": "member"}
                for m in validated["members"]
            ],
        ]
        emit_json({"members": members})
        return 0
    except ManifestError as exc:
        emit_json({}, ok=False, error=str(exc))
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes team manifest tools")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="Validate team.yaml")
    p_val.add_argument("team_yaml")
    p_val.add_argument("--template-root", default="")
    p_val.set_defaults(func=cmd_validate)

    p_res = sub.add_parser("resolve", help="Resolve runtime team manifest")
    p_res.add_argument("team_yaml")
    p_res.add_argument("--instance", required=True)
    p_res.add_argument("--template-root", default="")
    p_res.add_argument("--hermes-home", default="")
    p_res.set_defaults(func=cmd_resolve)

    p_list = sub.add_parser("list-members", help="List root + member profiles")
    p_list.add_argument("team_yaml")
    p_list.add_argument("--template-root", default="")
    p_list.set_defaults(func=cmd_list_members)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
