# 故障排查（v1.11.1）

## 插件未加载

症状：`hermes plugins list` 无 `hermes-sqlbot-adapter`

检查：

1. `instances/<p>/data/hermes/plugins/hermes-sqlbot-adapter/plugin.yaml` 是否存在
2. `config.yaml` 的 `plugins.enabled` 是否包含 `hermes-sqlbot-adapter`
3. 是否仍启用 `hermes-finance-bi-plugin`（必须移除）
4. 重新执行 `bin/post-start.sh` / `up-instance.sh`

## sqlbot-adapter 目录缺失

症状：无 `state/`、`audit/`、`package-state.yaml`

原因：未走专家包 `bin/install.sh`（或 install 未执行成功）。

处理：

```bash
bash expert-templates/bi-strategic-office/bin/install.sh \
  --profile <p> --instance-dir ... --data-dir ... --repo-root ...
```

确认 `install.sh` 对 `create-instance` 可执行（`-x`）。

## SQLBOT_NOT_CONFIGURED

检查 `.env` 是否具备：

- `SQLBOT_MCP_URL`
- `SQLBOT_USERNAME`
- `SQLBOT_PASSWORD`
- `SQLBOT_WORKSPACE_ID`
- `SQLBOT_DEFAULT_DATASOURCE_ID`
- `SQLBOT_SESSION_ENCRYPTION_KEY`（v1.11.1 必填）

然后：

```bash
bash scripts/sync-runtime-env.sh <profile>
```

## SQLBOT_TRANSPORT_ERROR / SQLBOT_INITIALIZE_FAILED

1. 确认 MCP URL 为 SSE 端点且网络可达
2. Doctor 默认可区分网络 vs initialize
3. 确认容器内 `mcp==1.26.0`

## SQLBOT_AUTH_FAILED

用户名/密码/工作空间错误。用 `--deep` 验证 `mcp_start`（勿在日志打印 Token）。

## SQLBOT_DATASOURCE_SESSION_ERROR

SQLBot 已生成 SQL，但数据源侧会话失效（常见 `DetachedInstanceError`）。Adapter 会保留 Hermes↔SQLBot 映射；需在 SQLBot 侧修复数据源会话，或换数据源后重试。完整 traceback 仅在审计中。

## RESULT_TOO_LARGE

返回行数超过 `SQLBOT_MAX_RESULT_ROWS`（默认 500）。收紧过滤条件后再问。

## QUERY_CONTEXT_NOT_FOUND

当前 Hermes 会话尚无 SQLBot 对话。先 `finance_bi_ask`，或确认未误调 `finance_bi_reset`。

## FILTER_NOT_PRESERVED

用户明确编号未进入生成 SQL，Adapter 已阻断返回。在 SQLBot 补充术语/SQL 示例，或改写问题。

## doctor 失败但容器仍在运行

符合设计：SQLBot 不可用不回退旧插件。按 doctor 输出修复 `SQLBOT_*` 后重跑 post-start。深度检查：

```bash
bash expert-templates/bi-strategic-office/bin/doctor.sh --profile <p> --deep
```

## 仍看到旧插件 / 重复 MCP 脚本

实例内不应存在 `hermes-finance-bi-plugin`；包内不应存在 `memories/test_sqlbot.py`。正式直连测试用：

```text
plugins/hermes-sqlbot-adapter/scripts/direct_flow_test.py
```
