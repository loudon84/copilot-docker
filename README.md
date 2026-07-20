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

## 专家模板

各专家的完整说明、注入脚本与部署步骤见对应模板目录 `README.md`。根 README 仅登记路径与简述。

| 模板路径 | 简述 | 说明 |
|----------|------|------|
| `expert-templates/writer/` | 中文写作与内容生产 | [README](expert-templates/writer/README.md) |
| `expert-templates/finance/` | 财务运营（账龄、回款、现金流） | [README](expert-templates/finance/README.md) |
| `expert-templates/sale/` | 企业销售助手 | [README](expert-templates/sale/README.md) |
| `expert-templates/bi-strategic-office/` | 财务 BI 智能问数 | [README](expert-templates/bi-strategic-office/README.md) |
| `expert-templates/ceo-strategic-office/` | CEO 战略办公室专家团队 | [README](expert-templates/ceo-strategic-office/README.md) |

基础设施模板 `base/`、`default/` 供注入脚本内部使用，无独立 README。

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
