from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from finance_bi.contracts import ErrorCode, FinanceBiError

_SYNONYMS = {
    "销售利润": ["销售毛利", "毛利", "利润报表", "销售利润报表", "毛利报表", "授权分销"],
    "销售利润报表": ["销售毛利", "毛利", "授权分销销售毛利", "产品销售利润"],
    "毛利": ["销售毛利", "毛利率", "gross_profit", "授权分销"],
    "日期": ["date", "时间", "期间", "posting", "transaction", "due"],
}


def _is_demo(ds: Dict[str, Any]) -> bool:
    return str(ds.get("status") or "").lower() in {"demo", "deprecated", "disabled"}


def _looks_like_date_field(field_id: str, meta: Dict[str, Any] | None = None) -> bool:
    meta = meta or {}
    fid = (field_id or "").lower()
    desc = str(meta.get("description") or "")
    ftype = str(meta.get("type") or "").lower()
    if ftype in {"date", "datetime", "timestamp"}:
        return True
    # Avoid false positives like last_updated_by (contains "date" inside "updated")
    if fid.endswith(("_date", "_time", "_at", "_period", "_datetime")):
        return True
    if re.search(r"(^|_)(date|time|period|datetime)($|_)", fid):
        return True
    if any(k in desc for k in ("日期", "时间", "期间")):
        return True
    return False


