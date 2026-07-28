from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from workcopilot_expert_factory.adapters.schema_loader import validate_against
from workcopilot_expert_factory.models import ExpertManifest
from workcopilot_expert_factory.validators.dependencies import validate_dependencies
from workcopilot_expert_factory.validators.permissions import validate_permissions
from workcopilot_expert_factory.validators.security import check_paths, scan_secrets

ValidateLevel = Literal[
    "structure",
    "schema",
    "security",
    "dependencies",
    "runtime",
    "release",
    "full",
]

V1_SCHEMA = "workcopilot.expert.v1"
LEGACY_INFRA = frozenset({"base", "default"})
PACKAGE_SCHEMA_HINT = "schema_version"

UNSAFE_PATH_PARTS = ("..",)
EXCLUDED_RUNTIME_NAMES = {
    ".env",
    "sessions",
    "logs",
    "webui",
    "hindsight",
    "memories",
    "obsidian-vault",
}

# keep aliases for older imports
_scan_secrets = scan_secrets
_check_paths = check_paths
_validate_permissions = validate_permissions

SKILL_REQUIRED_SECTIONS = [
    "# 技能目标",
    "# 适用条件",
    "# 前置检查",
    "# 执行流程",
    "# 工具调用规则",
    "# 输出要求",
    "# 异常处理",
    "# 禁止事项",
    "# 引用资料",
]

DOC_NAMES = frozenset({"SOUL.md", "AGENT.md", "AGENTS.md", "SKILL.md"})
ALLOWED_CTRL = frozenset({9, 10, 13})
ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff", "\u00ad")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n?", re.DOTALL)


@dataclass
class Issue:
    level: Literal["error", "warning"]
    code: str
    message: str
    path: str | None = None


@dataclass
class ValidationReport:
    expert_path: str
    level: str
    legacy: bool = False
    passed: bool = True
    issues: list[Issue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def add(self, level: Literal["error", "warning"], code: str, message: str, path: str | None = None) -> None:
        self.issues.append(Issue(level=level, code=code, message=message, path=path))
        if level == "error":
            self.passed = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "expert_path": self.expert_path,
            "level": self.level,
            "legacy": self.legacy,
            "passed": self.passed,
            "summary": self.summary,
            "issues": [issue.__dict__ for issue in self.issues],
        }


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text.startswith("---"):
        return None, text
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    raw = match.group(0)
    inner = raw.strip()
    if inner.startswith("---"):
        inner = inner[3:]
    if inner.endswith("---"):
        inner = inner[:-3]
    inner = inner.strip()
    meta = yaml.safe_load(inner) or {}
    body = text[match.end() :]
    return meta if isinstance(meta, dict) else None, body


def _is_v1_manifest(data: dict[str, Any]) -> bool:
    return data.get("schema_version") == V1_SCHEMA


def _check_doc_chars(root: Path, report: ValidationReport, require_zh: bool) -> None:
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name in DOC_NAMES):
        rel = str(path.relative_to(root)).replace("\\", "/")
        data = path.read_bytes()
        for i, byte in enumerate(data):
            if byte < 32 and byte not in ALLOWED_CTRL:
                report.add("error", "DOC_CONTROL_CHAR", f"control char U+{byte:04X}", rel)
                break
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            report.add("error", "DOC_ENCODING", f"invalid UTF-8: {exc}", rel)
            continue
        for ch in ZERO_WIDTH:
            if ch in text:
                report.add("error", "DOC_ZERO_WIDTH", f"zero-width/BOM U+{ord(ch):04X}", rel)
        if require_zh:
            body = FRONTMATTER_RE.sub("", text, count=1)
            body = re.sub(r"```.*?```", "", body, flags=re.DOTALL).strip()
            if body and not CJK_RE.search(body):
                report.add("error", "DOC_REQUIRE_ZH", "body must contain Simplified Chinese", rel)


