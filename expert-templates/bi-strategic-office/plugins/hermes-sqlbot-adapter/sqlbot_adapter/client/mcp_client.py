"""SQLBot MCP SSE client (official mcp SDK). One call = one SSE session."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlbot_adapter.async_bridge import run_coro
from sqlbot_adapter.client.result_parser import (
    ParsedQuestion,
    extract_from_mcp_result,
    parse_question_result,
    parse_start_result,
)
from sqlbot_adapter.config import AdapterConfig
from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError

logger = logging.getLogger(__name__)

SQLBOT_TOOL_START = "mcp_start"
SQLBOT_TOOL_QUESTION = "mcp_question"
SQLBOT_TOOL_WS_LIST = "mcp_ws_list"
SQLBOT_TOOL_DATASOURCE_LIST = "mcp_datasource_list"


@dataclass
class AuthSession:
    access_token: str = ""
    expires_at: float = 0.0
    chat_id: str = ""
    workspace_id: str = ""
    datasource_id: str = ""


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
    error: Optional[SqlbotAdapterError] = None


class SQLBotMCPClient:
    """Per-call SSE + ClientSession. Does not keep global transport."""

    def __init__(self, config: AdapterConfig):
        self.config = config

    def _timeout(self, kind: str = "request") -> float:
        if kind == "connect":
            return float(self.config.connect_timeout_seconds)
        if kind == "login":
            return float(self.config.login_timeout_seconds)
        return float(self.config.request_timeout_seconds)

    async def _call_tool_once(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        timeout: float,
    ) -> Any:
        if not self.config.mcp_url:
            raise SqlbotAdapterError(ErrorCode.SQLBOT_NOT_CONFIGURED, "缺少 SQLBot 配置")

        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError as exc:
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_NOT_CONFIGURED,
                "缺少 mcp SDK，请安装 mcp==1.26.0",
            ) from exc

        try:
            async with sse_client(self.config.mcp_url) as streams:
                read_stream, write_stream = streams
                async with ClientSession(read_stream, write_stream) as session:
                    try:
                        await session.initialize()
                    except Exception as exc:
                        raise SqlbotAdapterError(
                            ErrorCode.SQLBOT_INITIALIZE_FAILED,
                            f"MCP initialize 失败: {type(exc).__name__}",
                            source="sqlbot",
                        ) from exc
                    try:
                        return await session.call_tool(tool_name, arguments or {})
                    except Exception as exc:
                        msg = str(exc)
                        if "Unknown tool" in msg or "not found" in msg.lower():
                            raise SqlbotAdapterError(
                                ErrorCode.SQLBOT_MCP_TOOL_UNAVAILABLE,
                                f"固定工具不可调用: {tool_name}",
                                source="sqlbot",
                            ) from exc
                        raise SqlbotAdapterError(
                            ErrorCode.SQLBOT_TRANSPORT_ERROR,
                            f"MCP call_tool 失败: {type(exc).__name__}",
                            source="sqlbot",
                        ) from exc
        except SqlbotAdapterError:
            raise
        except Exception as exc:
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_TRANSPORT_ERROR,
                f"SQLBot MCP 网络或 SSE 错误: {type(exc).__name__}",
                source="sqlbot",
            ) from exc

    async def _call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        timeout: float,
        retry_transport: bool = False,
    ) -> Dict[str, Any]:
        try:
            raw = await self._call_tool_once(tool_name, arguments, timeout=timeout)
        except SqlbotAdapterError as exc:
            if retry_transport and exc.code in {
                ErrorCode.SQLBOT_TRANSPORT_ERROR,
                ErrorCode.SQLBOT_INITIALIZE_FAILED,
            }:
                raw = await self._call_tool_once(tool_name, arguments, timeout=timeout)
            else:
                raise
        return extract_from_mcp_result(raw)

    def call_tool_sync(
        self,
        tool_name: str,
        arguments: Dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
        retry_transport: bool = False,
    ) -> Dict[str, Any]:
        to = timeout if timeout is not None else self._timeout("request")
        return run_coro(
            self._call_tool(
                tool_name,
                arguments or {},
                timeout=to,
                retry_transport=retry_transport,
            ),
            timeout=to + 5,
        )

    async def initialize_and_ping(self) -> bool:
        """Doctor helper: initialize + optional ping; does not login."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError as exc:
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_NOT_CONFIGURED,
                "缺少 mcp SDK",
            ) from exc

        async with sse_client(self.config.mcp_url) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                if hasattr(session, "send_ping"):
                    try:
                        await session.send_ping()
                    except Exception:
                        logger.warning("MCP ping failed (non-fatal)")
                return True

    def initialize_and_ping_sync(self) -> bool:
        return run_coro(
            self.initialize_and_ping(),
            timeout=self._timeout("connect") + 10,
        )

    async def list_tools_names(self) -> List[str]:
        """Doctor/debug only — never used by finance_bi_* business path."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError:
            return []
        try:
            async with sse_client(self.config.mcp_url) as streams:
                read_stream, write_stream = streams
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [t.name for t in (result.tools or [])]
        except Exception as exc:
            logger.warning("tools/list incompatible or failed: %s", type(exc).__name__)
            return []

    def list_tools_names_sync(self) -> List[str]:
        try:
            return run_coro(self.list_tools_names(), timeout=self._timeout("connect") + 10)
        except Exception:
            logger.warning("tools/list failed")
            return []

    def start(self) -> Dict[str, Any]:
        if not self.config.is_configured():
            missing = ", ".join(self.config.missing_required())
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_NOT_CONFIGURED,
                f"缺少 SQLBot 配置: {missing}",
            )
        data = self.call_tool_sync(
            SQLBOT_TOOL_START,
            {
                "username": self.config.username,
                "password": self.config.password,
            },
            timeout=self._timeout("login"),
            retry_transport=True,
        )
        return parse_start_result(data)

    def list_workspaces(self, access_token: str = "") -> List[Dict[str, Any]]:
        args: Dict[str, Any] = {}
        if access_token:
            args["access_token"] = access_token
        data = self.call_tool_sync(SQLBOT_TOOL_WS_LIST, args, retry_transport=True)
        items = data.get("workspaces") or data.get("data") or data.get("items") or []
        return items if isinstance(items, list) else []

    def list_datasources(
        self,
        *,
        workspace_id: str = "",
        access_token: str = "",
    ) -> List[Dict[str, Any]]:
        args: Dict[str, Any] = {
            "workspace_id": workspace_id or self.config.workspace_id,
        }
        if access_token:
            args["access_token"] = access_token
        data = self.call_tool_sync(SQLBOT_TOOL_DATASOURCE_LIST, args, retry_transport=True)
        items = data.get("datasources") or data.get("data") or data.get("items") or []
        return items if isinstance(items, list) else []

    def question(
        self,
        question: str,
        *,
        chat_id: str = "",
        access_token: str = "",
        datasource_id: str = "",
        workspace_id: str = "",
        response_mode: str = "data_and_summary",
    ) -> QuestionResult:
        args: Dict[str, Any] = {
            "question": question,
            "workspace_id": workspace_id or self.config.workspace_id,
            "datasource_id": datasource_id or self.config.default_datasource_id,
            "response_mode": response_mode,
        }
        if chat_id:
            args["chat_id"] = chat_id
        if access_token:
            args["access_token"] = access_token

        # No automatic retry after question is submitted
        data = self.call_tool_sync(
            SQLBOT_TOOL_QUESTION,
            args,
            timeout=self._timeout("request"),
            retry_transport=False,
        )
        parsed: ParsedQuestion = parse_question_result(data)
        return QuestionResult(
            raw=parsed.raw,
            sql=parsed.sql,
            columns=parsed.columns,
            rows=parsed.rows,
            chart=parsed.chart,
            summary=parsed.summary,
            title=parsed.title,
            chat_id=parsed.chat_id or chat_id,
            filters=parsed.filters,
            error=parsed.error,
        )


# Back-compat alias
SqlbotMcpClient = SQLBotMCPClient
