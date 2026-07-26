"""Append-only audit log (no passwords / tokens / full result sets)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class AuditRepository:
    def __init__(self, audit_dir: str, enabled: bool = True):
        self.audit_dir = Path(audit_dir)
        self.enabled = enabled
        if enabled:
            self.audit_dir.mkdir(parents=True, exist_ok=True)

    def record(self, event: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        safe = dict(event)
        for key in ("password", "access_token", "token", "authorization"):
            safe.pop(key, None)
        # Never persist full rows
        if "rows" in safe:
            safe["rows"] = f"<{len(safe['rows']) if isinstance(safe['rows'], list) else '?'} rows omitted>"
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = self.audit_dir / f"audit-{day}.jsonl"
        line = json.dumps(
            {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                **safe,
            },
            ensure_ascii=False,
            default=str,
        )
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
