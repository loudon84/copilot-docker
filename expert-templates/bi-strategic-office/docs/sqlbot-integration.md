# SQLBot 集成说明（v1.11.1）

## 集成方式

Hermes 不直接把 SQLBot MCP 工具暴露给模型。生产路径：

```text
finance_bi_ask / followup / explain / reset
        │
    ▼
hermes-sqlbot-adapter（AsyncBridge + SQLBotMCPClient）
        │  每次调用：sse_client → ClientSession → initialize → call_tool
        ▼
mcp_start / mcp_question / mcp_ws_list / mcp_datasource_list
        │
        ▼
SQLBot MCP SSE 端点（SQLBOT_MCP_URL）
```

依赖锁定：`mcp==1.26.0`、`anyio==4.14.2`、`httpx==0.28.1`。业务路径**不**依赖 `tools/list`。

## 会话映射与加密

```text
Hermes Profile + Session ID + User ID
        ↕
sqlbot-adapter/state/sqlbot_sessions.db（schema v2）
        ↕
SQLBot chat_id + Fernet(access_token)
```

- 必填 `SQLBOT_SESSION_ENCRYPTION_KEY`（禁止明文回退）
- 首次 `ask`：登录并创建/绑定对话
- 后续 `followup`：复用 `chat_id`
- SQL 执行失败 / Datasource Session Error：**保留**映射；仅 `reset` 删除
- Token 失效：删映射后重登一次
- TTL 默认 24h（`SQLBOT_SESSION_TTL_SECONDS`）

## 查询保护

1. SQL 只读（SELECT / WITH）
2. 显式编号必须出现在 SQL，否则 `FILTER_NOT_PRESERVED`
3. 明细查询必须有有效过滤，否则 `DETAIL_QUERY_REQUIRES_FILTER`
4. 行数：模型截断 `SQLBOT_MODEL_RESULT_ROWS`（默认 100）；硬上限 `SQLBOT_MAX_RESULT_ROWS`（默认 500）超限 → `RESULT_TOO_LARGE`

## 错误码（节选）

| 错误码 | 含义 |
|--------|------|
| `SQLBOT_NOT_CONFIGURED` | 缺少环境变量（含加密 Key） |
| `SQLBOT_TRANSPORT_ERROR` | SSE/网络错误 |
| `SQLBOT_INITIALIZE_FAILED` | MCP initialize 失败 |
| `SQLBOT_AUTH_FAILED` | 登录失败 |
| `SQLBOT_DATASOURCE_SESSION_ERROR` | 如 `DetachedInstanceError`（SQL 已生成但数据源会话失效） |
| `SQLBOT_EXECUTION_FAILED` | SQL 执行失败 |
| `RESULT_TOO_LARGE` | 超过硬上限行数 |
| `RUNTIME_CONTEXT_UNAVAILABLE` | 无法解析 Hermes 运行时会话上下文 |
| `FILTER_NOT_PRESERVED` | 显式过滤丢失 |

完整 traceback **只**写入审计，不进入 Tool Result。

## Doctor

```bash
# 默认：plugin / env / MCP reachable / initialize / ping / store&audit
bash bin/doctor.sh --profile <p>

# 深度：mcp_start + workspace/datasource + SQL 探针
bash bin/doctor.sh --profile <p> --deep
```

`tools/list` 异常仅 WARN；默认不创建 `chat_id`。

## 配置位置

- 模板示例：`config/sqlbot.example.env`
- 运行时凭证：`instances/<profile>/.env`
- 正式直连脚本：`plugins/hermes-sqlbot-adapter/scripts/direct_flow_test.py`
- 实施记录：`docs/sqlbot-example.md`
