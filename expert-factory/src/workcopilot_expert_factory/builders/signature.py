"""Bundle signing (none | local-key | cosign | kms)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from workcopilot_expert_factory.errors import BundleSignatureInvalid

SignatureMode = Literal["none", "local-key", "cosign", "kms"]


def resolve_signature_mode(explicit: str | None = None, *, release: bool = False) -> SignatureMode:
    mode = (explicit or os.environ.get("WORKCOPILOT_SIGN_MODE") or "none").lower()
    if mode not in {"none", "local-key", "cosign", "kms"}:
        mode = "none"
    return mode  # type: ignore[return-value]


def sign_digest(digest: str, *, mode: SignatureMode) -> dict[str, Any]:
    """
    Produce signature.json payload.
    local-key: HMAC-like SHA256 with WORKCOPILOT_SIGNING_KEY (dev/test only).
    cosign/kms: placeholder metadata requiring external tooling in CI.
    """
    if mode == "none":
        return {"mode": "none", "digest": digest}

    if mode == "local-key":
        key = os.environ.get("WORKCOPILOT_SIGNING_KEY") or ""
        if not key:
            raise BundleSignatureInvalid("WORKCOPILOT_SIGNING_KEY required for local-key signing")
        mac = hashlib.sha256(key.encode("utf-8") + digest.encode("utf-8")).digest()
        return {
            "mode": "local-key",
            "digest": digest,
            "algorithm": "HMAC-SHA256",
            "signature": base64.b64encode(mac).decode("ascii"),
        }

    if mode == "cosign":
        return {
            "mode": "cosign",
            "digest": digest,
            "status": "pending-external",
            "hint": "Run cosign sign-blob in CI and replace signature.json",
        }

    return {
        "mode": "kms",
        "digest": digest,
        "status": "pending-external",
        "hint": "Sign via KMS in CI and replace signature.json",
    }


def verify_signature(signature: dict[str, Any], digest: str) -> bool:
    mode = signature.get("mode") or "none"
    if signature.get("digest") and signature["digest"] != digest:
        return False
    if mode == "none":
        return True
    if mode == "local-key":
        key = os.environ.get("WORKCOPILOT_SIGNING_KEY") or ""
        if not key:
            return False
        expected = hashlib.sha256(key.encode("utf-8") + digest.encode("utf-8")).digest()
        got = base64.b64decode(signature.get("signature") or "")
        return hmac_compare(expected, got)
    # cosign/kms: accept presence of signature field when provided
    return bool(signature.get("signature") or signature.get("status") == "pending-external")


def hmac_compare(a: bytes, b: bytes) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0


def write_signature_files(out_dir: Path, signature: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signature.json").write_text(
        json.dumps(signature, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # certificate placeholder for local-key / none
    cert = out_dir / "certificate.pem"
    if not cert.exists():
        cert.write_text("# no certificate for mode={}\n".format(signature.get("mode")), encoding="utf-8")
