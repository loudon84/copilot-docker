"""Repair common Chinese mojibake from wrong pymssql charset."""

from __future__ import annotations

from typing import Any


def _cjk_count(text: str) -> int:
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff")


def repair_chinese_text(value: Any) -> Any:
    """If a string looks like GBK/UTF-8 bytes mis-decoded as latin-1, repair it."""
    if not isinstance(value, str) or not value:
        return value
    if _cjk_count(value) >= 2:
        return value
    # Typical markers when GBK was read as latin-1/cp1252 (e.g. ÓÐÏÞ¹«Ë¾)
    markers = ("Ó", "Ë", "¹", "£", "â", "Ã", "Ê", "Ç", "Ð", "Ñ", "þ", "ÿ")
    if not any(m in value for m in markers):
        return value
    for enc in ("gbk", "gb18030", "utf-8"):
        try:
            fixed = value.encode("latin-1").decode(enc)
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
        if _cjk_count(fixed) >= 2:
            return fixed
    return value


def repair_row_strings(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        out[k] = repair_chinese_text(v)
    return out
