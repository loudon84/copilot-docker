# hermes-finance-bi-plugin

Hermes 进程内财务 BI 插件（PRD v1.9）。Toolset：`finance-bi`。

## Tools

- `finance_bi_ask`
- `finance_bi_followup`
- `finance_bi_explain`
- `finance_bi_catalog_search`
- `finance_bi_validate_result`
- `finance_bi_export_result`

## Install

由 `scripts/inject-expert.sh` 在专家为 `bi-strategic-office`（或模板含 `semantic/`）时自动复制到：

```text
instances/<profile>/data/hermes/plugins/hermes-finance-bi-plugin/
```

依赖见 `requirements.txt`（镜像 Dockerfile 已固化）。

## Config

通过实例 `.env` 的 `FINANCE_BI_*`（见仓库根 `.env.example`）。禁止提交生产 DSN。

## Tests

```bash
python -m pytest tests/test_finance_bi_plugin.py -q
```
