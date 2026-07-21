#!/usr/bin/env python3
"""Security: install paths must stay within instance data dir."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def test_install_script_uses_data_dir_args():
    text = (PACKAGE_ROOT / "bin" / "install.sh").read_text(encoding="utf-8")
    assert "--data-dir" in text
    assert "DATA_DIR" in text
    # Must not hardcode a sibling profile path
    assert "../other" not in text
    assert "instances/writer" not in text


def test_sync_script_scoped_to_data_dir():
    text = (PACKAGE_ROOT / "bin" / "sync-semantic-catalog.sh").read_text(encoding="utf-8")
    assert 'SEMANTIC_DST="$DATA_DIR/finance-bi/semantic"' in text
    assert "scripts/sync-bi-semantic-catalog.sh" not in text


def test_package_assets_under_package_root():
    for rel in (
        "runtime/semantic",
        "runtime/policies",
        "runtime/skills",
        "plugins/hermes-finance-bi-plugin",
        "bin/install.sh",
        "lib/merge_yaml.py",
    ):
        assert (PACKAGE_ROOT / rel).exists(), rel
