from __future__ import annotations

import re
from typing import List, Optional, Tuple

from finance_bi.catalog import SemanticCatalog
from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import ErrorCode, FinanceBiError, SemanticQuery


class SqlCompiler:
    """Deterministic SemanticQuery -> SQL compiler (no LLM SQL)."""

    _SUM_RE = re.compile(r"(?is)^\s*SUM\s*\((.*)\)\s*$")

    def __init__(self, catalog: SemanticCatalog, config: FinanceBiConfig):
        self.catalog = catalog
        self.config = config

    def compile(self, query: SemanticQuery) -> Tuple[str, List[str]]:
        dataset = self.catalog.datasets.get(query.dataset)
        if not dataset:
            raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, f"unknown dataset: {query.dataset}")

        table = str(dataset["physical_table"])
        schema = table.split(".", 1)[0] if "." in table else ""
        if schema and schema not in self.config.allowed_schemas:
            raise FinanceBiError(
                ErrorCode.QUERY_POLICY_VIOLATION,
                f"schema not allowed: {schema}",
            )

        table_sql = self._format_table(table)
        detail = str(query.mode or "aggregate").lower() == "detail"

        select_parts: List[str] = []
        group_parts: List[str] = []
        having_parts: List[str] = []
        where_parts: List[str] = []
        warnings: List[str] = []

        for dim in query.dimensions:
            field = self._dim_field(dataset, dim)
            select_parts.append(f"{field} AS {dim}")
            if not detail:
                group_parts.append(field)

        for mid in query.metrics:
            metric = self.catalog.metrics[mid]
            expr = str(metric.get("expression") or "")
            if not expr:
                raise FinanceBiError(ErrorCode.METRIC_NOT_FOUND, f"metric expression missing: {mid}")
            if detail:
                # Skip ratio metrics in detail mode; unwrap SUM(col) -> col
                if str(metric.get("aggregation") or "").lower() == "ratio" or "/" in expr:
                    warnings.append(f"detail mode skipped ratio metric: {mid}")
                    continue
                detail_expr = self._unwrap_sum(expr)
                select_parts.append(f"({detail_expr}) AS {mid}")
            else:
                select_parts.append(f"({expr}) AS {mid}")

        if not select_parts:
            raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, "query has no selectable columns")

        for flt in query.filters:
            if (not detail) and (flt.field in query.metrics or flt.field in self.catalog.metrics):
                mid = flt.field if flt.field in self.catalog.metrics else flt.field
                metric = self.catalog.metrics.get(mid)
                if not metric:
                    raise FinanceBiError(ErrorCode.METRIC_NOT_FOUND, f"metric not found: {mid}")
                expr = str(metric.get("expression"))
                having_parts.append(self._cmp(expr, flt.operator, flt.value))
            else:
                field = self._dim_field(dataset, flt.field)
                where_parts.append(self._cmp(field, flt.operator, flt.value))

        entity_field = str(dataset.get("entity_field") or "entity_code")
        if self.config.allowed_entities:
            # Normalize aliases: OU_101 / ou_101 -> 101 when entity_field is ou_code
            normalized: List[str] = []
            for raw in self.config.allowed_entities:
                val = str(raw).strip()
                if not val:
                    continue
                if entity_field == "ou_code":
                    m = re.match(r"(?i)^OU[_\-]?(\d+)$", val)
                    if m:
                        val = m.group(1)
                normalized.append(val)
            if normalized:
                entities = ", ".join(self._quote(e) for e in normalized)
                where_parts.append(f"{entity_field} IN ({entities})")
        else:
            warnings.append(
                "FINANCE_BI_ALLOWED_ENTITIES is empty — no OU/主体 scope filter. "
                "Customer/brand filters still work via WHERE on customer_name etc."
            )

        limit = min(int(query.limit or self.config.default_limit), self.config.hard_limit)
        if limit <= 0:
            limit = self.config.default_limit

        order_sql = ""
        if query.order_by:
            bits = []
            for ob in query.order_by:
                direction = "DESC" if str(ob.direction).lower().startswith("d") else "ASC"
                field = ob.field
                # In detail mode order by raw column if metric was skipped
                if detail and field in self.catalog.metrics:
                    metric = self.catalog.metrics[field]
                    if str(metric.get("aggregation") or "").lower() == "ratio" or "/" in str(
                        metric.get("expression") or ""
                    ):
                        continue
                    field = field  # alias still selected if not skipped
                bits.append(f"{field} {direction}")
            if bits:
                order_sql = " ORDER BY " + ", ".join(bits)
        if not order_sql and self.config.is_mssql:
            order_sql = " ORDER BY (SELECT NULL)"

        select_kw = "SELECT"
        limit_sql = ""
        if self.config.is_mssql:
            select_kw = f"SELECT TOP ({limit})"
        else:
            limit_sql = f" LIMIT {limit}"

        sql = f"{select_kw} " + ", ".join(select_parts) + f" FROM {table_sql}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        if group_parts:
            sql += " GROUP BY " + ", ".join(group_parts)
        if having_parts:
            sql += " HAVING " + " AND ".join(having_parts)
        sql += order_sql
        sql += limit_sql
        return sql, warnings

    def _unwrap_sum(self, expr: str) -> str:
        m = self._SUM_RE.match(expr.strip())
        return m.group(1).strip() if m else expr

    def _format_table(self, table: str) -> str:
        if self.config.dialect == "sqlite":
            return table.split(".")[-1]
        if self.config.is_mssql:
            parts = [p for p in table.split(".") if p]
            return ".".join(f"[{p}]" for p in parts)
        return table

    def _dim_field(self, dataset: dict, dim_or_field: str) -> str:
        dim = self.catalog.dimensions.get(dim_or_field)
        if dim:
            return str(dim.get("field") or dim_or_field)
        fields = dataset.get("fields") or {}
        if dim_or_field in fields or dim_or_field in (dataset.get("available_dimensions") or []):
            return dim_or_field
        if dim_or_field in (
            dataset.get("primary_time_field"),
            dataset.get("entity_field"),
            dataset.get("currency_field"),
        ):
            return dim_or_field
        raise FinanceBiError(ErrorCode.DIMENSION_NOT_FOUND, f"unknown field: {dim_or_field}")

    def _cmp(self, left: str, op: str, value) -> str:
        op = (op or "").lower()
        if op in ("eq", "=", "=="):
            return f"{left} = {self._literal(value)}"
        if op in ("neq", "!=", "<>"):
            return f"{left} <> {self._literal(value)}"
        if op in ("gt", ">"):
            return f"{left} > {self._literal(value)}"
        if op in ("gte", ">="):
            return f"{left} >= {self._literal(value)}"
        if op in ("lt", "<"):
            return f"{left} < {self._literal(value)}"
        if op in ("lte", "<="):
            return f"{left} <= {self._literal(value)}"
        if op in ("like", "contains", "ilike"):
            text = str(value)
            if op == "contains" or (op == "like" and "%" not in text and "_" not in text):
                text = f"%{text}%"
            # case-insensitive: LOWER both sides (works on mssql/sqlite/pg)
            return f"LOWER({left}) LIKE LOWER({self._literal(text)})"
        if op == "in":
            if not isinstance(value, (list, tuple)):
                raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, "IN value must be list")
            return f"{left} IN ({', '.join(self._literal(v) for v in value)})"
        raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, f"unsupported operator: {op}")

    def _literal(self, value) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        return self._quote(str(value))

    def _quote(self, value: str) -> str:
        escaped = value.replace("'", "''")
        if self.config.is_mssql:
            return "N'" + escaped + "'"
        return "'" + escaped + "'"
