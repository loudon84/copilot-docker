# 架构说明（v1.11 专家包）

## 目标

`bi-strategic-office` 通过轻量 Adapter 接入外部 SQLBot，Hermes 负责分析，SQLBot 负责问数。

```text
用户
  │
  ▼
Hermes WebUI / Agent API
  │
  ▼
bi-strategic-office
  ├── SOUL.md / Skills
  └── hermes-sqlbot-adapter  ──MCP──►  SQLBot  ──► 只读 BI 数据源
```

## 专家包结构

```text
expert-templates/bi-strategic-office/
├── expert.yaml          # 包清单（1.11.0）
├── VERSION
├── runtime/             # SOUL / skills / config.patch
├── plugins/             # hermes-sqlbot-adapter
├── config/              # sqlbot.example.env
├── evaluations/
├── bin/                 # install / post-start / update / validate / doctor / test
├── lib/
├── tests/
├── docs/
└── prd/
```

## 职责边界

| 组件 | 职责 |
|------|------|
| Hermes + Skills | 理解问题、编排分析、生成管理报告、附件分析 |
| hermes-sqlbot-adapter | MCP 连接、登录/Token、chat_id 映射、SQL 只读与过滤保护、结果标准化、审计 |
| SQLBot | 数据源/表字段/关系/术语/SQL 示例、Text-to-SQL、执行、图表、行列权限 |

## 生命周期

```text
create-instance.sh
  └─ expert.yaml + bin/install.sh → 安装 Adapter / skills / 合并配置

up-instance.sh
  └─ 容器启动后 → bin/post-start.sh（pip / 启用插件 / MCP 探测 / doctor）
```

公共脚本只做「识别 + 调用」，不含 SQLBot 专属逻辑。

## 实例落盘

```text
instances/<profile>/data/hermes/
├── SOUL.md / config.yaml / skills/
├── plugins/hermes-sqlbot-adapter/
├── sqlbot-adapter/
│   ├── state/sqlbot_sessions.db
│   ├── audit/
│   └── package-state.yaml
└── workspace/exports/bi/
```

## 安全

- 模型只看到 `finance-bi` 四工具
- 禁止暴露 SQLBot 密码 / Token / chat_id
- SQL 只读校验 + 显式标识符保留 + 明细过滤约束 + 行数截断
- 旧插件 `hermes-finance-bi-plugin` 不得同时启用
