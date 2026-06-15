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
  doctor-paths.sh
  repair-existing-instances.sh
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

## 2. 路径规则

所有 Hermes 实例资产遵循以下目录边界：

- **唯一主目录**：容器内 `/data/hermes`
- **实例目录**：宿主机 `instances/<profile>/data/hermes`
- **兼容路径**：`/home/hermeswebui/.hermes/tools`、`/home/hermeswebui/.hermes/plugins` 仅由 `docker-compose.yml` bind mount 到 `/data/hermes/tools`、`/data/hermes/plugins`
- **源码路径**：`/opt/hermes-agent` 只属于基础镜像，不作为实例资产分发来源

禁止事项：

- 禁止在容器内删除、重建或手工软链 `~/.hermes/tools`、`~/.hermes/plugins`
- 禁止从 `/opt/hermes-agent/tools` 直接当作实例资产导出或分发
- 禁止在 `tools/` 或 `plugins/` 下创建 `tools/tools`、`plugins/plugins` 嵌套路径

诊断与修复：

```bash
bash scripts/doctor-paths.sh <profile>
bash scripts/doctor-paths.sh <profile> --fix
bash scripts/repair-existing-instances.sh
```

## 3. 部署前置条件

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

如需在构建阶段安装 GBrain，需要能访问 `http://git.superic.com/aiplatform/gbrain.git`（可通过 `GBRAIN_REF=master` 指定分支），或者在实例 `.env` 中把 `GBRAIN_REPO` 改成内网 mirror。

## 4. 解压与授权

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
  gbrain:
    command: /usr/local/bin/gbrain
    args: []
    enabled: true

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

所有 instance 共用同一镜像 `hermes-agent-webui:latest`。**只需构建一次**，后续创建多个 instance 时直接 `up-instance` 即可，无需重复 `docker compose build`。

GBrain 安装由 [`docker/install-gbrain.sh`](docker/install-gbrain.sh) 负责（`git clone` + `npm install -g .`，失败则构建失败）。

```bash
# 推荐：重建共享镜像并自动 doctor 验收
bash scripts/rebuild-shared-image.sh zhang-zhen --no-cache

# 或：统一构建入口（构建后同样自动 doctor，失败则 exit 1）
bash scripts/build-image.sh
```

镜像更新后，让所有实例使用新镜像（**不要**只用 `docker restart`）：

```bash
bash scripts/recreate-all-instances.sh
```

单实例 force-recreate：

```bash
docker compose --env-file instances/<profile>/.env \
  -p hermes-<profile> up -d --no-build --force-recreate
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
GBRAIN_REPO=http://git.superic.com/aiplatform/gbrain.git
CLAWSEC_REPO=http://git.superic.com/aiplatform/clawsec.git
```

改成内网 Git mirror。

### 5.1 镜像验收（GBrain / Hermes Agent）

`build-image.sh` / `rebuild-shared-image.sh` 构建成功后会**自动**执行 `doctor-image.sh`，也可手动验收：

```bash
bash scripts/doctor-image.sh hermes-agent-webui:latest
```

通过标准：

```text
which bun 成功
which gbrain → /usr/local/bin/gbrain
gbrain --help 有输出
AIAgent import 成功
```

若 Dockerfile 已变更但本地仍有旧镜像，需强制重建：

```bash
bash scripts/build-image.sh --no-cache
# 或
bash scripts/up-instance.sh <profile> --build
bash scripts/up-instance.sh <profile> --no-cache
```

## 6. 启动容器

```bash
bash scripts/up-instance.sh writer
```

或构建并启动：

```bash
bash scripts/up-instance.sh writer --build
bash scripts/up-instance.sh writer --no-cache
```

`--no-cache` 会强制无缓存重建镜像（Dockerfile 变更后推荐使用）。

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

镜像级（构建后）：

```bash
bash scripts/doctor-image.sh hermes-agent-webui:latest
```

实例级：

```bash
bash scripts/doctor-instance.sh writer
```

检查 GBrain 可执行文件与 config：

```bash
docker exec -it hermes-writer bash -lc 'which gbrain && gbrain --help 2>&1 | head -80'
docker exec -it hermes-writer bash -lc 'grep -n "gbrain" -A8 -B4 /data/hermes/config.yaml'
docker logs --tail=200 hermes-writer | grep -i "gbrain\|missing executable"
```

通过标准：`command` 为 `/usr/local/bin/gbrain`，日志无 `missing executable 'gbrain'`。

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
GBRAIN_REF=master
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
  --build-arg GBRAIN_REPO="http://git.superic.com/aiplatform/gbrain.git" \
  --build-arg GBRAIN_REF=master \
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
- 若启用 GBrain，构建机需能访问 `GBRAIN_REPO`（或改为内网 mirror），并通过 `GBRAIN_REF` 指定分支（默认 `master`）

## 15. 本地 Registry 测试模式

在尚未开通火山、阿里云、Harbor 等正式镜像仓库时，可使用本地 Docker Registry 验证完整链路。

### 15.1 端口说明

`registry:2` 默认在**容器内**监听 **5000** 端口。若宿主机使用 **9900**，启动时必须使用 `-p 9900:5000` 映射。

### 15.2 快速流程

```bash
cp local-registry.env.example local-registry.env
# 编辑 LOCAL_REGISTRY_HOST、IMAGE_REPO、IMAGE_TAG、GBRAIN_REF

bash scripts/start-local-registry.sh
sudo bash scripts/configure-insecure-registry.sh
bash scripts/build-push-local-registry.sh --tag v1.4.1-hotfix-gbrain
bash scripts/doctor-image.sh <IMAGE_REPO>:<IMAGE_TAG>
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
