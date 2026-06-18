# Finance Workspace Rules

Inherits base document routing policy. Finance-specific paths:

| Output | Directory |
|--------|-----------|
| Raw financial data, statements | `/data/hermes/workspace/materials/finance` |
| Analysis drafts | `/data/hermes/workspace/drafts/finance` |
| Audit Markdown (pre-review) | `/data/hermes/workspace/reports/finance` |
| Final xlsx/pdf exports | `/data/hermes/workspace/exports/finance` |
| Reviewed summary (no sensitive detail) | `/data/hermes/obsidian-vault/60-Reports` |

Keep sensitive files inside `/data/hermes/workspace`. Do not call external upload endpoints unless explicitly approved.

**Never** write credentials, vouchers, scripts, or binary exports to `obsidian-vault`.
