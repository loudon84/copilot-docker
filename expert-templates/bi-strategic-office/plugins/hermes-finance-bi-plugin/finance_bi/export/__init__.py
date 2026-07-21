from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from finance_bi.config import FinanceBiConfig
from finance_bi.contracts import ErrorCode, FinanceBiError


def export_result(
    *,
    config: FinanceBiConfig,
    query_id: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    fmt: str,
) -> Dict[str, Any]:
    fmt = (fmt or "csv").lower()
    if fmt not in ("csv", "xlsx"):
        raise FinanceBiError(ErrorCode.INVALID_ARGUMENT, "format must be csv or xlsx")

    out_dir = Path(config.export_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{query_id}.{fmt}"
    path = out_dir / filename

    try:
        if fmt == "csv":
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                for row in rows:
                    writer.writerow({c: row.get(c) for c in columns})
        else:
            try:
                from openpyxl import Workbook
            except ImportError as exc:
                raise FinanceBiError(
                    ErrorCode.EXPORT_FAILED,
                    "openpyxl is required for xlsx export",
                ) from exc
            wb = Workbook()
            ws = wb.active
            ws.title = "result"
            ws.append(columns)
            for row in rows:
                ws.append([row.get(c) for c in columns])
            wb.save(path)
    except FinanceBiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FinanceBiError(ErrorCode.EXPORT_FAILED, f"export failed: {type(exc).__name__}") from exc

    return {
        "status": "ok",
        "query_id": query_id,
        "format": fmt,
        "path": str(path),
        "row_count": len(rows),
    }
