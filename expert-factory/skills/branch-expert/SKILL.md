---
schema_version: workcopilot.skill.v1
id: branch-expert
name: Branch Expert
version: 1.0.0
kind: procedural
description: >
  对 Expert Source 创建 Copy-on-Write 资产分支，支持 status/diff/rebase/materialize。
triggers:
  - branch expert
  - 专家分支
  - rebase expert
---

# 技能目标

实现 Expert Asset Branch（非 Git Branch），只保存 overlay 变更。

# 适用条件

需要在公共模板之上做部门定制，并希望后续能同步上游升级。

# 前置检查

- 源专家为 workcopilot.expert.v1
- 无未解决 conflict 时可 materialize / build / publish

# 执行流程

1. `expert branch create <source> --name <id> --target-id <id>`
2. 在 `.workcopilot/branches/<expert>/<branch>/overlay/` 放入变更文件
3. `expert branch status|diff`
4. 上游更新后 `expert branch rebase --onto <source>`
5. `expert branch materialize --output expert-templates/<id>`

# 工具调用规则

仅通过 `scripts/expert/expert branch` / Python CLI 执行；禁止手改 instances/。

# 输出要求

- branch.yaml 符合 workcopilot.expert-branch.v1
- reports/diff.md 与 conflict-report.md（如有）

# 异常处理

冲突未解决时禁止 build/publish；权限相关字段冲突禁止自动合并。

# 禁止事项

- 不复制完整源目录作为分支存储
- 不扩大权限除非显式允许

# 引用资料

- prd/v2.1_expert-factory.md §12
