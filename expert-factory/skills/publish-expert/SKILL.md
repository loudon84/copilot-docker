---
schema_version: workcopilot.skill.v1
id: publish-expert
name: Publish Expert
version: 1.0.0
kind: procedural
description: >
  将 Release Expert Bundle 发布到 Nacos AI Registry（AgentSpec + Skills）。
triggers:
  - publish expert
  - 发布专家
  - nacos publish
---

# 技能目标

把不可变 Expert Bundle 映射为 Nacos AgentSpec / Skill 并完成 draft→review→online。

# 适用条件

已有通过校验与评测的 Release Bundle（dev=false）。

# 前置检查

- Bundle 通过 `expert validate --level release`
- 签名策略满足环境要求
- Nacos 凭证仅来自环境变量

# 执行流程

1. `expert publish <bundle> --target nacos-dev --stage draft`
2. `--stage review --wait` 提交审核
3. `--stage online --update-latest --wait` 上线
4. 失败时 `expert publish resume <publish-record.json>`

# 工具调用规则

- 使用 `scripts/expert/expert publish`
- 敏感配置只用 NACOS_USERNAME / NACOS_PASSWORD / NACOS_ACCESS_TOKEN

# 输出要求

- Publish Record（workcopilot.publish-record.v1）
- 回读 AgentSpec / Skill 状态

# 异常处理

同版本不同摘要 → E_PUBLISH_VERSION_CONFLICT；部分失败可 resume。

# 禁止事项

- 不把 .expert.bundle 当普通 Config 写入配置中心
- 不在日志中输出 Token/密码
- 不用 --force 覆盖 online 版本

# 引用资料

- prd/v2.1_expert-factory.md §16
