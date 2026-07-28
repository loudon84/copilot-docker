"""Runtime-oriented checks for writer / finance templates when present."""

from __future__ import annotations

from pathlib import Path

import pytest

from workcopilot_expert_factory.evaluators.hermes_runtime import run_hermes_runtime_harness
from workcopilot_expert_factory.validators.expert import validate_expert

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "expert-templates"


@pytest.mark.parametrize("expert_id", ["writer", "finance"])
def test_template_validate_and_runtime_harness(expert_id: str):
    # @lat: [[tests#Runtime Templates#Writer and finance harness smoke]]
    root = TEMPLATES / expert_id
    if not (root / "expert.yaml").is_file():
        pytest.skip(f"{expert_id} not migrated")
    report = validate_expert(root, level="structure")
    # structure should pass for v1 experts
    errors = [i for i in report.issues if i.level == "error"]
    assert not errors, errors

    import yaml

    data = yaml.safe_load((root / "expert.yaml").read_text(encoding="utf-8"))
    checks, results, fixtures = run_hermes_runtime_harness(root, data, timeout=60)
    assert any(c.id == "runtime-smoke" and c.passed for c in checks)
    assert results and results[0].get("reply")
