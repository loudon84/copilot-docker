# PRD v1.11.1_hotfix

## bi-strategic-office / hermes-sqlbot-adapter 修复方案

## 1. 文档信息

| 项目          | 内容                                     |
| ----------- | -------------------------------------- |
| 项目仓库        | `loudon84/copilot-docker`              |
| 专家模板        | `expert-templates/bi-strategic-office` |
| 修复对象        | `plugins/hermes-sqlbot-adapter`        |
| PRD 版本      | `v1.11.1_hotfix`                       |
| 专家包版本       | `1.11.1`                               |
| 建议 Git Tag  | `bi-strategic-office-v1.11.1-hotfix`   |
| 实施工具        | Cursor                                 |
| SQLBot 源码修改 | 不包含                                    |

建议保存为：

```text
expert-templates/bi-strategic-office/prd/
bi-strategic-office-prd-v1.11.1_hotfix.md
```

---

# 2. 需求背景

`bi-strategic-office` v1.11.0 已将财务问数入口迁移到 SQLBot，并通过 `hermes-sqlbot-adapter` 对 SQLBot MCP 进行封装。

当前已完成以下验证：

```text
Hermes 容器
→ SQLBot MCP SSE 连接成功
→ MCP initialize 成功
→ MCP ping 成功
→ mcp_start 调用成功
→ access_token 获取成功
→ chat_id 获取成功
→ 工作空间和数据源可访问
→ mcp_question 可提交问题
→ SQLBot 可生成 SQL
```

当前 SQLBot 返回的执行错误为：

```text
sqlalchemy.orm.exc.DetachedInstanceError
```

错误发生在 SQLBot 内部 SQL 执行阶段：

```text
SQLBot execute_sql()
→ exec_sql(ds=self.ds, sql=...)
→ CoreDatasource 脱离 Session
```

该错误不属于 Hermes MCP 地址、SQLBot 登录、Token、`chat_id` 或问数参数问题。

同时，当前 Adapter 仍存在以下问题：

1. 正式插件代码和测试脚本使用了不同的 MCP Client 实现；
2. MCP SSE 生命周期曾采用手工 `__aenter__()` / `__aexit__()`，会引发 AnyIO Cancel Scope 错误；
3. `tools/list` 返回结果与固定工具调用结果不一致；
4. 业务调用不应依赖 `list_tools()`；
5. SQLBot 嵌套 JSON 错误没有统一解析；
6. SQLBot traceback 可能直接返回给 Hermes；
7. `access_token` 和 `chat_id` 的持久化及隔离未完成；
8. `finance_bi_ask`、`finance_bi_followup`、`finance_bi_explain`、`finance_bi_reset` 尚未统一使用正式 Client；
9. SQLBot 服务错误和 Adapter 自身错误没有明确区分；
10. `doctor.sh` 无法准确区分网络、认证、SQL 生成和 SQL 执行状态。

Hermes Plugin 应通过 `ctx.register_tool()` 注册业务工具，工具 handler 必须返回字符串，不能向 Agent Loop 抛出未处理异常。扩展逻辑应保留在 Plugin 内，不修改 `AIAgent` 和工具注册核心。

---

# 3. 修复目标

本次 Hotfix 完成以下目标：

1. 将已验证成功的 SQLBot MCP 直连逻辑迁移到正式 Adapter；
2. 统一 MCP Client，不再在测试脚本中保留独立实现；
3. 修复 SSE 和 `ClientSession` 生命周期；
4. 业务调用不再依赖 `list_tools()`；
5. 固定调用 SQLBot MCP 工具名称；
6. 完成 SQLBot Token 和 `chat_id` 会话管理；
7. 完成 Hermes Session 与 SQLBot Session 隔离；
8. 统一解析 SQLBot MCP 返回值；
9. 对 SQLBot 执行错误进行分类；
10. 对 `DetachedInstanceError` 返回明确错误码；
11. 禁止将 SQLBot Token、密码和完整 traceback 返回给模型；
12. 完成四个 `finance_bi_*` 工具；
13. 补充审计、日志、Doctor 和测试；
14. 保证 SQLBot 服务故障不会导致 Hermes Agent Loop 中断；
15. 不修改 SQLBot 源码。

---

# 4. 非目标

本版本不处理：

