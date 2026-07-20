from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _split_csv(value: str) -> List[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


@dataclass
class FinanceBiConfig:
    dsn: str = ""
    dialect: str = "postgresql"
    catalog_path: str = "/data/hermes/finance-bi/semantic"
    policy_path: str = "/data/hermes/finance-bi/policies"
    allowed_schemas: List[str] = field(default_factory=lambda: ["bi_finance", "bi_sales"])
    allowed_entities: List[str] = field(default_factory=list)
    default_currency: str = "HKD"
    timezone: str = "Asia/Hong_Kong"
    query_timeout_seconds: int = 30
    default_limit: int = 200
    hard_limit: int = 5000
    state_db: str = "/data/hermes/finance-bi/state/finance_bi.db"
    export_dir: str = "/data/hermes/workspace/exports/bi"
    retain_days: int = 7

    @classmethod
    def from_env(cls) -> "FinanceBiConfig":
        return cls(
            dsn=os.getenv("FINANCE_BI_DSN", ""),
            dialect=os.getenv("FINANCE_BI_DIALECT", "postgresql"),
            catalog_path=os.getenv("FINANCE_BI_CATALOG_PATH", "/data/hermes/finance-bi/semantic"),
            policy_path=os.getenv("FINANCE_BI_POLICY_PATH", "/data/hermes/finance-bi/policies"),
            allowed_schemas=_split_csv(os.getenv("FINANCE_BI_ALLOWED_SCHEMAS", "bi_finance,bi_sales")),
            allowed_entities=_split_csv(os.getenv("FINANCE_BI_ALLOWED_ENTITIES", "")),
            default_currency=os.getenv("FINANCE_BI_DEFAULT_CURRENCY", "HKD"),
            timezone=os.getenv("FINANCE_BI_TIMEZONE", "Asia/Hong_Kong"),
            query_timeout_seconds=int(os.getenv("FINANCE_BI_QUERY_TIMEOUT_SECONDS", "30")),
            default_limit=int(os.getenv("FINANCE_BI_DEFAULT_LIMIT", "200")),
            hard_limit=int(os.getenv("FINANCE_BI_HARD_LIMIT", "5000")),
            state_db=os.getenv("FINANCE_BI_STATE_DB", "/data/hermes/finance-bi/state/finance_bi.db"),
            export_dir=os.getenv(
                "FINANCE_BI_EXPORT_DIR",
                "/data/hermes/workspace/exports/bi",
            ),
            retain_days=int(os.getenv("FINANCE_BI_RETAIN_DAYS", "7")),
        )
