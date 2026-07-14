#!/usr/bin/env python3
"""Tests for scripts/lib/patch_config_runtime.py."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import patch_config_runtime as pcr  # noqa: E402


def test_root_defaults_preserve_paths(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model:\n  name: keep-me\n", encoding="utf-8")
    patch = pcr.runtime_patch(
        "writer",
        "http://hindsight.example:8888",
        "hermes-writer",
        kanban_dispatcher="on",
        enable_delegation=True,
    )
    data = pcr.load_yaml(cfg)
    pcr.deep_update(data, patch)
    assert data["model"]["name"] == "keep-me"
    assert data["memory"]["bank_id"] == "hermes-writer"
    assert data["mcp_servers"]["workspace"]["args"][-1] == "/data/hermes/workspace"
    assert data["kanban"]["dispatch_in_gateway"] is True
    assert data["delegation"]["orchestrator_enabled"] is True


def test_single_expert_omits_kanban():
    patch = pcr.runtime_patch(
        "writer",
        "http://hindsight.example:8888",
        "hermes-writer",
    )
    assert "kanban" not in patch
    assert "delegation" not in patch


def test_named_profile_paths():
    patch = pcr.runtime_patch(
        "ceo-office",
        "http://hindsight.example:8888",
        "hermes-ceo-office-strategy-investment",
        profile_home="/data/hermes/profiles/strategy-investment",
        kanban_dispatcher="off",
        enable_delegation=False,
    )
    assert patch["memory"]["bank_id"] == "hermes-ceo-office-strategy-investment"
    assert (
        patch["mcp_servers"]["workspace"]["args"][-1]
        == "/data/hermes/profiles/strategy-investment/workspace"
    )
    assert (
        patch["mcp_servers"]["obsidian_vault"]["args"][-1]
        == "/data/hermes/profiles/strategy-investment/obsidian-vault"
    )
    assert patch["kanban"]["dispatch_in_gateway"] is False
    assert "delegation" not in patch


def test_cli_named_profile(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("{}\n", encoding="utf-8")
    argv = [
        "patch_config_runtime.py",
        "--config",
        str(cfg),
        "--profile",
        "ceo-office",
        "--hindsight-bank-id",
        "hermes-ceo-office-alpha",
        "--profile-home",
        "/data/hermes/profiles/alpha",
        "--kanban-dispatcher",
        "off",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert pcr.main() == 0
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert data["memory"]["bank_id"] == "hermes-ceo-office-alpha"
    assert data["mcp_servers"]["workspace"]["args"][-1].endswith(
        "/profiles/alpha/workspace"
    )