* SQLBot `DetachedInstanceError` 的服务端源码修复；
* SQLBot 前端修改；
* SQLBot 数据库表结构修改；
* SQLBot MCP Server 修改；
* SQLBot ORM Session 修改；
* SQLBot 登录机制修改；
* SQLBot 用户同步；
* nodeskclaw 用户权限映射；
* 自研 Text-to-SQL；
* Adapter 直接执行 SQL；
* Hermes 原生 `hermes mcp add sqlbot` 配置；
* 修改 Hermes Agent 核心循环；
* 修改 `tools/registry.py`；
* 修改 `AIAgent.run_conversation()`；
* 修改其他专家模板；
* 修改公共脚本业务逻辑。

---

# 5. 修复边界

本次只允许修改：

```text
expert-templates/bi-strategic-office/
```

重点目录：

```text
expert-templates/bi-strategic-office/
├── expert.yaml
├── VERSION
├── CHANGELOG.md
├── runtime/
├── plugins/hermes-sqlbot-adapter/
├── bin/
├── tests/
├── docs/
└── prd/
```

本次不修改：

```text
scripts/create-instance.sh
scripts/up-instance.sh
scripts/sync-runtime-env.sh
docker-compose.yml
Hermes Agent 源码
SQLBot 源码
```

容器中的：

```text
/data/hermes/plugins/hermes-sqlbot-adapter/
```

只能作为运行副本，不作为源码修改位置。

---

# 6. 当前调用链判断

当前验证结果：

| 层级                      | 状态           |
| ----------------------- | ------------ |
| Hermes 容器到 18001        | 通过           |
| SSE Transport           | 通过           |
| MCP initialize          | 通过           |
| MCP ping                | 通过           |
| `mcp_start`             | 通过           |
| SQLBot 登录               | 通过           |
| Token 获取                | 通过           |
| `chat_id` 获取            | 通过           |
| 工作空间访问                  | 通过           |
| 数据源访问                   | 通过           |
| SQL 生成                  | 通过           |
| SQL 执行                  | SQLBot 服务端失败 |
| Adapter 统一错误处理          | 未完成          |
| Hermes `finance_bi_ask` | 待修复          |

目标链路：

```text
Hermes Agent
    │
    │ finance_bi_ask
    ▼
hermes-sqlbot-adapter
    │
    ├── Runtime Context
    ├── Session Store
    ├── MCP Client
    ├── Result Parser
    ├── Query Guard
    ├── Error Mapper
    └── Audit
    │
    ▼
SQLBot MCP
    │
    ├── mcp_start
    ├── mcp_ws_list
    ├── mcp_datasource_list
    └── mcp_question
```

Adapter 保留身份、会话、结果标准化和安全复核职责。SQLBot 负责 SQL 生成和执行。

---

# 7. 目标目录结构

```text
plugins/
└── hermes-sqlbot-adapter/
    ├── plugin.yaml
    ├── pyproject.toml
    ├── requirements.txt
    ├── __init__.py
    │
    ├── sqlbot_adapter/
    │   ├── __init__.py
    │   ├── config.py
    │   ├── contracts.py
    │   ├── errors.py
    │   ├── runtime_context.py
    │   ├── service.py
    │   │
    │   ├── client/
    │   │   ├── __init__.py
    │   │   ├── mcp_client.py
    │   │   └── result_parser.py
    │   │
    │   ├── session/
    │   │   ├── __init__.py
    │   │   ├── models.py
    │   │   └── session_store.py
    │   │
    │   ├── security/
    │   │   ├── __init__.py
    │   │   ├── query_guard.py
    │   │   └── result_guard.py
    │   │
    │   ├── audit/
    │   │   ├── __init__.py
    │   │   └── audit_repository.py
    │   │
    │   └── handlers/
    │       ├── __init__.py
    │       ├── ask.py
    │       ├── followup.py
    │       ├── explain.py
    │       └── reset.py
    │
    ├── scripts/
    │   ├── connection_test.py
    │   ├── direct_flow_test.py
    │   └── init_state.py
    │
    └── tests/
        ├── unit/
        ├── integration/
        ├── security/
        └── fixtures/
```

删除或停用重复测试文件：

```text
test_sqlbot.py
sqlbot_direct_start.py
sqlbot_direct_flow.py
```

保留一个正式测试入口：

```text
scripts/direct_flow_test.py
```

该脚本必须调用：

```text
sqlbot_adapter.client.mcp_client.SQLBotMCPClient
```

不得复制 MCP 连接代码。

---

# 8. 依赖锁定

当前验证通过的依赖版本：

```text
mcp=1.26.0
anyio=4.14.2
httpx=0.28.1
```

Hotfix 期间固定为：

```text
mcp==1.26.0
anyio==4.14.2
httpx==0.28.1
```

