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

## 5. 构建镜像

```bash
docker compose --env-file instances/writer/.env -p hermes-writer build
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
