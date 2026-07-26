"""Append-only audit log (no passwords / tokens / full result sets)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from sqlbot_adapter.errors import scrub_secrets


class AuditRepository:
    def __init__(self, audit_dir: str, enabled: bool = True):
        self.audit_dir = Path(audit_dir)
        self.enabled = enabled
        if enabled:
            self.audit_dir.mkdir(parents=True, exist_ok=True)

    def record(self, event: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        safe = scrub_secrets(dict(event))
        if "rows" in safe:
            safe["rows"] = f"<{len(event['rows']) if isinstance(event.get('rows'), list) else '?'} rows omitted>"
        # traceback allowed in audit only (not tool result)
        if event.get("traceback"):
            safe["traceback"] = str(event["traceback"])[:4000]
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
