#!/usr/bin/env python3
"""bi-strategic-office：本地插件冒烟（不依赖 Docker / Hermes / bash inject）。

验证：
- 模板语义目录可加载
- planner 能解析单据号等条件并编译出 WHERE
- finance_bi_cli 可导入并 dry-run（sql 子命令不连库）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "asset-bundles" / "hermes-finance-bi-plugin"
TEMPLATE_SEMANTIC = ROOT / "expert-templates" / "bi-strategic-office" / "semantic"
CLI = ROOT / "scripts" / "finance_bi_cli.py"

sys.path.insert(0, str(PLUGIN))


@pytest.fixture()
def bi_cfg(tmp_path: Path, monkeypatch):
    from finance_bi.config import FinanceBiConfig
    from finance_bi.handlers import reset_service

    state = tmp_path / "state"
    state.mkdir()
    cfg = FinanceBiConfig(
        dsn="",  # no DB for plan/compile smoke
        dialect="mssql",
        catalog_path=str(TEMPLATE_SEMANTIC),
        policy_path=str(ROOT / "expert-templates" / "bi-strategic-office" / "policies"),
        allowed_schemas=["dbo", "bi_finance", "bi_sales"],
        allowed_entities=[],
        state_db=str(state / "finance_bi.db"),
        export_dir=str(tmp_path / "exports"),
        mask_sensitive=False,
        charset="cp936",
    )
    (tmp_path / "exports").mkdir(exist_ok=True)
    monkeypatch.setenv("FINANCE_BI_CATALOG_PATH", cfg.catalog_path)
    svc = reset_service(cfg)
    return {"cfg": cfg, "svc": svc}


def test_template_files_exist():
    assert (ROOT / "expert-templates" / "bi-strategic-office" / "SOUL.md").is_file()
    assert (TEMPLATE_SEMANTIC / "datasets" / "ebs1_cux_ar_gp_details.yaml").is_file()
    assert (PLUGIN / "plugin.yaml").is_file()
    assert CLI.is_file()


def test_catalog_loads_production_dataset(bi_cfg):
    cat = bi_cfg["svc"].catalog
    assert "ebs1_cux_ar_gp_details" in cat.datasets
    assert "gross_profit_amount" in cat.metrics


def test_plan_trx_filter_compiles_where(bi_cfg):
    """单据号必须进入 SQL WHERE，而不是依赖上一轮 TOP N。"""
    svc = bi_cfg["svc"]
    q = svc.planner.plan("ar_trx_number=101IN26070199 明细")
    assert q.mode == "detail"
    assert any(f.field == "ar_trx_number" and str(f.value) == "101IN26070199" for f in q.filters)
    sql, _ = svc.compiler.compile(q)
    assert "ar_trx_number" in sql
    assert "101IN26070199" in sql
    assert "WHERE" in sql.upper()


def test_plan_trx_not_poisoned_by_false_quarter(bi_cfg):
    """101IN23120194 含 2019+4，不得变成 ar_fin_due_date 2019Q4，且必须带 trx 过滤。"""
    svc = bi_cfg["svc"]
    for question in (
        "ar_trx_number=101IN23120194 明细",
        "查询单据号 101IN23120194",
        "101IN23120194 交易明细",
    ):
        q = svc.planner.plan(question)
        assert any(
            f.field == "ar_trx_number" and str(f.value) == "101IN23120194" for f in q.filters
        ), (question, q.filters)
        assert not any(f.field == "ar_fin_due_date" for f in q.filters), (question, q.filters)
        sql, _ = svc.compiler.compile(q)
        assert "101IN23120194" in sql
        assert "2019-10-01" not in sql


def test_followup_clear_time_and_trx(bi_cfg):
    svc = bi_cfg["svc"]
    base = svc.planner.plan("查询2026Q2各品牌销售毛利")
    assert any(f.field == "ar_fin_due_date" for f in base.filters)
    q2 = svc.planner.apply_followup(base, "不限时间，ar_trx_number=101IN23120194")
    assert any(f.field == "ar_trx_number" and str(f.value) == "101IN23120194" for f in q2.filters)
    assert not any(f.field == "ar_fin_due_date" for f in q2.filters)


def test_trx_plus_explicit_quarter_both_kept(bi_cfg):
    """显式日历季度可与单据号并存；编号本身不产生时间。"""
    svc = bi_cfg["svc"]
    q = svc.planner.plan("2026Q2 ar_trx_number=101IN23120194 明细")
    assert any(f.field == "ar_trx_number" and str(f.value) == "101IN23120194" for f in q.filters)
    assert any(f.field == "ar_fin_due_date" and f.operator == "gte" and f.value == "2026-04-01" for f in q.filters)


def test_cli_sql_dry_run():
    """本地 CLI：只编译 SQL，不连库、不注入 Hermes。"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PLUGIN) + os.pathsep + env.get("PYTHONPATH", "")
    env["FINANCE_BI_CATALOG_PATH"] = str(TEMPLATE_SEMANTIC)
    env["FINANCE_BI_DIALECT"] = "mssql"
    env["FINANCE_BI_DSN"] = ""
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--catalog",
            str(TEMPLATE_SEMANTIC),
            "sql",
            "ar_trx_number=101IN26070199 明细",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "101IN26070199" in r.stdout
    assert "WHERE" in r.stdout.upper()


