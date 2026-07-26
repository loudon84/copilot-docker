ASK = {
    "name": "finance_bi_ask",
    "description": (
        "发起新的财务 BI 问数。通过 SQLBot Adapter 查询只读数据源。"
        "返回标准化表格：success/query_id/columns/rows。"
        "不得自行生成或执行 SQL；不得传递 SQLBot 内部 ID / Token / chat_id。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "用户原始问题，例如：查询2026Q2各产品销售利润",
            },
            "datasource_key": {
                "type": "string",
                "description": "配置中的数据源别名（可选），不要传 SQLBot datasource_id",
                "default": "",
            },
            "response_mode": {
                "type": "string",
                "description": "data_only | data_and_summary | chart",
                "default": "data_and_summary",
                "enum": ["data_only", "data_and_summary", "chart"],
            },
        },
        "required": ["question"],
    },
}

FOLLOWUP = {
    "name": "finance_bi_followup",
    "description": (
        "基于当前会话的 SQLBot 对话继续追问。"
        "不存在可继续上下文时返回 QUERY_CONTEXT_NOT_FOUND。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": "追问指令，例如：只看毛利率低于5%的产品",
            },
            "response_mode": {
                "type": "string",
                "default": "data_and_summary",
                "enum": ["data_only", "data_and_summary", "chart"],
            },
        },
        "required": ["instruction"],
    },
}

EXPLAIN = {
    "name": "finance_bi_explain",
    "description": (
        "解释最近一次查询：返回 SQL、数据源、筛选条件、表和字段信息。"
        "不重新查询数据库。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query_id": {
                "type": "string",
                "description": "可选的 query_id；默认解释最近一次查询",
                "default": "",
            },
        },
        "required": [],
    },
}

RESET = {
    "name": "finance_bi_reset",
    "description": (
        "清除当前 Hermes Session 与 SQLBot chat_id 的映射。"
        "下一次查询将重新创建 SQLBot 对话。"
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
