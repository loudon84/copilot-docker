"""Hermes finance-bi plugin entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

# Plugin directory name may contain hyphens (invalid as a Python package name).
# Always put this directory on sys.path and use absolute imports.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import schemas
from finance_bi.handlers import tools as handlers


def register(ctx):
    ctx.register_tool(
        name="finance_bi_ask",
        toolset="finance-bi",
        schema=schemas.ASK,
        handler=handlers.finance_bi_ask,
        description=schemas.ASK["description"],
    )
    ctx.register_tool(
        name="finance_bi_followup",
        toolset="finance-bi",
        schema=schemas.FOLLOWUP,
        handler=handlers.finance_bi_followup,
        description=schemas.FOLLOWUP["description"],
    )
    ctx.register_tool(
        name="finance_bi_explain",
        toolset="finance-bi",
        schema=schemas.EXPLAIN,
        handler=handlers.finance_bi_explain,
        description=schemas.EXPLAIN["description"],
    )
    ctx.register_tool(
        name="finance_bi_catalog_search",
        toolset="finance-bi",
        schema=schemas.CATALOG_SEARCH,
        handler=handlers.finance_bi_catalog_search,
        description=schemas.CATALOG_SEARCH["description"],
    )
    ctx.register_tool(
        name="finance_bi_validate_result",
        toolset="finance-bi",
        schema=schemas.VALIDATE,
        handler=handlers.finance_bi_validate_result,
        description=schemas.VALIDATE["description"],
    )
    ctx.register_tool(
        name="finance_bi_export_result",
        toolset="finance-bi",
        schema=schemas.EXPORT,
        handler=handlers.finance_bi_export_result,
        description=schemas.EXPORT["description"],
    )
