ASK = {
    "name": "finance_bi_ask",
    "description": (
        "Run a natural-language financial BI query through the semantic catalog. "
        "Returns a structured table with metric versions, entity scope, and warnings. "
        "Never invent numbers; use this tool instead of raw SQL."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Natural language question, e.g. 查询2026Q2各产品销售利润报表",
            },
            "output_mode": {
                "type": "string",
                "description": "Output mode",
                "default": "table_and_summary",
            },
            "session_id": {
                "type": "string",
                "description": "Optional session identifier for audit",
                "default": "",
            },
        },
        "required": ["question"],
    },
}

FOLLOWUP = {
    "name": "finance_bi_followup",
    "description": (
        "Refine a previous BI query by query_id. Applies filters/drilldowns on the saved "
        "SemanticQuery without freely regenerating SQL."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "base_query_id": {
                "type": "string",
                "description": "Previous query_id, e.g. biq_xxx",
            },
            "instruction": {
                "type": "string",
                "description": "Follow-up instruction, e.g. 只看毛利率低于5%的产品",
            },
            "session_id": {"type": "string", "default": ""},
            "output_mode": {"type": "string", "default": "table_and_summary"},
        },
        "required": ["base_query_id", "instruction"],
    },
}

EXPLAIN = {
    "name": "finance_bi_explain",
    "description": "Explain metric definitions, dataset grain, filters, or a prior query.",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {"type": "string", "default": ""},
            "metric": {"type": "string", "default": ""},
            "topic": {"type": "string", "default": ""},
        },
        "required": [],
    },
}

CATALOG_SEARCH = {
    "name": "finance_bi_catalog_search",
    "description": "Search available datasets, metrics, dimensions, and aliases.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "default": ""},
            "kind": {
                "type": "string",
                "description": "all | datasets | metrics | dimensions",
                "default": "all",
            },
        },
        "required": [],
    },
}

VALIDATE = {
    "name": "finance_bi_validate_result",
    "description": "Validate a prior query result before formal reporting.",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {"type": "string"},
        },
        "required": ["query_id"],
    },
}

EXPORT = {
    "name": "finance_bi_export_result",
    "description": "Export a prior query result to CSV or XLSX under workspace/exports/bi.",
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {"type": "string"},
            "format": {
                "type": "string",
                "description": "csv or xlsx",
                "default": "csv",
            },
        },
        "required": ["query_id"],
    },
}
