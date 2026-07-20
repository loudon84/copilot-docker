#!/usr/bin/env python3
"""Inject / template structure tests for bi-strategic-office (no Docker required)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _find_bash() -> str | None:
    candidates = [
        shutil.which("bash"),
        shutil.which("bash.exe"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


def test_validate_bi_template():
    import pytest

    bash = _find_bash()
    if not bash:
        pytest.skip("bash not available")
    r = subprocess.run(
        [bash, str(ROOT / "scripts" / "validate-expert-template.sh"), "bi-strategic-office"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_inject_bi_idempotent(tmp_path: Path, monkeypatch):
    import pytest

    bash = _find_bash()
    if not bash:
        pytest.skip("bash not available")

    # Create a disposable instance under instances/ for inject-expert path contract
    profile = f"bi-test-{os.getpid()}"
    inst = ROOT / "instances" / profile
    data = inst / "data" / "hermes"
    try:
        data.mkdir(parents=True, exist_ok=True)
        (inst / ".env").write_text(
            "HERMES_PROFILE={}\nHERMES_EXPERT=bi-strategic-office\nAPI_SERVER_KEY=test\n".format(
                profile
            ),
            encoding="utf-8",
        )
        # seed minimal config so merge works
        (data / "config.yaml").write_text("model:\n  name: keep\n", encoding="utf-8")

        r1 = subprocess.run(
            [bash, str(ROOT / "scripts" / "inject-expert.sh"), profile, "bi-strategic-office"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert r1.returncode == 0, r1.stdout + r1.stderr
        assert (data / "plugins" / "hermes-finance-bi-plugin" / "plugin.yaml").is_file()
        assert (data / "finance-bi" / "semantic" / "datasets").is_dir()
        assert (data / "workspace" / "exports" / "bi").is_dir()
        env_text = (inst / ".env").read_text(encoding="utf-8")
        assert "FINANCE_BI_CATALOG_PATH=" in env_text

        # second inject should succeed (idempotent)
        r2 = subprocess.run(
            [bash, str(ROOT / "scripts" / "inject-expert.sh"), profile, "bi-strategic-office"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert r2.returncode == 0, r2.stdout + r2.stderr

        # doctor
        r3 = subprocess.run(
            [bash, str(ROOT / "scripts" / "check-finance-bi.sh"), profile],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert r3.returncode == 0, r3.stdout + r3.stderr
    finally:
        shutil.rmtree(inst, ignore_errors=True)


def test_writer_template_still_valid():
    """Regression: writer template exists and has no team.yaml."""
    tpl = ROOT / "expert-templates" / "writer"
    assert tpl.is_dir()
    assert (tpl / "SOUL.md").is_file()
    assert not (tpl / "team.yaml").exists()
    assert not (tpl / "semantic").exists()
