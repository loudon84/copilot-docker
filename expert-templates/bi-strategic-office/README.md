# bi-strategic-office（专家包 v1.11）

财务经营分析办公室（BI 智能问数）：Hermes 通过 `hermes-sqlbot-adapter` 调用外部 **SQLBot**（MCP）取数；SQLBot 负责 Text-to-SQL / 执行 / 图表，Hermes 负责经营分析与报告。进程内插件，**不**注册原始 SQL Tool，**不**修改 SQLBot 源码。

> **v1.11**：以 SQLBot MCP 替换自研问数核心（原 `hermes-finance-bi-plugin`）。后续修改只允许进入本目录（含 `runtime/`、`plugins/`、`bin/`）。

- **业务使用指南**：[GUIDE.md](GUIDE.md)
- **架构 / 安装 / SQLBot 集成**：[docs/architecture.md](docs/architecture.md) · [docs/installation.md](docs/installation.md) · [docs/sqlbot-integration.md](docs/sqlbot-integration.md)
- **SQLBot 实施记录模板**：[docs/sqlbot-example.md](docs/sqlbot-example.md)
- **PRD**：[prd/bi-strategic-office-prd-v1.11.md](prd/bi-strategic-office-prd-v1.11.md)

## 能力边界

| 专家 | 职责 |
|------|------|
| `finance` | 账户、账龄、回款、头寸、资金计划、财务运营 |
| `bi-strategic-office` | BI 取数（经 SQLBot）、经营分析、产品/客户/区域利润、同比环比、指标口径、管理报告 |

## 专家包结构

```text
expert-templates/bi-strategic-office/
├── expert.yaml / VERSION / CHANGELOG.md
├── runtime/
│   ├── SOUL.md
│   ├── config.patch.yaml
│   ├── memories/MEMORY.md
│   └── skills/                 # 编排 / 问数 / SQLBot 复核 / 分析 / 报告
├── plugins/hermes-sqlbot-adapter/
├── config/sqlbot.example.env
├── evaluations/
├── bin/                        # install / post-start / update / validate / doctor / test
├── lib/
├── tests/
├── docs/
└── prd/
```

## 插件四工具

```text
finance_bi_ask
finance_bi_followup
finance_bi_explain
finance_bi_reset
```

模型不可见：SQLBot 用户名、密码、`access_token`、`chat_id`。

## 创建与启动

```bash
# 校验专家包
bash expert-templates/bi-strategic-office/bin/validate.sh
bash expert-templates/bi-strategic-office/bin/doctor.sh --package-only

# 创建实例
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office

# 配置 SQLBOT_* 后启动
bash scripts/up-instance.sh bi-strategic-office

# 诊断
bash expert-templates/bi-strategic-office/bin/doctor.sh \
  --profile bi-strategic-office \
  --data-dir instances/bi-strategic-office/data/hermes \
  --container hermes-bi-strategic-office
```

## 配置 SQLBot

编辑 `instances/<profile>/.env`（**勿提交真实密码**），参考 [config/sqlbot.example.env](config/sqlbot.example.env)：

```env
SQLBOT_MCP_URL=http://sqlbot-host:8001/mcp
SQLBOT_USERNAME=
SQLBOT_PASSWORD=
SQLBOT_WORKSPACE_ID=
SQLBOT_DEFAULT_DATASOURCE_ID=
SQLBOT_REQUEST_TIMEOUT_SECONDS=120
SQLBOT_SESSION_TTL_SECONDS=86400
SQLBOT_VERIFY_SSL=true
SQLBOT_MAX_RESULT_ROWS=500
SQLBOT_MODEL_RESULT_ROWS=100
SQLBOT_AUDIT_ENABLED=true
```

```bash
bash scripts/sync-runtime-env.sh <profile>
bash scripts/up-instance.sh <profile>
```

表、字段、关系、术语与 SQL 示例在 **SQLBot 管理界面**配置；完成后填写 [docs/sqlbot-example.md](docs/sqlbot-example.md)。

## 专家包测试

```bash
bash expert-templates/bi-strategic-office/bin/test.sh unit
bash expert-templates/bi-strategic-office/bin/test.sh security
bash expert-templates/bi-strategic-office/bin/test.sh all
```

## 运行时目录

```text
instances/<profile>/
├── .env
└── data/hermes/
    ├── SOUL.md / config.yaml / skills/
    ├── plugins/hermes-sqlbot-adapter/
    ├── sqlbot-adapter/
    │   ├── state/sqlbot_sessions.db
    │   ├── audit/
    │   └── package-state.yaml
    └── workspace/exports/bi/
```

## 安全约束

- 禁止向 Hermes 注册 `execute_sql` / `run_raw_sql` / `query_database`
- Adapter 对 SQLBot 返回 SQL 做只读 AST 校验；显式编号未保留则阻断
- 明细查询必须有有效过滤；超大结果截断后再交给模型
- 审计不保存完整结果集、密码与 Token
- 专家包内禁止包含 `.env`、真实凭证、运行状态数据库
- 不得与旧插件 `hermes-finance-bi-plugin` 同时启用
