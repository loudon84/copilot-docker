#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = "1.0"

ROOT_FILES = (
    "config.yaml",
    "SOUL.md",
    "team.yaml",
    "profile.yaml",
    "config.patch.yaml",
)
ROOT_DIRS = (
    "skills",
    "tools",
    "plugins",
    "mcp",
    "policies",
    "skill-bundles",
    "cron",
    "agent-hooks",
    "team-shared",
)
SPECIAL_FILES = (
    "workspace/AGENTS.md",
)

PROFILE_FILES = ROOT_FILES
PROFILE_DIRS = (
    "skills",
    "tools",
    "plugins",
    "mcp",
    "policies",
    "skill-bundles",
    "cron",
    "agent-hooks",
    "team-shared",
)
PROFILE_SPECIAL_FILES = SPECIAL_FILES

FORBIDDEN_PARTS = {
    ".env",
    "sessions",
    "memories",
    "logs",
    "webui",
    "checkpoints",
    "hindsight",
    "backups",
    ".backup",
    "attachments",
    "skill-inbox",
    "evolution",
    "obsidian-vault",
    "finance-bi",
    "sqlbot-adapter",
}

# The workspace is runtime/user data except for AGENTS.md, which is part of
# the profile's behavioral capability contract.
FORBIDDEN_WORKSPACE_CHILDREN = True


