# 财务工作区规则

继承基础文档路由策略。财务专用路径：

| 产出 | 目录 |
|------|------|
| 原始财务数据、流水 | `/data/hermes/workspace/materials/finance` |
| 分析草稿 | `/data/hermes/workspace/drafts/finance` |
| 审计 Markdown（审阅前） | `/data/hermes/workspace/reports/finance` |
| 最终 xlsx/pdf 导出 | `/data/hermes/workspace/exports/finance` |
| 已审阅摘要（无敏感明细） | `/data/hermes/obsidian-vault/60-Reports` |

敏感文件保留在 `/data/hermes/workspace` 内。未经明确批准，不要调用外部上传接口。

**禁止**将凭证、单据、脚本或二进制导出写入 `obsidian-vault`。
