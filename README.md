# Hermes Agent + WebUI + Obsidian Vault + Hindsight External Kit

目标：在 Ubuntu 24.04 上一键部署多个专用 Hermes Agent WebUI 实例，并支持脚本化注入专家配置。

当前实现边界：

- Hermes WebUI 对外访问，默认端口按实例分配。
- Hermes Agent 在 WebUI 容器内 in-process 使用，不单独暴露 8642。
- Obsidian 按 Vault 目录体系交付，不在服务器容器内运行 GUI Obsidian。
- Hindsight 使用外部 API：`http://hindsight.superic.com:8888`。
- 每个实例独立 HERMES_HOME、workspace、obsidian-vault、sessions、skills、memories。

## 快速开始

```bash
sudo mkdir -p /opt/hermes-agent-webui
sudo unzip hermes-agent-webui-obsidian-hindsight-kit.zip -d /opt
cd /opt/hermes-agent-webui

sudo bash scripts/install-docker-ubuntu24.sh
bash scripts/build-image.sh
bash scripts/create-instance.sh writer 8787 writer
bash scripts/up-instance.sh writer
bash scripts/create-instance.sh finance 8788 finance
bash scripts/up-instance.sh finance
bash scripts/create-instance.sh sale 9602 sale
bash scripts/up-instance.sh sale
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office
# 配置 instances/bi-strategic-office/.env 中只读 FINANCE_BI_DSN 后：
bash scripts/sync-runtime-env.sh bi-strategic-office
bash scripts/up-instance.sh bi-strategic-office
```

访问：

```text
http://服务器IP:8787  # writer
http://服务器IP:8788  # finance
http://服务器IP:9602  # sale
http://服务器IP:8790  # bi-strategic-office（财务 BI）
```

查看密码：

```bash
cat instances/writer/.env | grep HERMES_WEBUI_PASSWORD
cat instances/finance/.env | grep HERMES_WEBUI_PASSWORD
cat instances/bi-strategic-office/.env | grep HERMES_WEBUI_PASSWORD
```
## 镜像构建与国内镜像源

构建参数（apt / pip / npm 镜像）在 `instances/<profile>/.env` 中配置，详见 [docs/build-image.md](docs/build-image.md)。

```bash
bash scripts/build-image.sh writer --no-cache
docker run --rm hermes-agent-webui:latest /usr/local/bin/verify-mirrors.sh
```

## Hermes Agent API Server

每个实例同时暴露 WebUI（8787）与 Agent API（8642 → 宿主机 `HERMES_GATEWAY_PORT`）。详见 [docs/agent-api-server.md](docs/agent-api-server.md)。

```bash
bash scripts/create-instance.sh writer 8787 writer
bash scripts/up-instance.sh writer
bash scripts/check-agent-api.sh writer
```

## 专家注入

```bash
bash scripts/inject-expert.sh writer writer
bash scripts/inject-expert.sh finance finance
bash scripts/inject-expert.sh sale sale
bash scripts/restart-instance.sh writer
bash scripts/restart-instance.sh finance
bash scripts/restart-instance.sh sale
```

## CEO 战略办公室专家团队（Profile Team）

PRD v1.8：1 个容器 + 1 个 root 首席幕僚 + 7 个命名顾问 Profile + Hermes Kanban + Agency Agents 动态专家池。

```bash
bash scripts/create-instance.sh ceo-office 9600 ceo-strategic-office
bash scripts/up-instance.sh ceo-office
bash scripts/check-expert-team.sh ceo-office ceo-strategic-office
```

- 模板包：`expert-templates/ceo-strategic-office/`（含 `team.yaml`）
- 检测到 `team.yaml` 时，`inject-expert.sh` 自动转调 `inject-expert-team.sh`
- 现有 `writer` / `finance` / `sale` 单专家行为不变
- 单元与工作流测试：`python -m pytest tests/test_team_manifest.py tests/test_patch_config_runtime.py tests/test_inject_expert_team.py tests/test_ceo_team_workflows.py -q`

## 财务经营分析办公室（BI 智能问数）

PRD：[`prd/v1.9_strategic-office-finance-bi.md`](prd/v1.9_strategic-office-finance-bi.md)

单专家实例 + 进程内插件 `hermes-finance-bi-plugin`（语义目录 → `SemanticQuery` → 确定性 SQL → 只读库）。**不**新增独立查询服务、容器或端口；**禁止**注册原始 SQL Tool。

与现有 `finance` 专家边界：

| 专家 | 职责 |
|------|------|
| `finance` | 账户、账龄、回款、头寸、资金计划、财务运营 |
| `bi-strategic-office` | BI 取数、经营分析、产品/客户/区域利润、同比环比、指标口径、管理报告 |

### 交付内容

