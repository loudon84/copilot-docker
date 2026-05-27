已按当前需求生成一套可落地代码包：

[下载 hermes-agent-webui-obsidian-hindsight-kit.zip](sandbox:/mnt/data/hermes-agent-webui-obsidian-hindsight-kit.zip)

## 1. 实施边界

本方案采用 **单容器 All-in-One 模式**：

```text
一个专家实例 = 一个 Docker 容器
容器内：
  Hermes WebUI
  Hermes Agent runtime
  Obsidian Vault 目录体系
  Hindsight external memory config
  专家 SOUL / MEMORY / USER / skills
```

不在服务器容器内运行 Obsidian GUI。Obsidian 的核心数据形态是本地 Vault 文件夹，笔记是 Markdown 纯文本，外部程序写入 Vault 后 Obsidian 会自动刷新；因此 Docker 内交付的是 **Obsidian Vault 知识库结构**，不是桌面 GUI。([Obsidian][1])

Hermes WebUI 官方 Docker 说明中，单容器模式是最简单部署方式；WebUI 支持通过 `HERMES_WEBUI_PASSWORD` 启用访问密码，并且端口对外暴露时必须设置密码。([GitHub][2]) WebUI 多容器模式存在工具执行位置限制，因此本方案使用单容器并扩展 Dockerfile，把 git、node、ripgrep、ffmpeg 等运行工具补齐。([GitHub][2])

## 2. 目录结构

代码包解压后为：

```text
/opt/hermes-agent-webui/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── README.md
├── scripts/
│   ├── install-docker-ubuntu24.sh
│   ├── create-instance.sh
│   ├── inject-expert.sh
│   ├── up-instance.sh
│   ├── down-instance.sh
│   ├── restart-instance.sh
│   ├── logs.sh
│   ├── doctor.sh
│   └── package.sh
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

每个实例独立保存：

```text
instances/<profile>/data/hermes/
├── .env
├── config.yaml
├── SOUL.md
├── memories/
│   ├── MEMORY.md
│   └── USER.md
├── hindsight/
│   └── config.json
├── skills/
├── workspace/
├── obsidian-vault/
├── sessions/
├── logs/
└── webui/
```

Hermes Docker 官方设计也是镜像无状态、用户数据通过宿主机目录挂载保存；本方案把官方 `/opt/data` 思路改成每个实例独立的 `instances/<profile>/data/hermes`。([Hermes Agent][3])

## 3. 一键部署流程

```bash
sudo mkdir -p /opt/hermes-agent-webui
sudo unzip hermes-agent-webui-obsidian-hindsight-kit.zip -d /opt

cd /opt/hermes-agent-webui

sudo bash scripts/install-docker-ubuntu24.sh

bash scripts/create-instance.sh writer 8787 writer
bash scripts/create-instance.sh finance 8788 finance

bash scripts/up-instance.sh writer
bash scripts/up-instance.sh finance
```

访问地址：

```text
http://服务器IP:8787   writer 写作专家
http://服务器IP:8788   finance 财务专家
```

查看访问密码：

```bash
cat instances/writer/.env | grep HERMES_WEBUI_PASSWORD
cat instances/finance/.env | grep HERMES_WEBUI_PASSWORD
```

## 4. Hindsight external memory 配置

每个实例自动生成：

```json
{
  "mode": "local_external",
  "api_url": "http://hindsight.superic.com:8888",
  "bank_id_template": "hermes-{profile}",
  "bank_id": "hermes-__PROFILE__",
  "recall_budget": "mid",
  "recall_prefetch_method": "recall",
  "recall_max_tokens": 4096,
  "auto_recall": true,
  "auto_retain": true,
  "retain_async": true,
  "retain_every_n_turns": 1,
  "memory_mode": "hybrid"
}
```

Hindsight 官方支持 `local_external`，即连接一个已运行的 Hindsight HTTP 服务，不由 Hermes 管理 daemon。([GitHub][4]) `bank_id_template` 支持 `{profile}` 等占位符，用于按 profile 隔离 memory bank；`auto_recall`、`auto_retain`、`retain_every_n_turns`、`memory_mode` 都是 Hindsight provider 的原生配置项。([GitHub][4])

本方案固定：

```text
writer  -> bank_id = hermes-writer
finance -> bank_id = hermes-finance
```

`memory_mode=hybrid` 表示自动上下文注入 + 显式工具同时可用；Hindsight 在该模式下提供 `hindsight_retain`、`hindsight_recall`、`hindsight_reflect`。([GitHub][4])

## 5. 专家注入机制

专家注入脚本：

```bash
bash scripts/inject-expert.sh <profile> <expert>
```

示例：

```bash
bash scripts/inject-expert.sh writer writer
bash scripts/inject-expert.sh finance finance

