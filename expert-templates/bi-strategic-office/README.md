# bi-strategic-office

财务经营分析办公室（BI 智能问数）：语义目录 → `SemanticQuery` → 确定性 SQL → 只读库。进程内插件 `hermes-finance-bi-plugin`，**不**新增独立查询服务、容器或端口；**禁止**注册原始 SQL Tool。

PRD：[`prd/v1.9_strategic-office-finance-bi.md`](../../prd/v1.9_strategic-office-finance-bi.md)

## 能力边界

| 专家 | 职责 |
|------|------|
| `finance` | 账户、账龄、回款、头寸、资金计划、财务运营 |
| `bi-strategic-office` | BI 取数、经营分析、产品/客户/区域利润、同比环比、指标口径、管理报告 |

## 模板结构

```text
expert-templates/bi-strategic-office/
├── SOUL.md
├── config.patch.yaml
├── skills/                  # bi-office-orchestration, finance-bi-query, finance-performance-analysis 等
├── semantic/                # datasets / metrics / dimensions / glossary / examples
├── policies/
└── README.md

asset-bundles/hermes-finance-bi-plugin/   # Hermes 插件（toolset finance-bi）
```

## 插件六工具

```text
finance_bi_ask
finance_bi_followup
finance_bi_explain
finance_bi_catalog_search
finance_bi_validate_result
finance_bi_export_result
```

## 创建与注入

```bash
# 校验模板
bash scripts/validate-expert-template.sh bi-strategic-office

# 创建实例（WebUI 8790，Gateway 28790）
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office
```

`create-instance.sh` 会调用 `inject-expert.sh`，自动完成：模板复制、语义同步、插件安装、`FINANCE_BI_*` 占位写入。

## 配置只读 BI 数据源

编辑 `instances/bi-strategic-office/.env`（**勿提交真实密码**）：

```env
# SQL Server 2012+（pymssql）
FINANCE_BI_DSN=mssql+pymssql://readonly_user:PASSWORD@db-host:1433/bi_db
FINANCE_BI_DIALECT=mssql
FINANCE_BI_CATALOG_PATH=/data/hermes/finance-bi/semantic
FINANCE_BI_POLICY_PATH=/data/hermes/finance-bi/policies
FINANCE_BI_ALLOWED_SCHEMAS=bi_finance,bi_sales
FINANCE_BI_ALLOWED_ENTITIES=HK01
FINANCE_BI_DEFAULT_CURRENCY=HKD
FINANCE_BI_TIMEZONE=Asia/Hong_Kong
FINANCE_BI_QUERY_TIMEOUT_SECONDS=30
FINANCE_BI_DEFAULT_LIMIT=200
FINANCE_BI_HARD_LIMIT=5000
FINANCE_BI_STATE_DB=/data/hermes/finance-bi/state/finance_bi.db
FINANCE_BI_EXPORT_DIR=/data/hermes/workspace/exports/bi
```

同步到容器内 Hermes 可读的 `data/hermes/.env`：

```bash
bash scripts/sync-runtime-env.sh bi-strategic-office
bash scripts/up-instance.sh bi-strategic-office
```

说明：

- 数据库账号必须为**只读**
- `FINANCE_BI_ALLOWED_ENTITIES` 为实例级主体白名单（MVP 全实例共享同一权限）
- 本地联调可用 SQLite：`FINANCE_BI_DIALECT=sqlite` + `FINANCE_BI_DSN=sqlite:////data/hermes/finance-bi/state/demo.db`（需自备表结构）

## 健康检查

```bash
bash scripts/check-finance-bi.sh bi-strategic-office
```

常见输出：

| 输出 | 含义 | 处理 |
|------|------|------|
| `WARN: FINANCE_BI_DSN is empty` | 尚未配置只读库，结构检查仍可通过 | 编辑 `.env` 填 DSN → `sync-runtime-env` → `restart-instance` |
| `PASS: semantic catalog loads` | 语义 YAML 正常 | 无需处理 |
| `FAIL: config.yaml missing plugins.enabled` | Hermes 插件默认 opt-in，未 enable 不会加载 | 见下方 enable 步骤 |

**重要：插件必须 enable**（仅复制到 `plugins/` 不够）：

```bash
bash scripts/inject-expert.sh bi-strategic-office bi-strategic-office
bash scripts/restart-instance.sh bi-strategic-office

# 或手动写入配置
python3 scripts/lib/enable_finance_bi_plugin.py \
  --config instances/bi-strategic-office/data/hermes/config.yaml
bash scripts/restart-instance.sh bi-strategic-office
```

确认 `config.yaml` 含：

```yaml
plugins:
  enabled:
    - hermes-finance-bi-plugin
```

若存在 `platform_toolsets`（白名单），还必须包含 `finance-bi`：

```yaml
platform_toolsets:
  cli:
    - browser
    - finance-bi
```

实例名可为任意 profile（如 `financial-analysis`），专家模板仍是 `bi-strategic-office`：

```bash
bash scripts/inject-expert.sh financial-analysis bi-strategic-office
bash scripts/sync-runtime-env.sh financial-analysis
bash scripts/restart-instance.sh financial-analysis
bash scripts/check-finance-bi.sh financial-analysis
```

确认工具（容器内 CLI 为 `/app/venv/bin/hermes`，不要直接 `| grep` 喂给 hermes）：

```bash
docker exec -u hermeswebui -e HERMES_HOME=/data/hermes \
  hermes-financial-analysis bash -lc \
  'script -qfc "/app/venv/bin/hermes tools --summary" /dev/null' | grep finance_bi
```

## 访问

```text
WebUI:  http://服务器IP:8790
API:    http://服务器IP:28790
```

查看密码：

```bash
grep HERMES_WEBUI_PASSWORD instances/bi-strategic-office/.env
```

## 运行时目录

```text
instances/bi-strategic-office/
├── .env                          # FINANCE_BI_*（勿提交真实 DSN）
└── data/hermes/
    ├── SOUL.md
    ├── skills/
    ├── finance-bi/
    │   ├── semantic/             # 语义目录
    │   ├── policies/
    │   └── state/finance_bi.db   # 查询状态与审计（不含结果集）
    ├── plugins/hermes-finance-bi-plugin/
    └── workspace/exports/bi/     # CSV / XLSX 导出
```

## 日常运维

```bash
# 更新模板 / 语义目录 / 插件后重新注入（幂等）
bash scripts/inject-expert.sh bi-strategic-office bi-strategic-office
bash scripts/sync-bi-semantic-catalog.sh bi-strategic-office
bash scripts/sync-runtime-env.sh bi-strategic-office
bash scripts/restart-instance.sh bi-strategic-office

# 仅同步语义 YAML
bash scripts/sync-bi-semantic-catalog.sh bi-strategic-office

# 停止
bash scripts/down-instance.sh bi-strategic-office
```

## 单测

```bash
python -m pytest tests/test_finance_bi_plugin.py tests/test_bi_strategic_office_inject.py -q
```

## 安全约束

- 禁止向 Hermes 注册 `execute_sql` / `run_raw_sql` / `query_database`
- 查询经 SQL AST 校验：仅 SELECT/WITH、强制 LIMIT、schema/表白名单、主体过滤
- 审计库不保存完整结果集与数据库密码
- 未接入用户级动态权限前：勿作多租户公网服务、勿配置全公司无限制账号

更细的部署清单见 [README_DEPLOY.md §10.2](../../README_DEPLOY.md)。
