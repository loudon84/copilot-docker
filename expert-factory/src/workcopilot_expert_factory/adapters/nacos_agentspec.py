"""Adapter: Expert Bundle → Nacos AgentSpec document."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from workcopilot_expert_factory.builders.nacos_package import (
    build_agentspec_document,
    extract_bundle_meta,
    materialize_nacos_packages,
)


def bundle_to_agentspec(bundle_path: Path) -> dict[str, Any]:
    meta = extract_bundle_meta(bundle_path)
    return build_agentspec_document(meta["expert"], meta["bundle"], meta["evaluation"])


def prepare_nacos_artifacts(bundle_path: Path, output_dir: Path) -> dict[str, Any]:
    return materialize_nacos_packages(bundle_path, output_dir)
