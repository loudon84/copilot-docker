#!/usr/bin/env python3
"""Portable integration test for team inject (does not require bash mapfile).

Mirrors the core inject-expert-team behavior using team_manifest + patch_config_runtime
so CI can verify staging/promote/idempotency without Git Bash on Windows.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import patch_config_runtime as pcr  # noqa: E402
import team_manifest as tm  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "mini-team"
BASE_TPL = ROOT / "expert-templates" / "base"


def _substitute(text: str, profile: str, expert: str) -> str:
    return (
        text.replace("__PROFILE__", profile)
        .replace("__EXPERT__", expert)
        .replace("__INSTANCE__", profile)
        .replace("__HINDSIGHT_API_URL__", "http://hindsight.superic.com:8888")
    )


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def _subst_tree(root: Path, profile: str, expert: str) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".md", ".yaml", ".yml", ".json"} and path.name != ".env":
            continue
        text = path.read_text(encoding="utf-8")
        path.write_text(_substitute(text, profile, expert), encoding="utf-8")


def inject_team(
    instance: str,
    instance_dir: Path,
    template_root: Path,
    *,
    expert: str | None = None,
) -> None:
    data_dir = instance_dir / "data" / "hermes"
    data_dir.mkdir(parents=True, exist_ok=True)
    expert_name = expert or template_root.name
    env = instance_dir / ".env"
    if not env.exists():
        env.write_text(
            f"HERMES_PROFILE={instance}\nHERMES_EXPERT={expert_name}\n"
            f"HINDSIGHT_API_URL=http://hindsight.superic.com:8888\n"
            f"HINDSIGHT_BANK_ID=hermes-{instance}\nGBRAIN_ENABLED=1\n",
            encoding="utf-8",
        )

    team_yaml = template_root / "team.yaml"
    data = tm.load_manifest(team_yaml)
    resolved = tm.resolve_manifest(
        data, instance=instance, template_root=template_root, hermes_home=data_dir
    )

    staging = data_dir / ".backup" / "pytest-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    # Root
    root_stage = staging / "root"
    _copy_tree(BASE_TPL, root_stage)
    _copy_tree(template_root / resolved["root"]["template"], root_stage)

    # Members
    for member in resolved["members"]:
        mid = member["id"]
        mdir = staging / "profiles" / mid
        _copy_tree(BASE_TPL, mdir)
        _copy_tree(template_root / member["template"], mdir)

    shared_stage = staging / "shared"
    if (template_root / "shared").is_dir():
        _copy_tree(template_root / "shared", shared_stage)

    if (template_root / "skills").is_dir():
        _copy_tree(template_root / "skills", root_stage / "skills")
    if (template_root / "plugins").is_dir():
        _copy_tree(template_root / "plugins", root_stage / "plugins")

    (staging / "team.yaml").write_text(
        yaml.safe_dump(resolved, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _subst_tree(staging, instance, expert_name)

    # Patch root
    root_cfg = root_stage / "config.yaml"
    patch = pcr.runtime_patch(
        instance,
        "http://hindsight.superic.com:8888",
        resolved["banks"]["default"],
        profile_home="/data/hermes",
        kanban_dispatcher="on",
        enable_delegation=True,
    )
    cfg = pcr.load_yaml(root_cfg)
    pcr.deep_update(cfg, patch)
    root_cfg.write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    for member in resolved["members"]:
        mid = member["id"]
        mcfg_path = staging / "profiles" / mid / "config.yaml"
        mpatch = pcr.runtime_patch(
            instance,
            "http://hindsight.superic.com:8888",
            resolved["banks"][mid],
            profile_home=f"/data/hermes/profiles/{mid}",
            kanban_dispatcher="off",
        )
        mcfg = pcr.load_yaml(mcfg_path)
        pcr.deep_update(mcfg, mpatch)
        mcfg_path.write_text(
            yaml.safe_dump(mcfg, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    # Structure gate
    for req in (
        "SOUL.md",
        "config.yaml",
        "memories/MEMORY.md",
        "memories/USER.md",
        "workspace/AGENTS.md",
    ):
        assert (root_stage / req).is_file(), f"staging root missing {req}"
        for member in resolved["members"]:
            assert (staging / "profiles" / member["id"] / req).is_file()

    # Promote
    for item in root_stage.iterdir():
        target = data_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    for member in resolved["members"]:
        mid = member["id"]
        dest = data_dir / "profiles" / mid
        dest.mkdir(parents=True, exist_ok=True)
        _copy_tree(staging / "profiles" / mid, dest)

    shared_rel = resolved["shared_context"]["host_relative_path"]
    shared_dest = data_dir / shared_rel
    shared_dest.mkdir(parents=True, exist_ok=True)
    if shared_stage.is_dir():
        for f in list(shared_dest.rglob("*")):
            if f.is_file():
                try:
                    os.chmod(f, 0o666)
                except OSError:
                    pass
                try:
                    f.unlink()
                except OSError:
                    pass
        _copy_tree(shared_stage, shared_dest)
        for f in shared_dest.rglob("*"):
            if f.is_file():
                try:
                    os.chmod(f, 0o444)
                except OSError:
                    pass

    shutil.copy2(staging / "team.yaml", data_dir / "team.yaml")


def test_bad_manifest_does_not_activate(tmp_path: Path):
    instance = "bad-team"
    instance_dir = tmp_path / instance
    bad = tmp_path / "bad-tpl"
    shutil.copytree(FIXTURE, bad)
    data = yaml.safe_load((bad / "team.yaml").read_text(encoding="utf-8"))
    data["kind"] = "broken"
    (bad / "team.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    data_dir = instance_dir / "data" / "hermes"
    data_dir.mkdir(parents=True)
    try:
        inject_team(instance, instance_dir, bad)
        raise AssertionError("expected failure")
    except tm.ManifestError:
        pass
    assert not (data_dir / "team.yaml").exists()


def test_inject_success_and_idempotent(tmp_path: Path):
    instance = "mini-ok"
    instance_dir = tmp_path / instance
    inject_team(instance, instance_dir, FIXTURE)
    data_dir = instance_dir / "data" / "hermes"
    assert (data_dir / "team.yaml").is_file()
    assert (data_dir / "SOUL.md").is_file()
    assert (data_dir / "profiles" / "advisor-alpha" / "SOUL.md").is_file()
    assert (data_dir / "team-shared" / "COMPANY.md").is_file()

    root_cfg = yaml.safe_load((data_dir / "config.yaml").read_text(encoding="utf-8"))
    mem_cfg = yaml.safe_load(
        (data_dir / "profiles" / "advisor-alpha" / "config.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert root_cfg["memory"]["bank_id"] != mem_cfg["memory"]["bank_id"]
    assert root_cfg["kanban"]["dispatch_in_gateway"] is True
    assert mem_cfg["kanban"]["dispatch_in_gateway"] is False
    assert mem_cfg["mcp_servers"]["workspace"]["args"][-1].endswith(
        "/profiles/advisor-alpha/workspace"
    )

    bank_before = root_cfg["memory"]["bank_id"]
    inject_team(instance, instance_dir, FIXTURE)
    root_cfg2 = yaml.safe_load((data_dir / "config.yaml").read_text(encoding="utf-8"))
    assert root_cfg2["memory"]["bank_id"] == bank_before


def test_cli_validate_json():
    code = tm.main(
        ["validate", str(FIXTURE / "team.yaml"), "--template-root", str(FIXTURE)]
    )
    assert code == 0
