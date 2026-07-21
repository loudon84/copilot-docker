#!/usr/bin/env python3
"""Security: install must preserve runtime user data (simulated)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
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


def _run_install(tmp_path: Path) -> Path:
    if BASH is None:
        pytest.skip("bash not available")
    profile = "bi-pkg-test"
    instance_dir = tmp_path / "instances" / profile
    data_dir = instance_dir / "data" / "hermes"
    data_dir.mkdir(parents=True)

    # Seed protected runtime data
    (instance_dir / ".env").write_text(
        "HERMES_PROFILE=bi-pkg-test\nHERMES_EXPERT=bi-strategic-office\nFINANCE_BI_DSN=keep-me\n",
        encoding="utf-8",
    )
    (data_dir / "sessions").mkdir()
    (data_dir / "sessions" / "test.json").write_text('{"ok":1}', encoding="utf-8")
    (data_dir / "workspace" / "uploads").mkdir(parents=True)
    (data_dir / "workspace" / "uploads" / "test.xlsx").write_bytes(b"PK\x03\x04fake")
    (data_dir / "workspace" / "exports" / "bi").mkdir(parents=True)
    (data_dir / "workspace" / "exports" / "bi" / "report.xlsx").write_bytes(b"export")
    (data_dir / "finance-bi" / "state").mkdir(parents=True)
    (data_dir / "finance-bi" / "state" / "finance_bi.db").write_bytes(b"sqlite-fake")
    (data_dir / "memories").mkdir(parents=True)
    (data_dir / "memories" / "MEMORY.md").write_text("# user memory keep\n", encoding="utf-8")
    (data_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": {"default": "local-model"},
                "plugins": {"enabled": ["existing-plugin"]},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    cmd = [
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
    ]
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "C.UTF-8")
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    return data_dir


def test_runtime_data_preserved(tmp_path: Path):
    data_dir = _run_install(tmp_path)
    instance_dir = data_dir.parents[1]

    assert (instance_dir / ".env").read_text(encoding="utf-8").find("FINANCE_BI_DSN=keep-me") >= 0
    assert (data_dir / "sessions" / "test.json").is_file()
    assert (data_dir / "workspace" / "uploads" / "test.xlsx").is_file()
    assert (data_dir / "workspace" / "exports" / "bi" / "report.xlsx").is_file()
    assert (data_dir / "finance-bi" / "state" / "finance_bi.db").read_bytes() == b"sqlite-fake"
    assert "user memory keep" in (data_dir / "memories" / "MEMORY.md").read_text(encoding="utf-8")

    cfg = yaml.safe_load((data_dir / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "local-model"
    assert "existing-plugin" in cfg["plugins"]["enabled"]
    assert "hermes-finance-bi-plugin" in cfg["plugins"]["enabled"]


def test_install_idempotent(tmp_path: Path):
    if BASH is None:
        pytest.skip("bash not available")
    data_dir = _run_install(tmp_path)
    instance_dir = data_dir.parents[1]
    cfg1 = (data_dir / "config.yaml").read_text(encoding="utf-8")
    state1 = (data_dir / "finance-bi" / "package-state.yaml").read_text(encoding="utf-8")

    cmd = [
        BASH,
        str(PACKAGE_ROOT / "bin" / "install.sh"),
        "--profile",
        "bi-pkg-test",
        "--instance-dir",
        str(instance_dir),
        "--data-dir",
        str(data_dir),
        "--repo-root",
        str(REPO_ROOT),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8"},
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr

    cfg2 = yaml.safe_load((data_dir / "config.yaml").read_text(encoding="utf-8"))
    assert cfg2["plugins"]["enabled"].count("hermes-finance-bi-plugin") == 1
    assert (data_dir / "finance-bi" / "state" / "finance_bi.db").is_file()
    assert (data_dir / "workspace" / "uploads" / "test.xlsx").is_file()
    # model still preserved
    assert cfg2["model"]["default"] == "local-model"
    assert state1  # state rewritten ok
    assert (data_dir / "finance-bi" / "package-state.yaml").is_file()
