from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from finance_bi.contracts import ErrorCode, FinanceBiError


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
                    # allow field-only dimensions listed on dataset
                    if did not in self.dimensions:
                        # soft: dimension yaml optional if field exists
                        if did not in (ds.get("fields") or {}):
                            raise FinanceBiError(
                                ErrorCode.CATALOG_NOT_READY,
                                f"dataset {ds_id} references missing dimension {did}",
                            )
            table = str(ds.get("physical_table") or "")
            if "." in table:
                schema = table.split(".", 1)[0]
                # schemas validated at policy/config level
                _ = schema

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

    def search(self, query: str = "", kind: str = "all") -> Dict[str, Any]:
        q = str(query or "").strip().lower()
        kind = str(kind or "all").strip().lower()
        result: Dict[str, Any] = {"datasets": [], "metrics": [], "dimensions": []}

        def match(text: str) -> bool:
            return not q or q in (text or "").lower()

        if kind in ("all", "datasets"):
            for ds_id, ds in self.datasets.items():
                blob = " ".join(
                    [
                        ds_id,
                        str(ds.get("name") or ""),
                        " ".join(ds.get("use_cases") or []),
                    ]
                )
                if match(blob):
                    result["datasets"].append(
                        {
                            "id": ds_id,
                            "name": ds.get("name"),
                            "use_cases": ds.get("use_cases") or [],
                            "available_metrics": ds.get("available_metrics") or [],
                            "available_dimensions": ds.get("available_dimensions") or [],
                        }
                    )
        if kind in ("all", "metrics"):
            for mid, metric in self.metrics.items():
                blob = " ".join(
                    [mid, str(metric.get("name") or ""), " ".join(metric.get("aliases") or [])]
                )
                if match(blob):
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
            for did, dim in self.dimensions.items():
                blob = " ".join(
                    [did, str(dim.get("name") or ""), " ".join(dim.get("aliases") or [])]
                )
                if match(blob):
                    result["dimensions"].append(
                        {
                            "id": did,
                            "name": dim.get("name"),
                            "aliases": dim.get("aliases") or [],
                            "datasets": dim.get("datasets") or [],
                        }
                    )
        return result
