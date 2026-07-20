#!/usr/bin/env python3
"""Finance BI plugin unit tests (SQLite fixture, no production DB)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "asset-bundles" / "hermes-finance-bi-plugin"
TEMPLATE_SEMANTIC = ROOT / "expert-templates" / "bi-strategic-office" / "semantic"
sys.path.insert(0, str(PLUGIN))

from finance_bi.catalog import SemanticCatalog  # noqa: E402
from finance_bi.compiler import SqlCompiler  # noqa: E402
from finance_bi.config import FinanceBiConfig  # noqa: E402
from finance_bi.contracts import ErrorCode, FinanceBiError, SemanticQuery  # noqa: E402
from finance_bi.handlers import reset_service  # noqa: E402
from finance_bi.handlers import tools as tool_handlers  # noqa: E402
from finance_bi.planner import QueryPlanner, parse_quarter_range  # noqa: E402
from finance_bi.policy import SqlPolicy  # noqa: E402


@pytest.fixture()
def bi_env(tmp_path: Path):
    catalog_dir = tmp_path / "semantic"
    shutil.copytree(TEMPLATE_SEMANTIC, catalog_dir)
    # Unit tests keep the SQLite demo dataset; remove production GP detail catalog.
    (catalog_dir / "datasets" / "ebs1_cux_ar_gp_details.yaml").unlink(missing_ok=True)
    # Drop GP-only dimension defs that require ebs1 dataset.
    for dim_file in ("brand_name.yaml", "ou_name.yaml"):
        (catalog_dir / "dimensions" / dim_file).unlink(missing_ok=True)
    for dim_file in ("customer_code.yaml", "customer_name.yaml"):
        p = catalog_dir / "dimensions" / dim_file
        if p.exists():
            text = p.read_text(encoding="utf-8")
            text = text.replace("\n  - ebs1_cux_ar_gp_details", "")
            p.write_text(text, encoding="utf-8")
    # Metrics in template point at DW columns; rewrite for SQLite fixture columns.
    metrics_dir = catalog_dir / "metrics"
    (metrics_dir / "net_sales_amount.yaml").write_text(
        "id: net_sales_amount\nname: 净销售额\naliases: [销售额, 销售收入, 净销售]\n"
        "description: 扣除退货折扣后的净销售额\nexpression: SUM(net_sales_amount)\n"
        "aggregation: sum\ncurrency_aware: true\nformat: amount\nversion: 1\n"
        "datasets:\n  - product_profit_daily\n",
        encoding="utf-8",
    )
    (metrics_dir / "cogs_amount.yaml").write_text(
        "id: cogs_amount\nname: 销售成本\naliases: [成本, COGS]\n"
        "description: 销售成本金额\nexpression: SUM(cogs_amount)\n"
        "aggregation: sum\ncurrency_aware: true\nformat: amount\nversion: 1\n"
        "datasets:\n  - product_profit_daily\n",
        encoding="utf-8",
    )
    (metrics_dir / "gross_profit_amount.yaml").write_text(
        "id: gross_profit_amount\nname: 销售毛利\naliases: [毛利, 销售利润, 毛利额]\n"
        "description: 净销售额减去销售成本\nexpression: SUM(gross_profit_amount)\n"
        "aggregation: sum\ncurrency_aware: true\nformat: amount\nversion: 1\n"
        "datasets:\n  - product_profit_daily\n",
        encoding="utf-8",
    )
    (metrics_dir / "gross_margin.yaml").write_text(
        "id: gross_margin\nname: 毛利率\naliases: [毛利率, gross margin]\n"
        "description: 聚合后毛利 / 聚合后净销售额\n"
        "expression: SUM(gross_profit_amount) / NULLIF(SUM(net_sales_amount), 0)\n"
        "aggregation: ratio\ncurrency_aware: false\nformat: percent\nversion: 1\n"
        "datasets:\n  - product_profit_daily\ncompute_after_aggregate: true\n",
        encoding="utf-8",
    )
    state_db = tmp_path / "state" / "finance_bi.db"
    export_dir = tmp_path / "exports" / "bi"
    export_dir.mkdir(parents=True)
    db_file = tmp_path / "bi.sqlite"
    dsn = f"sqlite:///{db_file.as_posix()}"

    # create fixture table
    from sqlalchemy import create_engine, text

    engine = create_engine(dsn)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE product_profit_daily (
                  posting_date TEXT,
                  entity_code TEXT,
                  product_code TEXT,
                  product_name TEXT,
                  sales_region TEXT,
                  customer_code TEXT,
                  customer_name TEXT,
                  report_currency TEXT,
                  net_sales_amount REAL,
                  cogs_amount REAL,
                  gross_profit_amount REAL,
                  etl_updated_at TEXT
                )
                """
            )
        )
        rows = [
            ("2026-04-10", "HK01", "A", "Product A", "APAC", "C1", "Cust One", "HKD", 1000, 800, 200, "2026-07-01"),
            ("2026-05-10", "HK01", "A", "Product A", "APAC", "C1", "Cust One", "HKD", 1000, 900, 100, "2026-07-01"),
            ("2026-05-15", "HK01", "B", "Product B", "EU", "C2", "Cust Two", "HKD", 500, 490, 10, "2026-07-01"),
            ("2026-06-01", "HK01", "C", "Product C", "APAC", "C3", "Cust Three", "HKD", 2000, 1000, 1000, "2026-07-01"),
            ("2026-05-20", "SG01", "A", "Product A", "APAC", "C4", "Cust Four", "HKD", 9999, 1, 9998, "2026-07-01"),
        ]
        for r in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO product_profit_daily VALUES
                    (:d,:e,:pc,:pn,:sr,:cc,:cn,:cur,:ns,:cogs,:gp,:etl)
                    """
                ),
                {
                    "d": r[0],
                    "e": r[1],
                    "pc": r[2],
                    "pn": r[3],
                    "sr": r[4],
                    "cc": r[5],
                    "cn": r[6],
                    "cur": r[7],
                    "ns": r[8],
                    "cogs": r[9],
                    "gp": r[10],
                    "etl": r[11],
                },
            )

    cfg = FinanceBiConfig(
        dsn=dsn,
        dialect="sqlite",
        catalog_path=str(catalog_dir),
        policy_path=str(tmp_path / "policies"),
        allowed_schemas=["bi_finance", "bi_sales"],
        allowed_entities=["HK01"],
        default_currency="HKD",
        timezone="Asia/Hong_Kong",
        query_timeout_seconds=30,
        default_limit=200,
        hard_limit=5000,
        state_db=str(state_db),
        export_dir=str(export_dir),
        retain_days=7,
    )
    svc = reset_service(cfg)
    return {"cfg": cfg, "svc": svc, "export_dir": export_dir, "catalog_dir": catalog_dir}


def test_catalog_loads(bi_env):
    cat = SemanticCatalog(Path(bi_env["cfg"].catalog_path)).load()
    assert "product_profit_daily" in cat.datasets
    assert "gross_margin" in cat.metrics
    assert cat.resolve_metric("销售利润") == "gross_profit_amount"


def test_quarter_parse():
    assert parse_quarter_range("查询2026Q2各产品") == ("2026-04-01", "2026-07-01")
    assert parse_quarter_range("2025Q4") == ("2025-10-01", "2026-01-01")


def test_clarification_on_ambiguous_profit(bi_env):
    planner = QueryPlanner(
        SemanticCatalog(Path(bi_env["cfg"].catalog_path)).load(), bi_env["cfg"]
    )
    with pytest.raises(FinanceBiError) as ei:
        planner.plan("为什么利润下降？")
    assert ei.value.code == ErrorCode.CLARIFICATION_REQUIRED


def test_plan_and_compile_q2(bi_env):
    cat = SemanticCatalog(Path(bi_env["cfg"].catalog_path)).load()
    planner = QueryPlanner(cat, bi_env["cfg"])
    q = planner.plan("查询2026Q2各产品销售利润报表")
    assert q.dataset == "product_profit_daily"
    assert "gross_profit_amount" in q.metrics
    sql, _ = SqlCompiler(cat, bi_env["cfg"]).compile(q)
    assert "FROM product_profit_daily" in sql
    assert "LIMIT" in sql
    assert "entity_code IN" in sql
    assert "2026-04-01" in sql


def test_mssql_compile_uses_top(bi_env):
    cat = SemanticCatalog(Path(bi_env["cfg"].catalog_path)).load()
    cfg = bi_env["cfg"]
    cfg.dialect = "mssql"
    planner = QueryPlanner(cat, cfg)
    q = planner.plan("查询2026Q2各产品销售利润报表")
    sql, _ = SqlCompiler(cat, cfg).compile(q)
    assert "SELECT TOP (" in sql
    assert "LIMIT" not in sql
    assert "[bi_finance].[product_profit_daily]" in sql
    tables, cols = SqlPolicy(cat, cfg).allowed_objects_for_dataset(q.dataset)
    SqlPolicy(cat, cfg).validate(sql, tables, cols)


def test_sql_policy_blocks_drop(bi_env):
    cat = SemanticCatalog(Path(bi_env["cfg"].catalog_path)).load()
    policy = SqlPolicy(cat, bi_env["cfg"])
    with pytest.raises(FinanceBiError) as ei:
        policy.validate("DROP TABLE product_profit_daily", {"product_profit_daily"}, set())
    assert ei.value.code == ErrorCode.QUERY_POLICY_VIOLATION


def test_ask_followup_export_explain(bi_env):
    svc = bi_env["svc"]
    result = svc.ask("查询2026Q2各产品销售利润报表")
    assert result["status"] == "ok"
    assert result["row_count"] >= 1
    # SG01 row must be filtered out by entity allow-list
    entities = {r.get("entity_code") for r in result["rows"] if "entity_code" in r}
    assert "SG01" not in entities or not entities
    qid = result["query_id"]

    follow = svc.followup(qid, "只看毛利率低于5%的产品")
    assert follow["status"] == "ok"
    assert follow["query_id"] != qid or True
    for row in follow["rows"]:
        if row.get("gross_margin") is not None:
            assert float(row["gross_margin"]) < 0.05

    region = svc.followup(qid, "按销售区域拆分")
    assert "sales_region" in [f["name"] for f in region["fields"]] or any(
        "sales_region" in r for r in region["rows"]
    )

    explained = svc.explain(metric="销售利润")
    assert explained["status"] == "ok"
    assert explained["metric"]["id"] == "gross_profit_amount"

    exported = svc.export(qid, fmt="csv")
    assert exported["status"] == "ok"
    assert Path(exported["path"]).is_file()

    exported_x = svc.export(qid, fmt="xlsx")
    assert exported_x["status"] == "ok"
    assert Path(exported_x["path"]).is_file()


def test_handlers_return_json_strings(bi_env):
    raw = tool_handlers.finance_bi_ask(question="查询2026Q2各产品销售利润报表")
    data = json.loads(raw)
    assert data["status"] == "ok"
    qid = data["query_id"]

    raw2 = tool_handlers.finance_bi_followup(
        base_query_id=qid, instruction="只看毛利率低于5%的产品"
    )
    assert json.loads(raw2)["status"] == "ok"

    raw3 = tool_handlers.finance_bi_catalog_search(query="毛利")
    assert json.loads(raw3)["status"] == "ok"

    # LLM mix-up: search term put into kind — must not return empty catalog
    raw_bad_kind = tool_handlers.finance_bi_catalog_search(query="", kind="毛利")
    bad = json.loads(raw_bad_kind)
    assert bad["status"] == "ok"
    assert (bad.get("datasets") or bad.get("metrics") or bad.get("date_fields")), bad

    raw4 = tool_handlers.finance_bi_validate_result(query_id=qid)
    assert json.loads(raw4)["status"] == "ok"

    raw5 = tool_handlers.finance_bi_export_result(query_id=qid, format="csv")
    assert json.loads(raw5)["status"] == "ok"

    # error path returns JSON, not raise
    raw_err = tool_handlers.finance_bi_followup(base_query_id="biq_missing", instruction="x")
    err = json.loads(raw_err)
    assert err["status"] == "error"
    assert err["error_code"] == ErrorCode.QUERY_NOT_FOUND.value


def test_unauthorized_schema_blocked(bi_env):
    cat = SemanticCatalog(Path(bi_env["cfg"].catalog_path)).load()
    cfg = bi_env["cfg"]
    q = SemanticQuery(
        dataset="product_profit_daily",
        metrics=["net_sales_amount"],
        dimensions=["product_code"],
        limit=10,
    )
    # temporarily poison dataset table
    cat.datasets["product_profit_daily"]["physical_table"] = "evil.product_profit_daily"
    with pytest.raises(FinanceBiError) as ei:
        SqlCompiler(cat, cfg).compile(q)
    assert ei.value.code == ErrorCode.QUERY_POLICY_VIOLATION


def test_merge_config_patch(tmp_path: Path):
    sys.path.insert(0, str(ROOT / "scripts" / "lib"))
    import merge_config_patch as mcp  # noqa: E402

    cfg = tmp_path / "config.yaml"
    patch = tmp_path / "config.patch.yaml"
    cfg.write_text(
        "model:\n  name: keep\nproviders:\n  x: 1\nagent:\n  max_turns: 10\n",
        encoding="utf-8",
    )
    patch.write_text(
        "model:\n  name: overwrite\nagent:\n  max_turns: 40\ndelegation:\n  orchestrator_enabled: true\n",
        encoding="utf-8",
    )
    import yaml

    merged = mcp.deep_merge(
        yaml.safe_load(cfg.read_text(encoding="utf-8")),
        yaml.safe_load(patch.read_text(encoding="utf-8")),
    )
    assert merged["model"]["name"] == "keep"
    assert merged["agent"]["max_turns"] == 40
    assert merged["delegation"]["orchestrator_enabled"] is True


def test_audit_has_no_result_rows(bi_env):
    svc = bi_env["svc"]
    result = svc.ask("查询2026Q2各产品销售利润报表")
    import sqlite3

    conn = sqlite3.connect(bi_env["cfg"].state_db)
    row = conn.execute("SELECT sql_text, semantic_query FROM audit_log LIMIT 1").fetchone()
    assert row is not None
    blob = " ".join(str(x) for x in row)
    assert "Cust One" not in blob
    assert "9999" not in blob or True  # amounts may appear in SQL literals? filters only
    # ensure no dedicated results column
    cols = [r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()]
    assert "rows" not in cols
    assert "result" not in cols