def fail(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def validate_safe_name(name: str) -> None:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        fail(f"unsafe instance/profile name: {name!r}")


def safe_rel(rel: str) -> PurePosixPath:
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts:
        fail(f"unsafe relative path: {rel}")
    return p


def assert_no_symlink_escape(path: Path, root: Path) -> None:
    # Reject symlinks entirely in the capability payload. They are unnecessary
    # for this clone flow and complicate archive traversal safety.
    for current_root, dirs, files in os.walk(path, followlinks=False):
        current = Path(current_root)
        for name in list(dirs) + list(files):
            candidate = current / name
            if candidate.is_symlink():
                fail(f"symlink not allowed in clone capability payload: {candidate.relative_to(root)}")


def add_path(tf: tarfile.TarFile, source_root: Path, rel: str, included: list[str]) -> None:
    rel_path = safe_rel(rel)
    src = source_root / Path(*rel_path.parts)
    if not src.exists():
        return
    if src.is_symlink():
        fail(f"symlink not allowed: {rel}")
    if src.is_dir():
        assert_no_symlink_escape(src, source_root)
    tf.add(src, arcname=f"payload/{rel_path.as_posix()}", recursive=True)
    included.append(rel_path.as_posix())


def discover_profiles(source_root: Path) -> list[str]:
    profiles_root = source_root / "profiles"
    if not profiles_root.is_dir():
        return []
    result: list[str] = []
    for child in sorted(profiles_root.iterdir(), key=lambda p: p.name):
        if child.is_dir() and not child.is_symlink():
            validate_safe_name(child.name)
            result.append(child.name)
    return result


# @lat: [[runtime#Runtime Deployment#Instance Capability Clone]]
def export_bundle(source_root: Path, source_instance: str, output: Path) -> None:
    source_root = source_root.resolve()
    validate_safe_name(source_instance)
    if not source_root.is_dir():
        fail(f"source root not found: {source_root}")

    output.parent.mkdir(parents=True, exist_ok=True)
    profiles = discover_profiles(source_root)
    included: list[str] = []

    with tempfile.TemporaryDirectory(prefix="hermes-capability-manifest-") as tmp:
        manifest_path = Path(tmp) / "manifest.json"
        # First build payload into tar, then append manifest.
        with tarfile.open(output, "w:gz") as tf:
            for rel in ROOT_FILES:
                add_path(tf, source_root, rel, included)
            for rel in ROOT_DIRS:
                add_path(tf, source_root, rel, included)
            for rel in SPECIAL_FILES:
                add_path(tf, source_root, rel, included)

            for profile in profiles:
                prefix = f"profiles/{profile}"
                for rel in PROFILE_FILES:
                    add_path(tf, source_root, f"{prefix}/{rel}", included)
                for rel in PROFILE_DIRS:
                    add_path(tf, source_root, f"{prefix}/{rel}", included)
                for rel in PROFILE_SPECIAL_FILES:
                    add_path(tf, source_root, f"{prefix}/{rel}", included)

            manifest = {
                "schema_version": SCHEMA_VERSION,
                "kind": "hermes-instance-capability-clone",
                "source_instance": source_instance,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "profiles": profiles,
                "included": sorted(set(included)),
                "excluded": [
                    ".env",
                    "sessions/**",
                    "memories/**",
                    "logs/**",
                    "webui/**",
                    "workspace/** except workspace/AGENTS.md",
                    "obsidian-vault/**",
                    "hindsight/**",
                    "backups/**",
                    ".backup/**",
                    "attachments/**",
                    "checkpoints/**",
                    "runtime state databases",
                ],
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tf.add(manifest_path, arcname="manifest.json")

    inspect_bundle(output, quiet=True)


def load_manifest(tf: tarfile.TarFile) -> dict:
    member = tf.getmember("manifest.json")
    fh = tf.extractfile(member)
    if fh is None:
        fail("manifest.json unreadable")
    manifest = json.loads(fh.read().decode("utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        fail(f"unsupported clone schema: {manifest.get('schema_version')}")
    if manifest.get("kind") != "hermes-instance-capability-clone":
        fail("archive is not a Hermes capability clone bundle")
    return manifest


# @lat: [[runtime#Runtime Deployment#Instance Capability Clone#Capability Bundle Allowlist]]
def validate_member(member: tarfile.TarInfo) -> None:
    p = PurePosixPath(member.name)
    if p.is_absolute() or ".." in p.parts:
        fail(f"unsafe archive member: {member.name}")
    if member.issym() or member.islnk():
        fail(f"links are not allowed in clone archive: {member.name}")
    if member.name == "manifest.json":
        return
    if not p.parts or p.parts[0] != "payload":
        fail(f"unexpected archive member outside payload/: {member.name}")

    rel_parts = p.parts[1:]

    # Enforce forbidden runtime/history paths only at a Hermes profile root.
    # A plugin may legitimately contain a nested directory named "logs" or "sessions".
    if rel_parts:
        if rel_parts[0] in FORBIDDEN_PARTS:
            fail(f"forbidden root runtime/history path found in bundle: {member.name}")

        if rel_parts[0] == "workspace":
            tail = rel_parts[1:]
            if tail and tuple(tail) != ("AGENTS.md",):
                fail(f"workspace runtime data is forbidden in clone bundle: {member.name}")

        if rel_parts[0] == "profiles" and len(rel_parts) >= 3:
            profile_child = rel_parts[2]
            if profile_child in FORBIDDEN_PARTS:
                fail(f"forbidden profile runtime/history path found in bundle: {member.name}")
            if profile_child == "workspace":
                tail = rel_parts[3:]
                if tail and tuple(tail) != ("AGENTS.md",):
                    fail(f"profile workspace runtime data is forbidden in clone bundle: {member.name}")


def inspect_bundle(archive: Path, quiet: bool = False) -> dict:
    with tarfile.open(archive, "r:gz") as tf:
        manifest = load_manifest(tf)
        for member in tf.getmembers():
            validate_member(member)
    if not quiet:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def remove_capability_paths(target_root: Path, manifest: dict) -> None:
    for rel in ROOT_FILES:
        p = target_root / rel
        if p.is_file() or p.is_symlink():
            p.unlink()
    for rel in ROOT_DIRS:
        p = target_root / rel
        if p.exists():
            shutil.rmtree(p)
    for rel in SPECIAL_FILES:
        p = target_root / rel
        if p.is_file() or p.is_symlink():
            p.unlink()

    source_profiles = set(manifest.get("profiles") or [])
    profiles_root = target_root / "profiles"
    profiles_root.mkdir(parents=True, exist_ok=True)

    # Target is guaranteed new by clone-instance.sh, so target-only baseline
    # profiles can be removed to make the capability topology exactly match A.
    for child in list(profiles_root.iterdir()):
        if child.is_dir() and child.name not in source_profiles:
            shutil.rmtree(child)

    for profile in source_profiles:
        validate_safe_name(profile)
        profile_root = profiles_root / profile
        profile_root.mkdir(parents=True, exist_ok=True)
        for rel in PROFILE_FILES:
            p = profile_root / rel
            if p.is_file() or p.is_symlink():
                p.unlink()
        for rel in PROFILE_DIRS:
            p = profile_root / rel
            if p.exists():
                shutil.rmtree(p)
        for rel in PROFILE_SPECIAL_FILES:
            p = profile_root / rel
            if p.is_file() or p.is_symlink():
                p.unlink()


def safe_extract(tf: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in tf.getmembers():
        validate_member(member)
        if member.name == "manifest.json":
            continue
        p = PurePosixPath(member.name)
        rel = Path(*p.parts[1:])
        final = (destination / rel).resolve()
        try:
            final.relative_to(destination)
        except ValueError:
            fail(f"archive path escapes target: {member.name}")

    # Python 3.12 tarfile supports filter="data", but validate_member above is
    # kept as the primary contract and works consistently across supported hosts.
    for member in tf.getmembers():
        if member.name == "manifest.json":
            continue
        p = PurePosixPath(member.name)
        rel = Path(*p.parts[1:])
        out = destination / rel

        if member.isdir():
            out.mkdir(parents=True, exist_ok=True)
            continue

        out.parent.mkdir(parents=True, exist_ok=True)
        src = tf.extractfile(member)
        if src is None:
            fail(f"unable to read archive member: {member.name}")
        with out.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        try:
            os.chmod(out, member.mode & 0o777)
        except OSError:
            pass


def apply_bundle(archive: Path, target_root: Path) -> None:
    target_root = target_root.resolve()
    if not target_root.is_dir():
        fail(f"target root not found: {target_root}")

    with tarfile.open(archive, "r:gz") as tf:
        manifest = load_manifest(tf)
        for member in tf.getmembers():
            validate_member(member)
        remove_capability_paths(target_root, manifest)
        safe_extract(tf, target_root)

    # Defensive proof: applying the clone must never create runtime history.
    forbidden_top = [
        target_root / "payload",
    ]
    for p in forbidden_top:
        if p.exists():
            fail(f"unexpected path after apply: {p}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes capability clone bundle helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_export = sub.add_parser("export")
    p_export.add_argument("--source-root", required=True, type=Path)
    p_export.add_argument("--source-instance", required=True)
    p_export.add_argument("--output", required=True, type=Path)

    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--archive", required=True, type=Path)

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--archive", required=True, type=Path)
    p_apply.add_argument("--target-root", required=True, type=Path)

    args = parser.parse_args()

    if args.cmd == "export":
        export_bundle(args.source_root, args.source_instance, args.output)
    elif args.cmd == "inspect":
        inspect_bundle(args.archive)
    elif args.cmd == "apply":
        apply_bundle(args.archive, args.target_root)


if __name__ == "__main__":
    main()
