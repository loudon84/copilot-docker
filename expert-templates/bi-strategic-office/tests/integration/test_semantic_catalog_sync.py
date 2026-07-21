#!/usr/bin/env python3
"""Integration: semantic catalog sync helper."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2]

BASH = None
for candidate in (
    Path(r"C:\Program Files\Git\bin\bash.exe"),
    Path("/usr/bin/bash"),
    Path("/bin/bash"),
):
    if candidate.is_file():
        BASH = str(candidate)
        break


def test_sync_semantic_catalog(tmp_path: Path):
    if BASH is None:
        pytest.skip("bash not available")
    data_dir = tmp_path / "data" / "hermes"
    data_dir.mkdir(parents=True)
    proc = subprocess.run(
        [
            BASH,
            str(PACKAGE_ROOT / "bin" / "sync-semantic-catalog.sh"),
            "--profile",
            "sync-test",
            "--instance-dir",
            str(tmp_path),
            "--data-dir",
            str(data_dir),
            "--package-root",
            str(PACKAGE_ROOT),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert (data_dir / "finance-bi" / "semantic" / "datasets").is_dir()
    assert (data_dir / "finance-bi" / "policies" / "query-policy.yaml").is_file()
