# Hermes Self-Evolution Docker Bundle

## 1. 包内容

```text
Dockerfile
docker-compose.yml
scripts/
  create-instance.sh
  inject-expert.sh
  up-instance.sh
  down-instance.sh
  doctor-instance.sh
  install-blound-skills.sh
  init-brain-runtime.sh
  install-security-skills.sh
  install-self-evolution.sh
  bootstrap-self-evolution-stack.sh
  build-push-registry.sh
  start-local-registry.sh
  stop-local-registry.sh
  configure-insecure-registry.sh
  build-push-local-registry.sh
  doctor-local-registry.sh
  build-image.sh
  patch-config-runtime.sh
  import-legacy-config.sh
registry.env.example
local-registry.env.example
expert-templates/
  base/
  default/
  writer/
  finance/
```

## 2. 部署前置条件

服务器需要具备：

```bash
docker --version
docker compose version
git --version
openssl version
```

构建期需要能访问：

```text
HERMES_WEBUI_REPO=http://git.superic.com/aiplatform/hermes-webui.git
HERMES_AGENT_REPO=http://git.superic.com/aiplatform/hermes-agent.git
```

如需在构建阶段安装 GBrain，需要能访问 `github:garrytan/gbrain`，或者在实例 `.env` 中把 `GBRAIN_REPO` 改成内网 mirror。

## 3. 解压与授权

```bash
mkdir -p /data/hermes-self-evolution
cd /data/hermes-self-evolution
unzip hermes-self-evolution-bundle.zip

chmod +x scripts/*.sh
```

## 4. 创建 writer 实例

```bash
bash scripts/create-instance.sh writer 9601 writer
```

执行后生成：

```text
instances/writer/.env
instances/writer/data/hermes/
```

查看密码：

```bash
cat instances/writer/.env | grep HERMES_WEBUI_PASSWORD
```

### 4.1 config.yaml runtime 段（memory / gbrain / MCP）

新实例通过 `inject-expert.sh` 会自动写入以下 runtime 配置（保留完整 model/providers 时不覆盖）：

```yaml
memory:
  provider: hindsight
  mode: local_external
  api_url: http://hindsight.superic.com:8888
  bank_id: hermes-<profile>

mcp_servers:
  obsidian_vault: ...
  gbrain: ...

auxiliary:
  curator: ...

security:
  website_blocklist: ...

terminal:
  backend: docker
```

从旧版完整 config 迁移（如 `instance/config.yaml`）：

```bash
bash scripts/import-legacy-config.sh <profile> instance/config.yaml
```

已有 instance 仅补 runtime 段：

```bash
bash scripts/patch-config-runtime.sh <profile>
```

## 5. 构建镜像（全实例只需一次）

所有 instance 共用同一镜像 `hermes-agent-webui:lastest`。**只需构建一次**，后续创建多个 instance 时直接 `up-instance` 即可，无需重复 `docker compose build`。

```bash
# 推荐：统一构建入口
bash scripts/build-image.sh
```

或借用某个 instance 的构建参数：

```bash
bash scripts/build-image.sh writer
```

等价于：

```bash
docker compose --env-file instances/writer/.env -p hermes-build build
```

**apt 说明**：当前 `Dockerfile` 从 Git 源码构建 WebUI（非预构建 ghcr 镜像），首次构建会在镜像层内执行 2 次 `apt-get update`（Stage 1 装 git、Stage 2 装全部系统依赖）。已合并为单次安装，不再 `apt-get upgrade`，且 Stage 3 不再重复 apt。此过程**不影响 Ubuntu 宿主机**。

多实例流程：

```bash
bash scripts/build-image.sh                    # ① 只 build 一次
bash scripts/create-instance.sh writer 9601 writer
bash scripts/up-instance.sh writer             # ② 复用镜像，不 rebuild
bash scripts/create-instance.sh finance 9602 finance
bash scripts/up-instance.sh finance            # ③ 复用同一镜像
```

如果公网不可用，建议先编辑：

```bash
nano instances/writer/.env
```

