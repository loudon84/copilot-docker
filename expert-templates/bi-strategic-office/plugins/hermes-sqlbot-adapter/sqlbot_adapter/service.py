"""SQLBotService — business orchestration for finance_bi_* tools."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlbot_adapter.audit.audit_repository import AuditRepository
from sqlbot_adapter.client.mcp_client import QuestionResult, SQLBotMCPClient
from sqlbot_adapter.config import AdapterConfig, ensure_runtime_dirs, load_config
from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError
from sqlbot_adapter.normalizer.result_normalizer import new_query_id, normalize_question_result
from sqlbot_adapter.runtime_context import RuntimeContext, resolve_runtime_context
from sqlbot_adapter.security.query_guard import guard_sql
from sqlbot_adapter.security.result_guard import apply_result_guards, rows_as_dicts
from sqlbot_adapter.session.session_store import SessionStore

TZ_CN = timezone(timedelta(hours=8))


class SQLBotService:
    def __init__(self, config: AdapterConfig | None = None):
        self.config = config or load_config()
        ensure_runtime_dirs(self.config)
        self._require_config()
        self.store = SessionStore(
            self.config.state_db,
            encryption_key=self.config.session_encryption_key,
            ttl_seconds=self.config.session_ttl_seconds,
        )
        self.audit = AuditRepository(self.config.audit_dir, enabled=self.config.audit_enabled)
        self.client = SQLBotMCPClient(self.config)

    def _require_config(self) -> None:
        if not self.config.is_configured():
            missing = ", ".join(self.config.missing_required())
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_NOT_CONFIGURED,
                f"缺少 SQLBot 配置: {missing}",
            )

    def _ctx(self, hermes_ctx: Any = None) -> RuntimeContext:
        return resolve_runtime_context(hermes_ctx=hermes_ctx)

    def start_session(self, ctx: RuntimeContext) -> Dict[str, Any]:
        started = self.client.start()
        _tok = str(started.get("access_token") or "")
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(started.get("expires_in") or 3600))
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.store.upsert(
            profile_name=ctx.profile_name,
            hermes_session_id=ctx.hermes_session_id,
            hermes_user_id=ctx.hermes_user_id,
            access_token=_tok,
            sqlbot_chat_id=str(started.get("chat_id") or ""),
            workspace_id=self.config.workspace_id,
            datasource_id=self.config.default_datasource_id,
            token_expires_at=expires_at,
        )
        return {"chat_id": started.get("chat_id"), "ok": True}

    def ask(
        self,
        question: str,
        *,
        datasource_key: str = "",
        response_mode: str = "data_and_summary",
        hermes_ctx: Any = None,
    ) -> Dict[str, Any]:
        ctx = self._ctx(hermes_ctx)
        q = (question or "").strip()
        if not q:
            raise SqlbotAdapterError(ErrorCode.INVALID_ARGUMENT, "question 不能为空")

        ds_id = self.config.resolve_datasource_id(datasource_key)
        session = self.store.get(
            profile_name=ctx.profile_name,
            hermes_session_id=ctx.hermes_session_id,
            hermes_user_id=ctx.hermes_user_id,
        )
        token = ""
        chat_id = ""
        if session:
            try:
                token = self.store.access_token(session)
                chat_id = session.sqlbot_chat_id
            except SqlbotAdapterError:
                self.store.reset(
                    profile_name=ctx.profile_name,
                    hermes_session_id=ctx.hermes_session_id,
                    hermes_user_id=ctx.hermes_user_id,
                )
                session = None

        if not session or not token or not chat_id:
            started = self.client.start()
            token = started["access_token"]
            chat_id = str(started.get("chat_id") or "")
            expires_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=int(started.get("expires_in") or 3600))
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.store.upsert(
                profile_name=ctx.profile_name,
                hermes_session_id=ctx.hermes_session_id,
                hermes_user_id=ctx.hermes_user_id,
                access_token=token,
                sqlbot_chat_id=chat_id,
                workspace_id=self.config.workspace_id,
                datasource_id=ds_id,
                token_expires_at=expires_at,
            )

        result = self.client.question(
            q,
            chat_id=chat_id,
            access_token=token,
            datasource_id=ds_id,
            workspace_id=self.config.workspace_id,
            response_mode=response_mode or "data_and_summary",
        )
        return self._finalize(
            result,
            question=q,
            datasource_key=datasource_key or "default",
            response_mode=response_mode,
            ctx=ctx,
            ds_id=ds_id,
            access_token=token,
            chat_id=chat_id or result.chat_id,
        )

    def followup(
        self,
        instruction: str,
        *,
        response_mode: str = "data_and_summary",
        hermes_ctx: Any = None,
    ) -> Dict[str, Any]:
        ctx = self._ctx(hermes_ctx)
        instr = (instruction or "").strip()
        if not instr:
            raise SqlbotAdapterError(ErrorCode.INVALID_ARGUMENT, "instruction 不能为空")

        session = self.store.get(
            profile_name=ctx.profile_name,
            hermes_session_id=ctx.hermes_session_id,
            hermes_user_id=ctx.hermes_user_id,
        )
        if not session or not session.sqlbot_chat_id:
            raise SqlbotAdapterError(
                ErrorCode.QUERY_CONTEXT_NOT_FOUND,
                "当前会话没有可继续的问数记录，请先发起一次查询。",
            )
        try:
            token = self.store.access_token(session)
        except SqlbotAdapterError:
            self.store.reset(
                profile_name=ctx.profile_name,
                hermes_session_id=ctx.hermes_session_id,
                hermes_user_id=ctx.hermes_user_id,
            )
            raise SqlbotAdapterError(
                ErrorCode.SQLBOT_SESSION_EXPIRED,
                "会话已失效，请重新发起查询。",
            )

        ds_id = session.datasource_id or self.config.default_datasource_id
        result = self.client.question(
            instr,
            chat_id=session.sqlbot_chat_id,
            access_token=token,
            datasource_id=ds_id,
            workspace_id=session.workspace_id or self.config.workspace_id,
            response_mode=response_mode,
        )
        return self._finalize(
            result,
            question=instr,
            datasource_key="",
            response_mode=response_mode,
            ctx=ctx,
            ds_id=ds_id,
            access_token=token,
            chat_id=session.sqlbot_chat_id,
        )

    def explain(self, *, query_id: str = "", hermes_ctx: Any = None) -> Dict[str, Any]:
        ctx = self._ctx(hermes_ctx)
        session = self.store.get(
            profile_name=ctx.profile_name,
            hermes_session_id=ctx.hermes_session_id,
            hermes_user_id=ctx.hermes_user_id,
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
            "datasource": {"key": "", "id_omitted": True},
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
            "meta": {"source": "sqlbot-adapter-local"},
        }

    def reset(self, *, hermes_ctx: Any = None) -> Dict[str, Any]:
        ctx = self._ctx(hermes_ctx)
        deleted = self.store.reset(
            profile_name=ctx.profile_name,
            hermes_session_id=ctx.hermes_session_id,
            hermes_user_id=ctx.hermes_user_id,
        )
        self.audit.record(
            {
                "action": "reset",
                "request_id": ctx.request_id,
                "profile": ctx.profile_name,
                "session_id": ctx.hermes_session_id,
                "user_id": ctx.hermes_user_id,
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
        ctx: RuntimeContext,
        ds_id: str,
        access_token: str,
        chat_id: str,
    ) -> Dict[str, Any]:
        qid = new_query_id()

        # SQL generated but execution failed — still guard SQL if present, keep session
        if result.error is not None:
            if result.sql:
                try:
                    guard_sql(question, result.sql)
                except SqlbotAdapterError as guard_err:
                    self._audit_fail(ctx, qid, question, result.sql, guard_err)
                    raise
            self.store.upsert(
                profile_name=ctx.profile_name,
                hermes_session_id=ctx.hermes_session_id,
                hermes_user_id=ctx.hermes_user_id,
                access_token=access_token,
                sqlbot_chat_id=chat_id or result.chat_id,
                workspace_id=self.config.workspace_id,
                datasource_id=ds_id,
                last_query_id=qid,
                last_sql=result.sql or "",
                last_question=question,
                last_title=result.title or question[:80],
            )
            self._audit_fail(ctx, qid, question, result.sql, result.error)
            raise result.error

        identifiers = guard_sql(question, result.sql)
        dict_rows = rows_as_dicts(result.rows, result.columns)
        sliced, truncated, original, warnings = apply_result_guards(
            question,
            dict_rows,
            identifiers=identifiers,
            model_limit=self.config.model_result_rows,
            hard_limit=self.config.max_result_rows,
        )
        include_chart = response_mode in {"chart", "data_and_summary"}
        include_summary = response_mode != "data_only"
        if response_mode == "data_only":
            include_chart = False

        # Adapt QuestionResult for normalizer (compatible shape)
        class _QR:
            pass

        qr = _QR()
        qr.sql = result.sql
        qr.columns = result.columns
        qr.rows = result.rows
        qr.chart = result.chart
        qr.summary = result.summary
        qr.title = result.title
        qr.filters = result.filters
        qr.chat_id = result.chat_id

        normalized = normalize_question_result(
            qr,  # type: ignore[arg-type]
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

        self.store.upsert(
            profile_name=ctx.profile_name,
            hermes_session_id=ctx.hermes_session_id,
            hermes_user_id=ctx.hermes_user_id,
            access_token=access_token,
            sqlbot_chat_id=chat_id or result.chat_id,
            workspace_id=self.config.workspace_id,
            datasource_id=ds_id,
            last_query_id=qid,
            last_sql=result.sql or "",
            last_question=question,
            last_title=normalized.title,
            last_payload_json=json.dumps(
                {"query": data.get("query"), "columns": data.get("columns")},
                ensure_ascii=False,
                default=str,
            ),
        )
        self.store.record_query(
            query_id=qid,
            profile_name=ctx.profile_name,
            hermes_session_id=ctx.hermes_session_id,
            hermes_user_id=ctx.hermes_user_id,
            question=question,
            generated_sql=result.sql or "",
            datasource_id=ds_id,
            workspace_id=self.config.workspace_id,
            status="ok",
        )
        self.audit.record(
            {
                "action": "query",
                "request_id": ctx.request_id,
                "query_id": qid,
                "profile": ctx.profile_name,
                "session_id": ctx.hermes_session_id,
                "user_id": ctx.hermes_user_id,
                "question": question[:500],
                "row_count": original,
                "truncated": truncated,
                "sql_present": bool(result.sql),
            }
        )
        return data

    def _audit_fail(
        self,
        ctx: RuntimeContext,
        qid: str,
        question: str,
        sql: str,
        err: SqlbotAdapterError,
    ) -> None:
        self.store.record_query(
            query_id=qid,
            profile_name=ctx.profile_name,
            hermes_session_id=ctx.hermes_session_id,
            hermes_user_id=ctx.hermes_user_id,
            question=question,
            generated_sql=sql or "",
            status="error",
            error_code=err.code.value,
            error_message=err.message,
        )
        self.audit.record(
            {
                "action": "query_error",
                "request_id": ctx.request_id,
                "query_id": qid,
                "profile": ctx.profile_name,
                "error_code": err.code.value,
                "error_message": err.message,
                "traceback": (err.traceback_text or "")[:4000],
                "source": err.source,
            }
        )


_SERVICE: Optional[SQLBotService] = None


def get_service() -> SQLBotService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SQLBotService()
    return _SERVICE


def reset_service_for_tests() -> None:
    global _SERVICE
    _SERVICE = None