def _validate_structure(root: Path, report: ValidationReport) -> dict[str, Any] | None:
    expert_yaml = root / "expert.yaml"
    if not expert_yaml.is_file():
        report.legacy = True
        report.add("warning", "LEGACY_EXPERT", "missing workcopilot.expert.v1 expert.yaml; legacy mode")
        soul_ok = (
            (root / "SOUL.md").is_file()
            or (root / "runtime" / "SOUL.md").is_file()
            or (root / "root" / "SOUL.md").is_file()
        )
        if not soul_ok:
            report.add("error", "EXPERT_NOT_FOUND", "missing SOUL.md (root, runtime/, or root/ for teams)")
        if (root / "team.yaml").is_file():
            if not (root / "root").is_dir():
                report.add("error", "TEAM_LAYOUT", "team template missing root/")
            if not (root / "profiles").is_dir():
                report.add("error", "TEAM_LAYOUT", "team template missing profiles/")
        return None

    data = _load_yaml(expert_yaml)
    if not isinstance(data, dict):
        report.add("error", "EXPERT_SCHEMA_INVALID", "expert.yaml must be a mapping")
        return None

    if not _is_v1_manifest(data):
        report.legacy = True
        report.add(
            "warning",
            "LEGACY_EXPERT",
            f"expert.yaml schema_version is not {V1_SCHEMA}; treating as legacy/package manifest",
        )
        soul_ok = (
            (root / "SOUL.md").is_file()
            or (root / "runtime" / "SOUL.md").is_file()
            or (root / "root" / "SOUL.md").is_file()
        )
        if not soul_ok:
            report.add("error", "EXPERT_NOT_FOUND", "missing SOUL.md (root, runtime/, or root/ for teams)")
        if (root / "team.yaml").is_file():
            if not (root / "root").is_dir():
                report.add("error", "TEAM_LAYOUT", "team template missing root/")
            if not (root / "profiles").is_dir():
                report.add("error", "TEAM_LAYOUT", "team template missing profiles/")
        return data

    meta = data.get("metadata") or {}
    expert_id = meta.get("id")
    if expert_id and expert_id != root.name:
        report.add("error", "EXPERT_ID_MISMATCH", f"metadata.id={expert_id!r} != directory {root.name!r}")

    runtime = data.get("runtime") or {}
    entry = (runtime.get("entrypoints") or {})
    soul_rel = entry.get("soul", "SOUL.md")
    if not (root / soul_rel).is_file():
        report.add("error", "COMPONENT_MISSING", f"missing soul entrypoint: {soul_rel}", soul_rel)

    if runtime.get("mode") == "team":
        for req in ("team.yaml", "root", "profiles"):
            target = root / req
            if req.endswith(".yaml"):
                if not target.is_file():
                    report.add("error", "TEAM_LAYOUT", f"team mode missing {req}")
            elif not target.is_dir():
                report.add("error", "TEAM_LAYOUT", f"team mode missing {req}/")

    components = data.get("components") or {}
    for kind in ("skills", "tools", "plugins"):
        for item in components.get(kind) or []:
            if not isinstance(item, dict):
                continue
            rel = item.get("path")
            if not rel:
                report.add("error", "COMPONENT_MISSING", f"{kind} entry missing path")
                continue
            target = root / rel
            if not target.exists():
                report.add("error", "COMPONENT_MISSING", f"missing {kind} path: {rel}", rel)
            elif kind == "skills" and not (target / "SKILL.md").is_file() and target.is_dir():
                report.add("error", "COMPONENT_MISSING", f"skill missing SKILL.md: {rel}", rel)

    for item in components.get("policies") or []:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        if rel and not (root / rel).is_file():
            report.add("error", "COMPONENT_MISSING", f"missing policy: {rel}", rel)

    return data


def _validate_schema(root: Path, data: dict[str, Any], report: ValidationReport) -> ExpertManifest | None:
    errors = validate_against("expert-v1.schema.json", data)
    for err in errors:
        report.add("error", "EXPERT_SCHEMA_INVALID", err, "expert.yaml")
    if errors:
        return None

    for slot in data.get("connector_slots") or []:
        if not isinstance(slot, dict):
            report.add("error", "CONNECTOR_SLOT_INVALID", "slot must be object")
            continue
        slot_errors = validate_against("connector-slot-v1.schema.json", slot)
        for err in slot_errors:
            report.add("error", "CONNECTOR_SLOT_INVALID", err, f"connector_slots/{slot.get('id')}")

    # skills frontmatter
    for item in (data.get("components") or {}).get("skills") or []:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        if not rel:
            continue
        skill_md = root / rel / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        skill_rel = str(skill_md.relative_to(root)).replace("\\", "/")
        if not meta or meta.get("schema_version") != "workcopilot.skill.v1":
            report.add("error", "SKILL_SCHEMA_INVALID", "missing workcopilot.skill.v1 frontmatter", skill_rel)
            continue
        skill_errors = validate_against("skill-v1.schema.json", meta)
        for err in skill_errors:
            report.add("error", "SKILL_SCHEMA_INVALID", err, skill_rel)
        if meta.get("id") and item.get("id") and meta["id"] != item["id"]:
            report.add(
                "error",
                "SKILL_SCHEMA_INVALID",
                f"skill id {meta['id']!r} != component id {item['id']!r}",
                skill_rel,
            )
        if not meta.get("kind"):
            report.add(
                "warning",
                "SKILL_KIND_MISSING",
                "skill missing kind; required for publish (procedural|general|tool|connector|policy)",
                skill_rel,
            )
        missing = [sec for sec in SKILL_REQUIRED_SECTIONS if sec not in body]
        if missing:
            report.add(
                "warning",
                "SKILL_BODY_SECTIONS",
                f"missing recommended sections: {', '.join(missing)}",
                skill_rel,
            )

    eval_suite = (data.get("evaluations") or {}).get("suite")
    if eval_suite:
        suite_path = root / eval_suite
        if suite_path.is_file():
            suite = _load_yaml(suite_path)
            if isinstance(suite, dict):
                suite_errors = validate_against("evaluation-suite-v1.schema.json", suite)
                for err in suite_errors:
                    report.add("error", "EVAL_SUITE_INVALID", err, eval_suite)
        else:
            report.add("warning", "EVAL_SUITE_MISSING", f"evaluation suite not found: {eval_suite}", eval_suite)

    try:
        return ExpertManifest.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        report.add("error", "EXPERT_SCHEMA_INVALID", f"pydantic: {exc}", "expert.yaml")
        return None