class SemanticCatalog:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.datasources: Dict[str, Dict[str, Any]] = {}
        self.datasets: Dict[str, Dict[str, Any]] = {}
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.dimensions: Dict[str, Dict[str, Any]] = {}
        self.joins: Dict[str, Dict[str, Any]] = {}
        self.glossary: List[Dict[str, Any]] = []
        self.examples: List[Dict[str, Any]] = []
        self._alias_to_metric: Dict[str, str] = {}
        self._alias_to_dimension: Dict[str, str] = {}

    def load(self) -> "SemanticCatalog":
        if not self.root.is_dir():
            raise FinanceBiError(ErrorCode.CATALOG_NOT_READY, f"catalog path missing: {self.root}")

        self.datasources = self._load_dir("datasources")
        self.datasets = self._load_dir("datasets")
        self.metrics = self._load_dir("metrics")
        self.dimensions = self._load_dir("dimensions")
        self.joins = self._load_dir("joins")
        self.glossary = self._load_list("glossary")
        self.examples = self._load_list("examples")
        self._validate()
        self._build_aliases()
        return self

    def _load_dir(self, name: str) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        path = self.root / name
        if not path.is_dir():
            return out
        for file in sorted(path.glob("*.yaml")):
            data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict) or not data.get("id"):
                continue
            key = str(data["id"])
            if key in out:
                raise FinanceBiError(
                    ErrorCode.CATALOG_NOT_READY,
                    f"duplicate id in {name}: {key}",
                )
            out[key] = data
        return out

    def _load_list(self, name: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        path = self.root / name
        if not path.is_dir():
            return out
        for file in sorted(path.glob("*.yaml")):
            data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                if "terms" in data and isinstance(data["terms"], list):
                    out.extend(data["terms"])
                else:
                    out.append(data)
        return out

    def _validate(self) -> None:
        for mid, metric in self.metrics.items():
            for ds in metric.get("datasets") or []:
                if ds not in self.datasets:
                    raise FinanceBiError(
                        ErrorCode.CATALOG_NOT_READY,
                        f"metric {mid} references missing dataset {ds}",
                    )
        for did, dim in self.dimensions.items():
            for ds in dim.get("datasets") or []:
                if ds not in self.datasets:
                    raise FinanceBiError(
                        ErrorCode.CATALOG_NOT_READY,
                        f"dimension {did} references missing dataset {ds}",
                    )
        for ds_id, ds in self.datasets.items():
            for mid in ds.get("available_metrics") or []:
                if mid not in self.metrics:
                    raise FinanceBiError(
                        ErrorCode.CATALOG_NOT_READY,
                        f"dataset {ds_id} references missing metric {mid}",
                    )
            for did in ds.get("available_dimensions") or []:
                if did not in self.dimensions and did not in (ds.get("fields") or {}):
                    if did not in self.dimensions:
                        if did not in (ds.get("fields") or {}):
                            raise FinanceBiError(
                                ErrorCode.CATALOG_NOT_READY,
                                f"dataset {ds_id} references missing dimension {did}",
                            )

    def _build_aliases(self) -> None:
        for mid, metric in self.metrics.items():
            self._alias_to_metric[mid.lower()] = mid
            self._alias_to_metric[str(metric.get("name") or "").lower()] = mid
            for alias in metric.get("aliases") or []:
                self._alias_to_metric[str(alias).lower()] = mid
        for did, dim in self.dimensions.items():
            self._alias_to_dimension[did.lower()] = did
            self._alias_to_dimension[str(dim.get("name") or "").lower()] = did
            for alias in dim.get("aliases") or []:
                self._alias_to_dimension[str(alias).lower()] = did

    def resolve_metric(self, token: str) -> Optional[str]:
        return self._alias_to_metric.get((token or "").strip().lower())

    def resolve_dimension(self, token: str) -> Optional[str]:
        return self._alias_to_dimension.get((token or "").strip().lower())

    def production_datasets(self) -> Dict[str, Dict[str, Any]]:
        return {k: v for k, v in self.datasets.items() if not _is_demo(v)}

    def date_fields(self, dataset_id: str = "") -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        items = (
            {dataset_id: self.datasets[dataset_id]}
            if dataset_id and dataset_id in self.datasets
            else self.datasets
        )
        for ds_id, ds in items.items():
            primary = ds.get("primary_time_field")
            updated = ds.get("data_updated_at_field")
            for fid, meta in (ds.get("fields") or {}).items():
                if not _looks_like_date_field(fid, meta if isinstance(meta, dict) else {}):
                    continue
                out.append(
                    {
                        "dataset": ds_id,
                        "field": fid,
                        "description": (meta or {}).get("description") or fid,
                        "is_primary_time": fid == primary,
                        "is_data_updated_at": fid == updated,
                    }
                )
            # ensure primary is present even if fields map incomplete
            if primary and not any(x["field"] == primary and x["dataset"] == ds_id for x in out):
                out.append(
                    {
                        "dataset": ds_id,
                        "field": primary,
                        "description": "主时间字段",
                        "is_primary_time": True,
                        "is_data_updated_at": False,
                    }
                )
        return out

    def describe_report_catalog(self, topic: str = "") -> Dict[str, Any]:
        """Answer meta questions: which datasets / date fields for a report topic."""
        topic = str(topic or "").strip()
        search = self.search(topic or "销售利润", kind="all", include_demo=False)
        datasets = search.get("datasets") or []
        if not datasets:
            # fall back to production, then any dataset (unit-test demo-only catalogs)
            source = self.production_datasets() or self.datasets
            for ds_id, ds in source.items():
                datasets.append(
                    {
                        "id": ds_id,
                        "name": ds.get("name"),
                        "use_cases": ds.get("use_cases") or [],
                        "available_metrics": ds.get("available_metrics") or [],
                        "available_dimensions": ds.get("available_dimensions") or [],
                        "primary_time_field": ds.get("primary_time_field"),
                        "grain": ds.get("grain"),
                        "status": ds.get("status") or "active",
                    }
                )
        else:
            # enrich
            enriched = []
            for item in datasets:
                ds = self.datasets.get(item["id"]) or {}
                enriched.append(
                    {
                        **item,
                        "primary_time_field": ds.get("primary_time_field"),
                        "grain": ds.get("grain"),
                        "status": ds.get("status") or "active",
                        "physical_table": ds.get("physical_table"),
                    }
                )
            datasets = enriched

        date_fields = []
        for item in datasets:
            date_fields.extend(self.date_fields(item["id"]))

        return {
            "topic": topic or "销售利润报表",
            "datasets": datasets,
            "metrics": search.get("metrics")
            or [
                {
                    "id": mid,
                    "name": m.get("name"),
                    "aliases": m.get("aliases") or [],
                    "description": m.get("description"),
                    "expression": m.get("expression"),
                    "datasets": m.get("datasets") or [],
                }
                for mid, m in self.metrics.items()
                if any(d.get("id") in (m.get("datasets") or []) for d in datasets)
            ],
            "date_fields": date_fields,
            "notes": [
                "主时间字段用于期间筛选（如 2026Q2）。",
                "演示数据集 status=demo 默认不参与生产检索。",
            ],
        }

    def search(
        self,
        query: str = "",
        kind: str = "all",
        include_demo: bool = False,
    ) -> Dict[str, Any]:
        raw_q = str(query or "").strip()
        q = raw_q.lower()
        kind = str(kind or "all").strip().lower()
        result: Dict[str, Any] = {
            "datasets": [],
            "metrics": [],
            "dimensions": [],
            "date_fields": [],
        }

        # synonym tokens for matching
        tokens = {q} if q else set()
        for key, vals in _SYNONYMS.items():
            if key in raw_q or key.lower() in q:
                tokens.add(key.lower())
                tokens.update(v.lower() for v in vals)
            for v in vals:
                if v.lower() in q or v in raw_q:
                    tokens.add(key.lower())
                    tokens.update(x.lower() for x in vals)

        def match(*parts: object) -> bool:
            if not q and not tokens:
                return True
            blob = " ".join(str(p or "") for p in parts).lower()
            if q and q in blob:
                return True
            return any(t and t in blob for t in tokens)

        want_dates = kind in ("date_fields", "fields") or any(
            k in raw_q for k in ("日期", "时间字段", "时间", "期间字段")
        )

        if kind in ("all", "datasets", "date_fields", "fields"):
            for ds_id, ds in self.datasets.items():
                if _is_demo(ds) and not include_demo and q:
                    # still allow explicit id match
                    if q not in ds_id.lower() and q not in str(ds.get("name") or "").lower():
                        continue
                if _is_demo(ds) and not include_demo and not q:
                    continue
                field_blob = " ".join(
                    f"{fid} {((ds.get('fields') or {}).get(fid) or {}).get('description') or ''}"
                    for fid in (ds.get("fields") or {})
                )
                if match(
                    ds_id,
                    ds.get("name"),
                    " ".join(ds.get("use_cases") or []),
                    field_blob,
                    "销售利润" if not _is_demo(ds) else "",
                    "毛利" if not _is_demo(ds) else "",
                ):
                    result["datasets"].append(
                        {
                            "id": ds_id,
                            "name": ds.get("name"),
                            "use_cases": ds.get("use_cases") or [],
                            "available_metrics": ds.get("available_metrics") or [],
                            "available_dimensions": ds.get("available_dimensions") or [],
                            "primary_time_field": ds.get("primary_time_field"),
                            "status": ds.get("status") or "active",
                        }
                    )

        if kind in ("all", "metrics"):
            for mid, metric in self.metrics.items():
                if match(
                    mid,
                    metric.get("name"),
                    " ".join(metric.get("aliases") or []),
                    metric.get("description"),
                    metric.get("expression"),
                ):
                    result["metrics"].append(
                        {
                            "id": mid,
                            "name": metric.get("name"),
                            "aliases": metric.get("aliases") or [],
                            "description": metric.get("description"),
                            "version": metric.get("version"),
                            "datasets": metric.get("datasets") or [],
                        }
                    )

        if kind in ("all", "dimensions"):
            seen: set[str] = set()
            for did, dim in self.dimensions.items():
                if match(did, dim.get("name"), " ".join(dim.get("aliases") or []), dim.get("description")):
                    result["dimensions"].append(
                        {
                            "id": did,
                            "name": dim.get("name"),
                            "aliases": dim.get("aliases") or [],
                            "datasets": dim.get("datasets") or [],
                        }
                    )
                    seen.add(did)
            for ds_id, ds in self.datasets.items():
                if _is_demo(ds) and not include_demo:
                    continue
                for fid, meta in (ds.get("fields") or {}).items():
                    if fid in seen:
                        continue
                    desc = str((meta or {}).get("description") or "")
                    listed = fid in (ds.get("available_dimensions") or [])
                    if not listed and not (q and (q in fid.lower() or q in desc.lower())):
                        continue
                    if not match(fid, desc):
                        continue
                    result["dimensions"].append(
                        {
                            "id": fid,
                            "name": desc or fid,
                            "aliases": [],
                            "datasets": [ds_id],
                            "source": "dataset_field",
                        }
                    )
                    seen.add(fid)

        if want_dates or kind in ("all", "date_fields", "fields"):
            if result["datasets"]:
                for item in result["datasets"]:
                    result["date_fields"].extend(self.date_fields(item["id"]))
            elif want_dates:
                result["date_fields"] = self.date_fields()

        if q and not any(result[k] for k in ("datasets", "metrics", "dimensions", "date_fields")):
            prod = sorted(self.production_datasets().keys())
            result["hint"] = (
                "无精确匹配；生产数据集: "
                + ", ".join(prod)
                + "；可用指标: "
                + ", ".join(sorted(self.metrics.keys()))
            )
        return result
