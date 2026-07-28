#!/usr/bin/env python3
"""Initialize sqlbot-adapter SQLite schema (idempotent)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running from package scripts/
_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Init sqlbot session store schema v3")
    parser.add_argument("--data-dir", default="", help="Hermes data dir (contains sqlbot-adapter/)")
    parser.add_argument("--db", default="", help="Explicit sqlite path")
    parser.add_argument("--encryption-key", default="", help="SQLBOT_SESSION_ENCRYPTION_KEY")
    args = parser.parse_args()

    key = (args.encryption_key or os.environ.get("SQLBOT_SESSION_ENCRYPTION_KEY") or "").strip()
    if not key:
        # Install-time: allow a bootstrap key only for schema creation when env empty
        # Runtime plugin still requires real key via config.is_configured()
        key = "install-bootstrap-key-not-for-production"

    if args.db:
        db_path = args.db
    elif args.data_dir:
        db_path = str(Path(args.data_dir) / "sqlbot-adapter" / "state" / "sqlbot_sessions.db")
    else:
        db_path = os.environ.get(
            "SQLBOT_STATE_DB",
            "/data/hermes/sqlbot-adapter/state/sqlbot_sessions.db",
        )

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    audit_dir = Path(db_path).resolve().parents[1] / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    from sqlbot_adapter.session.session_store import SessionStore

    store = SessionStore(db_path, encryption_key=key, ttl_seconds=86400)
    store.init_schema()
    print(f"OK: schema ready at {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
