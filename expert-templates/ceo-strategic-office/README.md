# ceo-strategic-office

CEO 战略办公室专家团队：1 个容器 + 1 个 root 首席幕僚 + 7 个命名顾问 Profile + Hermes Kanban + Agency Agents 动态专家池。

`SOUL.md` / `AGENTS.md` / `SKILL.md`（含 root、profiles、skills、plugins）说明正文为简体中文（Profile ID、工具名等标识可英文）。

PRD：[`prd/v1.8_strategic-office-team-design.md`](../../prd/v1.8_strategic-office-team-design.md)

## 团队结构

| 角色 | Profile ID | 类型 |
|------|------------|------|
| 首席幕僚（root，面向 CEO） | `default` | orchestrator |
| 战略与投资 | `strategy-investment` | permanent-advisor |
| 商业与市场情报 | `commercial-market-intelligence` | permanent-advisor |
| 财务与董事会治理 | `finance-board-governance` | permanent-advisor |
| 运营与供应链风险 | `operations-supply-risk` | permanent-advisor |
| 技术与研发/AI | `technology-rd-ai` | permanent-advisor |
| 战略红队 | `strategy-red-team` | review-gate |
| 合规与证据 | `compliance-evidence` | review-gate |

编排引擎：Hermes Kanban（`ceo-strategic-office` 看板）。动态专家池：Agency Agents（`agency-agents-router` 插件，ephemeral 模式）。

## 模板结构

```text
expert-templates/ceo-strategic-office/
├── team.yaml
├── root/                    # 首席幕僚 SOUL / config / memories
├── profiles/                # 7 个命名顾问
├── shared/                  # 团队共享上下文（COMPANY.md, GOVERNANCE.md 等）
├── skills/                  # ceo-team-orchestrator, executive-decision-brief 等
└── plugins/agency-agents-router/
```

## 创建与注入

```bash
# 创建实例（WebUI 9600，Gateway 29600）
bash scripts/create-instance.sh ceo-office 9600 ceo-strategic-office
bash scripts/up-instance.sh ceo-office

# 团队注入（检测到 team.yaml 时 inject-expert.sh 自动转调 inject-expert-team.sh）
bash scripts/inject-expert-team.sh ceo-office ceo-strategic-office
# 或：
bash scripts/inject-expert.sh ceo-office ceo-strategic-office

bash scripts/restart-instance.sh ceo-office
```

## 健康检查

```bash
bash scripts/check-expert-team.sh ceo-office ceo-strategic-office
```

## 访问

```text
WebUI:  http://服务器IP:9600
API:    http://服务器IP:29600
```

查看密码：

```bash
grep HERMES_WEBUI_PASSWORD instances/ceo-office/.env
```

## 运行时目录

```text
instances/ceo-office/data/hermes/
├── team.yaml
├── team-shared/             # 只读共享上下文
├── profiles/                # 7 个命名顾问各自 HERMES_HOME
│   ├── strategy-investment/
│   ├── commercial-market-intelligence/
│   └── ...
└── SOUL.md                  # root 首席幕僚
```

## 测试

```bash
python -m pytest tests/test_team_manifest.py tests/test_patch_config_runtime.py \
  tests/test_inject_expert_team.py tests/test_ceo_team_workflows.py -q
```

## 约束

- 仅 root 首席幕僚面向 CEO（WebUI/Gateway）。
- D3/D4 决策须经过 `strategy-red-team` 与 `compliance-evidence` 审阅。
- 禁止执行保留动作（投资承诺、对外消息、合同、法律结论、人事决策、EBS 写入等）。


## Expert Factory（v2.0）

本团队模板已迁移至 `workcopilot.expert.v1`（`runtime.mode: team`）。

```bash
bash scripts/expert/expert validate expert-templates/ceo-strategic-office --level full
bash scripts/expert/expert evaluate expert-templates/ceo-strategic-office --mode static
bash scripts/inject-expert-team.sh <instance> ceo-strategic-office
```
