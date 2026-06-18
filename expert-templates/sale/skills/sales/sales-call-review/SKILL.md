---
name: sales-call-review
description: 复盘电话记录、会议纪要、销售聊天记录，提供销售辅导与 CRM 更新建议。聚焦 1–3 个改进点。
version: 1.0.0
metadata:
  hermes:
    tags: [sale, coaching, call-review, crm, hindsight]
    category: sales
---

# sales-call-review

## 使用时机

用户提供电话记录、会议纪要、销售聊天记录，要求复盘、辅导、call review、通话改进建议。

## 输出结构

1. What went well（基于具体语句）。
2. Missed signals（未追问的信号、未确认的假设）。
3. Discovery depth 评估。
4. Objection handling 评估。
5. Next step quality（是否具体、有 Owner、有截止时间）。
6. Coaching points（每次仅 1–3 个最高价值改进点）。
7. 下次通话建议与可执行练习。
8. CRM 更新字段建议。

## 输出约束

- 基于具体语句和行为反馈，不做人身评价。
- 每次只聚焦 1–3 个最高价值改进点。
- 输出可执行的练习动作，而非空泛批评。
- 不编造通话中未出现的内容。
- 输出保存：`/data/hermes/workspace/reports/sale/coaching/`。
- 可复用的 coaching 模式、常见失误模式写入 Hindsight。
