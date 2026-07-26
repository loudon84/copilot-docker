"""SQL read-only checks and explicit identifier preservation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

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

# Patterns that extract user-specified identifiers that MUST appear in SQL.
IDENTIFIER_PATTERNS = [
    re.compile(
        r"(?i)(?:ar_trx_number|trx_number)\s*=\s*['\"]?([A-Za-z0-9_-]+)['\"]?"
    ),
    re.compile(r"(?i)凭证号\s*[=:：]?\s*([A-Za-z0-9_-]+)"),
    re.compile(r"(?i)单据号\s*[=:：]?\s*([A-Za-z0-9_-]+)"),
    re.compile(r"(?i)订单号\s*[=:：]?\s*([A-Za-z0-9_-]+)"),
    re.compile(r"(?i)客户编号\s*[=:：]?\s*([A-Za-z0-9_-]+)"),
    re.compile(r"(?i)客户编码\s*[=:：]?\s*([A-Za-z0-9_-]+)"),
    re.compile(r"(?i)customer_code\s*=\s*['\"]?([A-Za-z0-9_-]+)['\"]?"),
]


@dataclass
class ExplicitIdentifier:
    value: str
    source: str = ""


def extract_explicit_identifiers(question: str) -> List[ExplicitIdentifier]:
    found: List[ExplicitIdentifier] = []
    seen = set()
    text = question or ""
    for pat in IDENTIFIER_PATTERNS:
        for m in pat.finditer(text):
            val = m.group(1).strip()
            if not val or val.lower() in seen:
                continue
            seen.add(val.lower())
            found.append(ExplicitIdentifier(value=val, source=m.group(0)))
    return found


def assert_readonly_sql(sql: str) -> None:
    text = (sql or "").strip()
    if not text:
        # Some SQLBot responses may omit SQL while returning rows; treat empty as soft fail later.
        return

    # Multi-statement rejection (allow trailing semicolon)
    stripped = text.rstrip().rstrip(";")
    if ";" in stripped:
        raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：禁止多语句")

    upper = text.upper()
    # Remove simple string literals to reduce false positives on keywords inside strings
    scrubbed = re.sub(r"'([^']|'')*'", "''", text)
    scrubbed = re.sub(r'"([^"]|"")*"', '""', scrubbed)
    scrubbed_upper = scrubbed.upper()

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", scrubbed_upper):
            raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, f"SQL 不符合只读要求：禁止 {kw}")

    # Prefer sqlglot when available
    try:
        import sqlglot
        from sqlglot import exp

        statements = sqlglot.parse(text, error_level=None)
        if not statements:
            # Fallback keyword check already done
            if not (upper.lstrip().startswith("SELECT") or upper.lstrip().startswith("WITH")):
                raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：仅允许 SELECT")
            return
        if len(statements) > 1:
            raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：禁止多语句")
        stmt = statements[0]
        if stmt is None:
            return
        if not isinstance(stmt, (exp.Select, exp.Union)):
            # WITH ... SELECT is usually wrapped as Select with CTEs
            if not isinstance(stmt, exp.Query) and not isinstance(stmt, exp.Select):
                # sqlglot may return With as part of Select; reject DML/DDL
                kind = type(stmt).__name__
                if kind not in {"Select", "Union", "With"}:
                    raise SqlbotAdapterError(
                        ErrorCode.UNSAFE_SQL,
                        f"SQL 不符合只读要求：仅允许 SELECT（got {kind}）",
                    )
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
                ),
            ):
                raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求")
    except ImportError:
        if not (upper.lstrip().startswith("SELECT") or upper.lstrip().startswith("WITH")):
            raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：仅允许 SELECT")
    except SqlbotAdapterError:
        raise
    except Exception:
        # Parser failure: fall back to keyword gate already applied
        if not (upper.lstrip().startswith("SELECT") or upper.lstrip().startswith("WITH")):
            raise SqlbotAdapterError(ErrorCode.UNSAFE_SQL, "SQL 不符合只读要求：仅允许 SELECT")


def assert_identifiers_preserved(question: str, sql: str) -> List[ExplicitIdentifier]:
    identifiers = extract_explicit_identifiers(question)
    if not identifiers:
        return []
    sql_text = sql or ""
    missing = [i for i in identifiers if i.value not in sql_text]
    if missing:
        vals = ", ".join(i.value for i in missing)
        raise SqlbotAdapterError(
            ErrorCode.FILTER_NOT_PRESERVED,
            "生成的查询未保留用户明确指定的过滤条件，已终止返回数据。",
            details={"missing_identifiers": [i.value for i in missing], "hint": vals},
        )
    return identifiers


def guard_sql(question: str, sql: str) -> List[ExplicitIdentifier]:
    assert_readonly_sql(sql)
    return assert_identifiers_preserved(question, sql)
