"""Expert Asset Branch — Copy-on-Write (PRD §12)."""

from __future__ import annotations

import difflib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.digest import compute_source_digest, iter_source_files
from workcopilot_expert_factory.errors import (
    BranchConflict,
    BranchNotFound,
    ExpertFactoryError,
    ExpertNotFound,
)
from workcopilot_expert_factory.models import (
    BranchManifest,
    BranchOverlay,
    BranchPermissions,
    BranchSource,
    BranchState,
    BranchTarget,
)

PROTECTED_PATH_HINTS = (
    "permissions",
    "access_mode",
    "maximum_classification",
    "export_allowed",
    "required_gates",
    "publishable",
    "secret",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3].parent


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def branch_dir(expert_id: str, branch_id: str, repo: Path | None = None) -> Path:
    root = repo or _repo_root()
    return root / ".workcopilot" / "branches" / expert_id / branch_id


def create_branch(
    source: Path,
    *,
    name: str,
    target_id: str | None = None,
    created_by: str = "local",
) -> dict[str, Any]:
    src = source.resolve()
    if not (src / "expert.yaml").is_file():
        raise ExpertNotFound(f"source expert missing expert.yaml: {src}")
    data = _load_yaml(src / "expert.yaml")
    expert_id = data["metadata"]["id"]
    version = data["metadata"]["version"]
    digest = compute_source_digest(src, iter_source_files(src))
    branch_id = name
    target = target_id or f"{branch_id}"
    dest = branch_dir(expert_id, branch_id)
    if dest.exists():
        raise ExpertFactoryError(f"branch already exists: {dest}", code="OUTPUT_EXISTS")

    overlay = dest / "overlay"
    overlay.mkdir(parents=True)
    (dest / "reports").mkdir(parents=True)
    _write_yaml(dest / "deleted-files.yaml", {"files": []})

    manifest = BranchManifest(
        metadata={
            "branch_id": branch_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by,
        },
        source=BranchSource(expert_id=expert_id, version=version, source_digest=digest),
        target=BranchTarget(expert_id=target, version="1.0.0"),
        state=BranchState(sync_state="synced", base_digest=digest, head_digest=digest),
        overlay=BranchOverlay(files=[], deleted_files=[]),
        permissions=BranchPermissions(allow_expansion=False),
    )
    _write_yaml(dest / "branch.yaml", manifest.to_yaml_dict())
    # record source pointer
    (dest / "SOURCE").write_text(str(src), encoding="utf-8")
    return {"branch_path": str(dest), "branch": manifest.to_yaml_dict()}


def _read_branch(path: Path) -> tuple[dict[str, Any], Path]:
    root = path.resolve()
    if not (root / "branch.yaml").is_file():
        raise BranchNotFound(f"branch.yaml not found: {root}")
    data = _load_yaml(root / "branch.yaml")
    source_ptr = root / "SOURCE"
    if source_ptr.is_file():
        source_path = Path(source_ptr.read_text(encoding="utf-8").strip())
    else:
        expert_id = data["source"]["expert_id"]
        source_path = _repo_root() / "expert-templates" / expert_id
    return data, source_path


def branch_status(path: Path) -> dict[str, Any]:
    data, source_path = _read_branch(path)
    if not source_path.is_dir():
        raise ExpertNotFound(f"source expert missing: {source_path}")
    current = compute_source_digest(source_path, iter_source_files(source_path))
    base = data["state"]["base_digest"]
    overlay_files = list((data.get("overlay") or {}).get("files") or [])
    # also discover overlay dir
    overlay_dir = path / "overlay"
    if overlay_dir.is_dir():
        for f in overlay_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(overlay_dir).as_posix()
                if rel not in overlay_files:
                    overlay_files.append(rel)

    if data["state"].get("sync_state") == "materialized":
        state = "materialized"
    elif current != base and overlay_files:
        # check conflicts
        conflicts = _detect_conflicts(source_path, path, base_digest=base)
        state = "conflicted" if conflicts else "diverged"
    elif current != base:
        state = "behind"
    else:
        state = "synced"

    data["state"]["sync_state"] = state
    data["state"]["head_digest"] = current
    data.setdefault("overlay", {})["files"] = overlay_files
    _write_yaml(path / "branch.yaml", data)
    return {
        "branch_path": str(path),
        "sync_state": state,
        "base_digest": base,
        "current_source_digest": current,
        "overlay_files": overlay_files,
    }


