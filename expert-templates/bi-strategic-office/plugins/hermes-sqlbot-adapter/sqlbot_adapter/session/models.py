"""Session models (schema v2)."""

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


SCHEMA_VERSION = 2
