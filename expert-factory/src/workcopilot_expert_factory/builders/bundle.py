"""Deterministic Expert Bundle builder (PRD v2.1 §15)."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory import __version__
from workcopilot_expert_factory.builders.sbom import build_cyclonedx_sbom
from workcopilot_expert_factory.builders.signature import resolve_signature_mode, sign_digest
from workcopilot_expert_factory.digest import (
    compute_json_digest,
    compute_source_digest,
    git_commit,
    iter_source_files,
    sha256_bytes,
    source_date_epoch,
)
from workcopilot_expert_factory.errors import EvaluationRequired, EvaluationStale, ValidationFailed
from workcopilot_expert_factory.models import BundleManifest, ExpertManifest
from workcopilot_expert_factory.services.evaluate import load_latest_evaluation
from workcopilot_expert_factory.validators.expert import validate_expert


def _arcname_for(rel: str) -> str:
    if rel == "expert.yaml":
        return "manifest/expert.yaml"
    if rel == "README.md":
        return "docs/README.md"
    if rel.startswith("docs/"):
        return rel
    if rel.startswith("evaluations/"):
        return rel
    if rel in {
        "python-requirements.txt",
        "requirements.txt",
        "npm-global.txt",
        "system-packages.txt",
        "package.json",
        "package-lock.json",
        "pyproject.toml",
    }:
        return f"dependencies/{Path(rel).name}"
    return f"runtime/{rel}"


def build_expert_bundle(
    expert_path: Path | str,
    output_dir: Path | str,
    *,
    dev: bool = True,
    skip_runtime_evaluation: bool = True,
    signature_mode: str | None = None,
) -> dict[str, Any]:
    root = Path(expert_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    report = validate_expert(root, level="full")
    if not report.passed:
        raise ValidationFailed(
            "validate failed before build: "
            + "; ".join(i.message for i in report.issues if i.level == "error")[:500]
        )
    if report.legacy:
        raise ValidationFailed("cannot build Expert Bundle for legacy expert without workcopilot.expert.v1")

    data = yaml.safe_load((root / "expert.yaml").read_text(encoding="utf-8"))
    manifest = ExpertManifest.model_validate(data)
    expert_id = manifest.metadata.id
    version = manifest.metadata.version
    minimum = float(manifest.evaluations.minimum_score)

    files = iter_source_files(root)
    source_digest = compute_source_digest(root, files)
    commit = git_commit(root)

    evaluation_payload: dict[str, Any]
    require_eval = (not dev) or (not skip_runtime_evaluation)
    if require_eval:
        evaluation_payload = load_latest_evaluation(root) or {}
        if not evaluation_payload:
            raise EvaluationRequired(
                "release build requires evaluation.json; run: "
                f"scripts/expert/expert evaluate {root} --mode full"
            )
        eval_digest = evaluation_payload.get("source_digest") or (
            (evaluation_payload.get("source") or {}).get("source_digest")
        )
        if eval_digest and eval_digest != source_digest:
            raise EvaluationStale(
                f"evaluation source_digest {eval_digest} != current {source_digest}; re-run evaluate"
            )
        gates_ok = evaluation_payload.get("security_gates_passed")
        if gates_ok is None:
            gates_ok = (evaluation_payload.get("decision") or {}).get("passed")
        if gates_ok is False:
            raise ValidationFailed("evaluation security gates failed; cannot release")
        passed = evaluation_payload.get("passed")
        if passed is None:
            passed = (evaluation_payload.get("decision") or {}).get("passed")
        if not passed:
            raise ValidationFailed("evaluation did not pass; cannot release")
        score = evaluation_payload.get("score")
        if score is None:
            score = (evaluation_payload.get("decision") or {}).get("score")
        if float(score or 0) < minimum:
            raise ValidationFailed(f"evaluation score {score} < minimum_score {minimum}")
        evaluation_payload = {
            **evaluation_payload,
            "skipped": False,
            "embedded_at_build": True,
            "source_digest": source_digest,
            "evaluation_digest": compute_json_digest(
                {k: evaluation_payload.get(k) for k in ("score", "passed", "security_gates_passed", "summary")}
            ),
        }
    else:
        evaluation_payload = {
            "skipped": True,
            "reason": "dev build with --skip-runtime-evaluation",
            "dev": True,
            "source_digest": source_digest,
        }

    sig_mode = resolve_signature_mode(signature_mode, release=not dev)
    bundle_name = f"{expert_id}-{version}.expert.bundle"
    bundle_path = out_dir / bundle_name
    build_json_path = out_dir / f"{expert_id}-{version}.build.json"
    sha_path = out_dir / f"{expert_id}-{version}.sha256"

    epoch = source_date_epoch()
    checksum_lines: list[str] = []
    payload_hasher = __import__("hashlib").sha256()
    built_at = datetime.now(timezone.utc).isoformat()

    # provenance without absolute paths / timestamps in payload
    provenance = {
        "source_digest": source_digest,
        "source_commit": commit,
        "source_repository": (manifest.provenance.source_repository if manifest.provenance else None),
        "relative_source": f"expert-templates/{expert_id}",
        "dev": dev,
    }

    sbom = build_cyclonedx_sbom(root, expert_id=expert_id, expert_version=version, files=files)

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        def add_bytes(arcname: str, content: bytes, *, into_payload: bool = True) -> None:
            info = zipfile.ZipInfo(arcname)
            info.date_time = datetime.fromtimestamp(epoch, tz=timezone.utc).timetuple()[:6]
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, content)
            digest = sha256_bytes(content)
            checksum_lines.append(f"{digest}  {arcname}")
            if into_payload:
                payload_hasher.update(arcname.encode("utf-8"))
                payload_hasher.update(b"\0")
                payload_hasher.update(content)

        # whitelist files
        for path in files:
            rel = path.relative_to(root).as_posix()
            if rel == "expert.yaml":
                continue  # written via manifest dump
            arc = _arcname_for(rel)
            add_bytes(arc, path.read_bytes())

        expert_yaml_bytes = yaml.safe_dump(
            manifest.to_yaml_dict(),
            allow_unicode=True,
            sort_keys=False,
        ).encode("utf-8")
        add_bytes("manifest/expert.yaml", expert_yaml_bytes)

        for dep_name in ("python-requirements.txt", "npm-global.txt", "system-packages.txt"):
            arc = f"dependencies/{dep_name}"
            try:
                zf.getinfo(arc)
            except KeyError:
                src = root / dep_name
                add_bytes(arc, src.read_bytes() if src.is_file() else b"")

        add_bytes("sbom/bom.cdx.json", json.dumps(sbom, ensure_ascii=False, indent=2).encode("utf-8"))
        add_bytes("manifest/source.json", json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
        add_bytes(
            "manifest/evaluation.json",
            json.dumps(evaluation_payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )
        add_bytes(
            "manifest/provenance.json",
            json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )

        payload_digest = f"sha256:{payload_hasher.hexdigest()}"
        signature = sign_digest(payload_digest, mode=sig_mode)
        add_bytes(
            "signature/signature.json",
            json.dumps(signature, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
            into_payload=False,
        )
        add_bytes(
            "signature/certificate.pem",
            f"# mode={sig_mode}\n".encode("utf-8"),
            into_payload=False,
        )

        checksum_content = ("\n".join(sorted(checksum_lines)) + "\n").encode("utf-8")
        info = zipfile.ZipInfo("manifest/checksums.sha256")
        info.date_time = datetime.fromtimestamp(epoch, tz=timezone.utc).timetuple()[:6]
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, checksum_content)

        bundle_meta = BundleManifest(
            expert_id=expert_id,
            expert_version=version,
            payload_digest=payload_digest,
            source_digest=source_digest,
            source_commit=commit,
            source_path=f"expert-templates/{expert_id}",
            build_tool_version=__version__,
            runtime={
                "engine": manifest.runtime.engine,
                "compatibility": (manifest.runtime.compatibility or {}).get("hermes", ""),
            },
            evaluation_digest=evaluation_payload.get("evaluation_digest"),
            signature_mode=sig_mode,
            dev=dev,
        )
        meta_bytes = json.dumps(bundle_meta.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True).encode(
            "utf-8"
        )
        info = zipfile.ZipInfo("manifest/bundle.json")
        info.date_time = datetime.fromtimestamp(epoch, tz=timezone.utc).timetuple()[:6]
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, meta_bytes)

    bundle_sha = sha256_bytes(bundle_path.read_bytes())
    sha_path.write_text(f"{bundle_sha}  {bundle_name}\n", encoding="utf-8")
    build_report = {
        "expert_id": expert_id,
        "version": version,
        "bundle": str(bundle_path),
        "sha256": bundle_sha,
        "payload_digest": payload_digest,
        "source_digest": source_digest,
        "built_at": built_at,
        "dev": dev,
        "signature_mode": sig_mode,
        "skip_runtime_evaluation": skip_runtime_evaluation,
        "validation": report.to_dict(),
    }
    build_json_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return build_report
