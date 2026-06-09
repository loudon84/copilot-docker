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
```

访问：

```text
http://服务器IP:8787  # writer
http://服务器IP:8788  # finance
```

查看密码：

```bash
cat instances/writer/.env | grep HERMES_WEBUI_PASSWORD
cat instances/finance/.env | grep HERMES_WEBUI_PASSWORD
```

## 专家注入

```bash
bash scripts/inject-expert.sh writer writer
bash scripts/inject-expert.sh finance finance
bash scripts/restart-instance.sh writer
bash scripts/restart-instance.sh finance
```

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
│   └── finance/
└── instances/
    ├── writer/
    │   ├── .env
    │   └── data/hermes/
    └── finance/
        ├── .env
        └── data/hermes/
```
