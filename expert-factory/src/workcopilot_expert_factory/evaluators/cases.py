from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from workcopilot_expert_factory.evaluators import CaseResult
from workcopilot_expert_factory.validators.expert import _parse_frontmatter


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _skill_texts(root: Path, data: dict[str, Any]) -> list[tuple[str, dict, str]]:
    out = []
    for item in (data.get("components") or {}).get("skills") or []:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        sid = item.get("id") or ""
        skill_md = root / (rel or "") / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta, body = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        out.append((sid, meta or {}, body))
    return out


def _prompt_keywords(prompt: str) -> set[str]:
    # CJK bigrams + ascii tokens
    tokens = set(re.findall(r"[A-Za-z0-9_-]{3,}", prompt.lower()))
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", prompt)
    tokens.update(cjk)
    return tokens


def run_cases(root: Path, data: dict[str, Any]) -> list[CaseResult]:
    suite_rel = (data.get("evaluations") or {}).get("suite") or "evaluations/cases.yaml"
    suite_path = root / suite_rel
    if not suite_path.is_file():
        return [
            CaseResult(
                id="suite-missing",
                type="smoke",
                passed=False,
                score=0.0,
                message=f"missing {suite_rel}",
            )
        ]

    suite = _load(suite_path)
    cases = suite.get("cases") or []
    perms = data.get("permissions") or {}
    tools = perms.get("tools") or {}
    allow = set(tools.get("allow") or [])
    deny = set(tools.get("deny") or [])
    slots = {s.get("id") for s in (data.get("connector_slots") or []) if isinstance(s, dict)}
    skills = _skill_texts(root, data)
    soul = ""
    entry = (data.get("runtime") or {}).get("entrypoints") or {}
    soul_path = root / entry.get("soul", "SOUL.md")
    if soul_path.is_file():
        soul = soul_path.read_text(encoding="utf-8")

    results: list[CaseResult] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        cid = str(case.get("id") or "case")
        ctype = str(case.get("type") or "task")
        prompt = str(case.get("prompt") or "")
        expected = case.get("expected") or {}
        fixture = case.get("fixture") or {}

        if ctype in {"policy", "security"}:
            action = expected.get("action")
            deny_tools = set(((expected.get("tools") or {}).get("deny") or []))
            ok = True
            msgs = []
            if action == "reject":
                # expert must deny write tools and have prohibit language
                if deny_tools and not deny_tools.issubset(deny) and tools.get("default") != "deny":
                    ok = False
                    msgs.append("expected deny tools not covered")
                elif tools.get("default") != "deny":
                    ok = False
                    msgs.append("default deny required for reject cases")
                body_blob = soul + "\n".join(b for _, _, b in skills)
                if ctype == "security":
                    if not any(k in body_blob for k in ("密钥", "密码", "凭证", "禁止", "API Key", "api key")):
                        ok = False
                        msgs.append("missing secret-rejection language")
                if ctype == "policy":
                    if not any(k in body_blob for k in ("写入", "生产", "禁止", "只读", "修改")):
                        ok = False
                        msgs.append("missing write-rejection language")
            results.append(
                CaseResult(
                    id=cid,
                    type=ctype,
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    message="; ".join(msgs) if msgs else "policy/security case ok",
                    details={"deny": sorted(deny), "expected_deny": sorted(deny_tools)},
                )
            )
            continue

        if ctype == "resilience":
            ok = True
            msg = "ok"
            if fixture.get("connector_status") == "unavailable":
                if not slots:
                    # experts without connectors: pass if skills mention 连接器/不可用
                    blob = "\n".join(b for _, _, b in skills)
                    if not any(k in blob for k in ("连接", "不可用", "异常", "Connector", "connector")):
                        ok = False
                        msg = "no connector slots and no connector-failure handling text"
                    else:
                        msg = "resilience text present without slots"
                else:
                    blob = "\n".join(b for _, _, b in skills) + soul
                    if not any(k in blob for k in ("连接", "不可用", "异常", "Connector", "connector", "失败")):
                        ok = False
                        msg = "connector declared but failure handling not documented"
                    else:
                        msg = "connector resilience documented"
            results.append(
                CaseResult(id=cid, type=ctype, passed=ok, score=1.0 if ok else 0.0, message=msg)
            )
            continue

        # task / smoke
        expected_skills = expected.get("skill") or expected.get("skills") or []
        kws = _prompt_keywords(prompt)
        matched = []
        for sid, meta, body in skills:
            blob = " ".join(
                [
                    sid,
                    str(meta.get("name") or ""),
                    str(meta.get("description") or ""),
                    " ".join(meta.get("triggers") or []),
                ]
            )
            if expected_skills and sid in expected_skills:
                matched.append(sid)
                continue
            if any(k in blob for k in kws):
                matched.append(sid)
        if expected_skills:
            ok = all(s in {m for m in matched} or any(s == sid for sid, _, _ in skills) for s in expected_skills)
            # simpler: all expected skill ids exist
            existing = {sid for sid, _, _ in skills}
            ok = set(expected_skills).issubset(existing)
            msg = f"expected skills present: {expected_skills}"
        else:
            ok = len(skills) > 0
            msg = f"keyword skill match={matched[:3]} skills={len(skills)}"
        allow_tools = set(((expected.get("tools") or {}).get("allow") or []))
        if allow_tools and allow and not allow_tools.issubset(allow):
            ok = False
            msg += "; expected allow tools not in permissions.allow"
        results.append(
            CaseResult(
                id=cid,
                type=ctype,
                passed=ok,
                score=1.0 if ok else 0.0,
                message=msg,
                details={"matched_skills": matched},
            )
        )

    return results
