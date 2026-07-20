#!/usr/bin/env python3
"""从 SQL Server 字典表 DW_AI_Table_Column_List 拉取字段说明，生成/更新语义 dataset YAML。

用法（在能访问 192.168.99.37 的机器上）:

  set FINANCE_BI_DSN=mssql+pymssql://AIUser:PASSWORD@192.168.99.37:4399/DW_TEMP
  python scripts/lib/sync_bi_semantic_from_dw_dict.py \\
    --table ebs1_cux_ar_gp_details \\
    --out expert-templates/bi-strategic-office/semantic/datasets/ebs1_cux_ar_gp_details.yaml

可选环境变量（按你们字典表真实列名调整）:
  DW_DICT_TABLE=DW_AI_Table_Column_List
  DW_DICT_TABLE_COL=table_name
  DW_DICT_COLUMN_COL=column_name
  DW_DICT_DESC_COL=column_comment
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: need PyYAML", file=sys.stderr)
    raise SystemExit(2)


def _quote_ident(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def fetch_columns(dsn: str, dict_table: str, table_name: str, table_col: str, column_col: str, desc_col: str):
    from sqlalchemy import create_engine, text

    engine = create_engine(dsn, pool_pre_ping=True)
    # Try common schema-qualified names
    candidates = [dict_table]
    if "." not in dict_table:
        candidates = [f"dbo.{dict_table}", dict_table]

    last_err: Exception | None = None
    rows: list[dict[str, Any]] = []
    with engine.connect() as conn:
        for dt in candidates:
            sql = text(
                f"""
                SELECT
                  {_quote_ident(table_col)} AS table_name,
                  {_quote_ident(column_col)} AS column_name,
                  {_quote_ident(desc_col)} AS description
                FROM {dt}
                WHERE LOWER({_quote_ident(table_col)}) = LOWER(:t)
                ORDER BY {_quote_ident(column_col)}
                """
            )
            try:
                result = conn.execute(sql, {"t": table_name})
                rows = [dict(r._mapping) for r in result]
                if rows:
                    print(f"[ok] read {len(rows)} columns from {dt}")
                    return rows
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
    if last_err:
        raise SystemExit(f"failed to read dictionary: {type(last_err).__name__}: {last_err}")
    raise SystemExit(f"no rows in dictionary for table={table_name}")


def build_dataset_yaml(table_name: str, columns: list[dict[str, Any]]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    dim_candidates: list[str] = []
    metric_candidates: list[str] = []

    for row in columns:
        col = str(row.get("column_name") or "").strip()
        if not col:
            continue
        desc = str(row.get("description") or "").strip() or col
        fields[col] = {"type": "string", "description": desc}
        low = col.lower()
        desc_l = desc.lower()
        if any(k in low or k in desc_l for k in ("amount", "amt", "qty", "quantity", "金额", "数量", "毛利", "成本", "销售")):
            if any(k in low or k in desc_l for k in ("amount", "amt", "金额", "毛利", "成本", "sales", "gp", "cogs")):
                metric_candidates.append(col)
        if any(
            k in low or k in desc_l
            for k in ("code", "name", "date", "period", "region", "entity", "customer", "product", "日期", "区域", "客户", "产品", "主体")
        ):
            dim_candidates.append(col)

    # Prefer explicit known business fields if present
    def pick(names: list[str], pool: list[str]) -> list[str]:
        found = []
        lower_map = {c.lower(): c for c in pool}
        for n in names:
            if n.lower() in lower_map:
                found.append(lower_map[n.lower()])
        return found

    all_cols = list(fields.keys())
    time_field = (
        pick(["posting_date", "trx_date", "gl_date", "period_date", "sales_date"], all_cols)
        or pick([c for c in all_cols if "date" in c.lower() or "日期" in str(fields[c].get("description"))], all_cols)
        or ([all_cols[0]] if all_cols else [])
    )
    entity_field = pick(["entity_code", "org_id", "ou_name", "company_code", "ou_code"], all_cols)

    return {
        "id": table_name.replace(".", "_"),
        "name": "授权分销销售毛利明细",
        "physical_table": f"dbo.{table_name}" if "." not in table_name else table_name,
        "grain": "detail",
        "primary_time_field": time_field[0] if time_field else None,
        "entity_field": entity_field[0] if entity_field else None,
        "currency_field": (pick(["currency_code", "report_currency", "currency"], all_cols) or [None])[0],
        "available_dimensions": sorted(set(dim_candidates))[:40],
        "available_metrics": sorted(set(metric_candidates))[:40],
        "allowed_joins": [],
        "data_updated_at_field": None,
        "use_cases": ["授权分销销售毛利报表", "产品/客户毛利分析"],
        "forbidden_use_cases": ["付款核销", "凭证过账"],
        "fields": fields,
        "source_dictionary": "DW_AI_Table_Column_List",
        "notes": "字段说明来自字典表；指标表达式需人工复核后写入 metrics/*.yaml",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.getenv("FINANCE_BI_DSN", ""))
    parser.add_argument("--table", default="ebs1_cux_ar_gp_details")
    parser.add_argument("--dict-table", default=os.getenv("DW_DICT_TABLE", "DW_AI_Table_Column_List"))
    parser.add_argument("--table-col", default=os.getenv("DW_DICT_TABLE_COL", "table_name"))
    parser.add_argument("--column-col", default=os.getenv("DW_DICT_COLUMN_COL", "column_name"))
    parser.add_argument("--desc-col", default=os.getenv("DW_DICT_DESC_COL", "column_comment"))
    parser.add_argument(
        "--out",
        default="expert-templates/bi-strategic-office/semantic/datasets/ebs1_cux_ar_gp_details.yaml",
    )
    parser.add_argument("--probe-columns", action="store_true", help="列出字典表前几列名后退出")
    args = parser.parse_args()

    if not args.dsn:
        print("ERROR: set FINANCE_BI_DSN or pass --dsn", file=sys.stderr)
        return 1

    if args.probe_columns:
        from sqlalchemy import create_engine, text

        eng = create_engine(args.dsn, pool_pre_ping=True)
        with eng.connect() as conn:
            r = conn.execute(text("SELECT TOP 5 * FROM dbo.DW_AI_Table_Column_List"))
            print("columns:", list(r.keys()))
            for row in r.fetchall():
                print(dict(zip(r.keys(), row)))
        return 0

    rows = fetch_columns(
        args.dsn,
        args.dict_table,
        args.table,
        args.table_col,
        args.column_col,
        args.desc_col,
    )
    data = build_dataset_yaml(args.table, rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"wrote {out} fields={len(data.get('fields') or {})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