把：

```text
GBRAIN_REPO=github:garrytan/gbrain
CLAWSEC_REPO=https://github.com/prompt-security/clawsec.git
```

改成内网 Git mirror。

## 6. 启动容器

```bash
bash scripts/up-instance.sh writer
```

或构建并启动：

```bash
bash scripts/up-instance.sh writer --build
```

查看状态：

```bash
docker ps | grep hermes-writer
docker logs -f hermes-writer
```

访问：

```text
http://<server-ip>:9601
```

## 7. 安装自我进化与记忆强化基础能力

推荐一键执行：

```bash
bash scripts/bootstrap-self-evolution-stack.sh writer
```

该脚本会顺序执行：

```text
1. install-blound-skills.sh
2. init-brain-runtime.sh
3. install-security-skills.sh
4. docker restart hermes-writer
5. doctor-instance.sh
```

## 8. 单独执行安装脚本

### 8.1 只安装 Skills

```bash
bash scripts/install-blound-skills.sh writer
```

不安装 community skills：

```bash
bash scripts/install-blound-skills.sh writer --no-awesome
```

不重启容器：

```bash
bash scripts/install-blound-skills.sh writer --no-restart
```

### 8.2 初始化 GBrain + Obsidian Vault MCP

```bash
bash scripts/init-brain-runtime.sh writer
```

写入 `/data/hermes/config.yaml`：

```text
mcp_servers.obsidian_vault
mcp_servers.gbrain
auxiliary.curator
security.website_blocklist
```

### 8.3 安装 Security Skills

```bash
bash scripts/install-security-skills.sh writer
```

### 8.4 安装离线 self-evolution runtime

默认不执行，只有维护人员需要时再安装：

```bash
bash scripts/install-self-evolution.sh writer
```

生产规则：该脚本只安装 runtime，不自动运行，不自动覆盖 production skills。

## 9. 验证

```bash
bash scripts/doctor-instance.sh writer
```

检查 skills 数量：

```bash
docker exec -it hermes-writer bash -lc 'find /data/hermes/skills -name SKILL.md | wc -l'
```

检查 config：

```bash
docker exec -it hermes-writer bash -lc 'cat /data/hermes/config.yaml | sed -n "1,180p"'
```

检查 vault：

```bash
docker exec -it hermes-writer bash -lc 'find /data/hermes/obsidian-vault -maxdepth 2 -type d | sort'
```

检查 GBrain：

```bash
docker exec -it hermes-writer bash -lc 'command -v gbrain && gbrain --help | head'
```

## 10. 新增 finance 实例

```bash
bash scripts/create-instance.sh finance 9602 finance
bash scripts/up-instance.sh finance --build
bash scripts/bootstrap-self-evolution-stack.sh finance
```

访问：

```text
http://<server-ip>:9602
```

## 11. 停止实例

```bash
bash scripts/down-instance.sh writer
```

## 12. 目录边界

容器内核心目录：

```text
/data/hermes/config.yaml
/data/hermes/SOUL.md
/data/hermes/memories/MEMORY.md
/data/hermes/memories/USER.md
/data/hermes/workspace
/data/hermes/obsidian-vault
/data/hermes/skills
/data/hermes/gbrain
/data/hermes/evolution
/data/hermes/backups
```

职责边界：

```text
Hindsight: agent memory provider
GBrain: entity/project/document knowledge brain
Obsidian Vault: auditable Markdown assets
Skills: reusable operational workflows
Curator: skill lifecycle governance
Self-Evolution: offline candidate patch generator
Security Skills: prompt and workspace boundary audit
```

## 13. 生产建议

1. `GBRAIN_REPO`、`CLAWSEC_REPO`、`SELF_EVOLUTION_REPO` 改为内网 mirror。
2. `HERMES_SELF_EVOLUTION_ENABLED` 保持 `0`。
3. 不允许 self-evolution 自动覆盖 `/data/hermes/skills`。
4. 新 skill 必须先经过 `skill-audit`。
5. 先在 writer/profile 测试，再扩展 finance/default。

