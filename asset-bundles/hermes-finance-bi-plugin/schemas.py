ASK = {
    "name": "finance_bi_ask",
    "description": (
        "Run a natural-language financial BI query through the semantic catalog. "
        "ALWAYS returns a tabular dataset: result_type=table with columns/fields + rows. "
        "Presentation (markdown, prose summary, charts) is done by skills from this table — "
        "do not invent numbers; use this tool instead of raw SQL."
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
                "description": "Deprecated compatibility field; tools always return result_type=table",
                "default": "table",
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
            "output_mode": {
                "type": "string",
                "default": "table",
                "description": "Deprecated; always returns result_type=table",
            },
        },
        "required": ["base_query_id", "instruction"],
    },
}

EXPLAIN = {
    "name": "finance_bi_explain",
    "description": (
        "Explain metric definitions, dataset grain, filters, or a prior query. "
        "Returns result_type=table (rows of metrics/catalog objects)."
    ),
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
    "description": (
        "Search available datasets, metrics, dimensions, date fields, and aliases. "
        "ALWAYS returns result_type=table (row-oriented). "
        "Use this for catalog exploration (哪些数据集/指标/日期字段). "
        "IMPORTANT: put the search text in `query` (e.g. query=毛利). "
        "`kind` must be one of: all | datasets | metrics | dimensions | date_fields. "
        "Do NOT put Chinese keywords into `kind`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search text, e.g. 毛利 / 销售利润报表 / 日期. Empty returns full production catalog.",
                "default": "",
            },
            "kind": {
                "type": "string",
                "description": "Filter type ONLY: all | datasets | metrics | dimensions | date_fields",
                "default": "all",
                "enum": ["all", "datasets", "metrics", "dimensions", "date_fields", "fields"],
            },
        },
        "required": [],
    },
}

VALIDATE = {
    "name": "finance_bi_validate_result",
    "description": (
        "Validate a prior query result before formal reporting. "
        "Returns result_type=table of check rows."
    ),
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
