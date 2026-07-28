---
name: create-expert
description: >
  根据业务 Brief 创建 WorkCopilot 专家源码（Discovery → Plan → Scaffold）。
  确定性脚手架与校验由 CLI 执行；正文与业务设计由 Agent 补全。
version: 2.0.0
---

# create-expert（Factory Skill）

## 目标

创建符合 `workcopilot.expert.v1` / `workcopilot.skill.v1` 的专家源码目录。

## 流程

1. **Discovery**：整理业务目标、用户、场景、系统集成、权限边界 → `expert-brief.yaml`
2. **Component Planning**：列出要创建/复用/不创建的组件 → `expert-plan.yaml`
3. **Scaffold**：调用 CLI 生成目录骨架
4. **Content**：按协议补全 SOUL / Skill 正文（简体中文）
5. **Validate**：`structure` 级校验通过

## CLI

```bash
bash scripts/expert/expert create --brief <brief.yaml> --output expert-templates/<id>
bash scripts/expert/expert create --brief <brief.yaml> --plan-only
bash scripts/expert/expert validate expert-templates/<id> --level structure
```

## 强制规则

- 默认复用已有 Plugin/Tool；禁止重复造轮子
- 一个 Skill 一个职责；禁止循环依赖
- 外部系统只声明 Connector Slot；禁止 Secret 与生产地址
- 权限默认 deny；写操作必须显式声明
- 必须生成 `expert.yaml`、`evaluations/cases.yaml`、`README.md`
- 不直接修改 `instances/`

## 参考

- `references/protocol.md`
- `examples/brief.yaml`