## 14. 一键构建推送到火山引擎（nodeskclaw）

将 Hermes 专家服务镜像构建并推送到火山引擎镜像仓库，供 nodeskclaw 按版本拉取部署。

### 14.1 准备配置

```bash
cd copilot-docker
cp registry.env.example registry.env
```

编辑 `registry.env`：

```text
IMAGE_REPO=cr.volces.com/<namespace>/hermes-webui-expert
IMAGE_TAG=v2026.6.8
REGISTRY_HOST=cr.volces.com
```

### 14.2 登录并构建推送

```bash
bash scripts/build-push-registry.sh --login
```

脚本等价于：

```bash
docker login cr.volces.com

docker buildx build \
  --platform linux/amd64 \
  -t "${IMAGE_REPO}:${IMAGE_TAG}" \
  --build-arg HERMES_WEBUI_REPO="http://git.superic.com/aiplatform/hermes-webui.git" \
  --build-arg HERMES_WEBUI_REF="master" \
  --build-arg HERMES_AGENT_REPO="http://git.superic.com/aiplatform/hermes-agent.git" \
  --build-arg HERMES_AGENT_REF="master" \
  --build-arg HERMES_VERSION="${IMAGE_TAG}" \
  --build-arg INSTALL_GBRAIN=1 \
  --build-arg INSTALL_FILESYSTEM_MCP=1 \
  --build-arg INSTALL_CLAWSEC=0 \
  --push \
  .
```

其他选项：

```bash
# 只预览命令
bash scripts/build-push-registry.sh --dry-run

# 指定版本号
bash scripts/build-push-registry.sh --login --tag v2026.6.1

# 仅本地构建不推送（调试用）
bash scripts/build-push-registry.sh --no-push
```

### 14.3 nodeskclaw 配置

推送成功后，在 nodeskclaw 控制台配置：

| 位置 | 填写内容 |
|------|----------|
| 组织设置 → 镜像仓库 → Hermes 专家服务 | `<your-registry>/<namespace>/hermes-webui-expert` |
| 组织设置 → 引擎版本 → Hermes 专家服务 → 发布新版本 | `v2026.6.8`（与 `IMAGE_TAG` 一致） |

部署时 nodeskclaw 将拉取：

```text
<your-registry>/<namespace>/hermes-webui-expert:v2026.6.8
```

### 14.4 构建机要求

- 已安装 `docker` + `docker buildx`（见 `scripts/install-docker-ubuntu24.sh`）
- 构建期可访问 `git.superic.com` 上的 hermes-webui / hermes-agent
- 若启用 GBrain，构建机需能访问 `GBRAIN_REPO`（或改为内网 mirror）

## 15. 本地 Registry 测试模式

在尚未开通火山、阿里云、Harbor 等正式镜像仓库时，可使用本地 Docker Registry 验证完整链路。

### 15.1 端口说明

`registry:2` 默认在**容器内**监听 **5000** 端口。若宿主机使用 **9900**，启动时必须使用 `-p 9900:5000` 映射。

### 15.2 快速流程

```bash
cp local-registry.env.example local-registry.env
# 编辑 LOCAL_REGISTRY_HOST、IMAGE_REPO、IMAGE_TAG

bash scripts/start-local-registry.sh
sudo bash scripts/configure-insecure-registry.sh
bash scripts/build-push-local-registry.sh
bash scripts/doctor-local-registry.sh
```

### 15.3 与远程推送的区别

| 项目 | 远程仓库 | 本地 Registry |
|------|----------|---------------|
| 配置文件 | `registry.env` | `local-registry.env` |
| 构建脚本 | `build-push-registry.sh` | `build-push-local-registry.sh` |
| 认证 | 需要 `docker login` | 无需认证 |
| 推送方式 | `buildx --push` | `--load` + `docker push` |
| HTTP 支持 | HTTPS | 需配置 `insecure-registries` |

完整文档见 [README_LOCAL_REGISTRY.md](README_LOCAL_REGISTRY.md)。
