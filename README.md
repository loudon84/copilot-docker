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
```

访问：

```text
http://服务器IP:8787  # writer
http://服务器IP:8788  # finance
http://服务器IP:9602  # sale
```

查看密码：

```bash
cat instances/writer/.env | grep HERMES_WEBUI_PASSWORD
cat instances/finance/.env | grep HERMES_WEBUI_PASSWORD
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

PRD v1.9：单专家实例 + 进程内插件 `hermes-finance-bi-plugin`（语义目录 → SemanticQuery → 确定性 SQL → 只读库）。与 `finance`（资金运营）职责分离。

```bash
bash scripts/validate-expert-template.sh bi-strategic-office
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office
# 编辑 instances/bi-strategic-office/.env，配置只读 FINANCE_BI_DSN
bash scripts/up-instance.sh bi-strategic-office
bash scripts/check-finance-bi.sh bi-strategic-office
```

- 模板：`expert-templates/bi-strategic-office/`（skills / semantic / policies）
- 插件：`asset-bundles/hermes-finance-bi-plugin/`
- 同步语义目录：`bash scripts/sync-bi-semantic-catalog.sh bi-strategic-office`
- 单测：`python -m pytest tests/test_finance_bi_plugin.py tests/test_bi_strategic_office_inject.py -q`
- 不新增独立查询服务、容器或端口；禁止注册原始 SQL Tool

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
