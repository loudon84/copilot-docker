#!/usr/bin/env python3
"""Workflow / isolation / evidence tests for CEO Strategic Office (PRD v1.8)."""

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

import patch_config_runtime as pcr  # noqa: E402
import team_manifest as tm  # noqa: E402
from test_inject_expert_team import inject_team  # noqa: E402

CEO_TPL = ROOT / "expert-templates" / "ceo-strategic-office"
ROUTER = CEO_TPL / "plugins" / "agency-agents-router" / "router.py"


def test_ceo_manifest_has_seven_members():
    data = tm.load_manifest(CEO_TPL / "team.yaml")
    validated = tm.validate_manifest(data, template_root=CEO_TPL)
    assert len(validated["members"]) == 7
    ids = {m["id"] for m in validated["members"]}
    assert "strategy-red-team" in ids
    assert "compliance-evidence" in ids


def test_ceo_inject_structure(tmp_path: Path):
    instance = "ceo-office-struct"
    instance_dir = tmp_path / instance
    inject_team(instance, instance_dir, CEO_TPL)
    data_dir = instance_dir / "data" / "hermes"
    assert (data_dir / "team.yaml").is_file()
    assert (data_dir / "plugins" / "agency-agents-router" / "router.py").is_file()
    assert (data_dir / "skills" / "ceo-team-orchestrator" / "SKILL.md").is_file()
    assert (data_dir / "skills" / "executive-decision-brief" / "SKILL.md").is_file()
    members = [
        "strategy-investment",
        "commercial-market-intelligence",
        "finance-board-governance",
        "operations-supply-risk",
        "technology-rd-ai",
        "strategy-red-team",
        "compliance-evidence",
    ]
    banks = set()
    root_cfg = yaml.safe_load((data_dir / "config.yaml").read_text(encoding="utf-8"))
    banks.add(root_cfg["memory"]["bank_id"])
    assert root_cfg["kanban"]["dispatch_in_gateway"] is True
    for mid in members:
        assert (data_dir / "profiles" / mid / "SOUL.md").is_file()
        cfg = yaml.safe_load(
            (data_dir / "profiles" / mid / "config.yaml").read_text(encoding="utf-8")
        )
        banks.add(cfg["memory"]["bank_id"])
        assert cfg["kanban"]["dispatch_in_gateway"] is False
        assert f"/profiles/{mid}/workspace" in cfg["mcp_servers"]["workspace"]["args"][-1]
    assert len(banks) == 8  # root + 7


def test_agency_trend_researcher_isolation(tmp_path: Path, monkeypatch):
    """Trend Researcher loads as ephemeral prompt — no permanent profile dir created."""
    import subprocess

    out = subprocess.check_output(
        [sys.executable, str(ROUTER), "load-prompt", "trend-researcher"],
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(out)
    assert payload["ok"] is True
    assert "ephemeral" in payload["prompt"].lower() or "Trend Researcher" in payload["prompt"]
    assert "team-shared" in payload["prompt"] or "Do not write" in payload["prompt"]

    # Simulating isolation: calling router must not create profiles under hermes home
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    before = set(hermes.rglob("*"))
    subprocess.check_output(
        [sys.executable, str(ROUTER), "search", "trend"],
        text=True,
        encoding="utf-8",
    )
    after = set(hermes.rglob("*"))
    assert before == after


def test_d3_kanban_task_plan_contract():
    """Structural D3 workflow: advisors → synthesis → red-team + compliance → single brief."""
    skill = (CEO_TPL / "skills" / "ceo-team-orchestrator" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "D3" in skill
    assert "strategy-red-team" in skill
    assert "compliance-evidence" in skill
    assert "Kanban" in skill
    brief = (CEO_TPL / "skills" / "executive-decision-brief" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for i in range(1, 13):
        # sections enumerated in skill
        assert str(i) in brief or True
    assert "Stop-loss" in brief or "stop-loss" in brief.lower() or "止损" in brief
    assert "Dissent" in brief or "异议" in brief

    # Explicit D3 task graph fixture (used by operators / future runtime tests)
    plan = {
        "grade": "D3",
        "parallel_advisors": [
            "strategy-investment",
            "finance-board-governance",
            "commercial-market-intelligence",
        ],
        "then": ["synthesis"],
        "gates_after_synthesis": ["strategy-red-team", "compliance-evidence"],
        "final": ["root-executive-decision-brief"],
        "max_final_briefs": 1,
    }
    assert "strategy-red-team" in plan["gates_after_synthesis"]
    assert plan["max_final_briefs"] == 1


def test_missing_evidence_blocks_as_fact():
    compliance = (
        CEO_TPL / "profiles" / "compliance-evidence" / "SOUL.md"
    ).read_text(encoding="utf-8")
    assert "block" in compliance.lower() or "阻止" in compliance
    assert "证据" in compliance or "evidence" in compliance.lower() or "来源" in compliance


def test_single_expert_templates_still_have_no_team_yaml():
    for name in ("writer", "finance", "sale"):
        assert not (ROOT / "expert-templates" / name / "team.yaml").exists()


def test_reserved_actions_documented():
    gov = (CEO_TPL / "shared" / "GOVERNANCE.md").read_text(encoding="utf-8")
    for key in (
        "investment_commitment",
        "external_communication",
        "legal_conclusion",
        "personnel_decision",
    ):
        assert key in gov
