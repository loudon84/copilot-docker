"""Adapter configuration from SQLBOT_* environment variables (v1.12.0)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError

DEFAULT_BUSINESS_IDENTIFIERS: List[Dict[str, Any]] = [
    {
        "names": [
            "交易凭证编号",
            "交易凭证号",
            "应收交易编号",
            "应收发票编号",
            "AR发票号",
            "凭证号",
            "单据号",
        ],
        "field": "ar_trx_number",
        "match": "exact",
    },
    {
        "names": ["订单号", "订单编号"],
        "field": "order_number",
        "match": "exact",
    },
    {
        "names": ["客户编号", "客户编码", "customer_code"],
        "field": "customer_code",
        "match": "exact",
    },
]


@dataclass
class DatasourceSpec:
    key: str
    id: str
    public_name: str = ""
    dialect: str = "tsql"
    allowed_schemas: List[str] = field(default_factory=list)
    allowed_tables: List[str] = field(default_factory=list)
    business_identifiers: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AdapterConfig:
    mcp_url: str = ""
    username: str = ""
    password: str = ""
    workspace_id: str = ""
    default_datasource_id: str = ""
    session_encryption_key: str = ""
    connect_timeout_seconds: int = 15
    login_timeout_seconds: int = 30
    request_timeout_seconds: int = 120
    read_timeout_seconds: int = 120
    write_timeout_seconds: int = 30
    pool_timeout_seconds: int = 15
    session_ttl_seconds: int = 86400
    verify_ssl: bool = True
    max_result_rows: int = 1000
    model_result_rows: int = 100
    max_result_columns: int = 50
    max_result_bytes: int = 2_000_000
    max_question_chars: int = 2000
    lang: str = "zh-CN"
    query_retention_days: int = 90
    audit_retention_days: int = 90
    audit_enabled: bool = True
    hermes_profile: str = ""
    state_db: str = "/data/hermes/sqlbot-adapter/state/sqlbot_sessions.db"
    audit_dir: str = "/data/hermes/sqlbot-adapter/audit"
    datasource_aliases: Dict[str, str] = field(default_factory=dict)
    datasources: Dict[str, DatasourceSpec] = field(default_factory=dict)
    business_identifiers: List[Dict[str, Any]] = field(
        default_factory=lambda: list(DEFAULT_BUSINESS_IDENTIFIERS)
    )

    def is_configured(self) -> bool:
        return not bool(self.missing_required())

    def missing_required(self) -> list[str]:
        required = {
            "SQLBOT_MCP_URL": self.mcp_url,
            "SQLBOT_USERNAME": self.username,
            "SQLBOT_PASSWORD": self.password,
            "SQLBOT_WORKSPACE_ID": self.workspace_id,
            "SQLBOT_DEFAULT_DATASOURCE_ID": self.default_datasource_id,
            "SQLBOT_SESSION_ENCRYPTION_KEY": self.session_encryption_key,
        }
        return [k for k, v in required.items() if not v]

    def resolve_datasource_id(self, datasource_key: str = "") -> str:
        key = (datasource_key or "").strip()
        if not key:
            return self.default_datasource_id
        if key in self.datasources:
            return self.datasources[key].id
        if key in self.datasource_aliases:
            return self.datasource_aliases[key]
        if key == self.default_datasource_id:
            return key
        raise SqlbotAdapterError(
            ErrorCode.INVALID_DATASOURCE_KEY,
            f"未知数据源别名: {key}",
        )

    def resolve_datasource_spec(self, datasource_key: str = "") -> Optional[DatasourceSpec]:
        key = (datasource_key or "").strip()
        if key and key in self.datasources:
            return self.datasources[key]
        ds_id = self.resolve_datasource_id(datasource_key) if key else self.default_datasource_id
        for spec in self.datasources.values():
            if spec.id == ds_id:
                return spec
        return None

    def dialect_for(self, datasource_key: str = "") -> str:
        spec = None
        try:
            spec = self.resolve_datasource_spec(datasource_key)
        except SqlbotAdapterError:
            spec = None
        if spec and spec.dialect:
            return spec.dialect
        return "tsql"

    def identifiers_for(self, datasource_key: str = "") -> List[Dict[str, Any]]:
        spec = None
        try:
            spec = self.resolve_datasource_spec(datasource_key)
        except SqlbotAdapterError:
            spec = None
        if spec and spec.business_identifiers:
            return list(spec.business_identifiers)
        return list(self.business_identifiers)


def _as_bool(value: str | None, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, value: str | None, default: int) -> int:
    raw = (value if value is not None and value != "" else str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise SqlbotAdapterError(
            ErrorCode.INVALID_ARGUMENT,
            f"环境变量 {name} 必须为整数，当前值: {raw!r}",
        ) from exc


def _parse_aliases(raw: str) -> Dict[str, str]:
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


def _parse_datasources_json(raw: str) -> Dict[str, DatasourceSpec]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SqlbotAdapterError(
            ErrorCode.INVALID_ARGUMENT,
            f"SQLBOT_DATASOURCES_JSON 不是合法 JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise SqlbotAdapterError(
            ErrorCode.INVALID_ARGUMENT,
            "SQLBOT_DATASOURCES_JSON 必须是对象",
        )
    out: Dict[str, DatasourceSpec] = {}
    for key, val in payload.items():
        if not isinstance(val, dict):
            continue
        ds_id = str(val.get("id") or "").strip()
        if not ds_id:
            continue
        out[str(key)] = DatasourceSpec(
            key=str(key),
            id=ds_id,
            public_name=str(val.get("public_name") or val.get("name") or key),
            dialect=str(val.get("dialect") or "tsql"),
            allowed_schemas=[str(x) for x in (val.get("allowed_schemas") or [])],
            allowed_tables=[str(x) for x in (val.get("allowed_tables") or [])],
            business_identifiers=list(val.get("business_identifiers") or []),
        )
    return out


def load_config(environ: dict | None = None) -> AdapterConfig:
    env = environ if environ is not None else os.environ
    state_default = "/data/hermes/sqlbot-adapter/state/sqlbot_sessions.db"
    audit_default = "/data/hermes/sqlbot-adapter/audit"
    aliases = _parse_aliases(env.get("SQLBOT_DATASOURCE_ALIASES") or "")
    datasources = _parse_datasources_json(env.get("SQLBOT_DATASOURCES_JSON") or "")
    for key, spec in datasources.items():
        aliases.setdefault(key, spec.id)
    return AdapterConfig(
        mcp_url=(env.get("SQLBOT_MCP_URL") or "").strip(),
        username=(env.get("SQLBOT_USERNAME") or "").strip(),
        password=env.get("SQLBOT_PASSWORD") or "",
        workspace_id=(env.get("SQLBOT_WORKSPACE_ID") or "").strip(),
        default_datasource_id=(env.get("SQLBOT_DEFAULT_DATASOURCE_ID") or "").strip(),
        session_encryption_key=(env.get("SQLBOT_SESSION_ENCRYPTION_KEY") or "").strip(),
        connect_timeout_seconds=_as_int(
            "SQLBOT_CONNECT_TIMEOUT_SECONDS", env.get("SQLBOT_CONNECT_TIMEOUT_SECONDS"), 15
        ),
        login_timeout_seconds=_as_int(
            "SQLBOT_LOGIN_TIMEOUT_SECONDS", env.get("SQLBOT_LOGIN_TIMEOUT_SECONDS"), 30
        ),
        request_timeout_seconds=_as_int(
            "SQLBOT_REQUEST_TIMEOUT_SECONDS", env.get("SQLBOT_REQUEST_TIMEOUT_SECONDS"), 120
        ),
        read_timeout_seconds=_as_int(
            "SQLBOT_READ_TIMEOUT_SECONDS",
            env.get("SQLBOT_READ_TIMEOUT_SECONDS") or env.get("SQLBOT_REQUEST_TIMEOUT_SECONDS"),
            120,
        ),
        write_timeout_seconds=_as_int(
            "SQLBOT_WRITE_TIMEOUT_SECONDS", env.get("SQLBOT_WRITE_TIMEOUT_SECONDS"), 30
        ),
        pool_timeout_seconds=_as_int(
            "SQLBOT_POOL_TIMEOUT_SECONDS", env.get("SQLBOT_POOL_TIMEOUT_SECONDS"), 15
        ),
        session_ttl_seconds=_as_int(
            "SQLBOT_SESSION_TTL_SECONDS", env.get("SQLBOT_SESSION_TTL_SECONDS"), 86400
        ),
        verify_ssl=_as_bool(env.get("SQLBOT_VERIFY_SSL", "true"), True),
        max_result_rows=_as_int("SQLBOT_MAX_RESULT_ROWS", env.get("SQLBOT_MAX_RESULT_ROWS"), 1000),
        model_result_rows=_as_int(
            "SQLBOT_MODEL_RESULT_ROWS", env.get("SQLBOT_MODEL_RESULT_ROWS"), 100
        ),
        max_result_columns=_as_int(
            "SQLBOT_MAX_RESULT_COLUMNS", env.get("SQLBOT_MAX_RESULT_COLUMNS"), 50
        ),
        max_result_bytes=_as_int(
            "SQLBOT_MAX_RESULT_BYTES", env.get("SQLBOT_MAX_RESULT_BYTES"), 2_000_000
        ),
        max_question_chars=_as_int(
            "SQLBOT_MAX_QUESTION_CHARS", env.get("SQLBOT_MAX_QUESTION_CHARS"), 2000
        ),
        lang=(env.get("SQLBOT_LANG") or "zh-CN").strip() or "zh-CN",
        query_retention_days=_as_int(
            "SQLBOT_QUERY_RETENTION_DAYS", env.get("SQLBOT_QUERY_RETENTION_DAYS"), 90
        ),
        audit_retention_days=_as_int(
            "SQLBOT_AUDIT_RETENTION_DAYS", env.get("SQLBOT_AUDIT_RETENTION_DAYS"), 90
        ),
        audit_enabled=_as_bool(env.get("SQLBOT_AUDIT_ENABLED", "true"), True),
        hermes_profile=(env.get("HERMES_PROFILE") or env.get("SQLBOT_HERMES_PROFILE") or "").strip(),
        state_db=(env.get("SQLBOT_STATE_DB") or state_default).strip(),
        audit_dir=(env.get("SQLBOT_AUDIT_DIR") or audit_default).strip(),
        datasource_aliases=aliases,
        datasources=datasources,
    )


def ensure_runtime_dirs(cfg: AdapterConfig) -> None:
    state_parent = Path(cfg.state_db).parent
    state_parent.mkdir(parents=True, exist_ok=True)
    audit_path = Path(cfg.audit_dir)
    audit_path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(state_parent, 0o700)
        os.chmod(audit_path, 0o700)
    except OSError:
        pass