`requirements.txt`：

```text
mcp==1.26.0
anyio==4.14.2
httpx==0.28.1
sqlglot>=26,<27
cryptography>=43,<45
```

规则：

* Hotfix 不自动升级 MCP SDK；
* 不使用未验证的 `mcp>=2`；
* 依赖变化必须重新执行完整 MCP 测试；
* `post-start.sh` 使用当前 Hermes `/app/venv` 安装依赖；
* 安装失败必须输出包名和版本。

---

# 9. MCP Client 修复

## 9.1 固定工具名称

创建：

```python
SQLBOT_TOOL_START = "mcp_start"
SQLBOT_TOOL_QUESTION = "mcp_question"
SQLBOT_TOOL_WS_LIST = "mcp_ws_list"
SQLBOT_TOOL_DATASOURCE_LIST = "mcp_datasource_list"
```

业务调用不得根据 `list_tools()` 动态推断工具名。

## 9.2 `list_tools()` 使用规则

`list_tools()` 只允许用于：

* Doctor；
* 调试；
* 诊断日志；
* 测试输出。

不得用于：

* `finance_bi_ask` 前置判断；
* `finance_bi_followup` 前置判断；
* Plugin 启动阻断；
* SQLBot 登录阻断。

当前兼容策略：

```text
tools/list 异常
→ 记录 WARNING
→ 继续固定工具调用

固定工具调用失败
→ 返回 SQLBOT_MCP_TOOL_UNAVAILABLE
```

## 9.3 SSE 生命周期

正式 Client 必须使用嵌套上下文：

```python
async with sse_client(url) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        return await session.call_tool(...)
```

禁止：

```python
await sse_client(url).__aenter__()
await session.__aexit__()
```

禁止：

* 全局保存 `ClientSession`；
* 全局保存 SSE Transport；
* 在不同 Task 中进入和退出；
* 在多个 Hermes 请求间复用同一个 AnyIO TaskGroup；
* 在运行中的事件循环内再次调用 `asyncio.run()`。

## 9.4 连接策略

首期采用：

```text
一次 MCP Tool 调用
→ 建立一次 SSE
→ initialize
→ call_tool
→ 关闭连接
```

业务会话依靠：

```text
access_token + chat_id
```

保持，不依靠长期 SSE 连接。

## 9.5 超时

环境变量：

```env
SQLBOT_CONNECT_TIMEOUT_SECONDS=15
SQLBOT_REQUEST_TIMEOUT_SECONDS=120
SQLBOT_LOGIN_TIMEOUT_SECONDS=30
```

规则：

* initialize 超时：重试一次；
* `mcp_start` 网络失败：重试一次；
* `mcp_question` 提交后断开：不自动重试；
* SQL 执行错误：不自动重试。

---

# 10. MCP 返回解析

新增：

```text
client/result_parser.py
```

必须支持：

1. MCP `TextContent`；
2. MCP `structuredContent`；
3. JSON 字符串；
4. Markdown JSON Code Fence；
5. JSON 中再次包含 JSON 字符串；
6. SQLBot 外层 `message` 字段中包含错误 JSON；
7. SQLBot SQL 已生成但执行失败；
8. 文本、表格、图表和数据混合返回。

解析层最多递归三层：

```text
MCP TextContent
→ JSON
→ message
→ JSON
```

示例：

```json
{
  "message": "{\"message\":\"Execute SQL Failed\",\"traceback\":\"...\",\"type\":\"exec-sql-err\"}"
}
```

解析后：

```json
{
  "message": "Execute SQL Failed",
  "traceback": "...",
  "type": "exec-sql-err"
}
```

---

# 11. 错误分类

新增错误类：