def test_cli_catalog_no_db():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PLUGIN) + os.pathsep + env.get("PYTHONPATH", "")
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--catalog",
            str(TEMPLATE_SEMANTIC),
            "--json",
            "catalog",
            "毛利",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.loads(r.stdout)
    assert data.get("status") == "ok"
    assert data.get("result_type") == "table"
    assert int(data.get("row_count") or 0) >= 1


def test_writer_template_still_valid():
    tpl = ROOT / "expert-templates" / "writer"
    assert tpl.is_dir()
    assert (tpl / "SOUL.md").is_file()
    assert not (tpl / "team.yaml").exists()


def test_catalog_prunes_bogus_available_metric(tmp_path: Path, monkeypatch):
    """Physical column wrongly listed as available_metric must NOT kill the catalog."""
    import shutil

    from finance_bi.catalog import SemanticCatalog
    from finance_bi.config import FinanceBiConfig
    from finance_bi.handlers import reset_service

    cat_dir = tmp_path / "semantic"
    shutil.copytree(TEMPLATE_SEMANTIC, cat_dir)
    ds_path = cat_dir / "datasets" / "ebs1_cux_ar_gp_details.yaml"
    text = ds_path.read_text(encoding="utf-8")
    text = text.replace(
        "available_metrics:\n- net_sales_amount\n",
        "available_metrics:\n- accrued_rebate_amount\n- net_sales_amount\n",
    )
    ds_path.write_text(text, encoding="utf-8")

    cat = SemanticCatalog(cat_dir).load()
    assert "ebs1_cux_ar_gp_details" in cat.datasets
    assert "accrued_rebate_amount" not in cat.datasets["ebs1_cux_ar_gp_details"]["available_metrics"]
    assert "net_sales_amount" in cat.datasets["ebs1_cux_ar_gp_details"]["available_metrics"]
    assert any("accrued_rebate_amount" in w for w in cat.load_warnings)

    cfg = FinanceBiConfig(
        dsn="",
        dialect="mssql",
        catalog_path=str(cat_dir),
        policy_path=str(ROOT / "expert-templates" / "bi-strategic-office" / "policies"),
        allowed_schemas=["dbo"],
        state_db=str(tmp_path / "s.db"),
        export_dir=str(tmp_path / "e"),
    )
    (tmp_path / "e").mkdir()
    svc = reset_service(cfg)
    q = svc.planner.plan("ar_trx_number=101IN26070199 明细")
    sql, _ = svc.compiler.compile(q)
    assert "101IN26070199" in sql
