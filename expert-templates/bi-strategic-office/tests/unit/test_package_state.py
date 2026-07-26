#!/usr/bin/env python3
"""Unit tests for lib/package_state.py (v1.11.1)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE_ROOT / "lib"))

from package_state import (  # noqa: E402
    build_state,
    compute_package_hash,
    read_state,
    write_state,
    write_success_state,
)


def test_build_state_fields():
    state = build_state(expert_version="1.11.1", package_hash="abc")
    assert state["expert_id"] == "bi-strategic-office"
    assert state["expert_version"] == "1.11.1"
    assert state["plugin"]["id"] == "hermes-sqlbot-adapter"
    assert state["plugin"]["version"] == "1.11.1"
    assert state["schema_version"] == 2
    assert state["query_backend"] == "sqlbot-mcp-sse"
    assert state["package_hash"] == "abc"
    assert "installed_at" in state


def test_write_and_read_atomic(tmp_path: Path):
    path = tmp_path / "sqlbot-adapter" / "package-state.yaml"
    state = build_state(expert_version="1.11.1")
    write_state(path, state)
    loaded = read_state(path)
    assert loaded is not None
    assert loaded["expert_version"] == "1.11.1"
    assert loaded["plugin"]["id"] == "hermes-sqlbot-adapter"
    assert loaded["schema_version"] == 2


def test_write_success_state_from_package(tmp_path: Path):
    out = write_success_state(tmp_path, PACKAGE_ROOT)
    assert out.is_file()
    assert "sqlbot-adapter" in str(out)
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["expert_version"] == "1.11.1"
    assert data["schema_version"] == 2
    assert data["package_hash"]
    assert compute_package_hash(PACKAGE_ROOT) == data["package_hash"]


def test_refuse_secret_like_state(tmp_path: Path):
    path = tmp_path / "package-state.yaml"
    bad = build_state()
    bad["password"] = "secret123"
    try:
        write_state(path, bad)
    except ValueError:
        pass
    else:
        assert False, "expected ValueError"
    assert not path.exists()
