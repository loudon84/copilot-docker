# hermes-sqlbot-adapter（v1.12.0）

Hermes 进程内插件：通过 **SQLBot MCP SSE** 提供 `finance-bi` Toolset。

## 工具

| 工具 | 行为 |
|---|---|
| `finance_bi_ask` | 每次新建独立 SQLBot 对话后问数 |
| `finance_bi_followup` | 复用当前 Hermes Session 的 SQLBot 对话追问 |
| `finance_bi_explain` | 解释本地已记录查询（可按 `query_id`），不访问 SQLBot |
| `finance_bi_reset` | 清除 Session↔SQLBot 映射，保留查询审计历史 |

模型看不到 SQLBot 用户名、密码、Token、`chat_id`、加密密钥、内部工作空间/数据源 ID。

## 安全边界

- Adapter **不**自行生成 SQL，**不**直连业务库。
- SQL Guard 是 **执行后校验**（SQLBot `mcp_question` 已生成并执行后），用于阻止不合规结果进入 Hermes；**不能**充当数据库执行防火墙。
- 业务数据源必须使用只读账号。

## 依赖

见 `requirements.txt` / `pyproject.toml`：`mcp==1.26.0`、`anyio`、`httpx`、`sqlglot`、`cryptography`、`PyYAML`。

## 必需环境变量

```text
SQLBOT_MCP_URL
SQLBOT_USERNAME
SQLBOT_PASSWORD
SQLBOT_WORKSPACE_ID
SQLBOT_DEFAULT_DATASOURCE_ID
SQLBOT_SESSION_ENCRYPTION_KEY
```

可选：`SQLBOT_DATASOURCE_ALIASES`、`SQLBOT_DATASOURCES_JSON`、`SQLBOT_VERIFY_SSL`、`SQLBOT_LANG`、`SQLBOT_MODEL_RESULT_ROWS`、`SQLBOT_MAX_RESULT_ROWS`、`SQLBOT_MAX_RESULT_COLUMNS`、`SQLBOT_MAX_RESULT_BYTES`、`SQLBOT_QUERY_RETENTION_DAYS`、`SQLBOT_AUDIT_RETENTION_DAYS`、`SQLBOT_CLI_SESSION_ID`（CLI 必填）。

## 安装方式

### 目录插件

将本目录挂到 Hermes plugins 路径后由 `plugin.yaml` + `__init__.register` 加载。

### Pip Wheel

```bash
python -m build
pip install dist/hermes_sqlbot_adapter-1.12.0-py3-none-any.whl
python -c "from sqlbot_adapter.client.mcp_client import SQLBotMCPClient"
```

Wheel 必须包含 `sqlbot_adapter/client|handlers|normalizer|security|session|audit` 子包。

## 脚本

```bash
# 初始化 Session Store（schema v3）
python scripts/init_state.py

# MCP 连通性
python scripts/connection_test.py

# 正式直连验收（与生产 Client 同协议）
python scripts/direct_flow_test.py --url <mcp_sse_url> --oid <workspace_oid> --datasource-id <id>
```

## 本地测试

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q
```

## 故障处理

| 现象 | 排查 |
|---|---|
| `INVALID_DATASOURCE_KEY` | 检查别名配置，未知别名不再静默回退 |
| `SQLBOT_SESSION_EXPIRED` | followup 时 Token 过期，需重新 `ask` |
| `SQLBOT_RESPONSE_INVALID` | SQLBot 成功体缺少 `sql` / `data.fields` / `data.data` |
| `SQLBOT_TOOL_ERROR` | MCP `isError=true` |
| `FILTER_NOT_PRESERVED` | 业务编号未出现在 WHERE/JOIN/HAVING 精确谓词 |
| `UNSAFE_SQL` | 含 DML/DDL/`SELECT INTO` 等 |

## 版本

- 当前：`1.12.0`（PRD v1.12 hotfix）
- 上一版：`1.11.1`
