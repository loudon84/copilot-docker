# 故障排查（v1.11）

## 插件未加载

症状：`hermes plugins list` 无 `hermes-sqlbot-adapter`

检查：

1. `instances/<p>/data/hermes/plugins/hermes-sqlbot-adapter/plugin.yaml` 是否存在
2. `config.yaml` 的 `plugins.enabled` 是否包含 `hermes-sqlbot-adapter`
3. 是否仍启用 `hermes-finance-bi-plugin`（必须移除）
4. 重新执行 `bin/post-start.sh` / `up-instance.sh`

## SQLBOT_NOT_CONFIGURED

检查 `.env` 是否具备：

- `SQLBOT_MCP_URL`
- `SQLBOT_USERNAME`
- `SQLBOT_PASSWORD`
- `SQLBOT_WORKSPACE_ID`
- `SQLBOT_DEFAULT_DATASOURCE_ID`

然后：

```bash
bash scripts/sync-runtime-env.sh <profile>
```

## SQLBOT_UNAVAILABLE / 登录失败

1. 从宿主机或容器探测 MCP URL（勿打印密码）
2. 确认 SQLBot 服务健康、网络可达
3. 确认用户名/密码/工作空间 ID 正确
4. 检查 `SQLBOT_VERIFY_SSL`（内网自签证书可临时 `false`，仅限受控环境）

## QUERY_CONTEXT_NOT_FOUND

含义：当前 Hermes 会话尚无 SQLBot 对话。

处理：先 `finance_bi_ask`，或确认未误调 `finance_bi_reset`。

## FILTER_NOT_PRESERVED

含义：用户明确编号未进入生成 SQL，Adapter 已阻断返回。

处理：

1. 在 SQLBot 补充术语与 SQL 示例
2. 改写问题，显式写出 `凭证号 XXX` / `ar_trx_number=XXX`
3. 用 `finance_bi_explain` 查看最近 SQL（若有）

## DETAIL_QUERY_REQUIRES_FILTER

明细查询缺少精确编号、日期范围、客户或主体。补充过滤后再问。

## doctor 失败但容器仍在运行

符合 v1.11 设计：SQLBot 不可用不回退旧插件。按 doctor 输出修复 `SQLBOT_*` 后重跑 post-start。

## 仍看到旧插件

```bash
# 实例内应不存在
ls instances/<p>/data/hermes/plugins/
# 重新 install / update
bash expert-templates/bi-strategic-office/bin/update.sh ...
```
