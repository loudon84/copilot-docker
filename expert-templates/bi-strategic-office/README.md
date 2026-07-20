# bi-strategic-office

财务经营分析办公室（BI 智能问数）专家模板。完整交付清单与 Docker 部署步骤见仓库根目录：

**[README.md — 财务经营分析办公室（BI 智能问数）](../../README.md#财务经营分析办公室bi-智能问数)**

PRD：[`prd/v1.9_strategic-office-finance-bi.md`](../../prd/v1.9_strategic-office-finance-bi.md)

快速创建：

```bash
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office
# 编辑 instances/bi-strategic-office/.env 配置 FINANCE_BI_DSN
bash scripts/sync-runtime-env.sh bi-strategic-office
bash scripts/up-instance.sh bi-strategic-office
bash scripts/check-finance-bi.sh bi-strategic-office
```
