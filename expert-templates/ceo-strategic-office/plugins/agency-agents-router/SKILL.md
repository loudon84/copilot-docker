---
name: agency-agents-router
description: 搜索/查看/加载内置 Agency Agents，并通过 delegate_task 临时运行。
---

# agency-agents-router

## 命令

```bash
python plugins/agency-agents-router/router.py search "<query>"
python plugins/agency-agents-router/router.py view <agent_id>
python plugins/agency-agents-router/router.py load-prompt <agent_id>
```

## 隔离规则

- 仅临时使用 — 不形成常驻 Profile 身份
- 最小任务上下文 — 不含凭证 / 不受限内部数据
- 禁止写入 `/data/hermes/team-shared` 或其他 Profile 的记忆
- 失败时：向调用方返回错误；调用方可收窄重试、另选 agent，或在明确披露缺失视角后继续
