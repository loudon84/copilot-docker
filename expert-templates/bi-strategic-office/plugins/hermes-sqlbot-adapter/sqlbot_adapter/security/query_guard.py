"""SQL read-only checks and explicit identifier preservation (postflight)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from sqlbot_adapter.errors import ErrorCode, SqlbotAdapterError

FORBIDDEN_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CALL",
    "COPY",
    "GRANT",
    "REVOKE",
    "CREATE",
    "REPLACE",
    "EXEC",
    "EXECUTE",
)

SYSTEM_SCHEMAS = frozenset(
    {
        "sys",
        "INFORMATION_SCHEMA",
        "information_schema",
        "pg_catalog",
        "mysql",
        "performance_schema",
    }
)

ID_VALUE_RE = re.compile(r"[A-Za-z0-9_./#\-]+")


@dataclass
class ExplicitIdentifier:
    value: str
    source: str = ""
    field: str = ""
    match: str = "exact"


def _default_identifier_specs() -> List[Dict[str, Any]]:
    return [
        {
            "names": [
                "交易凭证编号",
                "交易凭证号",
                "应收交易编号",
                "应收发票编号",
                "AR发票号",
                "凭证号",
                "单据号",
                "ar_trx_number",
                "trx_number",
            ],
            "field": "ar_trx_number",
            "match": "exact",
        },
        {
            "names": ["订单号", "订单编号"],
            "field": "order_number",
            "match": "exact",
        },
        {
            "names": ["客户编号", "客户编码", "customer_code"],
            "field": "customer_code",
            "match": "exact",
        },
    ]


def extract_explicit_identifiers(
    question: str,
    *,
    business_identifiers: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[ExplicitIdentifier]:
    specs = list(business_identifiers) if business_identifiers else _default_identifier_specs()
    found: List[ExplicitIdentifier] = []
    seen = set()
    text = question or ""

    for spec in specs:
        names = list(spec.get("names") or [])
        field = str(spec.get("field") or "")
        match = str(spec.get("match") or "exact")
        for name in names:
            name = str(name).strip()
            if not name:
                continue
            # Chinese / word label followed by optional separator then value
            pat = re.compile(
                rf"(?i)(?:{re.escape(name)})\s*[=:：]?\s*({ID_VALUE_RE.pattern})"
            )
            for m in pat.finditer(text):
                val = m.group(1).strip()
                # Avoid capturing trailing Chinese if any
                val = re.match(ID_VALUE_RE, val).group(0) if re.match(ID_VALUE_RE, val) else val
                if not val or val.lower() in seen:
                    continue
                seen.add(val.lower())
                found.append(
                    ExplicitIdentifier(value=val, source=m.group(0), field=field, match=match)
                )
            # Also: name glued to value without separator (交易凭证编号101IN...)
            pat2 = re.compile(
                rf"(?i)(?:{re.escape(name)})({ID_VALUE_RE.pattern})"
            )
            for m in pat2.finditer(text):
                val = m.group(1).strip()
                if not val or val.lower() in seen:
                    continue
                seen.add(val.lower())
                found.append(
                    ExplicitIdentifier(value=val, source=m.group(0), field=field, match=match)
                )

    return found


def assert_readonly_sql(sql: str, *, dialect: str = "tsql") -> None:
    text = (sql or "").strip()
    if not text:
        return

    stripped = text.rstrip().rstrip(";")
    if ";" in stripped:
        raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：禁止多语句")

    upper = text.upper()
    scrubbed = re.sub(r"'([^']|'')*'", "''", text)
    scrubbed = re.sub(r'"([^"]|"")*"', '""', scrubbed)
    scrubbed = re.sub(r"\[[^\]]*\]", "[]", scrubbed)
    scrubbed_upper = scrubbed.upper()

    # SELECT INTO is a write in SQL Server
    if re.search(r"\bSELECT\b[\s\S]*\bINTO\b", scrubbed_upper):
        raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：禁止 SELECT INTO")

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", scrubbed_upper):
            raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, f"SQL 不符合只读要求：禁止 {kw}")

    try:
        import sqlglot
        from sqlglot import exp

        read_dialect = dialect or "tsql"
        statements = sqlglot.parse(text, read=read_dialect, error_level=None)
        if not statements:
            if not (upper.lstrip().startswith("SELECT") or upper.lstrip().startswith("WITH")):
                raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：仅允许 SELECT")
            return
        if len(statements) > 1:
            raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：禁止多语句")
        stmt = statements[0]
        if stmt is None:
            return

        for node in stmt.walk():
            if isinstance(
                node,
                (
                    exp.Insert,
                    exp.Update,
                    exp.Delete,
                    exp.Drop,
                    exp.Create,
                    exp.Alter,
                    exp.Command,
                    exp.Merge,
                ),
            ):
                raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求")
            # SELECT INTO
            if isinstance(node, exp.Table) and getattr(node, "args", None):
                pass
            if type(node).__name__ in {"Into", "Create"}:
                raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：禁止 SELECT INTO")

            if isinstance(node, exp.Table):
                parts = [p for p in [node.catalog, node.db, node.name] if p]
                if len(parts) >= 3:
                    raise SqlbotAdapterError(
                        ErrorCode.UNSAFE_SQL,
                        "SQL 不符合只读要求：禁止跨数据库多段对象名",
                    )
                schema = str(node.db or "")
                if schema in SYSTEM_SCHEMAS or schema.lower() in {s.lower() for s in SYSTEM_SCHEMAS}:
                    raise SqlbotAdapterError(
                        ErrorCode.UNSAFE_SQL,
                        f"SQL 不符合只读要求：禁止访问系统 Schema {schema}",
                    )
                tname = str(node.name or "").lower()
                if tname.startswith("sys") and schema.lower() in {"", "dbo", "sys"}:
                    if tname in {"sysobjects", "syscolumns", "systables"} or tname.startswith("sys."):
                        raise SqlbotAdapterError(
                            ErrorCode.UNSAFE_SQL,
                            "SQL 不符合只读要求：禁止访问系统表",
                        )
    except ImportError:
        if not (upper.lstrip().startswith("SELECT") or upper.lstrip().startswith("WITH")):
            raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：仅允许 SELECT")
    except SqlbotAdapterError:
        raise
    except Exception:
        if not (upper.lstrip().startswith("SELECT") or upper.lstrip().startswith("WITH")):
            raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：仅允许 SELECT")


def _collect_predicate_literals(sql: str, *, dialect: str = "tsql") -> List[tuple[str, str]]:
    """Return list of (column_or_empty, literal_value) from WHERE/JOIN/HAVING predicates."""
    out: List[tuple[str, str]] = []
    try:
        import sqlglot
        from sqlglot import exp

        statements = sqlglot.parse(sql, read=dialect or "tsql", error_level=None)
        if not statements or statements[0] is None:
            return out
        stmt = statements[0]

        def col_name(node: Any) -> str:
            if isinstance(node, exp.Column):
                return str(node.name or "")
            return ""

        for node in stmt.walk():
            if isinstance(node, exp.EQ):
                left, right = node.left, node.right
                if isinstance(right, exp.Literal):
                    out.append((col_name(left), str(right.this)))
                elif isinstance(left, exp.Literal):
                    out.append((col_name(right), str(left.this)))
            elif isinstance(node, exp.In) and not getattr(node, "query", None):
                cname = col_name(node.this)
                for item in node.expressions or []:
                    if isinstance(item, exp.Literal):
                        out.append((cname, str(item.this)))
            elif type(node).__name__ == "In" and hasattr(node, "expressions"):
                cname = col_name(getattr(node, "this", None))
                for item in getattr(node, "expressions", []) or []:
                    if isinstance(item, exp.Literal):
                        out.append((cname, str(item.this)))
    except Exception:
        return out
    return out


def assert_identifiers_preserved(
    question: str,
    sql: str,
    *,
    business_identifiers: Optional[Sequence[Dict[str, Any]]] = None,
    dialect: str = "tsql",
) -> List[ExplicitIdentifier]:
    identifiers = extract_explicit_identifiers(question, business_identifiers=business_identifiers)
    if not identifiers:
        return []
    sql_text = sql or ""
    predicates = _collect_predicate_literals(sql_text, dialect=dialect)

    missing: List[ExplicitIdentifier] = []
    for ident in identifiers:
        matched = False
        for col, lit in predicates:
            if lit != ident.value:
                # Also allow unquoted numeric-ish equality via string compare without quotes
                if str(lit).strip("'\"") != ident.value:
                    continue
            if ident.field:
                # Accept field or alias.field
                if col and col.lower() not in {
                    ident.field.lower(),
                    ident.field.lower().split(".")[-1],
                }:
                    # column may be empty if parser missed — still accept value in predicate
                    if col:
                        continue
            if ident.match == "exact":
                matched = True
                break
            matched = True
            break
        if not matched:
            # Reject LIKE-only presence: value in SQL string alone is not enough
            missing.append(ident)

    if missing:
        raise SqlbotAdapterError(
            ErrorCode.FILTER_NOT_PRESERVED,
            "生成的查询未在 WHERE/JOIN/HAVING 谓词中保留用户明确指定的过滤条件，已终止返回数据。",
            details={"missing_identifiers": [i.value for i in missing]},
        )
    return identifiers


def assert_allowlist(
    sql: str,
    *,
    allowed_schemas: Optional[Sequence[str]] = None,
    allowed_tables: Optional[Sequence[str]] = None,
    dialect: str = "tsql",
) -> None:
    if not allowed_schemas and not allowed_tables:
        return
    try:
        import sqlglot
        from sqlglot import exp

        statements = sqlglot.parse(sql, read=dialect or "tsql", error_level=None)
        if not statements or statements[0] is None:
            return
        schemas = {s.lower() for s in (allowed_schemas or [])}
        tables = {t.lower() for t in (allowed_tables or [])}
        for node in statements[0].walk():
            if isinstance(node, exp.Table):
                schema = str(node.db or "").lower()
                name = str(node.name or "").lower()
                if schemas and schema and schema not in schemas:
                    raise SqlbotAdapterError(
                        ErrorCode.UNSAFE_SQL,
                        f"SQL 引用了未允许的 Schema: {schema}",
                    )
                if tables and name and name not in tables:
                    raise SqlbotAdapterError(
                        ErrorCode.UNSAFE_SQL,
                        f"SQL 引用了未允许的表: {name}",
                    )
    except SqlbotAdapterError:
        raise
    except Exception:
        return


def guard_sql(
    question: str,
    sql: str,
    *,
    dialect: str = "tsql",
    business_identifiers: Optional[Sequence[Dict[str, Any]]] = None,
    allowed_schemas: Optional[Sequence[str]] = None,
    allowed_tables: Optional[Sequence[str]] = None,
) -> List[ExplicitIdentifier]:
    assert_readonly_sql(sql, dialect=dialect)
    assert_allowlist(
        sql,
        allowed_schemas=allowed_schemas,
        allowed_tables=allowed_tables,
        dialect=dialect,
    )
    return assert_identifiers_preserved(
        question,
        sql,
        business_identifiers=business_identifiers,
        dialect=dialect,
    )
