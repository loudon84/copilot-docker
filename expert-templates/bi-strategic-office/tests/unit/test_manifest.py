#!/usr/bin/env python3
"""Unit tests for expert.yaml / VERSION / package layout."""

from __future__ import annotations

from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def test_version_file():
    ver = (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert ver == "1.10.0"


def test_expert_yaml_schema():
    data = yaml.safe_load((PACKAGE_ROOT / "expert.yaml").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["expert"]["id"] == "bi-strategic-office"
    assert data["expert"]["version"] == "1.10.0"
    assert "skills" in data["assets"]
    assert "semantic" in data["assets"]
    assert "policies" in data["assets"]
    assert data["lifecycle"]["install"] == "bin/install.sh"
    assert data["lifecycle"]["post_start"] == "bin/post-start.sh"
    plugins = data["plugins"]
    assert plugins[0]["id"] == "hermes-finance-bi-plugin"


def test_runtime_assets_exist():
    assert (PACKAGE_ROOT / "runtime" / "SOUL.md").is_file()
    assert (PACKAGE_ROOT / "runtime" / "memories" / "MEMORY.md").is_file()
    assert (PACKAGE_ROOT / "runtime" / "config.patch.yaml").is_file()
    assert (PACKAGE_ROOT / "runtime" / "skills" / "finance-bi-query" / "SKILL.md").is_file()
    assert (PACKAGE_ROOT / "runtime" / "semantic" / "datasets").is_dir()
    assert (PACKAGE_ROOT / "runtime" / "policies" / "query-policy.yaml").is_file()


def test_plugin_version_aligned():
    pdata = yaml.safe_load(
        (PACKAGE_ROOT / "plugins" / "hermes-finance-bi-plugin" / "plugin.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert str(pdata["version"]) == "1.10.0"
    assert (PACKAGE_ROOT / "plugins" / "hermes-finance-bi-plugin" / "requirements.txt").is_file()
    assert (PACKAGE_ROOT / "plugins" / "hermes-finance-bi-plugin" / "pyproject.toml").is_file()


def test_lifecycle_scripts_exist():
    for name in (
        "install.sh",
        "post-start.sh",
        "update.sh",
        "validate.sh",
        "doctor.sh",
        "test.sh",
        "sync-semantic-catalog.sh",
    ):
        assert (PACKAGE_ROOT / "bin" / name).is_file()


def test_validate_manifest_ok():
    import sys

    sys.path.insert(0, str(PACKAGE_ROOT / "lib"))
    from validate_manifest import validate_package

    assert validate_package(PACKAGE_ROOT) == 0