| 错误码                               | 含义                        |   是否重试 |
| --------------------------------- | ------------------------- | -----: |
| `SQLBOT_NOT_CONFIGURED`           | 缺少配置                      |      否 |
| `SQLBOT_TRANSPORT_ERROR`          | MCP 网络或 SSE 错误            | 是，最多一次 |
| `SQLBOT_INITIALIZE_FAILED`        | MCP 初始化失败                 | 是，最多一次 |
| `SQLBOT_MCP_TOOL_UNAVAILABLE`     | 固定工具不可调用                  |      否 |
| `SQLBOT_AUTH_FAILED`              | 登录失败                      |      否 |
| `SQLBOT_SESSION_EXPIRED`          | Token 或会话失效               | 重新登录一次 |
| `SQLBOT_WORKSPACE_NOT_FOUND`      | 工作空间不存在                   |      否 |
| `SQLBOT_DATASOURCE_NOT_FOUND`     | 数据源不存在                    |      否 |
| `SQLBOT_QUERY_GENERATION_FAILED`  | SQL 生成失败                  |      否 |
| `SQLBOT_EXECUTION_FAILED`         | SQL 执行失败                  |      否 |
| `SQLBOT_DATASOURCE_SESSION_ERROR` | SQLBot 数据源 ORM Session 失效 |      否 |
| `SQLBOT_RESPONSE_INVALID`         | 返回结构无法解析                  |      否 |
| `FILTER_NOT_PRESERVED`            | 明确过滤条件丢失                  |      否 |
| `UNSAFE_SQL`                      | SQL 包含非只读语句               |      否 |
| `DETAIL_QUERY_REQUIRES_FILTER`    | 明细查询缺少过滤                  |      否 |
| `RESULT_TOO_LARGE`                | 返回数据超限                    |      否 |
| `QUERY_CONTEXT_NOT_FOUND`         | followup 无上下文             |      否 |
| `INTERNAL_ERROR`                  | Adapter 未分类错误             |      否 |

当前错误映射：

```text
traceback 包含 DetachedInstanceError
→ SQLBOT_DATASOURCE_SESSION_ERROR
```

用户返回：

```json
{
  "success": false,
  "error": {
    "code": "SQLBOT_DATASOURCE_SESSION_ERROR",
    "message": "SQLBot 已生成 SQL，但数据源会话失效，查询未执行。",
    "retryable": false,
    "source": "sqlbot"
  }
}
```

完整 traceback 只写审计日志。

---

# 12. Session Store 修复

## 12.1 存储位置

```text
/data/hermes/sqlbot-adapter/state/sqlbot_sessions.db
```

宿主机对应：

```text
instances/bi-finance/data/hermes/
sqlbot-adapter/state/sqlbot_sessions.db
```

## 12.2 映射键

```text
profile_name
+ hermes_session_id
+ hermes_user_id
```

禁止所有用户共享同一个 SQLBot `chat_id`。

## 12.3 数据表

```sql
CREATE TABLE IF NOT EXISTS sqlbot_sessions (
    profile_name TEXT NOT NULL,
    hermes_session_id TEXT NOT NULL,
    hermes_user_id TEXT NOT NULL,

    access_token_encrypted TEXT NOT NULL,
    sqlbot_chat_id INTEGER NOT NULL,

    workspace_id TEXT,
    datasource_id TEXT,

    token_expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,

    PRIMARY KEY (
        profile_name,
        hermes_session_id,
        hermes_user_id
    )
);
```

查询审计表：

```sql
CREATE TABLE IF NOT EXISTS sqlbot_queries (
    query_id TEXT PRIMARY KEY,
    profile_name TEXT NOT NULL,
    hermes_session_id TEXT NOT NULL,
    hermes_user_id TEXT NOT NULL,

    question TEXT NOT NULL,
    generated_sql TEXT,
    datasource_id TEXT,
    workspace_id TEXT,

    status TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,

    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

## 12.4 Token 存储

增加环境变量：

```env
SQLBOT_SESSION_ENCRYPTION_KEY=
```

要求：

* Token 写入 SQLite 前加密；
* 日志不输出 Token；
* Tool Result 不输出 Token；
* `sqlbot-example.md` 不记录 Token；
* 缺少加密 Key 时，Plugin 启动失败；
* 不允许明文回退。

## 12.5 生命周期

```text
新 Hermes 会话
→ mcp_start
→ 保存 token/chat_id

已有有效映射
→ 复用 token/chat_id

Token 明确失效
→ 删除旧映射
→ 重新登录一次

finance_bi_reset
→ 删除映射

SQL 执行失败
→ 保留映射

