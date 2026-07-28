"""Security scanning for Expert Source / Bundle candidates (PRD §13.6)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from workcopilot_expert_factory.validators.expert import ValidationReport

SECRET_PATTERNS = [
    (
        re.compile(r"(?i)(api[_-]?key|secret|password|token|private[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
        "possible secret assignment",
    ),
    (re.compile(r"(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key block"),
    (re.compile(r"(?i)\bsk-[A-Za-z0-9]{20,}\b"), "openai-like api key"),
    (re.compile(r"(?i)\bAKIA[0-9A-Z]{16}\b"), "aws access key"),
    (re.compile(r"(?i)(mongodb|mysql|postgres(ql)?|redis)://[^\s'\"]+:[^\s'\"]+@"), "db connection string"),
    (re.compile(r"(?i)refresh[_-]?token\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{20,}"), "oauth refresh token"),
]

DANGEROUS_SHELL = re.compile(
    r"(?i)\b(rm\s+-rf\s+/|curl\s+[^\n]*\|\s*(ba)?sh|wget\s+[^\n]*\|\s*(ba)?sh|chmod\s+777\s+/)\b"
)

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

# Docs/prd/tests may mention secrets in prose; scripts/ and config.yaml ARE scanned (v2.1).
SKIP_SCAN_DIR_MARKERS = ("/docs/", "/prd/", "/tests/", "/.git/", "/node_modules/", "/__pycache__/")


def looks_like_false_secret(snippet: str) -> bool:
    if FALSE_SECRET_RE.search(snippet):
        return True
    if re.search(
        r"(?i)(your_|xxx|example|placeholder|changeme|<|\blocal\b|\bnone\b|\bnull\b|\btest\b|"
        r"redacted|\*{3}|access_token|sqlbot_token)",
        snippet,
    ):
        return True
    if re.search(
        r"(?i)[:=]\s*(str|int|float|bool|dict|list|Exception|Error|None|True|False|os\.|self\.|session\.|"
        r"config\.|getenv|environ|Field|Optional|Annotated)\b",
        snippet,
    ):
        return True
    if re.search(r"[:=]\s*[A-Za-z_][A-Za-z0-9_]*\s*[\(\[\.]", snippet):
        return True
    m = re.search(r"[:=]\s*['\"]?([^\s'\"]+)", snippet)
    if not m:
        return True
    val = m.group(1).rstrip(",;)]}")
    if len(val) < 8:
        return True
    if re.match(r"^[A-Za-z_][\w\.]*$", val) and not re.search(r"[0-9]{6,}", val):
        return True
    return False


def scan_secrets(root: Path, report: ValidationReport, *, as_warning: bool = False) -> None:
    skip_dirs = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "egg-info"}
    level: Literal["error", "warning"] = "warning" if as_warning else "error"
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs or part.endswith(".egg-info") for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc", ".zip", ".tgz", ".tar"}:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        name_l = path.name.lower()
        rel_slash = f"/{rel}/"
        if any(m in rel_slash for m in SKIP_SCAN_DIR_MARKERS):
            continue
        if (
            ".example." in name_l
            or name_l.endswith(".example")
            or name_l.endswith(".example.env")
            or "example.env" in name_l
        ):
            continue
        if name_l == ".env" or (name_l.endswith(".env") and "example" not in name_l):
            report.add(level, "E_SECRET_DETECTED", "env file must not ship in expert source", rel)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            # suspicious binary in whitelist tree
            if path.suffix.lower() in {".exe", ".dll", ".so", ".bin"}:
                report.add(level, "E_PATH_UNSAFE", "suspicious binary file", rel)
            continue
        for pattern, label in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                snippet = match.group(0)
                if looks_like_false_secret(snippet):
                    continue
                if "PRIVATE KEY" in snippet.upper():
                    report.add(level, "E_SECRET_DETECTED", label, rel)
                    break
                val_m = re.search(r"[:=]\s*['\"]?([^\s'\"]+)", snippet)
                if not val_m:
                    if "://" in snippet:
                        report.add(level, "E_SECRET_DETECTED", f"{label}: {snippet[:48]}", rel)
                        break
                    continue
                val = val_m.group(1)
                if val.lower() in {"true", "false", "none", "null", "password", "secret", "token"}:
                    continue
                if re.match(r"^[A-Za-z_][A-Za-z0-9_\.]*$", val) and "." in val:
                    continue
                report.add(level, "E_SECRET_DETECTED", f"{label}: {snippet[:48]}", rel)
                break
            else:
                continue
            break
        if DANGEROUS_SHELL.search(text) and path.suffix in {".sh", ".bash", ".py", ".ps1"}:
            report.add("warning", "DANGEROUS_SHELL", "potentially dangerous shell pattern", rel)


def check_paths(root: Path, report: ValidationReport) -> None:
    seen_norm: dict[str, str] = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        parts = rel.parts
        if any(p == ".." for p in parts):
            report.add("error", "E_PATH_UNSAFE", "path escape detected", str(rel))
        if path.is_symlink():
            target = path.resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                report.add("error", "E_PATH_UNSAFE", "symlink escapes expert root", str(rel))
        # case-insensitive duplicate detection
        norm = str(rel).replace("\\", "/").lower()
        if path.is_file():
            if norm in seen_norm and seen_norm[norm] != str(rel).replace("\\", "/"):
                report.add(
                    "error",
                    "E_PATH_UNSAFE",
                    f"case conflict with {seen_norm[norm]}",
                    str(rel).replace("\\", "/"),
                )
            else:
                seen_norm[norm] = str(rel).replace("\\", "/")
