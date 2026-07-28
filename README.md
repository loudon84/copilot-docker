# WorkCopilot Expert Factory（copilot-docker）

`copilot-docker` 是 **WorkCopilot 专家源码生产系统**：负责专家/Skill 源码、定制、结构校验与 Expert Bundle 构建，并继续提供 Hermes Agent 容器镜像与多实例运行时部署能力。

```text
需求 → create-expert → Expert Source → customize-expert
     → validate-expert → build-expert → .expert.bundle
     → nodeskclaw Registry → Connector/Secret 绑定 → Hermes 实例
```

设计文档：[prd/v2.0_work-expert-factory.md](prd/v2.0_work-expert-factory.md) · 工具包说明：[expert-factory/README.md](expert-factory/README.md)

## 产品边界

| 系统 | 定位 | 负责 |
|------|------|------|
| **copilot-docker** | Expert Factory + Hermes Runtime Kit | 专家源码、协议、校验、构建、镜像与本地/服务器实例部署 |
| **nodeskclaw** | Expert Control Plane | Registry、审批、Connector/Secret 绑定、部门授权、生产部署与审计 |
| **Hermes Agent** | Expert Runtime | 对话编排、Skill/Tool/Plugin/MCP 执行、会话与记忆 |

本仓库**不**实现：在线专家市场、生产 Secret 配置、nodeskclaw 审批后端、完整在线低代码编辑器。

## 统一协议（v2.0）

| 协议 | 说明 |
|------|------|
| `workcopilot.expert.v1` | 专家 Manifest（`expert-templates/<id>/expert.yaml`） |
| `workcopilot.skill.v1` | Skill Frontmatter + 标准正文章节 |
| Connector Slot | 只声明所需能力，不绑定生产地址/Secret |
| Expert Bundle v1 | 可注册发布包（`.expert.bundle` ZIP） |
| Asset Bundle | **保留**：实例间运行资产迁移（与 Expert Bundle 分离） |

Schema 与 CLI：`expert-factory/` · nodeskclaw 导入契约：[expert-factory/docs/nodeskclaw-api.md](expert-factory/docs/nodeskclaw-api.md)

## Expert Factory 快速开始

```bash
cd expert-factory && pip install -e ".[dev]"

# 从 Brief 脚手架（Agent 再按 skills/create-expert 补全正文）
bash scripts/expert/expert create --brief expert-factory/skills/create-expert/examples/brief.yaml \
  --output expert-templates/finance-receivable-risk-demo

# 校验 / 评测 / 构建开发包
bash scripts/expert/expert validate expert-templates/writer --level full
bash scripts/expert/expert evaluate expert-templates/writer --mode static
bash scripts/expert/expert build expert-templates/writer --output dist/experts --dev

# 发布包（需先 evaluate --mode full）
bash scripts/expert/expert evaluate expert-templates/writer --mode full
bash scripts/expert/expert build expert-templates/writer --output dist/experts --release

# 定制派生（不改源专家）
bash scripts/expert/expert customize expert-templates/writer \
  --output expert-templates/writer-acme --notes "组织定制"
```

创建约束见 `.cursor/rules/expert-factory-create.mdc`。评测与发布：`evaluate --mode static|full`，`build --release` 读取评测门禁。

CI：PR 全量 validate/evaluate；`master`/`main` 上传 dev Bundle Artifact；Tag `expert/<id>/v<version>` 发 GitHub Release（见 [expert-factory/README.md](expert-factory/README.md)）。

注入：v1 单专家精确注入（Manifest components/entrypoints）；Connector 用 `bind-check` 检查实例 `.env` 缺项（bi 见 `connectors/finance-query.example.yaml`）。

## 专家模板索引

各专家完整说明见模板目录 `README.md`。根表**仅登记**路径与简述。

**编写约束**：业务专家 `SOUL.md` / `AGENTS.md` / `SKILL.md` 正文须为**简体中文**；禁止 Form Feed 等控制/零宽字符。已迁移专家须含 `workcopilot.expert.v1`。

| 模板路径 | 简述 | 说明 |
|----------|------|------|
| `expert-templates/writer/` | 中文写作与内容生产（v1） | [README](expert-templates/writer/README.md) |
| `expert-templates/finance/` | 财务运营（账龄、回款、现金流）（v1） | [README](expert-templates/finance/README.md) |
| `expert-templates/sale/` | 企业销售助手（v1） | [README](expert-templates/sale/README.md) |
| `expert-templates/bi-strategic-office/` | 财务 BI 智能问数（SQLBot；v1 + package.yaml） | [README](expert-templates/bi-strategic-office/README.md) |
| `expert-templates/ceo-strategic-office/` | CEO 战略办公室专家团队（v1 team） | [README](expert-templates/ceo-strategic-office/README.md) |

基础设施模板 `base/`、`default/` 供注入脚本内部使用。

## Hermes 实例部署（运行时）

目标环境：Ubuntu 24.04 多实例 Hermes WebUI；每实例独立 `HERMES_HOME`、workspace、sessions、skills、memories。

```bash
sudo bash scripts/install-docker-ubuntu24.sh
bash scripts/build-image.sh
bash scripts/create-instance.sh writer 8787 writer
bash scripts/up-instance.sh writer
bash scripts/create-instance.sh finance 8788 finance
bash scripts/up-instance.sh finance
bash scripts/create-instance.sh sale 9602 sale
bash scripts/up-instance.sh sale
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office
# 配置 instances/bi-strategic-office/.env 中 SQLBOT_* 后：
bash scripts/sync-runtime-env.sh bi-strategic-office
bash scripts/up-instance.sh bi-strategic-office
```

```text
http://服务器IP:8787  # writer
http://服务器IP:8788  # finance
http://服务器IP:9602  # sale
http://服务器IP:8790  # bi-strategic-office
```

```bash
bash scripts/inject-expert.sh writer writer
bash scripts/restart-instance.sh writer
```

注入前会执行 `validate --level structure`。镜像构建参数见 [docs/build-image.md](docs/build-image.md)；Agent API 见 [docs/agent-api-server.md](docs/agent-api-server.md)。

## 镜像推送与本地 Registry

```bash
cp registry.env.example registry.env
bash scripts/build-push-registry.sh --login
```

详见 [README_DEPLOY.md](README_DEPLOY.md)。本地 Registry：[README_LOCAL_REGISTRY.md](README_LOCAL_REGISTRY.md)。

## Bundle 对照

| 类型 | 用途 | 入口 |
|------|------|------|
| **Expert Bundle** | 专家产品版本发布 | `scripts/expert/expert build` → `dist/experts/*.expert.bundle` |
| **Asset Bundle** | 实例间迁移 skills/tools/plugins… | `export-assets.sh` / `import-assets.sh`（Legacy Runtime Asset Flow） |

详见 [README_ASSET_BUNDLES.md](README_ASSET_BUNDLES.md)。

## 目录结构（摘要）

```text
copilot-docker/
├── expert-factory/          # 协议、CLI、Factory Skills、脚手架
├── expert-templates/        # 专家源码
├── scripts/expert/          # expert / create|validate|build|customize
├── dist/experts/            # Expert Bundle 输出
├── asset-bundles/           # Asset Bundle（运行资产）
├── instances/               # 运行实例（私有数据，勿提交 Secret）
├── docker-compose.yml
└── Dockerfile
```