SQLBot Datasource Session Error
→ 保留映射
```

---

# 13. Runtime Context

新增：

```text
runtime_context.py
```

统一提取：

```text
profile_name
hermes_session_id
hermes_user_id
source
request_id
```

规则：

* 不允许模型输入 `hermes_session_id`；
* 不允许模型输入 `user_id`；
* 不允许模型输入 SQLBot Token；
* 不允许模型输入 SQLBot `chat_id`；
* 运行上下文由 Plugin Handler 获取；
* CLI 无用户 ID 时使用固定值 `local-cli`；
* Gateway 必须使用实际平台用户 ID；
* Context 取不到时返回 `RUNTIME_CONTEXT_UNAVAILABLE`，不得回退到所有用户共享。

---

# 14. SQLBot Service 层

新增：

```text
service.py
```

职责：

```text
start_session()
list_workspaces()
list_datasources()
ask()
followup()
reset()
explain()
```

业务 Handler 不直接调用 `ClientSession`。

调用关系：

```text
Handler
→ SQLBotService
→ SessionStore
→ SQLBotMCPClient
→ ResultParser
→ QueryGuard
→ AuditRepository
```

---

# 15. `finance_bi_ask`

## 15.1 输入

```json
{
  "question": "查询应收交易编号 101IN26070199 的交易明细",
  "datasource_key": "finance-ar",
  "response_mode": "data_and_summary"
}
```

字段：

| 字段               | 必填 | 说明                                     |
| ---------------- | -: | -------------------------------------- |
| `question`       |  是 | 用户问题                                   |
| `datasource_key` |  否 | 专家包配置中的数据源别名                           |
| `response_mode`  |  否 | `data_only`、`data_and_summary`、`chart` |

模型不得传：

```text
token
chat_id
workspace_id
datasource_id
username
password
```

## 15.2 处理流程

```text
校验输入
→ 获取 Runtime Context
→ 查询 Session Store
→ 无会话时调用 mcp_start
→ 取得固定 workspace 和 datasource
→ 调用 mcp_question
→ 解析返回
→ 提取 SQL
→ Query Guard
→ Result Guard
→ 写审计
→ 返回 JSON 字符串
```

## 15.3 成功返回

```json
{
  "success": true,
  "query_id": "fbq_xxx",
  "question": "查询应收交易编号 101IN26070199 的交易明细",
  "datasource": {
    "key": "finance-ar",
    "id": "10"
  },
  "query": {
    "sql": "SELECT ...",
    "filters": [
      {
        "field": "ar_trx_number",
        "operator": "=",
        "value": "101IN26070199"
      }
    ],
    "row_count": 1,
    "truncated": false
  },
  "columns": [],
  "rows": [],
  "chart": null,
  "warnings": []
}
```

## 15.4 SQLBot 执行失败返回

```json
{
  "success": false,
  "query_id": "fbq_xxx",
  "query": {
    "sql_generated": true,
    "sql": "SELECT ..."
  },
  "error": {
    "code": "SQLBOT_DATASOURCE_SESSION_ERROR",
    "message": "SQLBot 已生成 SQL，但数据源会话失效，查询未执行。",
    "retryable": false
  }
}
```

---

# 16. `finance_bi_followup`

输入：

```json
{
  "instruction": "只显示客户名称和未收金额"
}
```

处理规则：

* 使用相同 Hermes Session；
* 使用相同 SQLBot Token；
* 使用相同 SQLBot `chat_id`；
* 不重新调用 `mcp_start`；
* 不允许模型传 `chat_id`；
* 上下文不存在时返回 `QUERY_CONTEXT_NOT_FOUND`；
* SQLBot 执行失败时保留 Session；
* Token 明确失效时允许重新登录一次；
* 首期不自动重放历史问题。

---

# 17. `finance_bi_explain`

输入：

```json
{
  "query_id": "fbq_xxx"
}
```

用途：

* 返回最近一次查询问题；
* 返回生成 SQL；
* 返回工作空间；
* 返回数据源；
* 返回过滤条件；
* 返回执行状态；
* 返回错误码；
* 不再次调用 SQLBot；
* 不返回 Token；
* 不返回完整 traceback。

---

# 18. `finance_bi_reset`

处理：

```text
删除当前 Hermes Session 的 SQLBot 映射
→ 保留查询审计
→ 返回 reset 成功
```

返回：

```json
{
  "success": true,
  "reset": true
}
```

---

# 19. Query Guard

保留 SQL 安全检查。

只允许：

```text
SELECT
WITH ... SELECT
```

拒绝：

```text
INSERT
UPDATE
DELETE
MERGE
DROP
ALTER
TRUNCATE
CALL
EXEC
COPY
多语句
```

明确过滤条件检查：

```text
用户问题：
查询应收交易编号 101IN26070199

