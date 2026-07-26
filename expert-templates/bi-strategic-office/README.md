# bi-strategic-office（专家包 v1.11.1）

财务经营分析办公室（BI 智能问数）：Hermes 通过 `hermes-sqlbot-adapter` 以 **MCP SSE** 调用外部 **SQLBot** 取数；SQLBot 负责 Text-to-SQL / 执行 / 图表，Hermes 负责经营分析与报告。进程内插件，**不**注册原始 SQL Tool，**不**修改 SQLBot 源码。

> **v1.11.1 hotfix**：官方 MCP SSE Client、会话 Token Fernet 加密、错误分类（含 Datasource Session）、Doctor `--deep`。后续修改只允许进入本目录。

- **业务使用指南**：[GUIDE.md](GUIDE.md)
- **架构 / 安装 / SQLBot 集成**：[docs/architecture.md](docs/architecture.md) · [docs/installation.md](docs/installation.md) · [docs/sqlbot-integration.md](docs/sqlbot-integration.md)
- **SQLBot 实施记录模板**：[docs/sqlbot-example.md](docs/sqlbot-example.md)
- **PRD**：[prd/bi-strategic-office-prd-v1.11.md](prd/bi-strategic-office-prd-v1.11.md) · [prd/bi-strategic-office-prd-v1.11.1_hotfix.md](prd/bi-strategic-office-prd-v1.11.1_hotfix.md)

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

模型不可见：SQLBot 用户名、密码、`access_token`、`chat_id`、加密密钥。

## 创建与启动

```bash
# 校验专家包
bash expert-templates/bi-strategic-office/bin/validate.sh
bash expert-templates/bi-strategic-office/bin/doctor.sh --package-only

# 创建实例
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office

# 配置 SQLBOT_*（含 SQLBOT_SESSION_ENCRYPTION_KEY）后启动
bash scripts/sync-runtime-env.sh <profile>
bash scripts/up-instance.sh <profile>

# 深度探活（会 mcp_start，可能创建 chat）
bash expert-templates/bi-strategic-office/bin/doctor.sh --profile <profile> --deep
```

`install.sh` 会创建 `sqlbot-adapter/state|audit`、初始化 SQLite schema v2，并写 `package-state.yaml`。
