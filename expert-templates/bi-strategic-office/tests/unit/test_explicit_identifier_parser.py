#!/usr/bin/env python3
"""Unit tests for explicit identifier parser."""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "hermes-sqlbot-adapter"
sys.path.insert(0, str(PLUGIN))

from sqlbot_adapter.security.query_guard import extract_explicit_identifiers


def test_parse_various_forms():
    samples = [
        ("ar_trx_number = 101IN26070199", "101IN26070199"),
        ("凭证号 101IN26070199", "101IN26070199"),
        ("单据号:ABC-001", "ABC-001"),
        ("订单号 XXX123", "XXX123"),
        ("客户编号 C009", "C009"),
        ("customer_code=HK99", "HK99"),
    ]
    for text, expected in samples:
        ids = extract_explicit_identifiers(text)
        assert any(i.value == expected for i in ids), text
