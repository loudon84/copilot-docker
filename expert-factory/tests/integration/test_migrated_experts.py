from __future__ import annotations

from pathlib import Path

from workcopilot_expert_factory.validators.expert import validate_expert

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "expert-templates"


def test_three_migrated_experts_full() -> None:
    for name in ("writer", "finance", "sale"):
        report = validate_expert(TEMPLATES / name, level="full")
        assert report.passed, (name, report.to_dict())
        assert report.summary.get("expert_id") == name
