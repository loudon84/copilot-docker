---
name: finance-bi-query
description: 自然语言财务经营问数、筛选与下钻。
version: 1.1.0
metadata:
  hermes:
    tags: [bi, query]
    category: finance-bi
---

# finance-bi-query

## 工具选择

1. **目录/字段探查**（「有哪些数据集」「日期字段」）  
   用 `finance_bi_catalog_search` 或 `finance_bi_explain(topic=...)`，**不要**用 ask 去跑汇总。  
   - 日期字段：`kind=date_fields` 或 query 含「日期」  
   - 销售利润报表：`query=销售利润报表`

2. **取数**  
   用 `finance_bi_ask`。后续筛选/下钻用 `finance_bi_followup(base_query_id=...)`。  
   - 按客户：`客户 天地偉業技術有限公司 交易明细，返回 10 条`  
   - **禁止**用 terminal / Docker 沙箱 / 手工 SQL 查库。  
   - **`FINANCE_BI_ALLOWED_ENTITIES`**：OU 主体白名单，填 `ou_code`（如 `101,104`）。  
     为空只表示不做 OU 裁剪，**不影响** `customer_name` 过滤。  
     填 `HK01` 无效（本表没有该值）。

3. **口径解释**  
   用 `finance_bi_explain(metric=...)` 或 `topic=...`。

4. 正式报告前用 `finance_bi_validate_result`；导出用 `finance_bi_export_result`。

## 注意

- ask 若问题是「列出数据集/日期字段」，工具会返回 `mode=catalog_meta`（不查业务库）。
- 生产主数据集是 `ebs1_cux_ar_gp_details`；`product_profit_daily` 为 demo，默认不参与检索。
- `finance_bi_catalog_search`：检索词放在 `query`（如 `query=毛利`）；`kind` 只能是 all/datasets/metrics/dimensions/date_fields，**禁止**把「毛利」写进 kind。
- 不得修改工具返回的数字。
