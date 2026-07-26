#!/usr/bin/env python3
"""Security: install paths must stay within instance data dir (v1.11)."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def test_install_script_uses_data_dir_args():
    text = (PACKAGE_ROOT / "bin" / "install.sh").read_text(encoding="utf-8")
    assert "--data-dir" in text
    assert "DATA_DIR" in text
    assert "hermes-sqlbot-adapter" in text
    assert "../other" not in text
    assert "instances/writer" not in text


def test_package_assets_under_package_root():
    for rel in (
        "runtime/skills",
        "plugins/hermes-sqlbot-adapter",
        "config/sqlbot.example.env",
        "bin/install.sh",
        "lib/merge_yaml.py",
        "evaluations/golden_questions.yaml",
    ):
        assert (PACKAGE_ROOT / rel).exists(), rel


def test_legacy_paths_removed():
    assert not (PACKAGE_ROOT / "plugins" / "hermes-finance-bi-plugin").exists()
    assert not (PACKAGE_ROOT / "bin" / "sync-semantic-catalog.sh").exists()
    assert not (PACKAGE_ROOT / "runtime" / "semantic").exists()
