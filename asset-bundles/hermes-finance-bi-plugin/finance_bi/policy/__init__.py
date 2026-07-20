from __future__ import annotations

from typing import Set

import sqlglot
from sqlglot import exp

from finance_bi.catalog import SemanticCatalog
from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import ErrorCode, FinanceBiError


FORBIDDEN_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.TruncateTable,
)


class SqlPolicy:
    def __init__(self, catalog: SemanticCatalog, config: FinanceBiConfig):
        self.catalog = catalog
        self.config = config

    def validate(self, sql: str, allowed_tables: Set[str], allowed_columns: Set[str]) -> str:
        text = (sql or "").strip()
        if not text:
            raise FinanceBiError(ErrorCode.QUERY_POLICY_VIOLATION, "empty SQL")
        if ";" in text.rstrip(";"):
            raise FinanceBiError(ErrorCode.QUERY_POLICY_VIOLATION, "multi-statement SQL forbidden")

        dialect = self.config.sqlglot_dialect
        try:
            statements = sqlglot.parse(text, read=dialect)
        except Exception as exc:  # noqa: BLE001
            raise FinanceBiError(
                ErrorCode.QUERY_POLICY_VIOLATION,
                f"SQL parse failed: {exc}",
            ) from exc

        if len(statements) != 1 or statements[0] is None:
            raise FinanceBiError(ErrorCode.QUERY_POLICY_VIOLATION, "exactly one SELECT required")

        tree = statements[0]
        for node in tree.walk():
            if isinstance(node, FORBIDDEN_TYPES):
                raise FinanceBiError(
                    ErrorCode.QUERY_POLICY_VIOLATION,
                    f"forbidden statement type: {type(node).__name__}",
                )

        if not isinstance(tree, (exp.Select, exp.With)):
            if not (isinstance(tree, exp.With) or tree.find(exp.Select)):
                raise FinanceBiError(ErrorCode.QUERY_POLICY_VIOLATION, "only SELECT/WITH allowed")

        for table in tree.find_all(exp.Table):
            name = table.name
            db = table.db
            full = f"{db}.{name}" if db else name
            short = name
            if full not in allowed_tables and short not in allowed_tables:
                ok = False
                for allowed in allowed_tables:
                    if allowed.endswith("." + short) or allowed == short or allowed == full:
                        ok = True
                        break
                if not ok:
                    raise FinanceBiError(
                        ErrorCode.QUERY_POLICY_VIOLATION,
                        f"table not allowed: {full}",
                    )
            if db and db not in self.config.allowed_schemas and self.config.dialect != "sqlite":
                raise FinanceBiError(
                    ErrorCode.QUERY_POLICY_VIOLATION,
                    f"schema not allowed: {db}",
                )

        has_limit = bool(tree.find(exp.Limit))
        has_top = bool(getattr(exp, "Top", None) and tree.find(exp.Top))
        has_fetch = bool(getattr(exp, "Fetch", None) and tree.find(exp.Fetch))
        # Fallback text check for TOP (n) if sqlglot version differs
        if not (has_limit or has_top or has_fetch):
            upper = text.upper()
            if " TOP (" not in upper and " TOP(" not in upper and " FETCH " not in upper:
                raise FinanceBiError(
                    ErrorCode.QUERY_POLICY_VIOLATION,
                    "row limit is required (LIMIT / TOP / FETCH)",
                )

        return text

    def allowed_objects_for_dataset(self, dataset_id: str) -> tuple[Set[str], Set[str]]:
        ds = self.catalog.datasets[dataset_id]
        table = str(ds["physical_table"])
        tables = {table, table.split(".")[-1]}
        cols: Set[str] = set((ds.get("fields") or {}).keys())
        cols.update(ds.get("available_dimensions") or [])
        return tables, cols
