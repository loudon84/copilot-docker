"""Shared service wiring for finance_bi_* tools."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlbot_adapter.audit.audit_repository import AuditRepository
from sqlbot_adapter.client.mcp_client import QuestionResult, SqlbotMcpClient
from sqlbot_adapter.config import AdapterConfig, ensure_runtime_dirs, load_config
from sqlbot_adapter.contracts import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.normalizer.result_normalizer import new_query_id, normalize_question_result
from sqlbot_adapter.security.query_guard import guard_sql
from sqlbot_adapter.security.result_guard import apply_result_guards, rows_as_dicts
from sqlbot_adapter.session.session_store import SessionStore


class AdapterService:
    def __init__(self, config: AdapterConfig | None = None):
        self.config = config or load_config()
        ensure_runtime_dirs(self.config)
        self.store = SessionStore(
            self.config.state_db,
            key_material=self.config.username or "sqlbot-adapter",
            ttl_seconds=self.config.session_ttl_seconds,
        )
        self.audit = AuditRepository(self.config.audit_dir, enabled=self.config.audit_enabled)

    def _require_config(self) -> None:
        if not self.config.is_configured():
            missing = ", ".join(self.config.missing_required())
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_NOT_CONFIGURED,
                f"缺少 SQLBot 配置: {missing}",
            )

    def _client(self) -> SqlbotMcpClient:
        return SqlbotMcpClient(self.config)

    def _profile(self) -> str:
        return self.config.hermes_profile or "default"

    def ask(
        self,
        question: str,
        *,
        datasource_key: str = "",
        response_mode: str = "data_and_summary",
        session_id: str = "",
        user_id: str = "",
    ) -> Dict[str, Any]:
        self._require_config()
        q = (question or "").strip()
        if not q:
            raise SqlbotAdapterError(ErrorCode.INVALID_ARGUMENT, "question 不能为空")

        ds_id = self.config.resolve_datasource_id(datasource_key)
        session = self.store.get(
            hermes_profile=self._profile(),
            hermes_session_id=session_id or "default",
            hermes_user_id=user_id or "anonymous",
        )

        with self._client() as client:
            if session and session.access_token(self.config.username):
                client.set_auth(
                    access_token=session.access_token(self.config.username),
                    expires_at=session.token_expires_at,
                    chat_id=session.sqlbot_chat_id,
                    workspace_id=session.sqlbot_workspace_id or self.config.workspace_id,
                    datasource_id=session.sqlbot_datasource_id or ds_id,
                )
            else:
                auth = client.login(force=True)
                session = self.store.upsert(
                    hermes_profile=self._profile(),
                    hermes_session_id=session_id or "default",
                    hermes_user_id=user_id or "anonymous",
                    sqlbot_chat_id=auth.chat_id,
                    sqlbot_workspace_id=self.config.workspace_id,
                    sqlbot_datasource_id=ds_id,
                    access_token=auth.access_token,
                    token_expires_at=auth.expires_at,
                )

            create_chat = not bool(session.sqlbot_chat_id)
            result = client.question(
                q,
                chat_id=session.sqlbot_chat_id,
                datasource_id=ds_id,
                workspace_id=self.config.workspace_id,
                response_mode=response_mode or "data_and_summary",
                create_chat=create_chat,
            )
            # Refresh token after successful call
            auth = client._auth

        return self._finalize(
            result,
            question=q,
            datasource_key=datasource_key or "default",
            response_mode=response_mode,
            session_id=session_id,
            user_id=user_id,
            ds_id=ds_id,
            access_token=auth.access_token,
            token_expires_at=auth.expires_at,
        )

    def followup(
        self,
        instruction: str,
        *,
        session_id: str = "",
        user_id: str = "",
        response_mode: str = "data_and_summary",
    ) -> Dict[str, Any]:
        self._require_config()
        instr = (instruction or "").strip()
        if not instr:
            raise SqlbotAdapterError(ErrorCode.INVALID_ARGUMENT, "instruction 不能为空")

        session = self.store.get(
            hermes_profile=self._profile(),
            hermes_session_id=session_id or "default",
            hermes_user_id=user_id or "anonymous",
        )
        if not session or not session.sqlbot_chat_id:
            raise SqlbotAdapterError(
                ErrorCode.QUERY_CONTEXT_NOT_FOUND,
                "当前会话没有可继续的问数记录，请先发起一次查询。",
            )

        ds_id = session.sqlbot_datasource_id or self.config.default_datasource_id
        with self._client() as client:
            token = session.access_token(self.config.username)
            if token:
                client.set_auth(
                    access_token=token,
                    expires_at=session.token_expires_at,
                    chat_id=session.sqlbot_chat_id,
                    workspace_id=session.sqlbot_workspace_id or self.config.workspace_id,
                    datasource_id=ds_id,
                )
            else:
                auth = client.login(force=True)
                token = auth.access_token

            result = client.question(
                instr,
                chat_id=session.sqlbot_chat_id,
                datasource_id=ds_id,
                workspace_id=session.sqlbot_workspace_id or self.config.workspace_id,
                response_mode=response_mode,
                create_chat=False,
            )
            auth = client._auth

        return self._finalize(
            result,
            question=instr,
            datasource_key="",
            response_mode=response_mode,
            session_id=session_id,
            user_id=user_id,
            ds_id=ds_id,
            access_token=auth.access_token or token,
            token_expires_at=auth.expires_at or session.token_expires_at,
            preserve_chat_id=session.sqlbot_chat_id,
        )

    def explain(
        self,
        *,
        query_id: str = "",
        session_id: str = "",
        user_id: str = "",
    ) -> Dict[str, Any]:
        session = self.store.get(
            hermes_profile=self._profile(),
            hermes_session_id=session_id or "default",
            hermes_user_id=user_id or "anonymous",
        )
        if not session or not session.last_query_id:
            raise SqlbotAdapterError(
                ErrorCode.QUERY_CONTEXT_NOT_FOUND,
                "当前会话没有可解释的问数记录。",
            )
        if query_id and session.last_query_id != query_id:
            raise SqlbotAdapterError(
                ErrorCode.QUERY_CONTEXT_NOT_FOUND,
                f"未找到 query_id={query_id} 的本地问数记录。",
            )

        payload: Dict[str, Any] = {}
        if session.last_payload_json:
            try:
                payload = json.loads(session.last_payload_json)
            except json.JSONDecodeError:
                payload = {}

        return {
            "success": True,
            "query_id": session.last_query_id,
            "title": session.last_title or "",
            "datasource": {
                "key": "",
                "id_omitted": True,
                "workspace_omitted": True,
            },
            "query": {
                "question": session.last_question or "",
                "sql": session.last_sql or "",
                "filters": (payload.get("query") or {}).get("filters") or [],
                "row_count": (payload.get("query") or {}).get("row_count"),
                "truncated": (payload.get("query") or {}).get("truncated"),
            },
            "columns": payload.get("columns") or [],
            "rows": [],
            "chart": None,
            "summary": None,
            "warnings": ["explain 不重新查询数据库，不返回结果行。"],
            "meta": {
                "source": "sqlbot-adapter-local",
                "note": "SQLBot chat_id / token 已隐藏",
            },
        }

    def reset(self, *, session_id: str = "", user_id: str = "") -> Dict[str, Any]:
        deleted = self.store.reset(
            hermes_profile=self._profile(),
            hermes_session_id=session_id or "default",
            hermes_user_id=user_id or "anonymous",
        )
        self.audit.record(
            {
                "action": "reset",
                "session_id": session_id or "default",
                "user_id": user_id or "anonymous",
                "deleted": deleted,
            }
        )
        return {
            "success": True,
            "reset": True,
            "message": "已清除 SQLBot 会话映射，下次查询将新建对话。",
        }

    def _finalize(
        self,
        result: QuestionResult,
        *,
        question: str,
        datasource_key: str,
        response_mode: str,
        session_id: str,
        user_id: str,
        ds_id: str,
        access_token: str,
        token_expires_at: float,
        preserve_chat_id: str = "",
    ) -> Dict[str, Any]:
        identifiers = guard_sql(question, result.sql)
        dict_rows = rows_as_dicts(result.rows, result.columns)
        sliced, truncated, original, warnings = apply_result_guards(
            question,
            dict_rows,
            identifiers=identifiers,
            model_limit=self.config.model_result_rows,
            hard_limit=self.config.max_result_rows,
        )
        include_chart = (response_mode or "") == "chart" or (response_mode or "") == "data_and_summary"
        include_summary = (response_mode or "") != "data_only"
        if response_mode == "data_only":
            include_chart = False

        qid = new_query_id()
        normalized = normalize_question_result(
            result,
            question=question,
            datasource_key=datasource_key,
            datasource_name=datasource_key,
            query_id=qid,
            rows=sliced,
            truncated=truncated,
            original_row_count=original,
            warnings=warnings,
            include_chart=include_chart,
            include_summary=include_summary,
        )
        data = normalized.to_dict()

        chat_id = preserve_chat_id or result.chat_id
        self.store.upsert(
            hermes_profile=self._profile(),
            hermes_session_id=session_id or "default",
            hermes_user_id=user_id or "anonymous",
            sqlbot_chat_id=chat_id,
            sqlbot_workspace_id=self.config.workspace_id,
            sqlbot_datasource_id=ds_id,
            access_token=access_token,
            token_expires_at=token_expires_at,
            last_query_id=qid,
            last_sql=result.sql or "",
            last_question=question,
            last_title=normalized.title,
            last_payload_json=json.dumps(
                {
                    "query": data.get("query"),
                    "columns": data.get("columns"),
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        self.audit.record(
            {
                "action": "query",
                "query_id": qid,
                "session_id": session_id or "default",
                "user_id": user_id or "anonymous",
                "question": question[:500],
                "row_count": original,
                "truncated": truncated,
                "sql_present": bool(result.sql),
            }
        )
        return data


_SERVICE: Optional[AdapterService] = None


def get_service() -> AdapterService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = AdapterService()
    return _SERVICE


def reset_service_for_tests() -> None:
    global _SERVICE
    _SERVICE = None
