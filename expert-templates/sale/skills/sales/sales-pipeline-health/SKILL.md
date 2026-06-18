---
name: sales-pipeline-health
description: 分析 pipeline 表、CRM 导出、销售漏斗、预测与主管复盘。识别 stalled、underqualified、single-threaded 商机。
version: 1.0.0
metadata:
  hermes:
    tags: [sale, pipeline, forecast, coaching, obsidian, hindsight]
    category: sales
---

# sales-pipeline-health

## 使用时机

用户上传 pipeline 表、CRM 导出、销售漏斗数据，要求分析预测、风险、主管复盘、pipeline health。

## 输出结构

1. 数据质量检查（缺失字段、过期更新、阶段定义不一致）。
2. Pipeline velocity 与 coverage ratio。
3. Stalled deals（停滞原因、建议干预）。
4. Underqualified deals。
5. Single-threaded deals。
6. Forecast 分类：Commit / Best Case / Upside（区间或分类，非单一预测值）。
7. 干预建议清单（Owner、优先级、截止日期）。
8. 数据不足时的 caveat。

## 输出约束

- 数据不足必须明确标记，不强行预测。
- 不输出单一预测值；必须给区间或分类。
- 不接受「感觉很好」的商机判断。
- 过期未更新商机标红。
- 原始 pipeline 文件应在 `/data/hermes/workspace/materials/sale/`。
- 分析报告保存：`/data/hermes/workspace/reports/sale/pipeline/`。
- 可复用的 pipeline review 口径写入 Hindsight。
