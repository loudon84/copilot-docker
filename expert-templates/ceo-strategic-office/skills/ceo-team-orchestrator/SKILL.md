---
name: ceo-team-orchestrator
description: 按决策等级 D0–D4 路由 CEO 请求，创建最小必要的 Kanban 顾问任务，并汇总保留异议的简报。
---

# ceo-team-orchestrator

## 何时使用

CEO 战略办公室中需要常驻顾问或审阅门禁的请求。

## 决策等级

| 等级 | 含义 | 最低路由 |
|------|------|----------|
| D0 | 信息检索 / 摘要 | root；可选动态专家 |
| D1 | 可逆的运营建议 | root + 1 名常驻顾问 |
| D2 | 跨职能 / 预算 / 组合 | root + 2+ 顾问；涉敏则加合规 |
| D3 | 董事会 / 上市公司 / 重大投资 / 并购 / 监管 | 顾问 + strategy-red-team + compliance-evidence |
| D4 | 法务 / 人事 / 披露 / 合同 / 对外承诺 | 仅分析；须人工决策 |

禁止为绕过审阅门禁而降级请求。不确定时上调等级。

## 协作

- 跨常驻 Profile 的工作**必须**使用 Hermes Kanban（禁止匿名 `delegate_task`）。
- Agency Agents / `delegate_task` 仅用于短寿命临时任务。
- 保留异议；禁止制造虚假共识。
