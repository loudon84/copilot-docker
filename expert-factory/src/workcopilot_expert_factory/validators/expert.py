from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from workcopilot_expert_factory.adapters.schema_loader import validate_against
from workcopilot_expert_factory.models import ExpertManifest

ValidateLevel = Literal["structure", "schema", "security", "full"]

V1_SCHEMA = "workcopilot.expert.v1"
LEGACY_INFRA = frozenset({"base", "default"})
PACKAGE_SCHEMA_HINT = "schema_version"

SECRET_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|password|token|private[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{8,}"), "possible secret assignment"),
    (re.compile(r"(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key block"),
    (re.compile(r"(?i)\bsk-[A-Za-z0-9]{20,}\b"), "openai-like api key"),
]

FALSE_SECRET_RE = re.compile(
    r"(?i)("
    r"password\s*[:=]\s*$|"
    r"(password|token|secret|api[_-]?key)\s*:\s*(str|optional|bool|int|float|any|dict|none|true|false)|"
    r"(password|token|secret|api[_-]?key)\s*=\s*(session\.|self\.|auth\.|cfg\.|config\.|os\.|env\.|os\.environ|getenv|_|"
    r"None|True|False|\"\"|''|\{\}|\[\]|"
    r"your_|xxx|example|placeholder|changeme|TODO|FIXME)|"
    r"SQLBOT_PASSWORD|HERMES_.*PASSWORD|getenv\(|environ\[|"
    r"Field\(|Annotated\["
    r")"
)


def _looks_like_false_secret(snippet: str) -> bool:
    if FALSE_SECRET_RE.search(snippet):
        return True
    if re.search(r"(?i)(your_|xxx|example|placeholder|changeme|<|\blocal\b|\bnone\b|\bnull\b|\btest\b)", snippet):
        return True
    # code references / constructors / slices
    if re.search(
        r"(?i)[:=]\s*(str|int|float|bool|dict|list|Exception|Error|None|True|False|os\.|self\.|session\.|"
        r"config\.|getenv|environ|Field|Optional|Annotated)\b",
        snippet,
    ):
        return True
    if re.search(r"[:=]\s*[A-Za-z_][A-Za-z0-9_]*\s*[\(\[\.]", snippet):
        return True
    # empty / short placeholder values
    m = re.search(r"[:=]\s*['\"]?([^\s'\"]+)", snippet)
    if not m:
        return True
    val = m.group(1).rstrip(",;)]}")
    if len(val) < 8:
        return True
    if re.match(r"^[A-Za-z_][\w\.]*$", val) and not re.search(r"[0-9]{6,}", val):
        # identifier-like, not a hard-coded secret blob
        return True
    return False


def _scan_secrets(root: Path, report: ValidationReport, *, as_warning: bool = False) -> None:
    skip_dirs = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "egg-info"}
    level: Literal["error", "warning"] = "warning" if as_warning else "error"
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs or part.endswith(".egg-info") for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc", ".zip", ".tgz"}:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        name_l = path.name.lower()
        # examples / docs / tests / scripts helpers are allowed to mention password fields
        if (
            ".example." in name_l
            or name_l.endswith(".example")
            or name_l.endswith(".example.env")
            or "example.env" in name_l
            or "/docs/" in f"/{rel}/"
            or "/prd/" in f"/{rel}/"
            or "/tests/" in f"/{rel}/"
            or "/scripts/" in f"/{rel}/"
            or rel == "config.yaml"
            or rel.endswith("/config.yaml")
        ):
            continue
        if name_l == ".env" or (name_l.endswith(".env") and "example" not in name_l):
            report.add(level, "SECRET_DETECTED", "env file must not ship in expert source", rel)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, label in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                snippet = match.group(0)
                if _looks_like_false_secret(snippet):
                    continue
                # private key blocks are always real
                if "PRIVATE KEY" in snippet.upper():
                    report.add(level, "SECRET_DETECTED", label, rel)
                    break
                # require high-entropy-ish value after assignment
                val_m = re.search(r"[:=]\s*['\"]?([^\s'\"]+)", snippet)
                if not val_m:
                    continue
                val = val_m.group(1)
                if val.lower() in {"true", "false", "none", "null", "password", "secret", "token"}:
                    continue
                if re.match(r"^[A-Za-z_][A-Za-z0-9_\.]*$", val) and "." in val:
                    # attribute / env key reference
                    continue
                report.add(level, "SECRET_DETECTED", f"{label}: {snippet[:48]}", rel)
                break
            else:
                continue
            break

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


def _check_paths(root: Path, report: ValidationReport) -> None:
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        parts = rel.parts
        if any(p == ".." for p in parts):
            report.add("error", "PATH_UNSAFE", "path escape detected", str(rel))
        if path.is_symlink():
            target = path.resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                report.add("error", "PATH_UNSAFE", "symlink escapes expert root", str(rel))
        name = path.name.lower()
        if name in EXCLUDED_RUNTIME_NAMES and path.is_dir() and rel.parts[0] in EXCLUDED_RUNTIME_NAMES:
            # memories may exist in templates historically; warn only for sessions/logs
            if name in {"sessions", "logs", "webui"}:
                report.add("warning", "RUNTIME_DIR", f"runtime dir present: {name}", str(rel).replace("\\", "/"))


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


def _validate_permissions(data: dict[str, Any], report: ValidationReport) -> None:
    perms = data.get("permissions") or {}
    tools = perms.get("tools") or {}
    if tools.get("default") != "deny":
        report.add("error", "PERMISSION_DEFAULT", "permissions.tools.default must be deny")
    network = perms.get("network") or {}
    if network.get("default") != "deny":
        report.add("error", "PERMISSION_DEFAULT", "permissions.network.default must be deny")


def validate_expert(path: Path | str, level: ValidateLevel = "full") -> ValidationReport:
    root = Path(path).resolve()
    report = ValidationReport(expert_path=str(root), level=level)
    if not root.is_dir():
        report.add("error", "EXPERT_NOT_FOUND", f"expert directory not found: {root}")
        return report

    require_zh = root.name not in LEGACY_INFRA
    data = _validate_structure(root, report)
    report.summary["directory"] = root.name

    if level in {"structure"} and report.legacy:
        _check_doc_chars(root, report, require_zh=require_zh)
        return report

    if level in {"schema", "security", "full"} and data and _is_v1_manifest(data):
        manifest = _validate_schema(root, data, report)
        if manifest:
            report.summary["expert_id"] = manifest.metadata.id
            report.summary["version"] = manifest.metadata.version
            report.summary["mode"] = manifest.runtime.mode
            report.summary["skills"] = len(manifest.components.skills)
            report.summary["connector_slots"] = len(manifest.connector_slots)

    if level in {"security", "full"}:
        _scan_secrets(root, report, as_warning=report.legacy)
        _check_paths(root, report)
        if data and _is_v1_manifest(data):
            _validate_permissions(data, report)

    if level == "full":
        _check_doc_chars(root, report, require_zh=require_zh)
        if data and _is_v1_manifest(data):
            # full also re-runs schema if not already
            if "expert_id" not in report.summary:
                _validate_schema(root, data, report)
                _validate_permissions(data, report)

    if level == "structure" and data and _is_v1_manifest(data):
        # structure still checks component paths (already done) + light id match
        pass

    return report
