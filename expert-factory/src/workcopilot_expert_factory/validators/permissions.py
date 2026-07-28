"""Permission and cross-reference validation (PRD §13.5 / §13.6)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workcopilot_expert_factory.validators.expert import ValidationReport

CLASSIFICATION_RANK = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "secret": 3,
    "restricted": 3,
}


def validate_permissions(data: dict[str, Any], report: ValidationReport) -> None:
    perms = data.get("permissions") or {}
    tools = perms.get("tools") or {}
    if tools.get("default") != "deny":
        report.add("error", "PERMISSION_DEFAULT", "permissions.tools.default must be deny")
    network = perms.get("network") or {}
    if network.get("default") != "deny":
        report.add("error", "PERMISSION_DEFAULT", "permissions.network.default must be deny")

    slot_ids = {s.get("id") for s in (data.get("connector_slots") or []) if isinstance(s, dict)}
    for slot_id in network.get("connector_slots") or []:
        if slot_id not in slot_ids:
            report.add(
                "error",
                "E_SCHEMA_INVALID",
                f"network.connector_slots references unknown slot: {slot_id}",
            )

    allow = set(tools.get("allow") or [])
    for item in (data.get("components") or {}).get("skills") or []:
        if not isinstance(item, dict):
            continue
        # tool_requirements checked at skill frontmatter level elsewhere
        _ = item

    for slot in data.get("connector_slots") or []:
        if not isinstance(slot, dict):
            continue
        for tool in slot.get("allowed_tools") or []:
            if allow and tool not in allow and tools.get("default") == "deny":
                # allowed_tools on connector should eventually be permitted; warn if not listed
                report.add(
                    "warning",
                    "TOOL_CONNECTOR_MISMATCH",
                    f"connector {slot.get('id')} tool {tool} not in permissions.tools.allow",
                )


def permission_expansion_diff(
    source: dict[str, Any],
    target: dict[str, Any],
) -> list[str]:
    """Return human-readable expansion issues (empty if no expansion)."""
    issues: list[str] = []
    s_tools = (source.get("permissions") or {}).get("tools") or {}
    t_tools = (target.get("permissions") or {}).get("tools") or {}
    s_allow = set(s_tools.get("allow") or [])
    t_allow = set(t_tools.get("allow") or [])
    expanded = t_allow - s_allow
    if expanded:
        issues.append(f"tools.allow expanded: {sorted(expanded)}")
    if s_tools.get("default") == "deny" and t_tools.get("default") == "allow":
        issues.append("tools.default deny → allow")

    s_data = (source.get("permissions") or {}).get("data") or {}
    t_data = (target.get("permissions") or {}).get("data") or {}
    s_cls = CLASSIFICATION_RANK.get(str(s_data.get("maximum_classification") or "internal").lower(), 1)
    t_cls = CLASSIFICATION_RANK.get(str(t_data.get("maximum_classification") or "internal").lower(), 1)
    if t_cls > s_cls:
        issues.append("data.maximum_classification raised")
    if not s_data.get("export_allowed") and t_data.get("export_allowed"):
        issues.append("data.export_allowed enabled")

    s_slots = {s.get("id"): s for s in (source.get("connector_slots") or []) if isinstance(s, dict)}
    for slot in target.get("connector_slots") or []:
        if not isinstance(slot, dict):
            continue
        sid = slot.get("id")
        prev = s_slots.get(sid)
        if not prev:
            if slot.get("access_mode") in {"write", "read-write"}:
                issues.append(f"new connector {sid} with write access")
            continue
        if prev.get("access_mode") == "read-only" and slot.get("access_mode") in {"write", "read-write"}:
            issues.append(f"connector {sid} access_mode read-only → {slot.get('access_mode')}")
    return issues
