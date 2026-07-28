from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory import __version__
from workcopilot_expert_factory.errors import ValidationFailed
from workcopilot_expert_factory.models import BundleManifest, ExpertManifest
from workcopilot_expert_factory.services.evaluate import load_latest_evaluation
from workcopilot_expert_factory.validators.expert import validate_expert

RUNTIME_INCLUDE = (
    "SOUL.md",
    "AGENT.md",
    "AGENTS.md",
    "config.patch.yaml",
    "team.yaml",
    "root",
    "profiles",
    "skills",
    "tools",
    "plugins",
    "mcp",
    "policies",
    "skill-bundles",
    "gbrain",
    "connectors",
    "workspace",
)

SKIP_NAMES = {
    ".git",
    ".env",
    "__pycache__",
    ".pytest_cache",
    "sessions",
    "logs",
    "webui",
    "node_modules",
    ".workcopilot",
}


def _git_commit(root: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def _iter_files(expert_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(expert_root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(expert_root).parts
        if any(part in SKIP_NAMES for part in rel_parts):
            continue
        if path.name.endswith(".pyc"):
            continue
        files.append(path)
    return files


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_expert_bundle(
    expert_path: Path | str,
    output_dir: Path | str,
    *,
    dev: bool = True,
    skip_runtime_evaluation: bool = True,
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

    evaluation_payload: dict[str, Any]
    require_eval = (not dev) or (not skip_runtime_evaluation)
    if require_eval:
        evaluation_payload = load_latest_evaluation(root) or {}
        if not evaluation_payload:
            raise ValidationFailed(
                "release build requires evaluation.json; run: "
                f"scripts/expert/expert evaluate {root} --mode full"
            )
        if not evaluation_payload.get("security_gates_passed", False):
            raise ValidationFailed("evaluation security gates failed; cannot release")
        if not evaluation_payload.get("passed", False):
            raise ValidationFailed("evaluation did not pass; cannot release")
        if float(evaluation_payload.get("score") or 0) < minimum:
            raise ValidationFailed(
                f"evaluation score {evaluation_payload.get('score')} < minimum_score {minimum}"
            )
        evaluation_payload = {
            **evaluation_payload,
            "skipped": False,
            "embedded_at_build": True,
        }
    else:
        evaluation_payload = {
            "skipped": True,
            "reason": "dev build with --skip-runtime-evaluation",
            "dev": True,
        }

    bundle_name = f"{expert_id}-{version}.expert.bundle"
    bundle_path = out_dir / bundle_name
    build_json_path = out_dir / f"{expert_id}-{version}.build.json"
    sha_path = out_dir / f"{expert_id}-{version}.sha256"

    files = _iter_files(root)
    checksum_lines: list[str] = []
    payload_hasher = hashlib.sha256()

    # deterministic zip
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    if epoch <= 0:
        epoch = int(datetime(1980, 1, 1, tzinfo=timezone.utc).timestamp())

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # manifest/expert.yaml
        expert_yaml_bytes = yaml.safe_dump(
            manifest.to_yaml_dict(),
            allow_unicode=True,
            sort_keys=False,
        ).encode("utf-8")

        def add_bytes(arcname: str, content: bytes) -> None:
            info = zipfile.ZipInfo(arcname)
            info.date_time = datetime.fromtimestamp(epoch, tz=timezone.utc).timetuple()[:6]
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, content)
            digest = _sha256_bytes(content)
            checksum_lines.append(f"{digest}  {arcname}")
            payload_hasher.update(arcname.encode("utf-8"))
            payload_hasher.update(b"\0")
            payload_hasher.update(content)

        add_bytes("manifest/expert.yaml", expert_yaml_bytes)

        # runtime + docs + evaluations from source
        for path in files:
            rel = path.relative_to(root).as_posix()
            # skip packaging factory-only drafts
            if rel.startswith("dist/"):
                continue
            arc = f"runtime/{rel}" if rel not in {"README.md"} and not rel.startswith("docs/") else (
                f"docs/{Path(rel).name}" if rel == "README.md" or rel.startswith("docs/") else f"runtime/{rel}"
            )
            if rel.startswith("docs/"):
                arc = rel
            elif rel == "README.md":
                arc = "docs/README.md"
            elif rel.startswith("evaluations/"):
                arc = rel
            elif rel == "expert.yaml":
                continue
            else:
                arc = f"runtime/{rel}"
            add_bytes(arc, path.read_bytes())

        # dependencies stubs
        for dep_name in ("python-requirements.txt", "npm-global.txt", "system-packages.txt"):
            src = root / dep_name
            content = src.read_bytes() if src.is_file() else b""
            add_bytes(f"dependencies/{dep_name}", content)

        sbom = {
            "schema_version": "workcopilot.sbom.v1",
            "expert_id": expert_id,
            "expert_version": version,
            "components": [
                {"path": p.relative_to(root).as_posix(), "type": "file"} for p in files if p.name != "expert.yaml"
            ],
        }
        add_bytes("sbom/components.json", json.dumps(sbom, ensure_ascii=False, indent=2).encode("utf-8"))

        source = {
            "source_path": str(root),
            "source_commit": _git_commit(root),
            "built_at": datetime.now(timezone.utc).isoformat(),
            "dev": dev,
        }
        add_bytes("manifest/source.json", json.dumps(source, ensure_ascii=False, indent=2).encode("utf-8"))

        evaluation = evaluation_payload
        add_bytes("manifest/evaluation.json", json.dumps(evaluation, ensure_ascii=False, indent=2).encode("utf-8"))

        checksum_content = ("\n".join(sorted(checksum_lines)) + "\n").encode("utf-8")
        # checksum file itself excluded from its own listing digest update already done per file;
        # write checksums after collecting
        info = zipfile.ZipInfo("manifest/checksums.sha256")
        info.date_time = datetime.fromtimestamp(epoch, tz=timezone.utc).timetuple()[:6]
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, checksum_content)

        payload_digest = f"sha256:{payload_hasher.hexdigest()}"
        bundle_meta = BundleManifest(
            expert_id=expert_id,
            expert_version=version,
            payload_digest=payload_digest,
            source_commit=source["source_commit"],
            source_path=str(root),
            build_tool_version=__version__,
            runtime={
                "engine": manifest.runtime.engine,
                "compatibility": (manifest.runtime.compatibility or {}).get("hermes", ""),
            },
            dev=dev,
        )
        add_bytes_meta = bundle_meta.model_dump(mode="json")
        meta_bytes = json.dumps(add_bytes_meta, ensure_ascii=False, indent=2).encode("utf-8")
        info = zipfile.ZipInfo("manifest/bundle.json")
        info.date_time = datetime.fromtimestamp(epoch, tz=timezone.utc).timetuple()[:6]
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, meta_bytes)

    bundle_sha = _sha256_bytes(bundle_path.read_bytes())
    sha_path.write_text(f"{bundle_sha}  {bundle_name}\n", encoding="utf-8")
    build_report = {
        "expert_id": expert_id,
        "version": version,
        "bundle": str(bundle_path),
        "sha256": bundle_sha,
        "payload_digest": payload_digest,
        "dev": dev,
        "skip_runtime_evaluation": skip_runtime_evaluation,
        "validation": report.to_dict(),
    }
    build_json_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return build_report
