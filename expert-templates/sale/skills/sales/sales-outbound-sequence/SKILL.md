---
name: sales-outbound-sequence
description: 开发客户、写销售邮件、外呼脚本、多触点 sequence、针对某客户的触达计划。邮件为草稿，不直接发送。
version: 1.0.0
metadata:
  hermes:
    tags: [sale, outbound, email, icp, sequence, obsidian, hindsight]
    category: sales
---

# sales-outbound-sequence

## 使用时机

用户要求开发客户、写销售邮件、做外呼脚本、生成多触点 sequence、针对某客户做触达计划、outbound。

## 输出结构

1. ICP 判断与 account tiering。
2. 触发信号（signal-based outbound）。
3. 目标联系人与角色假设。
4. 邮件主题选项。
5. 第一封邮件草稿（标记：草稿，发送前需人工确认）。
6. 后续 5–8 个触点（邮件 / 电话 / LinkedIn / 微信 / 短信）。
7. 电话开场与 voicemail 脚本。
8. 发送前检查项（客户姓名、公司、产品需求、合规、退订）。

## 输出约束

- 不生成垃圾群发文案；必须有具体触达理由。
- 所有 customer-facing 内容标记为草稿，不直接发送。
- 尊重退订和拒绝；不承诺价格、库存、交期。
- 不编造客户案例或合作关系。
- 输出保存：`/data/hermes/workspace/drafts/sale/outbound/`。
- 可复用的 sequence 模板、行业开场话术（审核后）写入 Obsidian。
