#!/usr/bin/env python3
"""Tests for scripts/lib/team_manifest.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import team_manifest as tm  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "mini-team"
FIXTURE_YAML = FIXTURE / "team.yaml"


def test_validate_ok():
    data = tm.load_manifest(FIXTURE_YAML)
    validated = tm.validate_manifest(data, template_root=FIXTURE)
    assert validated["kind"] == "hermes-profile-team"
    assert validated["root"]["profile"] == "default"
    assert len(validated["members"]) == 1
    assert validated["members"][0]["id"] == "advisor-alpha"


def test_resolve_banks():
    data = tm.load_manifest(FIXTURE_YAML)
    resolved = tm.resolve_manifest(
        data, instance="ceo-office", template_root=FIXTURE
    )
    assert resolved["banks"]["default"] == "hermes-ceo-office-default"
    assert resolved["banks"]["advisor-alpha"] == "hermes-ceo-office-advisor-alpha"
    assert resolved["profile_homes"]["advisor-alpha"] == (
        "/data/hermes/profiles/advisor-alpha"
    )


def test_list_members_cli(capsys):
    code = tm.main(["list-members", str(FIXTURE_YAML), "--template-root", str(FIXTURE)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    ids = [m["id"] for m in out["members"]]
    assert ids == ["default", "advisor-alpha"]


def test_reject_bad_kind(tmp_path: Path):
    bad = {
        "kind": "wrong",
        "version": 1,
        "id": "x",
        "name": "x",
        "root": {"profile": "default", "template": "root"},
        "members": [],
        "orchestration": {"engine": "kanban", "board": "b"},
        "shared_context": {
            "host_relative_path": "team-shared",
            "container_path": "/data/hermes/team-shared",
        },
    }
    path = tmp_path / "team.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    (tmp_path / "root").mkdir()
    code = tm.main(["validate", str(path), "--template-root", str(tmp_path)])
    assert code == 1


def test_reject_duplicate_member(tmp_path: Path):
    data = tm.load_manifest(FIXTURE_YAML)
    data["members"].append(dict(data["members"][0]))
    with pytest.raises(tm.ManifestError) as exc:
        tm.validate_manifest(data, template_root=FIXTURE)
    assert "duplicate" in str(exc.value)


def test_reject_bad_profile_id():
    data = tm.load_manifest(FIXTURE_YAML)
    data["members"][0]["id"] = "Bad_ID"
    with pytest.raises(tm.ManifestError) as exc:
        tm.validate_manifest(data, template_root=FIXTURE)
    assert "members[0].id" in str(exc.value)


def test_reject_non_default_root():
    data = tm.load_manifest(FIXTURE_YAML)
    data["root"]["profile"] = "other"
    with pytest.raises(tm.ManifestError) as exc:
        tm.validate_manifest(data, template_root=FIXTURE)
    assert "root.profile" in str(exc.value)


def test_reject_path_escape(tmp_path: Path):
    data = tm.load_manifest(FIXTURE_YAML)
    data["shared_context"]["host_relative_path"] = "../escape"
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    with pytest.raises(tm.ManifestError) as exc:
        tm.validate_manifest(data, template_root=FIXTURE, hermes_home=hermes)
    assert "host_relative_path" in str(exc.value)


def test_reject_missing_member_template(tmp_path: Path):
    data = tm.load_manifest(FIXTURE_YAML)
    root = tmp_path / "root"
    root.mkdir()
    data["root"]["template"] = "root"
    with pytest.raises(tm.ManifestError):
        tm.validate_manifest(data, template_root=tmp_path)


def test_validate_cli_ok(capsys):
    code = tm.main(["validate", str(FIXTURE_YAML), "--template-root", str(FIXTURE)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["manifest"]["id"] == "mini-team"


def test_resolve_cli_ok(capsys):
    code = tm.main(
        [
            "resolve",
            str(FIXTURE_YAML),
            "--instance",
            "test-inst",
            "--template-root",
            str(FIXTURE),
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["manifest"]["banks"]["default"] == "hermes-test-inst-default"
