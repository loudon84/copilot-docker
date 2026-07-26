#!/usr/bin/env python3
"""Security: package must not ship secrets / .env / state DBs."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
FORBIDDEN_NAMES = {".env", "finance_bi.db", "sqlbot_sessions.db"}


def test_no_env_or_state_db_in_package():
    offenders: list[str] = []
    for path in PACKAGE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or ".git" in path.parts:
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            offenders.append(str(path.relative_to(PACKAGE_ROOT)))
    assert not offenders, f"forbidden files: {offenders}"


def test_expert_yaml_declares_no_secrets():
    text = (PACKAGE_ROOT / "expert.yaml").read_text(encoding="utf-8")
    assert "secrets_in_package: false" in text
    assert "allow_raw_sql: false" in text


def test_config_patch_has_no_dsn_or_keys():
    text = (PACKAGE_ROOT / "runtime" / "config.patch.yaml").read_text(encoding="utf-8")
    lower = text.lower()
    assert "dsn" not in lower
    assert "password" not in lower
    assert "api_key" not in lower
    assert "api-key" not in lower
    assert "access_token" not in lower


def test_example_env_has_empty_secrets():
    text = (PACKAGE_ROOT / "config" / "sqlbot.example.env").read_text(encoding="utf-8")
    assert "SQLBOT_PASSWORD=" in text
    # Ensure no real-looking password value
    for line in text.splitlines():
        if line.startswith("SQLBOT_PASSWORD="):
            assert line.strip() == "SQLBOT_PASSWORD="
