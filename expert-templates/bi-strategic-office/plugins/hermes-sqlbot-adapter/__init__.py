"""Hermes SQLBot adapter plugin entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import schemas
from sqlbot_adapter.handlers import tools as handlers


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
        name="finance_bi_reset",
        toolset="finance-bi",
        schema=schemas.RESET,
        handler=handlers.finance_bi_reset,
        description=schemas.RESET["description"],
    )
