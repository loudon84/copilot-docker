"""Build Nacos AgentSpec / Skill ZIP packages from Expert Bundle."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import yaml


def extract_bundle_meta(bundle_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(bundle_path, "r") as zf:
        expert = yaml.safe_load(zf.read("manifest/expert.yaml").decode("utf-8"))
        bundle = json.loads(zf.read("manifest/bundle.json").decode("utf-8"))
        evaluation = {}
        try:
            evaluation = json.loads(zf.read("manifest/evaluation.json").decode("utf-8"))
        except KeyError:
            pass
        return {"expert": expert, "bundle": bundle, "evaluation": evaluation, "zip": zf.namelist()}


def build_agentspec_document(
    expert: dict[str, Any],
    bundle_meta: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    meta = expert.get("metadata") or {}
    release = expert.get("release") or {}
    registry = release.get("registry") or {}
    return {
        "name": meta.get("id"),
        "version": meta.get("version"),
        "description": meta.get("description"),
        "skills": [s.get("id") for s in ((expert.get("components") or {}).get("skills") or [])],
        "extensions": {
            "x-workcopilot": {
                "schemaVersion": expert.get("schema_version"),
                "bundleDigest": bundle_meta.get("payload_digest"),
                "bundleFormat": "workcopilot.expert-bundle.v1",
                "factoryVersion": bundle_meta.get("build_tool_version") or "2.1.0",
                "runtimeEngine": "hermes",
                "runtimeCompatibility": (expert.get("runtime") or {}).get("compatibility") or {},
                "connectorSlots": expert.get("connector_slots") or [],
                "evaluation": {
                    "score": evaluation.get("score"),
                    "digest": evaluation.get("evaluation_digest") or evaluation.get("source_digest"),
                    "passed": evaluation.get("passed"),
                },
                "provenance": expert.get("provenance") or {},
                "labels": registry.get("labels") or {},
                "visibility": registry.get("visibility") or "PRIVATE",
            }
        },
    }


def build_agentspec_zip_bytes(
    bundle_path: Path,
    agentspec: dict[str, Any],
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("agentspec.json", json.dumps(agentspec, ensure_ascii=False, indent=2))
        # embed original bundle for download
        zf.write(bundle_path, arcname=f"packages/{bundle_path.name}")
    return buf.getvalue()


def build_skill_zip_bytes(skill_dir: Path, skill_id: str, version: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file():
                arc = path.relative_to(skill_dir).as_posix()
                zf.write(path, arcname=arc)
        meta = {"id": skill_id, "version": version, "schema_version": "workcopilot.skill.v1"}
        zf.writestr("nacos-skill-meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return buf.getvalue()


def materialize_nacos_packages(
    bundle_path: Path,
    output_dir: Path,
    *,
    source_root: Path | None = None,
) -> dict[str, Any]:
    """Write AgentSpec ZIP and per-skill ZIPs under output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "r") as zf:
        expert = yaml.safe_load(zf.read("manifest/expert.yaml").decode("utf-8"))
        bundle_meta = json.loads(zf.read("manifest/bundle.json").decode("utf-8"))
        try:
            evaluation = json.loads(zf.read("manifest/evaluation.json").decode("utf-8"))
        except KeyError:
            evaluation = {}

    agentspec = build_agentspec_document(expert, bundle_meta, evaluation)
    agent_bytes = build_agentspec_zip_bytes(bundle_path, agentspec)
    expert_id = (expert.get("metadata") or {}).get("id")
    version = (expert.get("metadata") or {}).get("version")
    agent_path = output_dir / f"{expert_id}-{version}.agentspec.zip"
    agent_path.write_bytes(agent_bytes)

    skills_out: list[dict[str, Any]] = []
    root = source_root
    if root is None:
        # try extract skills from bundle runtime
        extract_dir = output_dir / "_runtime_extract"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(bundle_path, "r") as zf:
            for name in zf.namelist():
                if name.startswith("runtime/skills/"):
                    target = extract_dir / name[len("runtime/") :]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(name))
        root = extract_dir

    for item in (expert.get("components") or {}).get("skills") or []:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        rel = item.get("path") or f"skills/{sid}"
        skill_dir = root / rel
        if not skill_dir.is_dir():
            continue
        # version from frontmatter if present
        skill_ver = version
        skill_md = skill_dir / "SKILL.md"
        if skill_md.is_file():
            text = skill_md.read_text(encoding="utf-8")
            if text.startswith("---"):
                import re

                m = re.match(r"\A---\r?\n(.*?)\r?\n---", text, re.DOTALL)
                if m:
                    fm = yaml.safe_load(m.group(1)) or {}
                    skill_ver = fm.get("version") or skill_ver
        data = build_skill_zip_bytes(skill_dir, sid, skill_ver)
        spath = output_dir / f"{sid}-{skill_ver}.skill.zip"
        spath.write_bytes(data)
        skills_out.append({"id": sid, "version": skill_ver, "path": str(spath)})

    (output_dir / "agentspec.json").write_text(
        json.dumps(agentspec, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "agentspec_zip": str(agent_path),
        "agentspec": agentspec,
        "skills": skills_out,
    }
