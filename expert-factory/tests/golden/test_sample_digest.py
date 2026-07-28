"""Golden digest smoke — created expert has stable source digest under SOURCE_DATE_EPOCH."""

from __future__ import annotations

from pathlib import Path

import yaml

from workcopilot_expert_factory.digest import compute_source_digest, iter_source_files
from workcopilot_expert_factory.services.create import create_expert


def test_golden_source_digest_roundtrip(tmp_path: Path):
    # @lat: [[tests#Golden Digests#Golden sample digest roundtrip]]
    brief = tmp_path / "brief.yaml"
    brief.write_text(
        yaml.safe_dump(
            {
                "id": "golden-sample",
                "name": "Golden 样本专家",
                "business_goal": "用于 Golden Digest",
                "required_capabilities": ["样本任务"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "golden-sample"
    create_expert(brief, out, drafts_root=tmp_path / "drafts")
    d1 = compute_source_digest(out, iter_source_files(out))
    d2 = compute_source_digest(out, iter_source_files(out))
    assert d1 == d2
    assert d1.startswith("sha256:")
    (tmp_path / "expected-digest.txt").write_text(d1 + "\n", encoding="utf-8")
