from __future__ import annotations

from typing import List, Set, Tuple

from finance_bi.catalog import SemanticCatalog
from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import ErrorCode, FinanceBiError, SemanticQuery


class SqlCompiler:
    """Deterministic SemanticQuery -> SQL compiler (no LLM SQL)."""

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

        # SQLite fixture uses unqualified table name
        if self.config.dialect == "sqlite":
            table_sql = table.split(".")[-1]
        else:
            table_sql = table

        select_parts: List[str] = []
        group_parts: List[str] = []
        having_parts: List[str] = []
        where_parts: List[str] = []
        warnings: List[str] = []

        for dim in query.dimensions:
            field = self._dim_field(dataset, dim)
            select_parts.append(f"{field} AS {dim}")
            group_parts.append(field)

        for mid in query.metrics:
            metric = self.catalog.metrics[mid]
            expr = str(metric.get("expression") or "")
            if not expr:
                raise FinanceBiError(ErrorCode.METRIC_NOT_FOUND, f"metric expression missing: {mid}")
            # For SQLite ratio, keep expression as-is
            select_parts.append(f"({expr}) AS {mid}")

        having_fields: Set[str] = set()
        for flt in query.filters:
            if flt.field in query.metrics or flt.field in self.catalog.metrics:
                # HAVING on aggregated metric
                mid = flt.field if flt.field in self.catalog.metrics else flt.field
                metric = self.catalog.metrics.get(mid)
                if not metric:
                    raise FinanceBiError(ErrorCode.METRIC_NOT_FOUND, f"metric not found: {mid}")
                expr = str(metric.get("expression"))
                having_parts.append(self._cmp(expr, flt.operator, flt.value))
                having_fields.add(mid)
            else:
                field = self._dim_field(dataset, flt.field)
                where_parts.append(self._cmp(field, flt.operator, flt.value))

        # entity RLS injection
        entity_field = dataset.get("entity_field") or "entity_code"
        if self.config.allowed_entities:
            entities = ", ".join(self._quote(e) for e in self.config.allowed_entities)
            where_parts.append(f"{entity_field} IN ({entities})")
        else:
            warnings.append("FINANCE_BI_ALLOWED_ENTITIES is empty; no entity filter injected")

        limit = min(int(query.limit or self.config.default_limit), self.config.hard_limit)
        if limit <= 0:
            limit = self.config.default_limit

        order_sql = ""
        if query.order_by:
            bits = []
            for ob in query.order_by:
                direction = "DESC" if str(ob.direction).lower().startswith("d") else "ASC"
                # order by alias if metric/dim
                bits.append(f"{ob.field} {direction}")
            order_sql = " ORDER BY " + ", ".join(bits)

        sql = "SELECT " + ", ".join(select_parts) + f" FROM {table_sql}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        if group_parts:
            sql += " GROUP BY " + ", ".join(group_parts)
        if having_parts:
            sql += " HAVING " + " AND ".join(having_parts)
        sql += order_sql
        sql += f" LIMIT {limit}"
        return sql, warnings

    def _dim_field(self, dataset: dict, dim_or_field: str) -> str:
        dim = self.catalog.dimensions.get(dim_or_field)
        if dim:
            return str(dim.get("field") or dim_or_field)
        fields = dataset.get("fields") or {}
        if dim_or_field in fields or dim_or_field in (dataset.get("available_dimensions") or []):
            return dim_or_field
        # allow time/entity fields
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
        return "'" + value.replace("'", "''") + "'"
