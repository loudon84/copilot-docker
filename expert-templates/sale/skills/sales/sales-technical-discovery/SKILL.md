---
name: sales-technical-discovery
description: 售前技术问题、产品规格确认、Demo 计划、POC 范围、技术异议处理。替代料需 FAE/工程确认。
version: 1.0.0
metadata:
  hermes:
    tags: [sale, pre-sales, demo, poc, technical, obsidian, hindsight]
    category: sales
---

# sales-technical-discovery

## 使用时机

用户要求售前技术问题、产品规格确认、Demo 计划、POC 范围、技术异议处理、BOM/RFQ 技术澄清。

## 输出结构

1. 技术环境与约束问题清单。
2. 需求与限制（应用、封装、温度、供电、接口、认证、用量、交期）。
3. Demo narrative（演示目标、场景、成功标准）。
4. POC scope 与 pass/fail criteria。
5. 技术风险与竞品技术定位。
6. 需要 FAE / 产品 / 采购 / 工程确认的问题清单。
7. Fact-Impact-Act 式技术异议回应草稿。

## 输出约束

- 技术回答必须可追溯到规格书、产品资料或已知事实。
- 替代料建议必须标记为「需 FAE/工程确认」，不直接确认等价性。
- POC 必须有明确的 pass/fail criteria。
- 不做未验证的技术承诺；不编造认证、参数、兼容性。
- 参数不全时先输出澄清清单，不直接推荐具体型号。
- 输出保存：`/data/hermes/workspace/reports/sale/technical/` 或 `/data/hermes/workspace/drafts/sale/`。
- 审核后的技术 battlecard 写入 Obsidian `80-Product-Spec` 或 `60-Reports/Sales`。
