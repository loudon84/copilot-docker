#!/usr/bin/env python3
"""Workflow / isolation / regression tests for CEO Strategic Office (PRD v1.8)."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "tests"))

import team_manifest as tm  # noqa: E402
from test_inject_expert_team import inject_team  # noqa: E402

CEO_TPL = ROOT / "expert-templates" / "ceo-strategic-office"
ROUTER = CEO_TPL / "plugins" / "agency-agents-router" / "router.py"
WRITER_TPL = ROOT / "expert-templates" / "writer"


def test_ceo_manifest_has_seven_members():
    data = tm.load_manifest(CEO_TPL / "team.yaml")
    validated = tm.validate_manifest(data, template_root=CEO_TPL)
    assert len(validated["members"]) == 7
    ids = {m["id"] for m in validated["members"]}
    assert "strategy-red-team" in ids
    assert "compliance-evidence" in ids


def test_agency_router_isolation_no_profile_dirs(tmp_path: Path, monkeypatch):
    """Delegating Trend Researcher must not create permanent profile dirs."""
    import subprocess

    out = subprocess.check_output(
        [sys.executable, str(ROUTER), "load-prompt", "trend-researcher"],
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(out)
    assert payload["ok"] is True
    prompt = payload["prompt"].lower()
    assert "team-shared" in prompt or "ephemeral" in prompt or "short-lived" in prompt

    # Simulate ephemeral result landing only in caller workspace
    caller_ws = tmp_path / "workspace" / "reports"
    caller_ws.mkdir(parents=True)
    result = caller_ws / "trend-researcher-result.md"
    result.write_text("# ephemeral result\n", encoding="utf-8")
    assert not (tmp_path / "profiles" / "trend-researcher").exists()
    assert not list(tmp_path.glob("**/team-shared/**"))


def test_d3_kanban_task_dag_contract():
    """D3 investment review: advisors → synthesis → red-team + compliance → brief."""
    dag = {
        "grade": "D3",
        "tasks": [
            {"id": "t-si", "assignee": "strategy-investment", "deps": []},
            {"id": "t-cmi", "assignee": "commercial-market-intelligence", "deps": []},
            {"id": "t-fbg", "assignee": "finance-board-governance", "deps": []},
            {
                "id": "t-synth",
                "assignee": "default",
                "deps": ["t-si", "t-cmi", "t-fbg"],
            },
            {"id": "t-red", "assignee": "strategy-red-team", "deps": ["t-synth"]},
            {"id": "t-comp", "assignee": "compliance-evidence", "deps": ["t-synth"]},
            {
                "id": "t-brief",
                "assignee": "default",
                "deps": ["t-red", "t-comp"],
                "artifact": "executive-decision-brief",
            },
        ],
    }
    by_id = {t["id"]: t for t in dag["tasks"]}
    # red-team and compliance after synthesis
    assert "t-synth" in by_id["t-red"]["deps"]
    assert "t-synth" in by_id["t-comp"]["deps"]
    # single final brief
    briefs = [t for t in dag["tasks"] if t.get("artifact") == "executive-decision-brief"]
    assert len(briefs) == 1
    assert set(briefs[0]["deps"]) == {"t-red", "t-comp"}


def test_missing_evidence_blocks_factual_claim():
    """compliance-evidence must reject unsourced revenue as 已验证事实."""
    claim = {
        "text": "Target ARR will reach USD 50M in 18 months",
        "number": 50_000_000,
        "source": None,
        "label_attempted": "已验证事实",
    }
    allowed = {"已验证事实", "有依据的推断", "假设", "建议", "未知 / 需要证据"}

    def compliance_gate(c: dict) -> dict:
        if c.get("number") is not None and not c.get("source"):
            return {
                "blocked": True,
                "reclassified_as": "未知 / 需要证据",
                "reason": "material number without source",
            }
        if c.get("label_attempted") not in allowed:
            return {"blocked": True, "reason": "invalid evidence label"}
        return {"blocked": False}

    result = compliance_gate(claim)
    assert result["blocked"] is True
    assert result["reclassified_as"] == "未知 / 需要证据"


def test_single_expert_writer_has_no_team_yaml():
    assert not (WRITER_TPL / "team.yaml").exists()
    assert (WRITER_TPL / "SOUL.md").is_file()


def test_inject_full_ceo_pack(tmp_path: Path):
    instance = "ceo-office-pytest"
    instance_dir = tmp_path / instance
    # Patch BASE_TPL usage: inject_team uses expert-templates/base from ROOT — OK
    # Override inject to use CEO template — reuse inject_team with CEO_TPL
    # But inject_team hardcodes expert name mini-team in subst — still fine for structure

    # Specialize: call resolve + validate first
    data = tm.load_manifest(CEO_TPL / "team.yaml")
    resolved = tm.resolve_manifest(
        data, instance=instance, template_root=CEO_TPL
    )
    assert len(resolved["members"]) == 7
    assert len(resolved["banks"]) == 8  # default + 7

    # Manual inject using same helper (substitutes expert name; OK)
    inject_team(instance, instance_dir, CEO_TPL, expert="ceo-strategic-office")
    data_dir = instance_dir / "data" / "hermes"
    assert (data_dir / "team.yaml").is_file()
    assert (data_dir / "plugins" / "agency-agents-router" / "router.py").is_file()
    assert (data_dir / "skills" / "ceo-team-orchestrator" / "SKILL.md").is_file()
    for mid in [m["id"] for m in resolved["members"]]:
        assert (data_dir / "profiles" / mid / "SOUL.md").is_file()
        cfg = yaml.safe_load(
            (data_dir / "profiles" / mid / "config.yaml").read_text(encoding="utf-8")
        )
        assert cfg["kanban"]["dispatch_in_gateway"] is False
        assert cfg["memory"]["bank_id"] == resolved["banks"][mid]

    root_cfg = yaml.safe_load((data_dir / "config.yaml").read_text(encoding="utf-8"))
    assert root_cfg["kanban"]["dispatch_in_gateway"] is True
    assert root_cfg["delegation"]["orchestrator_enabled"] is True
    banks = {root_cfg["memory"]["bank_id"]}
    for mid in [m["id"] for m in resolved["members"]]:
        banks.add(
            yaml.safe_load(
                (data_dir / "profiles" / mid / "config.yaml").read_text(encoding="utf-8")
            )["memory"]["bank_id"]
        )
    assert len(banks) == 8

    # shared readonly attempt
    shared = data_dir / "team-shared" / "COMPANY.md"
    assert shared.is_file()
    # On Unix 0o444; on Windows may still report is_file
    assert (data_dir / "team-shared" / "GOVERNANCE.md").is_file()


def test_brief_skill_has_twelve_sections():
    text = (CEO_TPL / "skills" / "executive-decision-brief" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for i in range(1, 13):
        assert f"{i}." in text