| 路径 | 说明 |
|------|------|
| `expert-templates/bi-strategic-office/` | 专家模板：`SOUL.md`、`config.patch.yaml`、skills、semantic、policies |
| `expert-templates/bi-strategic-office/skills/` | 编排 / 问数 / 绩效分析 / 语义治理 / 质量检查 / 管理报告 |
| `expert-templates/bi-strategic-office/semantic/` | MVP 语义目录（datasets / metrics / dimensions / glossary / examples） |
| `asset-bundles/hermes-finance-bi-plugin/` | Hermes 插件源码包（toolset `finance-bi`） |
| `scripts/inject-expert.sh` | 注入时自动合并 patch、同步 semantic、安装插件、追加 `FINANCE_BI_*` |
| `scripts/sync-bi-semantic-catalog.sh` | 模板 semantic/policies → 实例 `finance-bi/` |
| `scripts/check-finance-bi.sh` | 插件 / 工具 / 语义目录 / 导出目录 / 环境变量诊断 |
| `scripts/validate-expert-template.sh` | 模板结构校验 |
| `scripts/lib/merge_config_patch.py` | `config.patch.yaml` 深度合并（保留 `model`/`providers`） |
| `.env.example` | `FINANCE_BI_*` 配置样例（勿填生产密码） |
| `Dockerfile` | 已固化 sqlalchemy / sqlglot / openpyxl / PyYAML / psycopg |
| `tests/test_finance_bi_plugin.py` | SQLite fixture 单测（不连生产库） |
| `tests/test_bi_strategic_office_inject.py` | 注入幂等与 doctor 验收 |

插件六工具：

```text
finance_bi_ask
finance_bi_followup
finance_bi_explain
finance_bi_catalog_search
finance_bi_validate_result
finance_bi_export_result
```

运行时目录（注入后）：

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

### Docker 部署步骤

前提：已安装 Docker / Compose，仓库在目标机可访问（与 writer/finance 相同）。

**1. 构建共享镜像（全实例只需一次）**

```bash
cd /opt/hermes-agent-webui   # 或本仓库根目录
bash scripts/build-image.sh
# 若镜像已含 finance-bi 依赖可跳过；新代码/新依赖建议：
# bash scripts/build-image.sh --no-cache
```

**2. 校验模板**

```bash
bash scripts/validate-expert-template.sh bi-strategic-office
```

**3. 创建实例并注入专家**

```bash
# 参数：<profile> <webui_port> <expert>
# Gateway 宿主机端口 = 20000 + webui_port（例：8790 → 28790）
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office
```

`create-instance.sh` 会调用 `inject-expert.sh`，自动完成：模板复制、语义同步、插件安装、`FINANCE_BI_*` 占位写入。

**4. 配置只读 BI 数据源**

编辑 `instances/bi-strategic-office/.env`（**勿提交真实密码**）：

```env
FINANCE_BI_DSN=postgresql+psycopg://readonly_user:PASSWORD@db-host:5432/bi_db
FINANCE_BI_DIALECT=postgresql
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
```

说明：

- 数据库账号必须为**只读**
- `FINANCE_BI_ALLOWED_ENTITIES` 为实例级主体白名单（MVP 全实例共享同一权限）
- 本地联调可用 SQLite：`FINANCE_BI_DIALECT=sqlite` + `FINANCE_BI_DSN=sqlite:////data/hermes/finance-bi/state/demo.db`（需自备表结构）

**5. 启动容器**

```bash
bash scripts/up-instance.sh bi-strategic-office
```

访问：

```text
WebUI:  http://服务器IP:8790
API:    http://服务器IP:28790   # HERMES_GATEWAY_PORT = 20000 + 8790
```

查看密码：

```bash
grep HERMES_WEBUI_PASSWORD instances/bi-strategic-office/.env
```

**6. 健康检查**

```bash
bash scripts/check-finance-bi.sh financial-analysis   # 或 bi-strategic-office
```

常见输出说明：

| 输出 | 含义 | 处理 |
|------|------|------|
| `WARN: FINANCE_BI_DSN is empty` | 尚未配置只读库，**结构检查仍可通过** | 编辑 `.env` 填 DSN → `sync-runtime-env` → `restart-instance` |
| `PASS: semantic catalog loads` | 语义 YAML 正常 | 无需处理 |
| `FAIL: config.yaml missing plugins.enabled` | **Hermes 插件默认 opt-in，未 enable 不会加载** | 见下方 enable 步骤 |
| `WARN: Hermes CLI listing skipped` | `hermes tools` **禁止 pipe/非 TTY** | 用 script 伪 TTY 或交互终端查看 |

**重要：插件必须 enable**（仅复制到 `plugins/` 不够）：

