# 镜像构建说明

本文档说明 `copilot-docker` 镜像构建时的国内镜像源配置与故障排查。

## 快速构建

```bash
# 使用 instances/<profile>/.env 中的镜像源参数
bash scripts/build-image.sh writer

# 无缓存重建
bash scripts/build-image.sh writer --no-cache

# 拉取最新基础镜像并重建
bash scripts/build-image.sh writer --pull --no-cache
```

构建完成后验证镜像源：

```bash
docker run --rm hermes-agent-webui:latest /usr/local/bin/verify-mirrors.sh
```

## 可配置变量

在 `instances/<profile>/.env` 或根级 `.env.example` 中设置：

| 变量 | 默认值 | 作用 |
|------|--------|------|
| `PYTHON_BASE_IMAGE` | `python:3.12-slim-bookworm` | 基础镜像（固定 Debian bookworm，避免 trixie 漂移） |
| `USE_CN_MIRRORS` | `1` | 是否启用国内 apt 镜像 |
| `APT_MIRROR` | `https://mirrors.aliyun.com/debian` | Debian apt 主源 |
| `PIP_INDEX_URL` | `https://mirrors.aliyun.com/pypi/simple/` | pip / uv 索引 |
| `NPM_REGISTRY` | `https://registry.npmmirror.com` | npm 全局安装 registry |
| `BUILD_APT_PROXY` | 空 | 构建期 apt 代理（如 `http://host.docker.internal:7890`） |

## 工作原理

Dockerfile 多阶段构建中，每个 `FROM` 之后 ARG 作用域重置。因此：

1. **Stage 1 (`webui-clone`)** 和 **Stage 2 (`hermes-webui-base`)** 在 `apt-get update` 前调用 `docker/apt-mirror.sh`，将 `deb.debian.org` 替换为 `APT_MIRROR`。
2. **Stage 3** 通过 `PIP_INDEX_URL`、`NPM_CONFIG_REGISTRY` 控制 pip 与 npm 安装。
3. `scripts/build-image.sh` 构建前打印当前镜像源参数，便于日志排查。

## 海外环境

关闭国内镜像：

```env
USE_CN_MIRRORS=0
PIP_INDEX_URL=https://pypi.org/simple/
NPM_REGISTRY=https://registry.npmjs.org/
```

## 故障排查

### 构建日志仍访问 deb.debian.org

- 确认 `USE_CN_MIRRORS=1` 且日志中出现 `[apt-mirror] APT_MIRROR=...`。
- `security.debian.org` 在 v1.5 未替换；若 security 源导致失败，后续版本将增加 `APT_SECURITY_MIRROR`。

### apt 仍然很慢或失败

- 检查 `APT_MIRROR` 是否支持你使用的基础 Debian 版本（默认 bookworm）。
- 如需 trixie：`PYTHON_BASE_IMAGE=python:3.12-slim-trixie`（部分 mirror 同步可能滞后）。

### Docker Hub 拉取慢

基础镜像 `python:3.12-slim-bookworm` 从 Docker Hub 拉取，需在 Docker daemon 配置 registry mirror，不属于本仓库范围。

### pip / npm 失败

构建日志中应出现：

```text
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
NPM registry=https://registry.npmmirror.com
```

运行 `verify-mirrors.sh` 确认容器内配置。
