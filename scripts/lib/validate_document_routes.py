#!/usr/bin/env python3
"""Validate and optionally fix document routing under /data/hermes."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_DIRS = [
    "workspace/materials",
    "workspace/references",
    "workspace/drafts",
    "workspace/reports",
    "workspace/exports",
    "workspace/artifacts",
    "workspace/scripts",
    "workspace/runtime",
    "workspace/tmp",
    "obsidian-vault/00-Inbox",
    "obsidian-vault/10-Articles",
    "obsidian-vault/20-Research",
    "obsidian-vault/30-Templates",
    "obsidian-vault/40-Skills",
    "obsidian-vault/50-Memory",
    "obsidian-vault/60-Reports",
    "obsidian-vault/70-Brain",
    "obsidian-vault/80-Product-Spec",
    "obsidian-vault/90-Archive",
    "skills",
    "skill-inbox",
    "policies",
]

OBSIDIAN_FORBIDDEN = {
    ".py", ".sh", ".js", ".ts", ".mjs", ".cjs", ".ps1",
    ".exe", ".bin", ".zip", ".tar", ".gz",
    ".docx", ".pdf", ".xlsx", ".pptx",
    ".tmp", ".cache", ".log",
}

SCRIPT_EXTENSIONS = {".py", ".sh", ".js", ".ts", ".mjs", ".cjs", ".ps1"}
EXPORT_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".pptx"}


def iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def check_directories(data_dir: Path) -> list[str]:
    issues: list[str] = []
    for rel in REQUIRED_DIRS:
        path = data_dir / rel
        if not path.is_dir():
            issues.append(f"MISSING_DIR: {path}")
    return issues


def check_obsidian_forbidden(data_dir: Path) -> list[tuple[Path, str]]:
    vault = data_dir / "obsidian-vault"
    violations: list[tuple[Path, str]] = []
    for f in iter_files(vault):
        ext = f.suffix.lower()
        if ext in OBSIDIAN_FORBIDDEN:
            violations.append((f, f"FORBIDDEN_IN_OBSIDIAN: {ext}"))
    return violations


def check_misplaced_scripts(data_dir: Path) -> list[tuple[Path, Path]]:
    """Scripts outside workspace/scripts (excluding skills/)."""
    misplaced: list[tuple[Path, Path]] = []
    scripts_dir = data_dir / "workspace" / "scripts"
    for f in iter_files(data_dir):
        if f.suffix.lower() not in SCRIPT_EXTENSIONS:
            continue
        rel = f.relative_to(data_dir)
        parts = rel.parts
        if parts[0] == "skills":
            continue
        if parts[0] == "workspace" and len(parts) > 1 and parts[1] == "scripts":
            continue
        if parts[0] == "obsidian-vault":
            target = scripts_dir / f.name
            misplaced.append((f, target))
    return misplaced


def check_misplaced_exports(data_dir: Path) -> list[tuple[Path, Path]]:
    """Export files outside workspace/exports."""
    misplaced: list[tuple[Path, Path]] = []
    exports_dir = data_dir / "workspace" / "exports"
    for f in iter_files(data_dir):
        if f.suffix.lower() not in EXPORT_EXTENSIONS:
            continue
        rel = f.relative_to(data_dir)
        parts = rel.parts
        if parts[0] == "workspace" and len(parts) > 1 and parts[1] == "exports":
            continue
        if parts[0] == "obsidian-vault":
            target = exports_dir / f.name
            misplaced.append((f, target))
    return misplaced


def check_skills_structure(data_dir: Path) -> list[str]:
    issues: list[str] = []
    skills = data_dir / "skills"
    if not skills.is_dir():
        return issues
    for d in skills.rglob("*"):
        if not d.is_dir():
            continue
        if d.name.startswith("."):
            continue
        children = list(d.iterdir())
        has_skill_md = (d / "SKILL.md").is_file()
        has_subdirs = any(c.is_dir() for c in children)
        if has_subdirs and not has_skill_md:
            rel = d.relative_to(skills)
            if rel != Path("."):
                sub_has_skill = any((d / c / "SKILL.md").is_file() for c in children if c.is_dir())
                if not sub_has_skill and len(list(d.glob("SKILL.md"))) == 0:
                    if not any(c.is_dir() for c in children):
                        pass
    for skill_md in skills.rglob("SKILL.md"):
        parent = skill_md.parent
        if not (parent / "SKILL.md").is_file():
            issues.append(f"INVALID_SKILL: missing SKILL.md parent at {parent}")
    return issues


def check_manifests(data_dir: Path) -> list[str]:
    issues: list[str] = []
    artifacts = data_dir / "workspace" / "artifacts"
    for mf in iter_files(artifacts):
        if not mf.name.endswith(".manifest.json"):
            continue
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            issues.append(f"INVALID_MANIFEST: {mf} ({e})")
            continue
        for field in ("task", "profile", "created_at", "files"):
            if field not in data:
                issues.append(f"INVALID_MANIFEST: {mf} missing field '{field}'")
    return issues


def check_config_workspace_mcp(data_dir: Path) -> list[str]:
    issues: list[str] = []
    config = data_dir / "config.yaml"
    if not config.is_file():
        issues.append(f"MISSING_CONFIG: {config}")
        return issues
    text = config.read_text(encoding="utf-8")
    if "workspace:" not in text or "mcp_servers" not in text:
        issues.append("CONFIG_MISSING_WORKSPACE_MCP: config.yaml lacks workspace MCP")
    return issues


def check_soul_routing_rules(data_dir: Path) -> list[str]:
    issues: list[str] = []
    soul = data_dir / "SOUL.md"
    if not soul.is_file():
        issues.append(f"MISSING_SOUL: {soul}")
        return issues
    text = soul.read_text(encoding="utf-8")
    if "Document Routing" not in text and "document routing" not in text.lower():
        if "workspace/exports" not in text and "workspace/materials" not in text:
            issues.append("SOUL_MISSING_ROUTING: SOUL.md lacks document routing rules")
    return issues


def unique_target(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    n = 1
    while True:
        candidate = target.parent / f"{stem}-{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def write_migration_index(obsidian_file: Path, new_path: Path, backup_dir: Path) -> None:
    index = obsidian_file.with_suffix(obsidian_file.suffix + ".migrated.md")
    if index.exists():
        return
    content = f"""---