```bash
# 推荐：重新 inject（会写入 plugins.enabled）
bash scripts/inject-expert.sh financial-analysis bi-strategic-office
bash scripts/restart-instance.sh financial-analysis

# 或手动写入配置
python3 scripts/lib/enable_finance_bi_plugin.py \
  --config instances/financial-analysis/data/hermes/config.yaml
bash scripts/restart-instance.sh financial-analysis

# 或容器内 CLI（需交互 TTY）
docker exec -it hermes-financial-analysis hermes plugins enable hermes-finance-bi-plugin
```

确认 `config.yaml` 含：

```yaml
plugins:
  enabled:
    - hermes-finance-bi-plugin
```

实例名可为任意 profile（如 `financial-analysis`），专家模板仍是 `bi-strategic-office`：

```bash
bash scripts/inject-expert.sh financial-analysis bi-strategic-office
bash scripts/sync-runtime-env.sh financial-analysis
bash scripts/restart-instance.sh financial-analysis
bash scripts/check-finance-bi.sh financial-analysis
```

确认工具（注意：`hermes tools` 不能直接 `| grep`，需要伪 TTY 或交互终端）：

```bash
# 推荐：容器内用 script 伪造 TTY，再在宿主机 grep
docker exec hermes-financial-analysis bash -lc \
  'script -qfc "hermes tools --summary" /dev/null' | grep finance_bi

# 查看插件是否已 enable
docker exec hermes-financial-analysis bash -lc \
  'script -qfc "hermes plugins list" /dev/null' | grep -i finance
```

配置 DSN 示例（写入 `instances/financial-analysis/.env`）：

```env
FINANCE_BI_DSN=postgresql+psycopg://readonly_user:PASSWORD@db-host:5432/bi_db
FINANCE_BI_ALLOWED_ENTITIES=HK01
```

然后：

```bash
bash scripts/sync-runtime-env.sh financial-analysis
bash scripts/restart-instance.sh financial-analysis
```

**7. 日常运维**

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

**8. 本地单测（不依赖生产库 / 可不启容器）**

```bash
python -m pytest tests/test_finance_bi_plugin.py tests/test_bi_strategic_office_inject.py -q
```

### 安全约束（部署必读）

- 禁止向 Hermes 注册 `execute_sql` / `run_raw_sql` / `query_database`
- 查询经 SQL AST 校验：仅 SELECT/WITH、强制 LIMIT、schema/表白名单、主体过滤
- 审计库不保存完整结果集与数据库密码
- 未接入用户级动态权限前：勿作多租户公网服务、勿配置全公司无限制账号

更细的部署清单见 [README_DEPLOY.md §10.2](README_DEPLOY.md)。

## 推送到火山引擎（nodeskclaw）

```bash
cp registry.env.example registry.env
# 编辑 IMAGE_REPO、IMAGE_TAG
bash scripts/build-push-registry.sh --login
```

详见 [README_DEPLOY.md §14](README_DEPLOY.md#14-一键构建推送到火山引擎nodeskclaw)。

## 本地 Docker Registry 测试

如果暂时没有火山/阿里云/Harbor 镜像仓库，可使用本地 Docker Registry 完成构建、推送与 nodeskclaw 联调。

```bash
cp local-registry.env.example local-registry.env
bash scripts/start-local-registry.sh
sudo bash scripts/configure-insecure-registry.sh
bash scripts/build-push-local-registry.sh
bash scripts/doctor-local-registry.sh
```

详见 [README_LOCAL_REGISTRY.md](README_LOCAL_REGISTRY.md)。

## 目录

```text
/opt/hermes-agent-webui/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── scripts/
├── expert-templates/
│   ├── base/
│   ├── writer/
│   ├── finance/
│   ├── sale/
│   ├── bi-strategic-office/    # 财务 BI 问数（PRD v1.9）
│   └── ceo-strategic-office/   # Profile Team（PRD v1.8）
└── instances/
    ├── writer/
    │   ├── .env
    │   └── data/hermes/
    ├── finance/
    │   ├── .env
    │   └── data/hermes/
    ├── bi-strategic-office/
    │   ├── .env                # 含 FINANCE_BI_*（勿提交真实 DSN）
    │   └── data/hermes/
    │       ├── finance-bi/     # semantic / policies / state
    │       └── plugins/hermes-finance-bi-plugin/
    └── ceo-office/             # 团队实例示例
        ├── .env
        └── data/hermes/
            ├── team.yaml
            ├── team-shared/
            └── profiles/       # 7 个命名顾问
```

## Hermes Asset Bundles

用于从成熟实例导出 skills、tools、plugins、mcp 能力包，并导入到新同事实例。

详见 [README_ASSET_BUNDLES.md](README_ASSET_BUNDLES.md)。
