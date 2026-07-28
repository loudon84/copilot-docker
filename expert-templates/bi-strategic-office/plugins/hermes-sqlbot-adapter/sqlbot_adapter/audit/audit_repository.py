"""Append-only audit log (no passwords / tokens / full result sets)."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Set

from sqlbot_adapter.errors import scrub_secrets

_WRITE_LOCK = threading.Lock()

ALLOWED_FIELDS: Set[str] = {
    "ts",
    "action",
    "request_id",
    "query_id",
    "profile",
    "session_id",
    "user_id",
    "question",
    "row_count",
    "returned_row_count",
    "truncated",
    "sql_present",
    "error_code",
    "error_message",
    "source",
    "deleted",
    "upstream_record_id",
    "traceback",
    "original_column_count",
}


class AuditRepository:
    def __init__(
        self,
        audit_dir: str,
        enabled: bool = True,
        retention_days: int = 90,
    ):
        self.audit_dir = Path(audit_dir)
        self.enabled = enabled
        self.retention_days = int(retention_days)
        self._last_cleanup_day = ""
        if enabled:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.audit_dir, 0o700)
            except OSError:
                pass
            self.cleanup_old_files()

    def record(self, event: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        safe = scrub_secrets(dict(event))
        if "rows" in safe:
            safe["rows"] = (
                f"<{len(event['rows']) if isinstance(event.get('rows'), list) else '?'} rows omitted>"
            )
        if event.get("traceback"):
            safe["traceback"] = str(event["traceback"])[:4000]
        filtered = {k: v for k, v in safe.items() if k in ALLOWED_FIELDS or k == "ts"}
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = self.audit_dir / f"audit-{day}.jsonl"
        line = json.dumps(
            {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                **filtered,
            },
            ensure_ascii=False,
            default=str,
        )
        with _WRITE_LOCK:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        self.maybe_cleanup()

    def cleanup_old_files(self) -> int:
        days = max(int(self.retention_days), 1)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = 0
        if not self.audit_dir.exists():
            return 0
        for path in self.audit_dir.glob("audit-*.jsonl"):
            try:
                day_str = path.stem.replace("audit-", "")
                file_day = datetime.strptime(day_str, "%Y%m%d").replace(tzinfo=timezone.utc)
                if file_day < cutoff.replace(hour=0, minute=0, second=0, microsecond=0):
                    path.unlink(missing_ok=True)
                    deleted += 1
            except (ValueError, OSError):
                continue
        self._last_cleanup_day = datetime.now(timezone.utc).strftime("%Y%m%d")
        return deleted

    def maybe_cleanup(self) -> None:
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        if self._last_cleanup_day == day:
            return
        self.cleanup_old_files()
