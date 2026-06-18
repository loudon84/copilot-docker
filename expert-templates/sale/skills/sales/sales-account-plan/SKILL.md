---
name: sales-account-plan
description: 客户经营计划、QBR、客户复盘、续费扩展、客户地图、stakeholder mapping、Mutual Action Plan。
version: 1.0.0
metadata:
  hermes:
    tags: [sale, account-management, qbr, expansion, obsidian, hindsight]
    category: sales
---

# sales-account-plan

## 使用时机

用户要求做客户经营计划、QBR、客户复盘、续费扩展、客户地图、account plan、客户健康分析。

## 输出结构

1. Account overview（行业、合作状态、采购规模、健康状态）。
2. Stakeholder map（姓名、职位、角色、影响力、态度、最近联系、下一步）。
3. Account health（Green / Yellow / Red + 依据）。
4. Whitespace（机会、依据、客户价值、风险、下一步）。
5. Expansion hypothesis。
6. Churn risk 与 save plan。
7. Mutual action plan（动作、我方 Owner、客户 Owner、截止日期、状态）。
8. QBR agenda。

## 输出约束

- 红色健康客户不得直接跑扩展动作；优先 stabilize / save plan。
- 单线程客户必须标为高风险。
- 所有扩展建议从客户价值角度表达，不强行推销。
- 不编造年采购额、合作历史、客户满意度。
- 输出保存：`/data/hermes/workspace/reports/sale/account-plan/`。
- 审核后的 account playbook 写入 `/data/hermes/obsidian-vault/60-Reports/Sales/Account/`。
