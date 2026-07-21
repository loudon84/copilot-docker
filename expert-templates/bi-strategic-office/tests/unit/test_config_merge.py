#!/usr/bin/env python3
"""Unit tests for lib/merge_yaml.py deep-merge behaviour."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE_ROOT / "lib"))

from merge_yaml import deep_merge, ensure_plugin_enabled, merge_files  # noqa: E402


def test_preserve_model_and_union_plugins(tmp_path: Path):
    config = {
        "model": {"default": "local-model"},
        "plugins": {"enabled": ["existing-plugin"]},
        "agent": {"max_turns": 10},
    }
    patch = {
        "model": {"default": "should-not-overwrite"},
        "plugins": {"enabled": ["hermes-finance-bi-plugin"]},
        "agent": {"max_turns": 40},
    }
    merged = deep_merge(config, patch)
    assert merged["model"]["default"] == "local-model"
    assert merged["plugins"]["enabled"] == ["existing-plugin", "hermes-finance-bi-plugin"]
    assert merged["agent"]["max_turns"] == 40


def test_toolsets_union():
    base = {"toolsets": ["file", "skills"]}
    patch = {"toolsets": ["skills", "finance-bi"]}
    merged = deep_merge(base, patch)
    assert merged["toolsets"] == ["file", "skills", "finance-bi"]


def test_ensure_plugin_enabled_appends_platform_toolsets():
    config = {
        "plugins": {"enabled": []},
        "platform_toolsets": {"cli": ["file", "skills"]},
    }
    ensure_plugin_enabled(config, "hermes-finance-bi-plugin", "finance-bi")
    assert "hermes-finance-bi-plugin" in config["plugins"]["enabled"]
    assert "finance-bi" in config["platform_toolsets"]["cli"]


def test_merge_files_inplace_atomic_and_idempotent(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    patch_path = tmp_path / "config.patch.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "model": {"default": "local-model"},
                "plugins": {"enabled": ["existing-plugin"]},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    patch_path.write_text(
        yaml.safe_dump(
            {
                "plugins": {"enabled": ["hermes-finance-bi-plugin"]},
                "agent": {"max_turns": 24},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    merge_files(config_path, patch_path, inplace=True, do_backup=True)
    once = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    merge_files(config_path, patch_path, inplace=True, do_backup=True)
    twice = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert once["model"]["default"] == "local-model"
    assert once["plugins"]["enabled"] == [
        "existing-plugin",
        "hermes-finance-bi-plugin",
    ]
    assert twice["plugins"]["enabled"] == once["plugins"]["enabled"]
    assert twice["agent"]["max_turns"] == 24
    # backup created
    backups = list((tmp_path / ".backup").rglob("config.yaml"))
    assert backups
