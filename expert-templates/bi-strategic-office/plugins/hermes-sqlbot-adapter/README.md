# hermes-sqlbot-adapter（v1.11.1）

Hermes 进程内插件：通过 **SQLBot MCP SSE** 提供 `finance-bi` Toolset。

## 工具

- `finance_bi_ask`
- `finance_bi_followup`
- `finance_bi_explain`
- `finance_bi_reset`

模型看不到 SQLBot 用户名、密码、`access_token`、`chat_id`、加密密钥。

## 依赖

见 `requirements.txt`：`mcp==1.26.0`、`anyio==4.14.2`、`httpx==0.28.1`、`sqlglot`、`cryptography`、`PyYAML`。

## 脚本

- `scripts/init_state.py` — 初始化 schema v2
- `scripts/connection_test.py` — initialize + ping
- `scripts/direct_flow_test.py` — 正式直连验收（`--deep` 同源）
