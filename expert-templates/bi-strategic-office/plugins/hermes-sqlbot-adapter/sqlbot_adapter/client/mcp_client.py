"""SQLBot MCP HTTP client.

Calls SQLBot MCP tools internally:
  mcp_start, mcp_question, mcp_ws_list, mcp_datasource_list

Never returns access_token / chat_id / password to callers that feed the model.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from sqlbot_adapter.config import AdapterConfig
from sqlbot_adapter.contracts import ErrorCode, SqlbotAdapterError, map_http_error


@dataclass
class AuthSession:
    access_token: str = ""
    expires_at: float = 0.0
    chat_id: str = ""
    workspace_id: str = ""
    datasource_id: str = ""

    def token_valid(self, skew_seconds: int = 60) -> bool:
        return bool(self.access_token) and time.time() < (self.expires_at - skew_seconds)


@dataclass
class QuestionResult:
    raw: Dict[str, Any] = field(default_factory=dict)
    sql: str = ""
    columns: List[Any] = field(default_factory=list)
    rows: List[Any] = field(default_factory=list)
    chart: Any = None
    summary: Any = None
    title: str = ""
    chat_id: str = ""
    filters: List[Any] = field(default_factory=list)


class SqlbotMcpClient:
    def __init__(self, config: AdapterConfig, client: httpx.Client | None = None):
        self.config = config
        self._client = client
        self._owns_client = client is None
        self._auth = AuthSession()

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.config.request_timeout_seconds,
                verify=self.config.verify_ssl,
            )
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "SqlbotMcpClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _mcp_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        token: str = "",
        retry: bool = True,
    ) -> Dict[str, Any]:
        if not self.config.mcp_url:
            raise SqlbotAdapterError(ErrorCode.SQLBOT_NOT_CONFIGURED, "缺少 SQLBot 配置")

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # JSON-RPC style tools/call payload used by many MCP HTTP bridges
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 1_000_000_000,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        try:
            resp = self._get_client().post(self.config.mcp_url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise SqlbotAdapterError(ErrorCode.SQLBOT_UNAVAILABLE, "SQLBot 请求超时") from exc
        except httpx.HTTPError as exc:
            if retry:
                return self._mcp_call(tool_name, arguments, token=token, retry=False)
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_UNAVAILABLE, f"SQLBot 服务不可访问: {type(exc).__name__}"
            ) from exc

        if resp.status_code >= 400:
            raise map_http_error(resp.status_code, resp.text[:200])

        try:
            body = resp.json()
        except Exception as exc:
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_RESPONSE_INVALID, "SQLBot 返回结构无法解析"
            ) from exc

        if isinstance(body, dict) and body.get("error"):
            err = body["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise SqlbotAdapterError(ErrorCode.QUERY_EXECUTION_FAILED, str(msg or "MCP error"))

        result = body.get("result") if isinstance(body, dict) else body
        return self._unwrap_result(result)

    def _unwrap_result(self, result: Any) -> Dict[str, Any]:
        if result is None:
            return {}
        if isinstance(result, dict):
            # MCP content blocks: {"content":[{"type":"text","text":"...json..."}]}
            if "content" in result and isinstance(result["content"], list):
                texts = []
                for block in result["content"]:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text") or "")
                joined = "\n".join(texts).strip()
                if joined:
                    try:
                        parsed = json.loads(joined)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        return {"text": joined, "raw_text": joined}
            return result
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"text": result}
        return {"data": result}

    def login(self, force: bool = False) -> AuthSession:
        if not force and self._auth.token_valid():
            return self._auth
        if not self.config.is_configured():
            missing = ", ".join(self.config.missing_required())
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_NOT_CONFIGURED,
                f"缺少 SQLBot 配置: {missing}",
            )

        data = self._mcp_call(
            "mcp_start",
            {
                "username": self.config.username,
                "password": self.config.password,
                "workspace_id": self.config.workspace_id,
            },
            token="",
        )
        token = (
            data.get("access_token")
            or data.get("token")
            or (data.get("data") or {}).get("access_token")
            or ""
        )
        if not token:
            raise SqlbotAdapterError(ErrorCode.SQLBOT_AUTH_FAILED, "SQLBot 登录失败")

        expires_in = int(data.get("expires_in") or data.get("ttl") or 3600)
        chat_id = str(data.get("chat_id") or (data.get("data") or {}).get("chat_id") or "")
        self._auth = AuthSession(
            access_token=str(token),
            expires_at=time.time() + expires_in,
            chat_id=chat_id,
            workspace_id=self.config.workspace_id,
            datasource_id=self.config.default_datasource_id,
        )
        return self._auth

    def ensure_auth(self) -> AuthSession:
        return self.login(force=False)

    def set_auth(
        self,
        *,
        access_token: str,
        expires_at: float,
        chat_id: str = "",
        workspace_id: str = "",
        datasource_id: str = "",
    ) -> None:
        self._auth = AuthSession(
            access_token=access_token,
            expires_at=expires_at,
            chat_id=chat_id,
            workspace_id=workspace_id or self.config.workspace_id,
            datasource_id=datasource_id or self.config.default_datasource_id,
        )

    def list_workspaces(self) -> List[Dict[str, Any]]:
        auth = self.ensure_auth()
        data = self._mcp_call("mcp_ws_list", {}, token=auth.access_token)
        items = data.get("workspaces") or data.get("data") or data.get("items") or []
        return items if isinstance(items, list) else []

    def list_datasources(self, workspace_id: str = "") -> List[Dict[str, Any]]:
        auth = self.ensure_auth()
        ws = workspace_id or self.config.workspace_id
        data = self._mcp_call(
            "mcp_datasource_list",
            {"workspace_id": ws},
            token=auth.access_token,
        )
        items = data.get("datasources") or data.get("data") or data.get("items") or []
        return items if isinstance(items, list) else []

    def question(
        self,
        question: str,
        *,
        chat_id: str = "",
        datasource_id: str = "",
        workspace_id: str = "",
        response_mode: str = "data_and_summary",
        create_chat: bool = False,
    ) -> QuestionResult:
        auth = self.ensure_auth()
        args: Dict[str, Any] = {
            "question": question,
            "workspace_id": workspace_id or self.config.workspace_id,
            "datasource_id": datasource_id or self.config.default_datasource_id,
            "response_mode": response_mode,
        }
        if chat_id:
            args["chat_id"] = chat_id
        if create_chat:
            args["create_chat"] = True

        try:
            data = self._mcp_call("mcp_question", args, token=auth.access_token)
        except SqlbotAdapterError as exc:
            if exc.code == ErrorCode.SQLBOT_AUTH_FAILED:
                auth = self.login(force=True)
                data = self._mcp_call("mcp_question", args, token=auth.access_token)
            else:
                raise

        return self._parse_question_result(data, fallback_chat_id=chat_id or auth.chat_id)

    def _parse_question_result(self, data: Dict[str, Any], fallback_chat_id: str = "") -> QuestionResult:
        if not isinstance(data, dict):
            raise SqlbotAdapterError(ErrorCode.SQLBOT_RESPONSE_INVALID, "SQLBot 返回结构无法解析")

        nested = data.get("data") if isinstance(data.get("data"), dict) else data
        sql = str(
            nested.get("sql")
            or nested.get("query_sql")
            or (nested.get("query") or {}).get("sql")
            or ""
        )
        columns = nested.get("columns") or nested.get("fields") or []
        rows = nested.get("rows") or nested.get("data") or nested.get("result") or []
        if isinstance(rows, dict):
            rows = rows.get("rows") or []
        if not isinstance(rows, list):
            rows = []
        if not isinstance(columns, list):
            columns = []

        chat_id = str(
            nested.get("chat_id")
            or data.get("chat_id")
            or fallback_chat_id
            or ""
        )
        title = str(nested.get("title") or nested.get("name") or "")
        chart = nested.get("chart")
        summary = nested.get("summary") or nested.get("answer")
        filters = nested.get("filters") or []
        if not isinstance(filters, list):
            filters = []

        if not sql and not rows and nested.get("error"):
            raise SqlbotAdapterError(
                ErrorCode.QUERY_GENERATION_FAILED,
                str(nested.get("error")),
            )

        return QuestionResult(
            raw=data,
            sql=sql,
            columns=columns,
            rows=rows,
            chart=chart,
            summary=summary,
            title=title,
            chat_id=chat_id,
            filters=filters,
        )

    def ping(self) -> bool:
        """Lightweight connectivity check without exposing credentials."""
        try:
            self.login(force=True)
            return True
        except SqlbotAdapterError:
            return False
