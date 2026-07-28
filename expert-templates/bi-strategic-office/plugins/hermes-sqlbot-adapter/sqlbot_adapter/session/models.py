"""Session models (schema v3)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionRecord:
    profile_name: str
    hermes_session_id: str
    hermes_user_id: str
    access_token_encrypted: str = ""
    sqlbot_chat_id: str = ""
    workspace_id: str = ""
    datasource_id: str = ""
    token_expires_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    expires_at: str = ""
    last_query_id: str = ""
    last_sql: str = ""
    last_question: str = ""
    last_title: str = ""
    last_payload_json: str = ""
    session_version: int = 3
    last_upstream_record_id: str = ""
    last_response_mode: str = ""
    last_error_code: str = ""


@dataclass
class QueryRecord:
    query_id: str
    profile_name: str
    hermes_session_id: str
    hermes_user_id: str
    question: str = ""
    generated_sql: str = ""
    datasource_id: str = ""
    workspace_id: str = ""
    status: str = "ok"
    error_code: str = ""
    error_message: str = ""
    created_at: str = ""
    completed_at: str = ""
    upstream_record_id: str = ""
    query_payload_json: str = ""
    title: str = ""
    row_count: int = 0
    returned_row_count: int = 0
    truncated: int = 0
    request_id: str = ""


SCHEMA_VERSION = 3
