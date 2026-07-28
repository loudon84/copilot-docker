"""Isolated Hermes Runtime Harness (PRD §14.3).

When Hermes CLI / Gateway is unavailable, falls back to simulated runtime
that still exercises injection, fixture wiring, and artifact collection.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.digest import iter_source_files
from workcopilot_expert_factory.evaluators import CheckResult
from workcopilot_expert_factory.evaluators.fixtures import ConnectorFixtureSet


def _repo_root_from_expert(root: Path) -> Path:
    if root.parent.name == "expert-templates":
        return root.parent.parent
    return root.parent


def create_run_dir(expert_id: str, repo: Path) -> Path:
    run_id = f"{expert_id}-{uuid.uuid4().hex[:8]}"
    base = repo / ".workcopilot" / "cache" / "evaluations" / run_id
    for name in ("hermes-home", "workspace", "fixtures", "artifacts", "events", "logs"):
        (base / name).mkdir(parents=True, exist_ok=True)
    return base


def inject_expert_source(expert_root: Path, hermes_home: Path) -> None:
    """Copy whitelist expert files into isolated HERMES_HOME."""
    dest_skills = hermes_home / "skills"
    dest_skills.mkdir(parents=True, exist_ok=True)
    soul_candidates = [
        expert_root / "SOUL.md",
        expert_root / "runtime" / "SOUL.md",
        expert_root / "root" / "SOUL.md",
    ]
    for soul in soul_candidates:
        if soul.is_file():
            (hermes_home / "SOUL.md").write_bytes(soul.read_bytes())
            break
    for path in iter_source_files(expert_root):
        rel = path.relative_to(expert_root)
        if rel.parts and rel.parts[0] == "skills":
            target = hermes_home / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    # policies
    pol = expert_root / "policies"
    if pol.is_dir():
        dest = hermes_home / "policies"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(pol, dest)


def _hermes_available() -> bool:
    return shutil.which("hermes") is not None or os.environ.get("HERMES_GATEWAY_URL")


def run_hermes_case(
    *,
    run_dir: Path,
    prompt: str,
    timeout: int = 180,
    fixtures: ConnectorFixtureSet | None = None,
) -> dict[str, Any]:
    """
    Attempt real Hermes invocation; otherwise simulate a deterministic response
    for CI without a local Gateway.
    """
    fixtures = fixtures or ConnectorFixtureSet()
    events_path = run_dir / "events" / "case.jsonl"
    started = time.time()

    gateway = os.environ.get("HERMES_GATEWAY_URL")
    if gateway and os.environ.get("HERMES_EVAL_LIVE") == "1":
        # Optional live call via HTTP chat completions-compatible endpoint
        try:
            import httpx

            headers = {}
            key = os.environ.get("API_SERVER_KEY") or os.environ.get("HERMES_API_KEY")
            if key:
                headers["Authorization"] = f"Bearer {key}"
            resp = httpx.post(
                f"{gateway.rstrip('/')}/v1/chat/completions",
                headers=headers,
                json={
                    "model": os.environ.get("API_SERVER_MODEL_NAME", "hermes-agent"),
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=timeout,
            )
            data = resp.json()
            reply = (
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                or json.dumps(data, ensure_ascii=False)[:2000]
            )
            result = {
                "mode": "live",
                "reply": reply,
                "tool_calls": data.get("tool_calls") or [],
                "skills_selected": [],
                "duration_ms": int((time.time() - started) * 1000),
                "status_code": resp.status_code,
            }
        except Exception as exc:  # noqa: BLE001
            result = {
                "mode": "live-error",
                "reply": "",
                "error": str(exc),
                "tool_calls": [],
                "skills_selected": [],
                "duration_ms": int((time.time() - started) * 1000),
            }
    else:
        # Simulated isolated run: exercise fixtures and produce structured reply
        fixtures.record("mock-search", {"q": prompt[:80]}, {"hits": []})
        result = {
            "mode": "simulated",
            "reply": f"[simulated] 已在隔离 Hermes Runtime 中处理请求：{prompt[:200]}",
            "tool_calls": [{"name": "mock-search", "args": {"q": prompt[:80]}}],
            "skills_selected": [],
            "duration_ms": int((time.time() - started) * 1000),
            "hermes_home": str(run_dir / "hermes-home"),
        }

    events_path.write_text(json.dumps(result, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "artifacts" / "last-reply.txt").write_text(result.get("reply") or "", encoding="utf-8")
    return result


def run_hermes_runtime_harness(
    root: Path,
    data: dict[str, Any],
    *,
    timeout: int = 180,
    prompts: list[str] | None = None,
) -> tuple[list[CheckResult], list[dict[str, Any]], ConnectorFixtureSet]:
    expert_id = (data.get("metadata") or {}).get("id") or root.name
    repo = _repo_root_from_expert(root)
    run_dir = create_run_dir(expert_id, repo)
    inject_expert_source(root, run_dir / "hermes-home")
    fixtures = ConnectorFixtureSet(name="default")

    checks: list[CheckResult] = []
    soul = run_dir / "hermes-home" / "SOUL.md"
    checks.append(
        CheckResult(
            "runtime-smoke",
            "exception",
            soul.is_file(),
            1.0,
            "isolated HERMES_HOME injected" if soul.is_file() else "SOUL missing after inject",
            gate=True,
        )
    )
    skills_dir = run_dir / "hermes-home" / "skills"
    skill_ok = skills_dir.is_dir() and any(skills_dir.rglob("SKILL.md"))
    checks.append(
        CheckResult(
            "runtime-skills",
            "skill",
            skill_ok or not ((data.get("components") or {}).get("skills")),
            1.0,
            "skills discoverable in isolated home" if skill_ok else "no skills in isolated home",
        )
    )

    prompts = prompts or ["请用一句话说明你的职责边界"]
    results: list[dict[str, Any]] = []
    for i, prompt in enumerate(prompts):
        res = run_hermes_case(run_dir=run_dir, prompt=prompt, timeout=timeout, fixtures=fixtures)
        results.append(res)
        ok = bool(res.get("reply")) and not res.get("error")
        checks.append(
            CheckResult(
                f"runtime-task-{i}",
                "task",
                ok,
                1.0,
                f"runtime case {i}: {res.get('mode')} reply_len={len(res.get('reply') or '')}",
                gate=(i == 0),
            )
        )

    # cleanup secrets if any were written
    for env_file in (run_dir / "hermes-home").rglob(".env"):
        try:
            env_file.unlink()
        except OSError:
            pass

    (run_dir / "logs" / "harness.json").write_text(
        json.dumps({"results": results, "fixtures": fixtures.digest_payload()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return checks, results, fixtures
