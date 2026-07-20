#!/usr/bin/env python3
"""本地直连 Finance BI 插件问数（不经过 Hermes / Docker）。

用法示例（PowerShell）:
  # 1) 安装依赖（一次）
  pip install -r asset-bundles/hermes-finance-bi-plugin/requirements.txt

  # 2) 从实例 .env 加载 DSN（推荐）
  python scripts/finance_bi_cli.py --env instances/financial-analysis/.env health
  python scripts/finance_bi_cli.py --env instances/financial-analysis/.env ask "按品牌汇总销售毛利，返回 5 条"
  python scripts/finance_bi_cli.py --env instances/financial-analysis/.env ask "ar_trx_number=101IN26070199 明细"
  python scripts/finance_bi_cli.py --env instances/financial-analysis/.env followup biq_xxx "只看毛利率低于5%"
  python scripts/finance_bi_cli.py --env instances/financial-analysis/.env catalog "毛利"
  python scripts/finance_bi_cli.py --env instances/financial-analysis/.env explain --metric 销售利润

  # 3) 无实例时：指定模板语义目录 + DSN
  $env:FINANCE_BI_DSN="mssql+pymssql://user:pass@host:1433/DW_TEMP"
  python scripts/finance_bi_cli.py --catalog expert-templates/bi-strategic-office/semantic ask "客户 天地偉業 交易明细，返回 3 条"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "asset-bundles" / "hermes-finance-bi-plugin"
DEFAULT_CATALOG = ROOT / "expert-templates" / "bi-strategic-office" / "semantic"
DEFAULT_POLICY = ROOT / "expert-templates" / "bi-strategic-office" / "policies"


def _die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _load_dotenv(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.is_file():
        _die(f".env not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def _apply_env(values: Dict[str, str], *, overwrite: bool = True) -> None:
    for k, v in values.items():
        if not k.startswith("FINANCE_BI_"):
            continue
        if overwrite or k not in os.environ or not str(os.environ.get(k) or "").strip():
            os.environ[k] = v


def _setup_paths(catalog: Optional[Path], policy: Optional[Path], state_dir: Path) -> None:
    sys.path.insert(0, str(PLUGIN))
    cat = catalog or DEFAULT_CATALOG
    pol = policy or DEFAULT_POLICY
    if not cat.is_dir():
        _die(f"catalog not found: {cat}")
    state_dir.mkdir(parents=True, exist_ok=True)
    export_dir = state_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("FINANCE_BI_CATALOG_PATH", str(cat.resolve()))
    os.environ.setdefault("FINANCE_BI_POLICY_PATH", str(pol.resolve()))
    os.environ.setdefault("FINANCE_BI_STATE_DB", str((state_dir / "finance_bi.db").resolve()))
    os.environ.setdefault("FINANCE_BI_EXPORT_DIR", str(export_dir.resolve()))
    os.environ.setdefault("FINANCE_BI_DIALECT", "mssql")
    os.environ.setdefault("FINANCE_BI_CHARSET", "cp936")
    os.environ.setdefault("FINANCE_BI_MASK_SENSITIVE", "false")
    os.environ.setdefault("FINANCE_BI_ALLOWED_SCHEMAS", "dbo,bi_finance,bi_sales")
    os.environ.setdefault("FINANCE_BI_ALLOWED_ENTITIES", "")
    os.environ.setdefault("FINANCE_BI_DEFAULT_LIMIT", "200")
    os.environ.setdefault("FINANCE_BI_HARD_LIMIT", "5000")


def _get_service():
    from finance_bi.handlers import reset_service

    return reset_service()


def _print_table(payload: Dict[str, Any], *, max_rows: int = 50) -> None:
    rows: List[Dict[str, Any]] = list(payload.get("rows") or [])
    cols = payload.get("columns") or payload.get("fields") or []
    names = [c.get("name") if isinstance(c, dict) else str(c) for c in cols]
    if not names and rows:
        names = list(rows[0].keys())

    print(f"status={payload.get('status')} result_type={payload.get('result_type')} "
          f"kind={payload.get('result_kind')} query_id={payload.get('query_id')} "
          f"row_count={payload.get('row_count')}")
    meta = payload.get("meta") or {}
    if meta.get("applied_filters"):
        print("applied_filters=", json.dumps(meta["applied_filters"], ensure_ascii=False))
    if payload.get("warnings"):
        print("warnings=", json.dumps(payload["warnings"], ensure_ascii=False))
    if not names:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return

    # header
    print(" | ".join(names))
    print("-+-".join("-" * max(4, len(n)) for n in names))
    for row in rows[:max_rows]:
        cells = []
        for n in names:
            v = row.get(n, "")
            if v is None:
                v = ""
            s = str(v).replace("\n", " ")
            if len(s) > 80:
                s = s[:77] + "..."
            cells.append(s)
        print(" | ".join(cells))
    if len(rows) > max_rows:
        print(f"... ({len(rows) - max_rows} more rows)")


def cmd_health(_: argparse.Namespace) -> int:
    svc = _get_service()
    h = svc.health()
    print(json.dumps(h, ensure_ascii=False, indent=2))
    dsn = os.environ.get("FINANCE_BI_DSN") or ""
    print(f"dsn_set={bool(dsn)} dialect={os.environ.get('FINANCE_BI_DIALECT')} "
          f"charset={os.environ.get('FINANCE_BI_CHARSET')} "
          f"catalog={os.environ.get('FINANCE_BI_CATALOG_PATH')}")
    if h.get("load_warnings"):
        print("CATALOG_WARNINGS:")
        for w in h["load_warnings"]:
            print(" -", w)
    if dsn:
        probe = svc.executor.probe_readonly()
        print("probe=", json.dumps(probe, ensure_ascii=False))
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    """Validate catalog; prove ebs1 dataset is query-plannable (no Hermes)."""
    svc = _get_service()
    h = svc.health()
    print("=== health ===")
    print(json.dumps(h, ensure_ascii=False, indent=2))
    ds_id = "ebs1_cux_ar_gp_details"
    if ds_id not in svc.catalog.datasets:
        print(f"FAIL: dataset {ds_id} missing")
        return 1
    ds = svc.catalog.datasets[ds_id]
    print("=== dataset", ds_id, "===")
    print("available_metrics=", ds.get("available_metrics"))
    print("status=", ds.get("status"))
    # Prove a past false claim: physical column must NOT be required as metric
    fields = ds.get("fields") or {}
    print("has_field accrued_rebate_amount=", "accrued_rebate_amount" in fields)
    print("is_metric accrued_rebate_amount=", "accrued_rebate_amount" in svc.catalog.metrics)
    q = svc.planner.plan("ar_trx_number=101IN26070199 明细")
    sql, warnings = svc.compiler.compile(q)
    print("=== plan+sql ok ===")
    print("filters=", [(f.field, f.operator, f.value) for f in q.filters])
    print(sql)
    if warnings:
        print("compile_warnings=", warnings)
    if h.get("load_warnings"):
        print("load_warnings (soft, catalog still usable):")
        for w in h["load_warnings"]:
            print(" -", w)
    print("DOCTOR: OK — catalog loads; accrued_rebate_amount is a field not a required metric")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    svc = _get_service()
    payload = svc.ask(args.question, session_id=args.session_id or "cli")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_table(payload, max_rows=args.max_rows)
    return 0 if payload.get("status") == "ok" else 1


def cmd_followup(args: argparse.Namespace) -> int:
    svc = _get_service()
    payload = svc.followup(args.query_id, args.instruction, session_id=args.session_id or "cli")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_table(payload, max_rows=args.max_rows)
    return 0 if payload.get("status") == "ok" else 1


def cmd_catalog(args: argparse.Namespace) -> int:
    svc = _get_service()
    payload = svc.catalog_search(query=args.query or "", kind=args.kind or "all")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_table(payload, max_rows=args.max_rows)
    return 0 if payload.get("status") == "ok" else 1


def cmd_explain(args: argparse.Namespace) -> int:
    svc = _get_service()
    payload = svc.explain(query_id=args.query_id or "", topic=args.topic or "", metric=args.metric or "")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_table(payload, max_rows=args.max_rows)
    return 0 if payload.get("status") == "ok" else 1


def cmd_export(args: argparse.Namespace) -> int:
    svc = _get_service()
    payload = svc.export(args.query_id, fmt=args.format or "csv")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload.get("status") == "ok" else 1


def cmd_sql_preview(args: argparse.Namespace) -> int:
    """Plan + compile SQL without executing (safe dry-run)."""
    svc = _get_service()
    semantic = svc.planner.plan(args.question)
    sql, warnings = svc.compiler.compile(semantic)
    print("title:", semantic.title)
    print("mode:", semantic.mode, "limit:", semantic.limit)
    print("filters:", json.dumps([f.__dict__ for f in semantic.filters], ensure_ascii=False, default=str))
    print("dimensions:", semantic.dimensions)
    print("metrics:", semantic.metrics)
    print("warnings:", warnings)
    print("--- SQL ---")
    print(sql)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local Finance BI plugin CLI (no Hermes)")
    p.add_argument(
        "--env",
        type=Path,
        default=None,
        help="Load FINANCE_BI_* from instance .env (e.g. instances/financial-analysis/.env)",
    )
    p.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help=f"Semantic catalog dir (default: {DEFAULT_CATALOG})",
    )
    p.add_argument(
        "--policy",
        type=Path,
        default=None,
        help=f"Policy dir (default: {DEFAULT_POLICY})",
    )
    p.add_argument(
        "--state-dir",
        type=Path,
        default=ROOT / ".local" / "finance-bi-cli",
        help="Local state/export dir",
    )
    p.add_argument("--json", action="store_true", help="Print full JSON")
    p.add_argument("--max-rows", type=int, default=50)
    p.add_argument("--session-id", default="cli")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("health", help="Catalog + DSN probe")
    sp.set_defaults(func=cmd_health)

    sp = sub.add_parser("doctor", help="Prove catalog loads; accrued_rebate is a field not a metric")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("ask", help="finance_bi_ask")
    sp.add_argument("question")
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("followup", help="finance_bi_followup")
    sp.add_argument("query_id")
    sp.add_argument("instruction")
    sp.set_defaults(func=cmd_followup)

    sp = sub.add_parser("catalog", help="finance_bi_catalog_search")
    sp.add_argument("query", nargs="?", default="")
    sp.add_argument("--kind", default="all")
    sp.set_defaults(func=cmd_catalog)

    sp = sub.add_parser("explain", help="finance_bi_explain")
    sp.add_argument("--query-id", default="")
    sp.add_argument("--topic", default="")
    sp.add_argument("--metric", default="")
    sp.set_defaults(func=cmd_explain)

    sp = sub.add_parser("export", help="finance_bi_export_result")
    sp.add_argument("query_id")
    sp.add_argument("--format", default="csv", choices=["csv", "xlsx"])
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("sql", help="Plan+compile SQL only (no DB execute)")
    sp.add_argument("question")
    sp.set_defaults(func=cmd_sql_preview)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    # Windows console UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.env:
        vals = _load_dotenv(args.env.resolve())
        _apply_env(vals, overwrite=True)
        # Prefer instance semantic if present
        profile_guess = args.env.resolve().parent.name
        inst_cat = ROOT / "instances" / profile_guess / "data" / "hermes" / "finance-bi" / "semantic"
        inst_pol = ROOT / "instances" / profile_guess / "data" / "hermes" / "finance-bi" / "policies"
        if args.catalog is None and inst_cat.is_dir():
            args.catalog = inst_cat
        if args.policy is None and inst_pol.is_dir():
            args.policy = inst_pol

    if args.catalog:
        os.environ["FINANCE_BI_CATALOG_PATH"] = str(args.catalog.resolve())
    if args.policy:
        os.environ["FINANCE_BI_POLICY_PATH"] = str(args.policy.resolve())

    _setup_paths(args.catalog, args.policy, args.state_dir.resolve())

    if not (os.environ.get("FINANCE_BI_DSN") or "").strip() and args.cmd not in {"health", "sql", "catalog", "explain"}:
        print(
            "WARN: FINANCE_BI_DSN empty — ask/followup/export will fail. "
            "Pass --env instances/<profile>/.env or set FINANCE_BI_DSN.",
            file=sys.stderr,
        )

    try:
        return int(args.func(args))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        from finance_bi.contracts import FinanceBiError

        if isinstance(exc, FinanceBiError):
            print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
            return 1
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
