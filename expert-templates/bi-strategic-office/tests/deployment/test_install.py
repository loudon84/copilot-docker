#!/usr/bin/env python3
"""Deployment: install places expected assets."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parents[1]

BASH = None
for candidate in (
    Path(r"C:\Program Files\Git\bin\bash.exe"),
    Path("/usr/bin/bash"),
    Path("/bin/bash"),
):
    if candidate.is_file():
        BASH = str(candidate)
        break


@pytest.fixture()
def installed(tmp_path: Path):
    if BASH is None:
        pytest.skip("bash not available")
    profile = "bi-deploy-test"
    instance_dir = tmp_path / "instances" / profile
    data_dir = instance_dir / "data" / "hermes"
    data_dir.mkdir(parents=True)
    (instance_dir / ".env").write_text(
        "HERMES_PROFILE=bi-deploy-test\nHERMES_EXPERT=bi-strategic-office\n",
        encoding="utf-8",
    )
    (data_dir / "config.yaml").write_text(
        "model:\n  default: local-model\nplugins:\n  enabled: []\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "C.UTF-8")
    proc = subprocess.run(
        [
            BASH,
            str(PACKAGE_ROOT / "bin" / "install.sh"),
            "--profile",
            profile,
            "--instance-dir",
            str(instance_dir),
            "--data-dir",
            str(data_dir),
            "--repo-root",
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    return data_dir, instance_dir


def test_install_copies_core_assets(installed):
    data_dir, _instance_dir = installed
    assert (data_dir / "SOUL.md").is_file()
    assert (data_dir / "skills" / "finance-bi-query" / "SKILL.md").is_file()
    assert (data_dir / "plugins" / "hermes-finance-bi-plugin" / "plugin.yaml").is_file()
    assert (data_dir / "finance-bi" / "semantic" / "datasets").is_dir()
    assert (data_dir / "finance-bi" / "policies" / "query-policy.yaml").is_file()
    assert (data_dir / "finance-bi" / "package-state.yaml").is_file()
    state = yaml.safe_load((data_dir / "finance-bi" / "package-state.yaml").read_text(encoding="utf-8"))
    assert state["expert_id"] == "bi-strategic-office"
    assert state["expert_version"] == "1.10.0"


def test_install_merges_plugin_enable(installed):
    data_dir, instance_dir = installed
    cfg = yaml.safe_load((data_dir / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "local-model"
    assert "hermes-finance-bi-plugin" in cfg["plugins"]["enabled"]
    env_text = (instance_dir / ".env").read_text(encoding="utf-8")
    assert "FINANCE_BI_CATALOG_PATH=" in env_text
    assert "FINANCE_BI_MASK_SENSITIVE=false" in env_text