def _validate_release_gates(root: Path, data: dict[str, Any], report: ValidationReport) -> None:
    release = data.get("release") or {}
    if not release.get("publishable", True):
        report.add("error", "E_RELEASE_BUNDLE_REQUIRED", "release.publishable is false")
    if not (release.get("registry") or {}):
        report.add(
            "warning",
            "RELEASE_REGISTRY_MISSING",
            "release.registry missing; Dev Bundle allowed, publish forbidden until filled",
        )
    # evaluation digest binding checked at build time; here ensure suite exists
    suite = (data.get("evaluations") or {}).get("suite") or "evaluations/cases.yaml"
    if not (root / suite).is_file():
        report.add("error", "E_EVALUATION_REQUIRED", f"missing evaluation suite: {suite}", suite)


def validate_branch(path: Path | str, level: ValidateLevel = "full") -> ValidationReport:
    root = Path(path).resolve()
    report = ValidationReport(expert_path=str(root), level=level)
    branch_yaml = root / "branch.yaml"
    if not branch_yaml.is_file():
        report.add("error", "E_BRANCH_NOT_FOUND", "missing branch.yaml")
        return report
    data = _load_yaml(branch_yaml)
    if not isinstance(data, dict):
        report.add("error", "E_SCHEMA_INVALID", "branch.yaml must be a mapping")
        return report
    errors = validate_against("expert-branch-v1.schema.json", data)
    for err in errors:
        report.add("error", "E_SCHEMA_INVALID", err, "branch.yaml")
    state = (data.get("state") or {}).get("sync_state")
    report.summary["sync_state"] = state
    if state == "conflicted":
        report.add("error", "E_BRANCH_CONFLICT", "branch is conflicted; resolve before build/publish")
    overlay = root / "overlay"
    if not overlay.is_dir():
        report.add("warning", "BRANCH_OVERLAY", "overlay/ directory missing")
    return report


def validate_expert(path: Path | str, level: ValidateLevel = "full") -> ValidationReport:
    root = Path(path).resolve()

    # Bundle file
    if root.is_file() and (
        root.name.endswith(".expert.bundle") or root.suffix in {".bundle", ".zip"}
    ):
        from workcopilot_expert_factory.validators.bundle import validate_bundle

        return validate_bundle(root, level=level if level != "structure" else "full")

    report = ValidationReport(expert_path=str(root), level=level)
    if not root.is_dir():
        report.add("error", "EXPERT_NOT_FOUND", f"expert directory not found: {root}")
        return report

    # Expert Branch directory
    if (root / "branch.yaml").is_file():
        return validate_branch(root, level=level)

    require_zh = root.name not in LEGACY_INFRA
    data = _validate_structure(root, report)
    report.summary["directory"] = root.name

    run_schema = level in {"schema", "security", "dependencies", "runtime", "release", "full"}
    run_security = level in {"security", "runtime", "release", "full"}
    run_deps = level in {"dependencies", "release", "full"}
    run_release = level in {"release", "full"}
    run_docs = level in {"full", "release", "runtime"}

    if level == "structure" and report.legacy:
        _check_doc_chars(root, report, require_zh=require_zh)
        return report

    if run_schema and data and _is_v1_manifest(data):
        manifest = _validate_schema(root, data, report)
        if manifest:
            report.summary["expert_id"] = manifest.metadata.id
            report.summary["version"] = manifest.metadata.version
            report.summary["mode"] = manifest.runtime.mode
            report.summary["skills"] = len(manifest.components.skills)
            report.summary["connector_slots"] = len(manifest.connector_slots)

    if run_security:
        scan_secrets(root, report, as_warning=report.legacy)
        check_paths(root, report)
        # sessions/logs warning
        for name in ("sessions", "logs", "webui"):
            if (root / name).is_dir():
                report.add("warning", "RUNTIME_DIR", f"runtime dir present: {name}", name)
        if data and _is_v1_manifest(data):
            validate_permissions(data, report)

    if run_deps:
        validate_dependencies(root, report, release_mode=level in {"release", "full"})

    if run_release and data and _is_v1_manifest(data):
        _validate_release_gates(root, data, report)

    if run_docs:
        _check_doc_chars(root, report, require_zh=require_zh)
        if data and _is_v1_manifest(data) and "expert_id" not in report.summary:
            _validate_schema(root, data, report)
            validate_permissions(data, report)

    return report
