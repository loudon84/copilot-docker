"""Expert Bundle ZIP validation (PRD §13.8)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from workcopilot_expert_factory.errors import BundleDigestMismatch, BundleInvalid, BundleSignatureInvalid
from workcopilot_expert_factory.validators.expert import ValidationReport, validate_expert

MAX_SINGLE_FILE = 50 * 1024 * 1024  # 50 MiB
MAX_TOTAL_UNCOMPRESSED = 500 * 1024 * 1024  # 500 MiB
MAX_COMPRESSION_RATIO = 100


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_bundle(
    bundle_path: Path | str,
    *,
    level: str = "full",
    verify_signature: bool = True,
) -> ValidationReport:
    path = Path(bundle_path).resolve()
    report = ValidationReport(expert_path=str(path), level=level)
    if not path.is_file():
        report.add("error", "E_BUNDLE_INVALID", f"bundle not found: {path}")
        return report

    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as exc:
        report.add("error", "E_BUNDLE_INVALID", f"not a valid zip: {exc}")
        return report

    with zf:
        names = zf.namelist()
        if len(names) != len(set(names)):
            report.add("error", "E_BUNDLE_INVALID", "duplicate zip entries")
        total_uncompressed = 0
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or name.startswith("\\") or ":/" in name[:3]:
                report.add("error", "E_PATH_UNSAFE", f"absolute path in zip: {name}")
            if ".." in name.split("/"):
                report.add("error", "E_PATH_UNSAFE", f"path escape in zip: {name}")
            if info.file_size > MAX_SINGLE_FILE:
                report.add("error", "E_BUNDLE_INVALID", f"file too large when uncompressed: {name}")
            total_uncompressed += info.file_size
            if info.compress_size > 0 and info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO:
                if info.file_size > 1024 * 1024:
                    report.add("error", "E_BUNDLE_INVALID", f"possible zip bomb: {name}")
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED:
            report.add("error", "E_BUNDLE_INVALID", "total uncompressed size exceeds limit")

        # checksums
        try:
            checksum_raw = zf.read("manifest/checksums.sha256").decode("utf-8")
        except KeyError:
            report.add("error", "E_BUNDLE_INVALID", "missing manifest/checksums.sha256")
            checksum_raw = ""

        expected: dict[str, str] = {}
        for line in checksum_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                expected[parts[1]] = parts[0]

        payload_hasher = hashlib.sha256()
        for name in sorted(n for n in names if not n.endswith("/")):
            if name in {"manifest/checksums.sha256", "manifest/bundle.json"}:
                continue
            data = zf.read(name)
            digest = _sha256_bytes(data)
            if name in expected and expected[name] != digest:
                report.add("error", "E_BUNDLE_DIGEST_MISMATCH", f"checksum mismatch: {name}")
            if name != "manifest/bundle.json":
                payload_hasher.update(name.encode("utf-8"))
                payload_hasher.update(b"\0")
                payload_hasher.update(data)

        # Note: payload digest in current builder includes files before bundle.json;
        # verify against declared bundle.json if present
        try:
            bundle_meta = json.loads(zf.read("manifest/bundle.json").decode("utf-8"))
            report.summary["bundle"] = {
                "expert_id": bundle_meta.get("expert_id"),
                "version": bundle_meta.get("expert_version"),
                "dev": bundle_meta.get("dev"),
                "payload_digest": bundle_meta.get("payload_digest"),
            }
        except KeyError:
            report.add("error", "E_BUNDLE_INVALID", "missing manifest/bundle.json")
            bundle_meta = {}

        if verify_signature and level in {"security", "release", "full"}:
            sig_mode = bundle_meta.get("signature_mode") or "none"
            if sig_mode != "none":
                try:
                    sig = json.loads(zf.read("signature/signature.json").decode("utf-8"))
                    if not sig.get("digest") and not sig.get("signature"):
                        report.add("error", "E_BUNDLE_SIGNATURE_INVALID", "empty signature")
                except KeyError:
                    report.add("error", "E_BUNDLE_SIGNATURE_INVALID", "missing signature/signature.json")
            elif not bundle_meta.get("dev", True) and level == "release":
                report.add("warning", "E_BUNDLE_SIGNATURE_INVALID", "release bundle uses signature_mode=none")

        if level in {"release", "full"}:
            if bundle_meta.get("dev"):
                report.add("error", "E_RELEASE_BUNDLE_REQUIRED", "dev bundle cannot pass release validation")
            try:
                evaluation = json.loads(zf.read("manifest/evaluation.json").decode("utf-8"))
                if evaluation.get("skipped"):
                    report.add("error", "E_EVALUATION_REQUIRED", "release bundle missing real evaluation")
            except KeyError:
                report.add("error", "E_EVALUATION_REQUIRED", "missing manifest/evaluation.json")

        # re-validate extracted runtime source (no script execution)
        if level in {"full", "release"} and report.passed:
            with tempfile.TemporaryDirectory(prefix="ef-bundle-") as tmp:
                tmp_path = Path(tmp)
                # extract only runtime/ + reconstruct expert.yaml
                for name in names:
                    if ".." in name.split("/"):
                        continue
                    if name.startswith("runtime/") or name in {
                        "manifest/expert.yaml",
                        "evaluations/cases.yaml",
                    }:
                        target = tmp_path / name
                        if name.startswith("runtime/"):
                            target = tmp_path / name[len("runtime/") :]
                        elif name == "manifest/expert.yaml":
                            target = tmp_path / "expert.yaml"
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(name) as src, target.open("wb") as dst:
                            dst.write(src.read())
                if (tmp_path / "expert.yaml").is_file():
                    import yaml

                    expert_data = yaml.safe_load((tmp_path / "expert.yaml").read_text(encoding="utf-8")) or {}
                    eid = ((expert_data.get("metadata") or {}).get("id")) or "expert"
                    named = tmp_path / eid
                    # move contents into id-named dir for id/dir consistency check
                    named.mkdir()
                    for child in list(tmp_path.iterdir()):
                        if child.name == eid:
                            continue
                        child.rename(named / child.name)
                    nested = validate_expert(named, level="schema")
                    for issue in nested.issues:
                        if issue.level == "error":
                            report.add(issue.level, issue.code, f"extracted: {issue.message}", issue.path)

    return report


def assert_bundle_valid(bundle_path: Path | str, *, release: bool = False) -> dict[str, Any]:
    level = "release" if release else "full"
    report = validate_bundle(bundle_path, level=level)
    if not report.passed:
        codes = {i.code for i in report.issues if i.level == "error"}
        if "E_BUNDLE_DIGEST_MISMATCH" in codes:
            raise BundleDigestMismatch("bundle digest mismatch", payload=report.to_dict())
        if "E_BUNDLE_SIGNATURE_INVALID" in codes:
            raise BundleSignatureInvalid("bundle signature invalid", payload=report.to_dict())
        raise BundleInvalid(
            "bundle validation failed: "
            + "; ".join(i.message for i in report.issues if i.level == "error")[:400],
            payload=report.to_dict(),
        )
    return report.to_dict()
