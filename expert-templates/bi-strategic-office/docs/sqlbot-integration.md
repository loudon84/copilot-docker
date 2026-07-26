# SQLBot 集成说明

## 集成方式

Hermes 不直接把 SQLBot MCP 工具暴露给模型。生产路径：

```text
finance_bi_ask / followup / explain / reset
        │
        ▼
hermes-sqlbot-adapter
        │  内部调用
        ▼
mcp_start / mcp_question / mcp_ws_list / mcp_datasource_list
        │
        ▼
SQLBot MCP HTTP 端点（SQLBOT_MCP_URL）
```

## 会话映射

```text
Hermes Profile + Session ID + User ID
        ↕
sqlbot-adapter/state/sqlbot_sessions.db
        ↕
SQLBot chat_id + encrypted token
```

- 首次 `ask`：登录并创建/绑定对话
- 后续 `followup`：复用 `chat_id`
- `reset`：清除映射
- TTL 默认 24h（`SQLBOT_SESSION_TTL_SECONDS`）

## 查询保护

1. SQL 只读（SELECT / WITH）
2. 显式编号必须出现在 SQL，否则 `FILTER_NOT_PRESERVED`
3. 明细查询必须有有效过滤，否则 `DETAIL_QUERY_REQUIRES_FILTER`
4. 行数截断：`SQLBOT_MODEL_RESULT_ROWS`（默认 100）/ `SQLBOT_MAX_RESULT_ROWS`（默认 500）

## 错误码

见 PRD v1.11 §15。常见：

| 错误码 | 含义 |
|--------|------|
| `SQLBOT_NOT_CONFIGURED` | 缺少环境变量 |
| `SQLBOT_UNAVAILABLE` | MCP 不可达/超时 |
| `SQLBOT_AUTH_FAILED` | 登录失败 |
| `QUERY_CONTEXT_NOT_FOUND` | 无会话可追问 |
| `FILTER_NOT_PRESERVED` | 显式过滤丢失 |
| `UNSAFE_SQL` | 非只读 SQL |

## 配置位置

- 模板示例：`config/sqlbot.example.env`
- 运行时凭证：`instances/<profile>/.env`（及同步后的 `data/hermes/.env`）
- 实施记录：`docs/sqlbot-example.md`
