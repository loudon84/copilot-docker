# Changelog

## 1.11.1

- Hotfix：MCP Client 改为官方 `mcp==1.26.0` SSE + `ClientSession`（废弃 httpx JSON-RPC 伪实现）
- 固定工具名 `mcp_start` / `mcp_question` / `mcp_ws_list` / `mcp_datasource_list`；业务路径不依赖 `list_tools()`
- 新增 `AsyncBridge`、`result_parser`、错误码 `SQLBOT_DATASOURCE_SESSION_ERROR`（含 `DetachedInstanceError`）
- Session Store schema v2：Fernet 加密 Token（必填 `SQLBOT_SESSION_ENCRYPTION_KEY`，禁止明文回退）
- 运行时上下文自 Hermes 注入；模型不可传 session/user/token/chat_id
- Result Guard：超过硬上限 500 行返回 `RESULT_TOO_LARGE`
- `install.sh` 幂等建目录并执行 `init_state.py`；Doctor 默认 initialize/ping，`--deep` 才登录
- 删除重复 `memories/test_sqlbot.py`；正式入口为插件 `scripts/direct_flow_test.py`

## 1.11.0

- 以 `hermes-sqlbot-adapter` 替换自研 `hermes-finance-bi-plugin`
- 问数后端改为外部 SQLBot（MCP）；不再直连 BI 库、不再维护本地 Semantic Catalog
- 工具收敛为四工具：`finance_bi_ask` / `finance_bi_followup` / `finance_bi_explain` / `finance_bi_reset`
- 新增 Session Store（Hermes session ↔ SQLBot chat_id）、查询保护与结果标准化
- 环境变量改为 `SQLBOT_*`；新增 `config/sqlbot.example.env` 与 `docs/sqlbot-example.md`
- Skills：新增 `sqlbot-query-review`；更新问数/编排/分析说明；移除 `semantic-governance`
- 生命周期脚本与 doctor/validate 全面切换到 Adapter 检查项
- 新增 evaluations Golden Questions；补充单元/安全/部署测试

## 1.10.0

- 将 Finance BI Plugin 归入专家包 `plugins/hermes-finance-bi-plugin/`
- 将 Semantic Catalog 归入专家包 `runtime/semantic/`
- 将 Policies、Skills、SOUL、MEMORY 归入 `runtime/`
- 将专家专属测试归入专家包 `tests/`
- 增加专家包安装和启动后生命周期（`bin/install.sh`、`bin/post-start.sh` 等）
- `create-instance.sh` 支持新专家包识别与 `bin/install.sh` 调用
- `up-instance.sh` 支持专家启动后初始化（`bin/post-start.sh`）
- 新增 `expert.yaml` / `VERSION` / `package-state.yaml` 统一版本管理
- 过渡期保留旧目录副本与公共 BI 脚本，不删除；新流程不再依赖公共 BI 专属脚本