bash scripts/restart-instance.sh writer
bash scripts/restart-instance.sh finance
```

注入内容：

```text
expert-templates/<expert>/
├── SOUL.md
├── memories/
│   └── MEMORY.md
├── skills/
└── obsidian-vault/
```

写作专家模板参考了附件中 writer-9601 的结构：独立 runtime、workspace、Obsidian Vault、writing skills、Hindsight 记忆体系。

财务专家模板参考了附件中 finance MEMORY 规则：`SOUL.md` 放角色和行为边界，`MEMORY.md` 只放长期稳定事实；实时财务数据以 ERP/CRM/银行/MCP 为准，Obsidian/RAG/Hindsight 只作为制度、模板、历史案例和口径解释辅助。

## 6. Obsidian 知识库体系

默认 Vault：

```text
obsidian-vault/
├── 00-Inbox/
├── 10-Articles/
├── 20-Research/
├── 30-Templates/
├── 40-Content-Calendar/
├── 50-Policies/
├── 60-Reports/
└── 90-Archive/
```

写作专家重点使用：

```text
10-Articles/
20-Research/
30-Templates/article-template.md
40-Content-Calendar/
```

财务专家重点使用：

```text
50-Policies/
60-Reports/
30-Templates/finance-report-template.md
```

知识分层：

```text
Hindsight
  长期偏好、稳定口径、复盘结论、跨会话记忆

Obsidian Vault
  制度、模板、文章、报告、案例、研究资料、可审计知识资产

MEMORY.md
  2200 字以内的 profile 稳定事实和行为约束

SOUL.md
  专家身份、边界、默认工作流程、输出纪律

skills/
  可重复执行的专家任务能力
```

## 7. 运维命令

启动：

```bash
bash scripts/up-instance.sh writer
bash scripts/up-instance.sh finance
```

停止：

```bash
bash scripts/down-instance.sh writer
bash scripts/down-instance.sh finance
```

重启：

```bash
bash scripts/restart-instance.sh writer
```

日志：

```bash
bash scripts/logs.sh writer
```

检查：

```bash
bash scripts/doctor.sh writer
bash scripts/doctor.sh finance
```

重新打包：

```bash
bash scripts/package.sh
```

## 8. 验收标准

```text
1. docker compose ps 显示 writer、finance 容器为 running。
2. http://服务器IP:8787 可打开 writer WebUI，并要求密码登录。
3. http://服务器IP:8788 可打开 finance WebUI，并要求密码登录。
4. instances/writer/data/hermes/hindsight/config.json 中 mode=local_external。
5. instances/finance/data/hermes/hindsight/config.json 中 bank_id=hermes-finance。
6. writer 实例存在 skills/writing/*。
7. finance 实例存在 skills/finance/*。
8. Obsidian Vault 目录可被 Hermes 写入 Markdown。
9. WebUI 会话中询问专家身份，writer 返回写作专家边界，finance 返回财务专家边界。
10. 完成一轮对话后，Hindsight 外部服务能按 hermes-writer 或 hermes-finance 查询到 retained memory。
```

代码包已包含 Dockerfile、Compose、Ubuntu 24.04 Docker 安装脚本、实例创建脚本、专家注入脚本、writer/finance 专家模板和 Obsidian Vault 模板。

[1]: https://obsidian.md/help/data-storage "How Obsidian stores data - Obsidian Help"
[2]: https://github.com/nesquena/hermes-webui "GitHub - nesquena/hermes-webui: Hermes WebUI: The best way to use Hermes Agent from the web or from your phone! · GitHub"
[3]: https://hermes-agent.nousresearch.com/docs/user-guide/docker "Docker | Hermes Agent"
[4]: https://github.com/NousResearch/hermes-agent/blob/main/plugins/memory/hindsight/README.md "hermes-agent/plugins/memory/hindsight/README.md at main · NousResearch/hermes-agent · GitHub"