migrated_from: {obsidian_file}
migrated_to: {new_path}
migrated_at: {datetime.now(timezone.utc).isoformat()}
---

此文件已从 Obsidian 迁移。请使用新路径访问原文件。
"""
    index.write_text(content, encoding="utf-8")


def apply_fixes(
    data_dir: Path,
    obsidian_violations: list[tuple[Path, str]],
    script_moves: list[tuple[Path, Path]],
    export_moves: list[tuple[Path, Path]],
) -> list[str]:
    actions: list[str] = []
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = data_dir / "backups" / f"document-routing-fix-{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for src, dst in script_moves + export_moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        final_dst = unique_target(dst)
        shutil.copy2(src, backup_dir / src.name)
        shutil.move(str(src), str(final_dst))
        actions.append(f"MOVED: {src} -> {final_dst}")
        if "obsidian-vault" in str(src):
            write_migration_index(src, final_dst, backup_dir)

    report = {
        "fixed_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_dir),
        "actions": actions,
        "backup_dir": str(backup_dir),
    }
    report_path = backup_dir / "migration-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    actions.append(f"REPORT: {report_path}")
    return actions


def validate(data_dir: Path, fix: bool = False) -> int:
    data_dir = data_dir.resolve()
    if not data_dir.is_dir():
        print(f"ERROR: not a directory: {data_dir}", file=sys.stderr)
        return 2

    all_issues: list[str] = []
    all_issues.extend(check_directories(data_dir))
    obsidian_violations = check_obsidian_forbidden(data_dir)
    for path, msg in obsidian_violations:
        all_issues.append(f"{msg}: {path}")

    script_moves = check_misplaced_scripts(data_dir)
    for src, dst in script_moves:
        all_issues.append(f"MISPLACED_SCRIPT: {src} (expected under workspace/scripts)")

    export_moves = check_misplaced_exports(data_dir)
    for src, dst in export_moves:
        all_issues.append(f"MISPLACED_EXPORT: {src} (expected under workspace/exports)")

    all_issues.extend(check_skills_structure(data_dir))
    all_issues.extend(check_manifests(data_dir))
    all_issues.extend(check_config_workspace_mcp(data_dir))
    all_issues.extend(check_soul_routing_rules(data_dir))

    print(f"=== Document routing check: {data_dir} ===")
    if not all_issues:
        print("OK: no violations")
        return 0

    for issue in all_issues:
        print(issue)

    if fix and (obsidian_violations or script_moves or export_moves):
        print("\n--- Applying fixes ---")
        obs_script = [(p, d) for p, d in script_moves if "obsidian-vault" in str(p)]
        obs_export = [(p, d) for p, d in export_moves if "obsidian-vault" in str(p)]
        actions = apply_fixes(data_dir, obsidian_violations, obs_script, obs_export)
        for a in actions:
            print(a)
        return 1

    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate document routing for a Hermes instance")
    parser.add_argument("data_dir", type=Path, help="Path to instance data/hermes directory")
    parser.add_argument("--fix", action="store_true", help="Migrate obvious misplacements from obsidian-vault")
    args = parser.parse_args()
    return validate(args.data_dir, fix=args.fix)


if __name__ == "__main__":
    raise SystemExit(main())