生成 SQL 必须包含：
101IN26070199
```

不包含时返回：

```text
FILTER_NOT_PRESERVED
```

明细查询没有限定条件时返回：

```text
DETAIL_QUERY_REQUIRES_FILTER
```

SQLBot 已生成 SQL但执行失败时，仍需对 SQL 执行只读检查后再记录审计。

---

# 20. Result Guard

配置：

```env
SQLBOT_MAX_RESULT_ROWS=500
SQLBOT_MODEL_RESULT_ROWS=100
```

规则：

* 模型最多接收 100 行；
* Adapter 最多接受 500 行；
* 超过 100 行标记 `truncated=true`；
* 超过 500 行返回 `RESULT_TOO_LARGE`；
* 不把 SQLBot 原始大结果直接放入上下文；
* 图表地址必须通过允许域名校验；
* 返回中的密码、Token、连接串必须脱敏。

---

# 21. Plugin 注册

`__init__.py` 只注册：

```text
finance_bi_ask
finance_bi_followup
finance_bi_explain
finance_bi_reset
```

Toolset：

```text
Finance-Bi
```

不注册：

```text
mcp_start
mcp_question
mcp_ws_list
mcp_datasource_list
access_token
chat_id
```

所有 Handler：

* 返回 JSON 字符串；
* 捕获所有 Adapter 异常；
* 捕获未分类异常；
* 不向 Hermes Registry 抛异常；
* 不打印密码和 Token。

---

# 22. 异步调用边界

优先实现：

```python
async def finance_bi_ask_handler(...)
```

如果当前 Hermes Plugin Registry 支持异步 Handler，直接注册异步函数。

如果当前版本只接受同步 Handler：

* 增加 `AsyncBridge`；
* 使用单独后台线程和固定事件循环；
* 同步 Handler 通过 `run_coroutine_threadsafe()` 提交；
* 禁止在运行中的事件循环内调用 `asyncio.run()`；
* 禁止每个调用创建后台线程。

Cursor 实施前先确认当前 Plugin Registry 对 awaitable Handler 的支持方式，不得猜测后直接写入。

---

# 23. 配置调整

`config/sqlbot.example.env`：

```env
SQLBOT_MCP_URL=http://192.168.102.247:18001/mcp

SQLBOT_USERNAME=
SQLBOT_PASSWORD=

SQLBOT_WORKSPACE_ID=
SQLBOT_DEFAULT_DATASOURCE_ID=

SQLBOT_SESSION_ENCRYPTION_KEY=

SQLBOT_CONNECT_TIMEOUT_SECONDS=15
SQLBOT_LOGIN_TIMEOUT_SECONDS=30
SQLBOT_REQUEST_TIMEOUT_SECONDS=120
SQLBOT_SESSION_TTL_SECONDS=86400

SQLBOT_MAX_RESULT_ROWS=500
SQLBOT_MODEL_RESULT_ROWS=100

SQLBOT_VERIFY_SSL=false
SQLBOT_AUDIT_ENABLED=true
```

真实值写入：

```text
instances/bi-finance/data/hermes/.env
```

不得写入 Git。

---

# 24. `plugin.yaml`

版本更新：

```yaml
id: hermes-sqlbot-adapter
version: 1.11.1
```

要求环境变量：

```yaml
requires_env:
  - SQLBOT_MCP_URL
  - SQLBOT_USERNAME
  - SQLBOT_PASSWORD
  - SQLBOT_WORKSPACE_ID
  - SQLBOT_DEFAULT_DATASOURCE_ID
  - SQLBOT_SESSION_ENCRYPTION_KEY
```

---

# 25. 安装与生命周期

## `bin/install.sh`

必须：

* 创建 `sqlbot-adapter/state`；
* 创建 `sqlbot-adapter/audit`；
* 安装 Plugin；
* 初始化 SQLite Schema；
* 写入 `package-state.yaml`；
* 不连接 SQLBot；
* 不执行问数；
* 幂等执行。

## `bin/post-start.sh`

必须：

* 检查依赖版本；
* 检查 Plugin 加载；
* 检查 Toolset；
* 执行 MCP initialize 和 ping；
* 不默认执行 `mcp_start`；
* 深度检查由参数触发；
* 返回清晰状态。

## `bin/update.sh`

必须：

* 备份旧 Plugin；
* 备份 SQLite；
* 更新 Plugin；
* 执行 Schema Migration；
* 保留已有 Session；
* 更新失败自动恢复旧 Plugin。

## `package-state.yaml`

至少记录：

```yaml
expert_id: bi-strategic-office
expert_version: 1.11.1
plugin_id: hermes-sqlbot-adapter
plugin_version: 1.11.1
installed_at:
updated_at:
schema_version: 2
```

---

# 26. Doctor 修复

默认检查：

```text
[OK] Adapter plugin installed
[OK] Finance-Bi toolset registered
[OK] SQLBot env configured
[OK] SQLBot MCP endpoint reachable
[OK] MCP initialize
[OK] MCP ping
[WARN] MCP tools/list incompatible
[OK] Session store writable
[OK] Audit directory writable
```

深度检查：

```bash
bin/doctor.sh --deep
```

增加：

```text
[OK] mcp_start
[OK] workspace access
[OK] datasource access
[FAIL] SQL execution
       code: SQLBOT_DATASOURCE_SESSION_ERROR
