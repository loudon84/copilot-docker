# bi-strategic-office（专家包 v1.10）

财务经营分析办公室（BI 智能问数）：语义目录 → `SemanticQuery` → 确定性 SQL → 只读库。进程内插件 `hermes-finance-bi-plugin`，**不**新增独立查询服务、容器或端口；**禁止**注册原始 SQL Tool。

> **v1.10**：本目录已改造为自包含专家包。后续修改只允许进入本目录（含 `runtime/`、`plugins/`、`bin/`）。旧公共 BI 脚本与根下副本为过渡兼容，新流程不再依赖它们。

- **业务使用指南**：[GUIDE.md](GUIDE.md)
- **架构 / 安装 / 升级**：[docs/architecture.md](docs/architecture.md) · [docs/installation.md](docs/installation.md) · [docs/upgrade.md](docs/upgrade.md)
- **PRD**：[prd/bi-strategic-office-prd-v1.10.md](prd/bi-strategic-office-prd-v1.10.md)

## 能力边界

| 专家 | 职责 |
|------|------|
| `finance` | 账户、账龄、回款、头寸、资金计划、财务运营 |
| `bi-strategic-office` | BI 取数、经营分析、产品/客户/区域利润、同比环比、指标口径、管理报告 |

## 专家包结构（唯一维护位置）

```text
expert-templates/bi-strategic-office/
├── expert.yaml / VERSION / CHANGELOG.md
├── runtime/
│   ├── SOUL.md
│   ├── config.patch.yaml
│   ├── memories/MEMORY.md
│   ├── skills/                 # 6 个 Skill（含编排角色 references）
│   ├── policies/
│   └── semantic/
├── plugins/hermes-finance-bi-plugin/
├── bin/                        # install / post-start / update / validate / doctor / …
├── lib/                        # merge_yaml / package_state / validate_manifest
├── tests/
├── docs/
└── prd/
```

过渡期仍保留模板根下 `skills/`、`semantic/`、`policies/`、`SOUL.md` 等旧路径副本，以及 `asset-bundles/hermes-finance-bi-plugin/`；**请勿再改旧副本，改 `runtime/` / `plugins/`**。

## 插件六工具

```text
finance_bi_ask
finance_bi_followup
finance_bi_explain
finance_bi_catalog_search
finance_bi_validate_result
finance_bi_export_result
```

## 创建与启动（新包流程）

```bash
# 校验专家包
bash expert-templates/bi-strategic-office/bin/validate.sh
bash expert-templates/bi-strategic-office/bin/doctor.sh --package-only

# 创建实例（自动识别 expert.yaml → 调用 bin/install.sh）
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office

# 配置只读 DSN 后启动（自动调用 bin/post-start.sh）
bash scripts/up-instance.sh bi-strategic-office

# 诊断
bash expert-templates/bi-strategic-office/bin/doctor.sh \
  --profile bi-strategic-office \
  --data-dir instances/bi-strategic-office/data/hermes \
  --container hermes-bi-strategic-office
```

## 配置只读 BI 数据源

编辑 `instances/<profile>/.env`（**勿提交真实密码**）：

```env
FINANCE_BI_DSN=mssql+pymssql://readonly_user:PASSWORD@db-host:1433/bi_db
FINANCE_BI_DIALECT=mssql
FINANCE_BI_CHARSET=cp936
FINANCE_BI_CATALOG_PATH=/data/hermes/finance-bi/semantic
FINANCE_BI_POLICY_PATH=/data/hermes/finance-bi/policies
FINANCE_BI_ALLOWED_SCHEMAS=bi_finance,bi_sales
FINANCE_BI_ALLOWED_ENTITIES=
FINANCE_BI_DEFAULT_CURRENCY=HKD
FINANCE_BI_TIMEZONE=Asia/Hong_Kong
FINANCE_BI_STATE_DB=/data/hermes/finance-bi/state/finance_bi.db
FINANCE_BI_EXPORT_DIR=/data/hermes/workspace/exports/bi
FINANCE_BI_MASK_SENSITIVE=false
```

```bash
bash scripts/sync-runtime-env.sh <profile>
bash scripts/up-instance.sh <profile>
```

## 本地直连验证（不经过 Hermes）

```powershell
pip install -r expert-templates/bi-strategic-office/plugins/hermes-finance-bi-plugin/requirements.txt
python scripts/finance_bi_cli.py --catalog expert-templates/bi-strategic-office/runtime/semantic doctor
python scripts/finance_bi_cli.py --env instances/<profile>/.env ask "按品牌汇总销售毛利，返回 5 条"
```

## 专家包测试

```bash
bash expert-templates/bi-strategic-office/bin/test.sh unit
bash expert-templates/bi-strategic-office/bin/test.sh security
python -m pytest expert-templates/bi-strategic-office/tests/unit expert-templates/bi-strategic-office/tests/security -q
```

## 运行时目录

```text
instances/<profile>/
├── .env
└── data/hermes/
    ├── SOUL.md / config.yaml / skills/
    ├── plugins/hermes-finance-bi-plugin/
    ├── finance-bi/
    │   ├── semantic/ / policies/ / state/ / cache/
    │   └── package-state.yaml
    └── workspace/exports/bi/
```

## 安全约束

- 禁止向 Hermes 注册 `execute_sql` / `run_raw_sql` / `query_database`
- 查询经 SQL AST 校验：仅 SELECT/WITH、强制 LIMIT、schema/表白名单
- 审计库不保存完整结果集与数据库密码
- 专家包内禁止包含 `.env`、真实 DSN、运行状态数据库
