# 本地 Docker Registry 测试指南

本文档说明如何在尚未开通火山、阿里云、Harbor 等正式镜像仓库时，使用本地 Docker Registry 完成 Hermes 专家服务镜像的构建、推送与 nodeskclaw 联调。

## 1. 用途

本地 Registry 仅用于开发、联调、POC，**不作为正式生产镜像仓库**。

完整链路：

```text
copilot-docker 构建 hermes-webui-expert 镜像
  ↓
推送到本地 Docker Registry（如 192.168.102.247:9900）
  ↓
nodeskclaw 配置本地镜像仓库
  ↓
nodeskclaw 发布引擎版本
  ↓
nodeskclaw 拉取镜像并部署 Hermes 专家员工
```

nodeskclaw 只负责拉取镜像和部署，**不在 nodeskclaw 内执行镜像构建**。

## 2. 端口说明

`registry:2` 镜像默认在**容器内**监听 **5000** 端口。若宿主机使用 **9900**，启动时必须映射：

```text
-p 9900:5000
```

即：宿主机 9900 → 容器 5000。

## 3. 快速开始

### 3.1 准备配置

```bash
cd copilot-docker
cp local-registry.env.example local-registry.env
nano local-registry.env
```

关键字段：

| 变量 | 说明 |
|------|------|
| `LOCAL_REGISTRY_HOST` | Registry 宿主机 IP |
| `LOCAL_REGISTRY_PORT` | 宿主机端口（默认 9900） |
| `IMAGE_REPO` | 完整仓库路径，如 `192.168.102.247:9900/hermes-webui-expert` |
| `IMAGE_TAG` | 引擎版本号，与 nodeskclaw 一致 |

### 3.2 启动 Registry

```bash
bash scripts/start-local-registry.sh
```

验证：

```bash
curl http://192.168.102.247:9900/v2/_catalog
# 期望返回: {"repositories":[]}
```

### 3.3 配置 Docker insecure registry

本地 Registry 使用 HTTP，Docker 默认按 HTTPS 访问，需在所有需要 push/pull 的主机上配置：

```bash
sudo bash scripts/configure-insecure-registry.sh
```

该脚本会：

1. 将 `192.168.102.247:9900` 合并写入 `/etc/docker/daemon.json` 的 `insecure-registries`
2. 重启 Docker
3. 输出当前 `Insecure Registries` 列表

### 3.4 构建并推送镜像

```bash
bash scripts/build-push-local-registry.sh
```

脚本采用 **`--load` 构建到本地 daemon，再 `docker push`**，避免 `buildx --push` 与 HTTP insecure registry 不兼容。

其他选项：

```bash
# 只预览命令
bash scripts/build-push-local-registry.sh --dry-run

# 指定版本号
bash scripts/build-push-local-registry.sh --tag v2026.6.1

# 仅本地构建不推送
bash scripts/build-push-local-registry.sh --no-push
```

### 3.5 验证

```bash
bash scripts/doctor-local-registry.sh
```

期望输出示例：

```text
[pass] registry container running
[pass] http://192.168.102.247:9900/v2/_catalog reachable
[pass] hermes-webui-expert:v2026.6.1 exists
[pass] docker insecure registry configured
[pass] docker pull succeeded
```

### 3.6 停止 Registry

```bash
bash scripts/stop-local-registry.sh
```

保留数据目录（默认）：

```bash
# 数据保留在 /data/docker-registry
bash scripts/stop-local-registry.sh
```

同时删除数据：

```bash
bash scripts/stop-local-registry.sh --remove-data
```

## 4. 配置 nodeskclaw

推送成功后，在 nodeskclaw 控制台：

| 位置 | 填写内容 |
|------|----------|
| 组织设置 → 镜像仓库 → Hermes 专家服务 | `192.168.102.247:9900/hermes-webui-expert` |
| 用户名 / 密码 | **留空**（本地 registry 无需认证） |
| 组织设置 → 引擎版本 → Hermes 专家服务 → 发布新版本 | `v2026.6.1`（与 `IMAGE_TAG` 一致） |

部署时 nodeskclaw 将拉取：

```text
192.168.102.247:9900/hermes-webui-expert:v2026.6.1
```

## 5. 常见错误

### 5.1 `http: server gave HTTP response to HTTPS client`

**原因**：Docker 默认按 HTTPS 访问 registry，但本地 registry 是 HTTP。

**处理**：在所有需要 push/pull 的 Docker 主机上执行：

```bash
sudo bash scripts/configure-insecure-registry.sh
```

### 5.2 `connection refused`

**原因**：registry 容器未启动、端口映射错误或防火墙未放行。

**处理**：

```bash
docker ps | grep local-registry
curl http://192.168.102.247:9900/v2/_catalog
```

确认使用 `-p 9900:5000` 映射。

### 5.3 `no basic auth credentials`

**原因**：`IMAGE_REPO` 配错或误用了需要认证的远程 registry。

**处理**：确认 `IMAGE_REPO=192.168.102.247:9900/hermes-webui-expert`，本地测试模式**不需要** `docker login`。

### 5.4 `docker buildx 不可用`

**原因**：主机只安装了 `docker-ce`，未安装 `docker-buildx-plugin`。

**处理**（二选一）：

```bash
# 推荐：安装 buildx 插件
sudo apt-get update
sudo apt-get install -y docker-buildx-plugin

# 或一键重装 Docker（含 buildx + compose）
sudo bash scripts/install-docker-ubuntu24.sh
```

未安装 buildx 时，`build-push-local-registry.sh` 会自动回退到 `docker build`（仅适用于本机 amd64 构建 `linux/amd64`）。

### 5.5 buildx push 失败

**原因**：`buildx` 的 `docker-container` builder 可能无法继承宿主机 insecure registry 配置。

**处理**：使用本仓库提供的 `build-push-local-registry.sh`，它采用 `--load` + `docker push` 方案。

## 6. 文件清单

```text
local-registry.env.example       # 配置模板
local-registry.env               # 本地配置（勿提交）
scripts/start-local-registry.sh  # 启动 registry:2
scripts/stop-local-registry.sh   # 停止 registry
scripts/configure-insecure-registry.sh  # 配置 insecure-registries
scripts/build-push-local-registry.sh    # 构建并推送
scripts/doctor-local-registry.sh        # 健康检查
```

## 7. 与远程仓库方案的关系

- **远程仓库**（火山/阿里云/Harbor）：见 [README_DEPLOY.md §14](README_DEPLOY.md#14-一键构建推送到火山引擎nodeskclaw)，使用 `registry.env` + `build-push-registry.sh`
- **本地 Registry 测试**：使用 `local-registry.env` + `build-push-local-registry.sh`

两套脚本独立，互不影响。
