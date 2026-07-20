---
name: finance-bi-query
description: 自然语言财务经营问数、筛选与下钻。
version: 1.2.0
metadata:
  hermes:
    tags: [bi, query]
    category: finance-bi
---

# finance-bi-query

## 返回契约（强制）

所有 `finance_bi_*` **取数/目录/解释/校验**工具统一返回：

- `result_type=table`
- `columns` / `fields`（列定义）
- `rows`（数据行）
- `row_count`
- 口径与过滤等放在 `meta`（如 `totals`、`time_range`、`entity_scope`、`metric_versions`）

**工具只交付表格数据集，不负责最终呈现。**  
Markdown 表、摘要、经营结论、图表说明等，由本 skill / 编排 skill **按用户要求**基于 `rows` 转换输出；**不得改写工具返回的数字**。

`finance_bi_export_result` 例外：`result_type=export`，写入文件；路径在 `meta.path`。

## 工具选择

1. **目录/字段探查**（「有哪些数据集」「日期字段」）  
   用 `finance_bi_catalog_search` 或 `finance_bi_explain(topic=...)`，**不要**用 ask 去跑汇总。  
   - 日期字段：`kind=date_fields` 或 query 含「日期」  
   - 销售利润报表：`query=销售利润报表`  
   - 结果仍是表格行；完整分类可看 `meta.tables`

2. **取数**  
   用 `finance_bi_ask`。后续筛选/下钻用 `finance_bi_followup(base_query_id=...)`。  
   - 按客户：`客户 天地偉業技術有限公司 交易明细，返回 10 条`  
   - **禁止**用 terminal / Docker 沙箱 / 手工 SQL 查库。  
   - **`FINANCE_BI_ALLOWED_ENTITIES`**：OU 主体白名单，填 `ou_code`（如 `101,104`）。  
     为空只表示不做 OU 裁剪，**不影响** `customer_name` 过滤。  
     填 `HK01` 无效（本表没有该值）。

3. **口径解释**  
   用 `finance_bi_explain(metric=...)` 或 `topic=...`（返回表格行）。

4. 正式报告前用 `finance_bi_validate_result`；导出用 `finance_bi_export_result`。

## 注意

- ask 若问题是「列出数据集/日期字段」，返回目录表格（`result_kind` 以 `catalog_` 开头），不查业务库。
- 生产主数据集是 `ebs1_cux_ar_gp_details`；`product_profit_daily` 为 demo，默认不参与检索。
- `finance_bi_catalog_search`：检索词放在 `query`（如 `query=毛利`）；`kind` 只能是 all/datasets/metrics/dimensions/date_fields，**禁止**把「毛利」写进 kind。
- 客户字段默认掩码；查询已指定「客户 XXX」时会明文回显以便核对。需要全量明文可设 `FINANCE_BI_MASK_SENSITIVE=false`。
- `output_mode` 参数已废弃；工具始终返回表格。