def _file_digest(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _detect_conflicts(source: Path, branch: Path, *, base_digest: str) -> list[str]:
    """Heuristic: overlay file also changed in source vs base snapshot — we don't keep base files,
    so treat same-path edits as conflict when source digest moved and overlay exists."""
    conflicts: list[str] = []
    overlay = branch / "overlay"
    if not overlay.is_dir():
        return conflicts
    # If source moved and overlay touches protected yaml keys → conflict
    for f in overlay.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(overlay).as_posix()
        src_file = source / rel
        if not src_file.is_file():
            continue
        if rel.endswith((".yaml", ".yml")):
            try:
                overlay_data = _load_yaml(f)
                src_data = _load_yaml(src_file)
            except Exception:  # noqa: BLE001
                conflicts.append(rel)
                continue
            if _yaml_protected_conflict(overlay_data, src_data):
                conflicts.append(rel)
            elif overlay_data != src_data:
                # both differ — mark diverged candidate; conflict if nested same keys differ
                if _deep_key_conflicts(overlay_data, src_data):
                    conflicts.append(rel)
        else:
            # markdown: if both exist and differ, conflict for manual merge when source changed
            if f.read_text(encoding="utf-8", errors="ignore") != src_file.read_text(
                encoding="utf-8", errors="ignore"
            ):
                # only conflict if source digest changed from base (caller ensures)
                conflicts.append(rel)
    return conflicts


def _yaml_protected_conflict(a: Any, b: Any) -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    for key in set(a) | set(b):
        if any(h in str(key).lower() for h in PROTECTED_PATH_HINTS):
            if a.get(key) != b.get(key):
                return True
        va, vb = a.get(key), b.get(key)
        if isinstance(va, dict) and isinstance(vb, dict) and _yaml_protected_conflict(va, vb):
            return True
    return False


def _deep_key_conflicts(a: Any, b: Any, path: str = "") -> bool:
    if type(a) != type(b):
        return True
    if isinstance(a, dict):
        for k in set(a) & set(b):
            if _deep_key_conflicts(a[k], b[k], f"{path}.{k}"):
                # both modified same key to different values — conflict if both are scalars differing
                if not isinstance(a[k], (dict, list)) and a[k] != b[k]:
                    return True
        return False
    return False


def branch_diff(path: Path) -> dict[str, Any]:
    data, source_path = _read_branch(path)
    status = branch_status(path)
    diffs: list[dict[str, Any]] = []
    overlay = path / "overlay"
    if overlay.is_dir():
        for f in sorted(overlay.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(overlay).as_posix()
            src_file = source_path / rel
            left = src_file.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True) if src_file.is_file() else []
            right = f.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
            udiff = "".join(difflib.unified_diff(left, right, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
            diffs.append({"path": rel, "diff": udiff})

    report = {
        "status": status,
        "diffs": diffs,
    }
    (path / "reports" / "diff.json").write_text(
        __import__("json").dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = ["# Branch Diff", "", f"- sync_state: `{status['sync_state']}`", ""]
    for d in diffs:
        md.append(f"## {d['path']}\n\n```diff\n{d['diff']}\n```\n")
    (path / "reports" / "diff.md").write_text("\n".join(md), encoding="utf-8")
    return report


def _three_way_merge_text(base: str, source: str, branch: str) -> tuple[str, bool]:
    """Simple line-based 3-way merge. Returns (merged, conflicted)."""
    base_lines = base.splitlines(keepends=True)
    src_lines = source.splitlines(keepends=True)
    br_lines = branch.splitlines(keepends=True)
    if source == branch:
        return source, False
    if base == source:
        return branch, False
    if base == branch:
        return source, False
    # conflict
    merged = (
        "<<<<<<< source\n"
        + source
        + ("\n" if not source.endswith("\n") else "")
        + "=======\n"
        + branch
        + ("\n" if not branch.endswith("\n") else "")
        + ">>>>>>> branch\n"
    )
    return merged, True


def _three_way_merge_yaml(base: Any, source: Any, branch: Any) -> tuple[Any, bool]:
    if base == source:
        return branch, False
    if base == branch:
        return source, False
    if source == branch:
        return source, False
    if isinstance(source, dict) and isinstance(branch, dict) and isinstance(base, dict):
        out: dict[str, Any] = {}
        conflicted = False
        keys = set(base) | set(source) | set(branch)
        for k in keys:
            bv, sv, brv = base.get(k, None), source.get(k, None), branch.get(k, None)
            if sv == brv:
                out[k] = sv
            elif bv == sv:
                out[k] = brv
            elif bv == brv:
                out[k] = sv
            elif isinstance(sv, dict) and isinstance(brv, dict):
                merged, c = _three_way_merge_yaml(bv if isinstance(bv, dict) else {}, sv, brv)
                out[k] = merged
                conflicted = conflicted or c
            else:
                # protected keys → force conflict
                if any(h in str(k).lower() for h in PROTECTED_PATH_HINTS):
                    conflicted = True
                    out[k] = {"__conflict__": {"source": sv, "branch": brv}}
                else:
                    conflicted = True
                    out[k] = {"__conflict__": {"source": sv, "branch": brv}}
        return out, conflicted
    return {"__conflict__": {"source": source, "branch": branch}}, True


def branch_rebase(path: Path, *, onto: Path | None = None) -> dict[str, Any]:
    data, source_path = _read_branch(path)
    onto_path = onto.resolve() if onto else source_path
    if not onto_path.is_dir():
        raise ExpertNotFound(f"rebase onto missing: {onto_path}")

    # We don't store full base tree; approximate: treat current onto files as source-head,
    # overlay as branch-head, and previous digest inequality as base!=source.
    overlay = path / "overlay"
    conflicts: list[str] = []
    if overlay.is_dir():
        for f in list(overlay.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(overlay).as_posix()
            src_file = onto_path / rel
            branch_text = f.read_text(encoding="utf-8", errors="ignore")
            source_text = src_file.read_text(encoding="utf-8", errors="ignore") if src_file.is_file() else ""
            base_text = source_text  # without historical base, prefer overlay keep on soft paths
            if rel.endswith((".yaml", ".yml")):
                try:
                    merged, c = _three_way_merge_yaml(
                        _load_yaml(src_file) if src_file.is_file() else {},
                        _load_yaml(src_file) if src_file.is_file() else {},
                        _load_yaml(f),
                    )
                    # Since base≈source in approximation, merge yields branch; detect protected conflicts vs source
                    if c or _yaml_protected_conflict(
                        _load_yaml(src_file) if src_file.is_file() else {},
                        _load_yaml(f),
                    ):
                        # keep conflict markers in yaml dump
                        f.write_text(yaml.safe_dump(merged, allow_unicode=True), encoding="utf-8")
                        conflicts.append(rel)
                except Exception:  # noqa: BLE001
                    conflicts.append(rel)
            else:
                merged, c = _three_way_merge_text(base_text, source_text, branch_text)
                if c:
                    f.write_text(merged, encoding="utf-8")
                    conflicts.append(rel)

    new_digest = compute_source_digest(onto_path, iter_source_files(onto_path))
    data["state"]["base_digest"] = new_digest
    data["state"]["head_digest"] = new_digest
    data["source"]["source_digest"] = new_digest
    data["source"]["version"] = (_load_yaml(onto_path / "expert.yaml").get("metadata") or {}).get("version")
    if conflicts:
        data["state"]["sync_state"] = "conflicted"
        (path / "reports" / "conflict-report.md").write_text(
            "# Conflicts\n\n" + "\n".join(f"- {c}" for c in conflicts) + "\n",
            encoding="utf-8",
        )
        _write_yaml(path / "branch.yaml", data)
        raise BranchConflict(
            "branch rebase conflicts: " + ", ".join(conflicts),
            payload={"conflicts": conflicts, "branch_path": str(path)},
        )
    data["state"]["sync_state"] = "synced"
    _write_yaml(path / "branch.yaml", data)
    return {"branch_path": str(path), "sync_state": "synced", "base_digest": new_digest}


def materialize_branch(path: Path, output: Path) -> dict[str, Any]:
    data, source_path = _read_branch(path)
    status = branch_status(path)
    if status["sync_state"] == "conflicted":
        raise BranchConflict("resolve conflicts before materialize")
    if output.exists():
        raise ExpertFactoryError(f"output exists: {output}", code="OUTPUT_EXISTS")
    shutil.copytree(source_path, output, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    overlay = path / "overlay"
    if overlay.is_dir():
        for f in overlay.rglob("*"):
            if f.is_file():
                rel = f.relative_to(overlay)
                dest = output / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
    deleted = _load_yaml(path / "deleted-files.yaml") if (path / "deleted-files.yaml").is_file() else {}
    for rel in deleted.get("files") or []:
        target = output / rel
        if target.is_file():
            target.unlink()

    # rewrite expert id
    expert_yaml = output / "expert.yaml"
    edata = _load_yaml(expert_yaml)
    edata["metadata"]["id"] = data["target"]["expert_id"]
    edata["metadata"]["version"] = data["target"].get("version") or "1.0.0"
    edata.setdefault("provenance", {})
    edata["provenance"]["branch"] = {
        "branch_id": data["metadata"]["branch_id"],
        "base_version": data["source"]["version"],
        "base_digest": data["state"]["base_digest"],
    }
    edata["provenance"]["derived_from"] = {
        "expert_id": data["source"]["expert_id"],
        "version": data["source"]["version"],
    }
    # directory name sync
    if output.name != edata["metadata"]["id"]:
        edata["metadata"]["id"] = output.name
    _write_yaml(expert_yaml, edata)

    suite = output / "evaluations" / "cases.yaml"
    if suite.is_file():
        sdata = _load_yaml(suite)
        if isinstance(sdata, dict):
            sdata["expert_id"] = edata["metadata"]["id"]
            _write_yaml(suite, sdata)

    data["state"]["sync_state"] = "materialized"
    _write_yaml(path / "branch.yaml", data)
    return {
        "output": str(output),
        "expert_id": edata["metadata"]["id"],
        "version": edata["metadata"]["version"],
        "branch_path": str(path),
    }