```

规则：

* `tools/list` 异常只记 WARNING；
* 固定工具调用失败记 FAIL；
* SQLBot SQL 执行失败记 FAIL；
* Doctor 不输出 Token；
* 默认 Doctor 不创建新 `chat_id`；
* `--deep` 才执行登录。

---

# 27. 日志与审计

审计目录：

```text
/data/hermes/sqlbot-adapter/audit/
```

记录：

```text
request_id
query_id
profile
session_id_hash
user_id_hash
workspace_id
datasource_id
question_hash
generated_sql
status
error_code
duration_ms
created_at
```

禁止记录：

```text
SQLBOT_PASSWORD
access_token
完整 Authorization Header
数据库连接密码
未脱敏用户原始数据
```

完整 SQLBot traceback：

* 只写服务端审计；
* 默认保留 7 天；
* 文件权限 `0600`；
* 用户响应中不显示。

---

# 28. 测试要求

## 28.1 单元测试

新增：

```text
test_mcp_client_lifecycle.py
test_result_parser.py
test_nested_json_error.py
test_error_mapper.py
test_detached_instance_error.py
test_session_store.py
test_session_isolation.py
test_token_encryption.py
test_query_guard.py
test_result_guard.py
test_handler_json_string.py
test_tool_list_not_required.py
test_secret_redaction.py
```

## 28.2 MCP 生命周期测试

连续调用 20 次：

```text
initialize
→ ping
→ call_tool
→ close
```

不得出现：

```text
Attempted to exit cancel scope in a different task
ClientSession has no attribute _task_group
GeneratorExit
```

## 28.3 Mock MCP 测试

覆盖：

* 登录成功；
* 登录失败；
* Token 失效；
* 工作空间不存在；
* 数据源不存在；
* SQL 生成成功；
* SQL 执行成功；
* SQL 执行失败；
* 嵌套 JSON 错误；
* `DetachedInstanceError`；
* Tool Not Found；
* SSE 超时；
* 返回结果超限。

## 28.4 实际 SQLBot 分层测试

```text
L1 initialize + ping
L2 mcp_start
L3 workspace
L4 datasource
L5 SQL generation
L6 SQL execution
L7 finance_bi_ask
L8 finance_bi_followup
```

当前允许记录：

```text
L1 PASS
L2 PASS
L3 PASS
L4 PASS
L5 PASS
L6 FAIL — SQLBOT_DATASOURCE_SESSION_ERROR
L7 PASS — 返回结构化错误
```

Hotfix 可在 L6 未通过时完成 Adapter 验收，但不得开放生产问数。

---

# 29. Cursor 实施任务

## T01 源码盘点

检查：

```text
expert-templates/bi-strategic-office/
plugins/hermes-sqlbot-adapter/
```

输出：

* 当前文件树；
* 重复 MCP Client；
* 重复测试脚本；
* 当前 Plugin 注册；
* 当前 Session Store；
* 当前错误处理。

## T02 升级版本

修改：

```text
VERSION
expert.yaml
plugin.yaml
CHANGELOG.md
README.md
```

版本：

```text
1.11.1
```

## T03 统一 MCP Client

将验证成功的直连逻辑迁入：

```text
sqlbot_adapter/client/mcp_client.py
```

删除生产代码中的手工 `__aenter__()`。

## T04 移除工具发现硬依赖

`finance_bi_*` 不得依赖 `list_tools()`。

## T05 新增 Result Parser

完成嵌套 JSON、TextContent 和错误解析。

## T06 新增错误体系

完成错误类和错误码。

## T07 修复 Session Store

完成：

* SQLite；
* 加密 Token；
* Session 隔离；
* TTL；
* reset；
* Schema Migration。

## T08 实现 Service 层

所有业务调用从 Service 进入。

## T09 重写四个 Handler

统一返回 JSON 字符串。

## T10 修复 Query Guard

检查只读 SQL和明确过滤条件。

## T11 修复 Result Guard

限制行数和敏感字段。

## T12 修复 Audit

完成脱敏和错误记录。

## T13 修复 Doctor

区分：

```text
网络
初始化
认证
SQL 生成
SQL 执行
```

## T14 清理测试脚本

只保留正式 Client 驱动的测试脚本。

## T15 补充测试

完成单元、集成、安全和部署测试。

## T16 更新文档

修改：

```text
docs/sqlbot-integration.md
docs/sqlbot-example.md
docs/troubleshooting.md
```

记录当前 SQLBot 服务端问题：

```text
SQLBOT_DATASOURCE_SESSION_ERROR
```

---

# 30. 部署步骤

## 30.1 开发环境

先修改源码：

```text
expert-templates/bi-strategic-office/
plugins/hermes-sqlbot-adapter/
```

禁止只修改容器文件。

## 30.2 测试同步

开发验证期间：

```bash
rsync -a --delete \
  expert-templates/bi-strategic-office/plugins/hermes-sqlbot-adapter/ \
  instances/bi-finance/data/hermes/plugins/hermes-sqlbot-adapter/
