#!/usr/bin/env python3
"""Integration smoke: plugin registration surface (no Hermes runtime)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = PACKAGE_ROOT / "plugins" / "hermes-finance-bi-plugin"


def test_plugin_register_callable():
    sys.path.insert(0, str(PLUGIN))
    spec = importlib.util.spec_from_file_location(
        "hermes_finance_bi_plugin",
        PLUGIN / "__init__.py",
        submodule_search_locations=[str(PLUGIN)],
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hermes_finance_bi_plugin"] = mod
    spec.loader.exec_module(mod)
    assert callable(getattr(mod, "register", None))


def test_toolset_name_in_plugin_yaml():
    text = (PLUGIN / "plugin.yaml").read_text(encoding="utf-8")
    assert "finance_bi_ask" in text
    assert "hermes-finance-bi-plugin" in text
