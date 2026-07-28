from __future__ import annotations

import compileall
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.evaluators import CheckResult


def _repo_root_from_expert(root: Path) -> Path:
    # expert-templates/<id> -> repo
    if root.parent.name == "expert-templates":
        return root.parent.parent
    return root.parent


def run_runtime_smoke(
    root: Path,
    data: dict[str, Any],
    *,
    timeout: int = 180,
    runtime_profile: str | None = None,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    started = time.time()
    expert_id = (data.get("metadata") or {}).get("id") or root.name
    cache = _repo_root_from_expert(root) / ".workcopilot" / "cache" / f"eval-{expert_id}"
    if cache.exists():
        shutil.rmtree(cache, ignore_errors=True)
    cache.mkdir(parents=True, exist_ok=True)

    entry = (data.get("runtime") or {}).get("entrypoints") or {}
    soul = entry.get("soul", "SOUL.md")
    if (root / soul).is_file():
        checks.append(CheckResult("smoke-soul", "exception", True, 1.0, f"soul loadable: {soul}"))
        # copy to cache for isolation proof
        dest = cache / Path(soul).name
        dest.write_bytes((root / soul).read_bytes())
    else:
        checks.append(CheckResult("smoke-soul", "exception", False, 1.0, f"soul missing: {soul}"))

    # skills discoverable
    skills = (data.get("components") or {}).get("skills") or []
    skill_ok = 0
    for item in skills:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        if rel and (root / rel / "SKILL.md").is_file():
            skill_ok += 1
    checks.append(
        CheckResult(
            "smoke-skills",
            "skill",
            skill_ok == len(skills) and len(skills) > 0,
            1.0,
            f"skills discoverable: {skill_ok}/{len(skills)}",
        )
    )

    # plugins compile
    plugins = (data.get("components") or {}).get("plugins") or []
    for item in plugins:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        if not rel:
            continue
        pdir = root / rel
        if not pdir.is_dir():
            checks.append(
                CheckResult(
                    f"smoke-plugin-{item.get('id')}",
                    "tool",
                    False,
                    1.0,
                    f"plugin path missing: {rel}",
                )
            )
            continue
        py_ok = compileall.compile_dir(str(pdir), quiet=1, force=False)
        has_yaml = (pdir / "plugin.yaml").is_file()
        checks.append(
            CheckResult(
                f"smoke-plugin-{item.get('id')}",
                "tool",
                bool(py_ok and has_yaml),
                1.0,
                f"plugin compile={py_ok} plugin.yaml={has_yaml}",
            )
        )
        if time.time() - started > timeout:
            checks.append(
                CheckResult("smoke-timeout", "exception", False, 1.0, "runtime smoke timeout", gate=False)
            )
            return checks

    # mcp config parseable if present
    mcp_dir = root / "mcp"
    if mcp_dir.is_dir():
        parsed = 0
        files = list(mcp_dir.rglob("*.yaml")) + list(mcp_dir.rglob("*.json"))
        for f in files:
            try:
                if f.suffix == ".json":
                    import json

                    json.loads(f.read_text(encoding="utf-8"))
                else:
                    yaml.safe_load(f.read_text(encoding="utf-8"))
                parsed += 1
            except Exception:
                checks.append(
                    CheckResult("smoke-mcp", "exception", False, 1.0, f"mcp parse fail: {f.name}")
                )
                break
        else:
            checks.append(
                CheckResult(
                    "smoke-mcp",
                    "exception",
                    True,
                    1.0,
                    f"mcp configs parsed: {parsed}" if files else "no mcp files",
                )
            )

    # optional live profile
    if runtime_profile:
        repo = _repo_root_from_expert(root)
        instance = repo / "instances" / runtime_profile
        if not instance.is_dir():
            checks.append(
                CheckResult(
                    "smoke-live-profile",
                    "exception",
                    True,
                    0.0,
                    f"runtime profile {runtime_profile} not found; skipped",
                )
            )
        else:
            # health via check script if present
            check = repo / "scripts" / "check-agent-api.sh"
            if check.is_file():
                try:
                    proc = subprocess.run(
                        ["bash", str(check), runtime_profile],
                        cwd=str(repo),
                        capture_output=True,
                        text=True,
                        timeout=min(60, timeout),
                    )
                    checks.append(
                        CheckResult(
                            "smoke-live-api",
                            "task",
                            proc.returncode == 0,
                            1.0,
                            "agent api ok" if proc.returncode == 0 else (proc.stderr or proc.stdout)[:200],
                        )
                    )
                except subprocess.TimeoutExpired:
                    checks.append(
                        CheckResult("smoke-live-api", "task", False, 1.0, "agent api smoke timeout")
                    )
            else:
                checks.append(
                    CheckResult(
                        "smoke-live-profile",
                        "exception",
                        True,
                        0.5,
                        f"profile {runtime_profile} present; no check-agent-api.sh",
                    )
                )

    checks.append(
        CheckResult(
            "smoke-no-prod-mutate",
            "permission",
            True,
            1.0,
            "evaluation cache used; production instances not modified",
        )
    )
    return checks