```

## 30.3 更新实例

```bash
bash expert-templates/bi-strategic-office/bin/update.sh \
  --profile bi-finance \
  --instance-dir instances/bi-finance \
  --data-dir instances/bi-finance/data/hermes \
  --repo-root "$PWD"
```

然后：

```bash
bash scripts/sync-runtime-env.sh bi-finance
bash scripts/up-instance.sh bi-finance
```

## 30.4 验证

```bash
docker exec hermes-bi-finance hermes plugins list
docker exec hermes-bi-finance hermes tools --summary
```

预期：

```text
hermes-sqlbot-adapter
Finance-Bi
finance_bi_ask
finance_bi_followup
finance_bi_explain
finance_bi_reset
```

---

# 31. 回滚方案

更新前备份：

```text
instances/bi-finance/data/hermes/plugins/
instances/bi-finance/data/hermes/sqlbot-adapter/state/
instances/bi-finance/data/hermes/config.yaml
instances/bi-finance/data/hermes/.env
```

回滚步骤：

1. 停止 `hermes-bi-finance`；
2. 恢复 v1.11.0 Plugin；
3. 恢复 SQLite 备份；
4. 恢复 `package-state.yaml`；
5. 重新启动实例；
6. 执行 `hermes plugins list`；
7. 执行 `hermes tools --summary`。

Hotfix 不修改 SQLBot，因此 SQLBot 不需要回滚。

---

# 32. 验收标准

## Adapter 验收

* MCP initialize 成功；
* MCP ping 成功；
* `mcp_start` 成功；
* Token 不进入日志；
* `chat_id` 正确保存；
* 多 Session 不串话；
* `finance_bi_ask` 可调用；
* `finance_bi_followup` 复用同一上下文；
* `finance_bi_explain` 不重复查询；
* `finance_bi_reset` 删除映射；
* Handler 全部返回 JSON 字符串；
* AnyIO 生命周期错误不再出现；
* `tools/list` 异常不阻断业务；
* SQLBot 错误可分类；
* `DetachedInstanceError` 映射为 `SQLBOT_DATASOURCE_SESSION_ERROR`；
* 完整 traceback 不返回给用户；
* 明确过滤条件丢失时拒绝返回；
* 非只读 SQL 被拒绝。

## 生产问数验收

以下条件满足后才允许开放：

* SQLBot Web 页面 SQL 执行正常；
* SQLBot MCP SQL 执行正常；
* 10 条基础问题通过；
* 10 条精确编号查询通过；
* 10 条连续追问通过；
* 行列权限通过；
* 数据源只读权限通过；
* 无 `DetachedInstanceError`；
* 无跨 Session 串话。

---

# 33. 完成标准

以下项目全部完成，Hotfix 才可合并：

1. 专家包版本升级至 `1.11.1`；
2. 正式 Adapter 使用唯一 MCP Client；
3. SSE 生命周期修复；
4. 业务调用不依赖 `list_tools()`；
5. 固定工具调用完成；
6. Session Store 完成；
7. Token 加密完成；
8. 四个 Handler 完成；
9. 错误分类完成；
10. SQLBot 嵌套错误解析完成；
11. Query Guard 完成；
12. Result Guard 完成；
13. Audit 完成；
14. Doctor 完成；
15. 单元测试通过；
16. Mock MCP 测试通过；
17. 容器部署测试通过；
18. `finance_bi_ask` 可返回正常结果或标准错误；
19. SQLBot 源码未修改；
20. Hermes Agent 核心未修改；
21. 生产凭证未提交到 Git。
