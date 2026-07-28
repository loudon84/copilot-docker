"""publish-expert orchestration (PRD §16)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from workcopilot_expert_factory.adapters.nacos_agentspec import prepare_nacos_artifacts
from workcopilot_expert_factory.errors import (
    PublishPartial,
    PublishTimeout,
    PublishVersionConflict,
    ReleaseBundleRequired,
)
from workcopilot_expert_factory.events import emit, timed_event
from workcopilot_expert_factory.models import PublishRecord, PublishSkillRecord
from workcopilot_expert_factory.publishers.nacos import NacosPublisher
from workcopilot_expert_factory.validators.bundle import assert_bundle_valid

Stage = Literal["draft", "review", "online"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3].parent


def load_registry_target(target: str, repo: Path | None = None) -> dict[str, Any]:
    root = repo or _repo_root()
    path = root / ".workcopilot" / "registry" / f"{target}.yaml"
    if path.is_file():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # defaults for known targets
    return {
        "provider": "nacos",
        "server_url": "http://127.0.0.1:8848/nacos",
        "namespace": f"workcopilot-{target.replace('nacos-', '')}",
        "visibility": "PRIVATE",
        "timeout_seconds": 30,
        "poll_interval_seconds": 3,
    }


def publish_expert(
    bundle_path: Path,
    *,
    target: str = "nacos-dev",
    stage: Stage = "draft",
    dry_run: bool = False,
    wait: bool = False,
    overwrite_draft: bool = False,
    update_latest: bool = False,
    published_by: str = "local",
) -> dict[str, Any]:
    bundle = Path(bundle_path).resolve()
    with timed_event("expert.publish", target=target) as ctx:
        report = assert_bundle_valid(bundle, release=True)
        bundle_meta = report.get("summary", {}).get("bundle") or {}
        if bundle_meta.get("dev"):
            raise ReleaseBundleRequired("dev bundle cannot be published")

        artifacts_dir = _repo_root() / ".workcopilot" / "publish" / uuid.uuid4().hex[:12]
        arts = prepare_nacos_artifacts(bundle, artifacts_dir)
        agentspec = arts["agentspec"]
        expert_id = agentspec["name"]
        version = agentspec["version"]
        bundle_digest = (agentspec.get("extensions") or {}).get("x-workcopilot", {}).get("bundleDigest")
        ctx["expert_id"] = expert_id
        ctx["version"] = version
        ctx["bundle_digest"] = bundle_digest

        cfg = load_registry_target(target)
        publisher = NacosPublisher(
            cfg.get("server_url") or "http://127.0.0.1:8848/nacos",
            namespace=cfg.get("namespace") or "public",
            timeout=float(cfg.get("timeout_seconds") or 30),
            mock=True if dry_run else None,
        )

        publish_id = artifacts_dir.name
        record = PublishRecord(
            publish_id=publish_id,
            expert={"id": expert_id, "version": version, "bundle_digest": bundle_digest},
            registry={
                "provider": "nacos",
                "namespace": publisher.namespace,
                "agent_spec_name": expert_id,
                "agent_spec_version": version,
                "status": "started",
                "visibility": cfg.get("visibility") or "PRIVATE",
            },
            skills=[],
            publication={
                "published_at": datetime.now(timezone.utc).isoformat(),
                "published_by": published_by,
                "target": target,
            },
            stage=stage,
            status="started",
        )

        if dry_run:
            record.status = "dry_run"
            _write_record(artifacts_dir, record)
            return {"dry_run": True, "record": record.model_dump(mode="json"), "artifacts": arts}

        # conflict check
        existing = publisher.get_resource("agentspec", expert_id, version)
        if existing and existing.get("status") == "online":
            if existing.get("digest") and bundle_digest and existing.get("digest") in str(bundle_digest):
                record.status = "already_published"
                _write_record(artifacts_dir, record)
                return {"status": "already_published", "record": record.model_dump(mode="json")}
            raise PublishVersionConflict(
                f"version {expert_id}@{version} already online with different digest",
            )

        # upload skills
        skill_results = []
        for skill in arts.get("skills") or []:
            zip_bytes = Path(skill["path"]).read_bytes()
            up = publisher.upload_skill(
                skill["id"],
                skill["version"],
                zip_bytes,
                overwrite_draft=overwrite_draft,
            )
            if up.get("status") == "conflict":
                raise PublishVersionConflict(f"skill {skill['id']}@{skill['version']} conflict")
            st = PublishSkillRecord(
                id=skill["id"],
                version=skill["version"],
                digest=up.get("resource", {}).get("digest"),
                status=up.get("resource", {}).get("status") or "draft",
            )
            record.skills.append(st)
            skill_results.append(up)
            emit("expert.publish.uploaded", expert_id=expert_id, version=version, skill_id=skill["id"])

        # upload agentspec
        agent_zip = Path(arts["agentspec_zip"]).read_bytes()
        up_agent = publisher.upload_agentspec(
            expert_id, version, agent_zip, overwrite_draft=overwrite_draft
        )
        if up_agent.get("status") == "conflict":
            raise PublishVersionConflict(f"agentspec {expert_id}@{version} conflict")

        visibility = cfg.get("visibility") or "PRIVATE"
        publisher.set_visibility("agentspec", expert_id, version, visibility)
        labels = ((agentspec.get("extensions") or {}).get("x-workcopilot") or {}).get("labels") or {}
        if update_latest:
            labels = {**labels, "latest": "true"}
        if labels:
            publisher.set_labels("agentspec", expert_id, version, {str(k): str(v) for k, v in labels.items()})

        record.registry["status"] = "draft"
        record.status = "draft"
        _write_record(artifacts_dir, record)

        if stage == "draft":
            return {"status": "draft", "record": record.model_dump(mode="json"), "artifacts": arts}

        # submit
        emit("expert.publish.reviewing", expert_id=expert_id, version=version, target=target)
        for sk in record.skills:
            publisher.submit("skill", sk.id, sk.version)
        publisher.submit("agentspec", expert_id, version)
        record.status = "reviewing"
        _write_record(artifacts_dir, record)

        if wait or stage == "online":
            for sk in record.skills:
                wr = publisher.wait_reviewed(
                    "skill",
                    sk.id,
                    sk.version,
                    timeout_seconds=float(cfg.get("poll_timeout_seconds") or 600),
                    poll_interval=float(cfg.get("poll_interval_seconds") or 3),
                )
                if wr.get("status") == "timeout":
                    raise PublishTimeout(f"skill review timeout: {sk.id}")
                sk.status = wr.get("status") or sk.status
            wr = publisher.wait_reviewed(
                "agentspec",
                expert_id,
                version,
                timeout_seconds=float(cfg.get("poll_timeout_seconds") or 600),
                poll_interval=float(cfg.get("poll_interval_seconds") or 3),
            )
            if wr.get("status") == "timeout":
                raise PublishTimeout("agentspec review timeout")
            emit("expert.publish.reviewed", expert_id=expert_id, version=version, target=target)

        if stage == "review":
            record.status = "reviewed"
            record.registry["status"] = "reviewed"
            _write_record(artifacts_dir, record)
            return {"status": "reviewed", "record": record.model_dump(mode="json"), "artifacts": arts}

        # online
        for sk in record.skills:
            publisher.publish("skill", sk.id, sk.version)
            sk.status = "online"
        publisher.publish("agentspec", expert_id, version)
        # readback
        readback = publisher.get_resource("agentspec", expert_id, version)
        if not readback or readback.get("status") != "online":
            record.status = "partial"
            _write_record(artifacts_dir, record)
            raise PublishPartial("agentspec publish readback failed", payload=record.model_dump(mode="json"))

        record.status = "online"
        record.registry["status"] = "online"
        record.registry["labels"] = labels
        _write_record(artifacts_dir, record)
        emit("expert.publish.online", expert_id=expert_id, version=version, target=target, bundle_digest=bundle_digest)
        return {"status": "online", "record": record.model_dump(mode="json"), "artifacts": arts, "readback": readback}


def resume_publish(record_path: Path) -> dict[str, Any]:
    data = json.loads(Path(record_path).read_text(encoding="utf-8"))
    status = data.get("status")
    if status == "online":
        return {"status": "already_published", "record": data}
    # Re-run from stored publication target / stage
    pub = data.get("publication") or {}
    expert = data.get("expert") or {}
    # find bundle via artifacts sibling
    publish_dir = Path(record_path).parent
    bundles = list(publish_dir.glob("*.expert.bundle")) + list(publish_dir.glob("**/*.agentspec.zip"))
    # Prefer re-publish using original stage progression
    stage = data.get("stage") or "draft"
    # Without original bundle path, return guidance
    if not any(p.suffix == ".bundle" or p.name.endswith(".expert.bundle") for p in publish_dir.rglob("*")):
        return {
            "status": "resume_needed_manual",
            "message": "original bundle not in publish dir; re-run publish with same bundle",
            "record": data,
        }
    bundle = next(p for p in publish_dir.rglob("*") if p.name.endswith(".expert.bundle"))
    return publish_expert(
        bundle,
        target=pub.get("target") or "nacos-dev",
        stage=stage,
        wait=True,
        overwrite_draft=True,
        published_by=pub.get("published_by") or "resume",
    )


def _write_record(artifacts_dir: Path, record: PublishRecord) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / "publish-record.json"
    path.write_text(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    yaml_path = artifacts_dir / "publish-record.yaml"
    yaml_path.write_text(yaml.safe_dump(record.to_yaml_dict(), allow_unicode=True), encoding="utf-8")
