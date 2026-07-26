"""Adapter configuration from SQLBOT_* environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class AdapterConfig:
    mcp_url: str = ""
    username: str = ""
    password: str = ""
    workspace_id: str = ""
    default_datasource_id: str = ""
    request_timeout_seconds: int = 120
    session_ttl_seconds: int = 86400
    verify_ssl: bool = True
    max_result_rows: int = 500
    model_result_rows: int = 100
    audit_enabled: bool = True
    hermes_profile: str = ""
    state_db: str = "/data/hermes/sqlbot-adapter/state/sqlbot_sessions.db"
    audit_dir: str = "/data/hermes/sqlbot-adapter/audit"
    datasource_aliases: Dict[str, str] = field(default_factory=dict)

    def is_configured(self) -> bool:
        return bool(
            self.mcp_url
            and self.username
            and self.password
            and self.workspace_id
            and self.default_datasource_id
        )

    def missing_required(self) -> list[str]:
        required = {
            "SQLBOT_MCP_URL": self.mcp_url,
            "SQLBOT_USERNAME": self.username,
            "SQLBOT_PASSWORD": self.password,
            "SQLBOT_WORKSPACE_ID": self.workspace_id,
            "SQLBOT_DEFAULT_DATASOURCE_ID": self.default_datasource_id,
        }
        return [k for k, v in required.items() if not v]

    def resolve_datasource_id(self, datasource_key: str = "") -> str:
        key = (datasource_key or "").strip()
        if not key:
            return self.default_datasource_id
        if key in self.datasource_aliases:
            return self.datasource_aliases[key]
        # Allow passing the raw default id; otherwise fall back to default.
        if key == self.default_datasource_id:
            return key
        return self.default_datasource_id


def _as_bool(value: str, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_aliases(raw: str) -> Dict[str, str]:
    """Parse SQLBOT_DATASOURCE_ALIASES like key1:id1,key2:id2."""
    out: Dict[str, str] = {}
    for part in (raw or "").split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        k, v = part.split(":", 1)
        k, v = k.strip(), v.strip()
        if k and v:
            out[k] = v
    return out


def load_config(environ: dict | None = None) -> AdapterConfig:
    env = environ if environ is not None else os.environ
    state_default = "/data/hermes/sqlbot-adapter/state/sqlbot_sessions.db"
    audit_default = "/data/hermes/sqlbot-adapter/audit"
    return AdapterConfig(
        mcp_url=(env.get("SQLBOT_MCP_URL") or "").strip(),
        username=(env.get("SQLBOT_USERNAME") or "").strip(),
        password=env.get("SQLBOT_PASSWORD") or "",
        workspace_id=(env.get("SQLBOT_WORKSPACE_ID") or "").strip(),
        default_datasource_id=(env.get("SQLBOT_DEFAULT_DATASOURCE_ID") or "").strip(),
        request_timeout_seconds=int(env.get("SQLBOT_REQUEST_TIMEOUT_SECONDS") or 120),
        session_ttl_seconds=int(env.get("SQLBOT_SESSION_TTL_SECONDS") or 86400),
        verify_ssl=_as_bool(env.get("SQLBOT_VERIFY_SSL", "true"), True),
        max_result_rows=int(env.get("SQLBOT_MAX_RESULT_ROWS") or 500),
        model_result_rows=int(env.get("SQLBOT_MODEL_RESULT_ROWS") or 100),
        audit_enabled=_as_bool(env.get("SQLBOT_AUDIT_ENABLED", "true"), True),
        hermes_profile=(env.get("HERMES_PROFILE") or env.get("SQLBOT_HERMES_PROFILE") or "").strip(),
        state_db=(env.get("SQLBOT_STATE_DB") or state_default).strip(),
        audit_dir=(env.get("SQLBOT_AUDIT_DIR") or audit_default).strip(),
        datasource_aliases=_parse_aliases(env.get("SQLBOT_DATASOURCE_ALIASES") or ""),
    )


def ensure_runtime_dirs(cfg: AdapterConfig) -> None:
    Path(cfg.state_db).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg.audit_dir).mkdir(parents=True, exist_ok=True)
