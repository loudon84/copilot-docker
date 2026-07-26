#!/usr/bin/env python3
"""Unit tests for expert.yaml / VERSION / package layout (v1.11.1)."""

from __future__ import annotations

from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def test_version_file():
    ver = (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert ver == "1.11.1"


def test_expert_yaml_schema():
    data = yaml.safe_load((PACKAGE_ROOT / "expert.yaml").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["expert"]["id"] == "bi-strategic-office"
    assert data["expert"]["version"] == "1.11.1"
    assert "skills" in data["assets"]
    assert "semantic" not in data.get("assets", {})
    assert "policies" not in data.get("assets", {})
    assert data["lifecycle"]["install"] == "bin/install.sh"
    assert data["lifecycle"]["post_start"] == "bin/post-start.sh"
    plugins = data["plugins"]
    assert plugins[0]["id"] == "hermes-sqlbot-adapter"
    required_env = data.get("required_env") or []
    assert "SQLBOT_MCP_URL" in required_env
    assert "SQLBOT_PASSWORD" in required_env
    assert "SQLBOT_SESSION_ENCRYPTION_KEY" in required_env


def test_runtime_assets_exist():
    assert (PACKAGE_ROOT / "runtime" / "SOUL.md").is_file()
    assert (PACKAGE_ROOT / "runtime" / "memories" / "MEMORY.md").is_file()
    assert (PACKAGE_ROOT / "runtime" / "config.patch.yaml").is_file()
    assert (PACKAGE_ROOT / "runtime" / "skills" / "finance-bi-query" / "SKILL.md").is_file()
    assert (PACKAGE_ROOT / "runtime" / "skills" / "sqlbot-query-review" / "SKILL.md").is_file()
    assert not (PACKAGE_ROOT / "runtime" / "semantic").exists()
    assert not (PACKAGE_ROOT / "runtime" / "policies").exists()
    assert not (PACKAGE_ROOT / "memories" / "test_sqlbot.py").exists()


def test_plugin_version_aligned():
    pdata = yaml.safe_load(
        (PACKAGE_ROOT / "plugins" / "hermes-sqlbot-adapter" / "plugin.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert str(pdata["version"]) == "1.11.1"
    assert "finance_bi_reset" in pdata["provides_tools"]
    assert "SQLBOT_SESSION_ENCRYPTION_KEY" in (pdata.get("requires_env") or [])
    assert (PACKAGE_ROOT / "plugins" / "hermes-sqlbot-adapter" / "requirements.txt").is_file()
    assert (PACKAGE_ROOT / "plugins" / "hermes-sqlbot-adapter" / "pyproject.toml").is_file()
    assert not (PACKAGE_ROOT / "plugins" / "hermes-finance-bi-plugin").exists()


def test_lifecycle_scripts_exist():
    for name in (
        "install.sh",
        "post-start.sh",
        "update.sh",
        "validate.sh",
        "doctor.sh",
        "test.sh",
    ):
        assert (PACKAGE_ROOT / "bin" / name).is_file()
    assert not (PACKAGE_ROOT / "bin" / "sync-semantic-catalog.sh").exists()


def test_config_patch_enables_adapter():
    data = yaml.safe_load(
        (PACKAGE_ROOT / "runtime" / "config.patch.yaml").read_text(encoding="utf-8")
    )
    assert "hermes-sqlbot-adapter" in data["plugins"]["enabled"]
    assert "hermes-finance-bi-plugin" not in data["plugins"]["enabled"]


def test_validate_manifest_ok():
    import sys

    sys.path.insert(0, str(PACKAGE_ROOT / "lib"))
    from validate_manifest import validate_package

    assert validate_package(PACKAGE_ROOT) == 0
