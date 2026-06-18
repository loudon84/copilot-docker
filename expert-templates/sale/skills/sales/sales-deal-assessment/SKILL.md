---
name: sales-deal-assessment
description: 判断商机、评估客户、复盘机会、MEDDPICC 评估、看这个单能不能成。输出评分、风险与下一步动作。
version: 1.0.0
metadata:
  hermes:
    tags: [sale, meddpicc, deal-strategy, pipeline, obsidian, hindsight]
    category: sales
---

# sales-deal-assessment

## 使用时机

用户要求判断商机、评估客户、复盘机会、做 MEDDPICC、看这个单能不能成、重点跟进决策。

## 输出结构

1. 结论（Green / Yellow / Red + Advance / Intervene / Nurture / Disqualify）。
2. 已知事实表（事实、来源、可信度）。
3. MEDDPICC 表（维度、状态、评分、证据、缺口、下一步）。
4. 交易风险表（风险、等级、影响、处理动作、Owner、Deadline）。
5. 竞争与 do-nothing 风险。
6. 下一步行动（含 Owner 与截止时间）。
7. 需要销售补充的信息清单。

## 评分标准

```text
0 = unknown
1 = weak
2 = partial
3 = acceptable
4 = strong
5 = validated
```

## 输出约束

- 不把“可能下单”“感觉不错”当成强机会。
- 单线程客户（仅一个联系人）必须标为高风险。
- Economic Buyer 或 Decision Process 缺失时不得建议 Advance。
- 不编造客户预算、采购意图、竞品报价。
- 输出保存：`/data/hermes/workspace/reports/sale/deals/`。
- 可复用的成交/失败模式写入 Hindsight；审核后 battlecard 写入 Obsidian。
