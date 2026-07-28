---
name: Expert Factory v2.1
overview: 将 copilot-docker Expert Factory 从 v2.0 基础能力升级到 v2.1 完整生产链路，包含七项标准生产 Skill（create/customize/validate/evaluate/build/branch/publish），实现从业务需求到 Nacos Registry 发布的端到端闭环。
todos:
  - id: p1-validate
    content: 阶段一：validate-expert 升级 — 新建 bundle/security/permissions/dependencies validators，扩展校验级别到 7 级，新增 3 个 JSON Schema
    status: completed
  - id: p1-build
    content: 阶段一：build-expert 升级 — 白名单打包、Source Digest 绑定、可重复构建、SBOM (CycloneDX)、签名、Nacos Package Builder
    status: completed
  - id: p1-evaluate
    content: 阶段一：evaluate-expert 升级 — Hermes Runtime Harness、Scenario 引擎、Security 对抗、Regression、Scoring 修复、Report v2
    status: completed
  - id: p1-create
    content: 阶段一：create-expert 升级 — Requirement Compiler、Component Catalog/Planner、完整 Skill 生成、场景化评测用例
    status: completed
  - id: p1-customize
    content: 阶段一：customize-expert 升级 — 结构化 spec 定制、权限扩大检测、差异报告生成
    status: completed
  - id: p1-infra
    content: 阶段一：横切基础设施 — errors.py 25 错误码、events.py 可观测性、models 扩展、pyproject.toml 2.1.0
    status: completed
  - id: p2-branch
    content: 阶段二：branch-expert — Branch Schema、Overlay、Diff、Status、Rebase (三方合并)、Materialize、CLI 子命令组
    status: completed
  - id: p3-publish
    content: 阶段三：publish-expert — Nacos 3.x Client、AgentSpec/Skill Adapter、发布流程编排、幂等/冲突/Resume、Publish Record
    status: completed
  - id: p4-ci
    content: 阶段四：CI/CD — expert-release.yml 增加 Runtime Eval + Sign + Nacos Draft；新建 expert-publish.yml (workflow_dispatch + Environment 审批)
    status: completed
  - id: tests
    content: 测试：单元测试 + 集成测试 + Runtime Test (至少 writer/finance) + Nacos Contract Test + Golden Test
    status: completed
isProject: false
---

# Expert Factory v2.1 完整生产链路改造

## 当前状态

已有 Python CLI 包 `workcopilot-expert-factory` v2.0（[pyproject.toml](expert-factory/pyproject.toml)），通过 [scripts/expert/expert](scripts/expert/expert) bash wrapper 暴露 5 个命令：`create`、`customize`、`validate`、`evaluate`、`build` + 辅助命令 `bind-check`、`inspect`、`version`。

当前源码结构：
- `expert-factory/src/workcopilot_expert_factory/` — 22 个 Python 文件
- `expert-factory/schemas/` — 5 个 JSON Schema
- `expert-factory/skills/` — 5 个 Skill SKILL.md（缺 branch-expert、publish-expert）
- CI: 两个 Workflow（`expert-factory.yml` PR/main、`expert-release.yml` tag）

---

## 改造总览（四阶段）

```mermaid
flowchart LR
  P1[阶段一: 现有能力加固] --> P2[阶段二: branch-expert]
  P2 --> P3[阶段三: publish-expert]
  P3 --> P4[阶段四: CI/CD Release]
```

---

## 阶段一：现有五项能力加固

### 1.1 create-expert 升级

**当前问题**：只从 YAML Brief 生成 Skill Stub，无需求解析、无组件复用、无完整 Skill 内容。

**改造内容**：

- 新增 `planners/` 目录：
  - `requirement_compiler.py` — 从 Markdown PRD / 自然语言提取结构化 Brief
  - `component_catalog.py` — 扫描 `expert-templates/*/skills` 和 Nacos（可选）发现可复用组件
  - `component_planner.py` — 生成 Expert Plan（含复用决策、风险分析）
- 升级 `services/create.py`：
  - 新增 `--requirements` 参数接受 Markdown PRD
  - 接受已有 Expert Plan 跳过规划
  - Skill 生成从 Stub 升级为完整九章内容（带触发条件、I/O 契约、工具规则等）
  - 生成场景化评测用例（至少 2 正常 + 1 异常 + 1 安全）
- CLI 新增选项：`--requirements`、`--plan-only`（已有）

关键文件：
- 新建 `expert-factory/src/workcopilot_expert_factory/planners/__init__.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/planners/requirement_compiler.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/planners/component_catalog.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/planners/component_planner.py`
- 改造 `expert-factory/src/workcopilot_expert_factory/services/create.py`
- 更新 `expert-factory/skills/create-expert/SKILL.md`

### 1.2 customize-expert 升级

**当前问题**：`shutil.copytree` 完整复制，无结构化差异、无权限扩大检测。

**改造内容**：

- 新建 `services/customize.py`（从 create.py 拆出 customize 逻辑）：
  - 接受 YAML spec 定义变更内容（`--spec`）
  - 生成结构化 permission-diff / component-diff
  - 权限扩大检测（默认禁止，`--allow-permission-expansion` 放行）
  - 生成 `provenance.derived_from` 完整信息
  - Skill 修改时自动补充回归用例
- CLI 新增选项：`--spec`、`--allow-permission-expansion`

关键文件：
- 新建 `expert-factory/src/workcopilot_expert_factory/services/customize.py`
- 改造 `cli.py` customize 命令

### 1.3 validate-expert 升级

**当前问题**：只有 structure/schema/security/full 四级，缺 Bundle 校验、依赖校验、发布校验。

**改造内容**：

- 扩展 `ValidateLevel` 为 7 级：`structure | schema | security | dependencies | runtime | release | full`
- 新建 validators：
  - `validators/bundle.py` — ZIP 安全（路径规范、ZIP Bomb、解压大小限制、Checksum、Payload Digest、签名）
  - `validators/security.py` — 从 expert.py 拆出安全扫描逻辑，扩展扫描范围（不再跳过 scripts/、config.yaml）
  - `validators/permissions.py` — 权限默认拒绝校验、Tool/Connector 一致性
  - `validators/dependencies.py` — Python/Node/系统包依赖、许可证、漏洞、未锁定版本
- 支持三种校验对象：Expert Source / Expert Branch / Expert Bundle
- 新增 3 个 JSON Schema：
  - `schemas/expert-branch-v1.schema.json`
  - `schemas/evaluation-report-v2.schema.json`
  - `schemas/publish-record-v1.schema.json`

关键文件：
- 新建 `expert-factory/src/workcopilot_expert_factory/validators/bundle.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/validators/security.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/validators/permissions.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/validators/dependencies.py`
- 改造 `expert-factory/src/workcopilot_expert_factory/validators/expert.py`
- 新建 3 个 Schema 文件

### 1.4 evaluate-expert 升级

**当前问题**：静态关键词匹配 + 运行时只检查文件存在/Python 编译，未实际调用 Hermes。

**改造内容**：

- 新建 Hermes Runtime Harness：
  - `evaluators/hermes_runtime.py` — 创建隔离 HERMES_HOME、注入 Expert、启动 Gateway、执行 Case、采集结果
  - `evaluators/scenario.py` — Evaluation Case v2 执行引擎
  - `evaluators/security.py` — 安全对抗用例（prompt injection、secret exfiltration）
  - `evaluators/regression.py` — 回归测试比对
- 改造 `evaluators/scoring.py`：Required Dimension 缺失 score=0（不再默认 1.0）
- Evaluation Report v2：绑定 `source_digest`、`git_commit`、`hermes_version`、`cost`
- Connector Fixture 系统：mock connector 记录调用

关键文件：
- 新建 `expert-factory/src/workcopilot_expert_factory/evaluators/hermes_runtime.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/evaluators/scenario.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/evaluators/security.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/evaluators/regression.py`
- 改造 `expert-factory/src/workcopilot_expert_factory/evaluators/scoring.py`
- 改造 `expert-factory/src/workcopilot_expert_factory/services/evaluate.py`

### 1.5 build-expert 升级

**当前问题**：全目录递归扫描（非白名单）、Evaluation 未绑定 Source Digest、Bundle 含本地路径和时间戳。

**改造内容**：

- 改造 `builders/bundle.py`：
  - 改为显式白名单打包（PRD 15.3 定义的文件列表）
  - Source Digest 只计算发布相关文件、排除绝对路径
  - `built_at` 只进 Build Report，不进 Payload
  - Evaluation Digest 绑定 Source Digest（变更即失效）
- 新建：
  - `builders/sbom.py` — CycloneDX JSON SBOM 生成
  - `builders/signature.py` — 签名逻辑（none/local-key/cosign/kms）
  - `builders/nacos_package.py` — Nacos AgentSpec ZIP 打包
- Bundle 结构升级为 PRD 15.8 规范

关键文件：
- 改造 `expert-factory/src/workcopilot_expert_factory/builders/bundle.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/builders/sbom.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/builders/signature.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/builders/nacos_package.py`

---

## 阶段二：branch-expert（新增）

实现 Expert Asset Branch（Copy-on-Write）机制。

**新增内容**：

- 新建 `services/branch.py`：
  - `branch create` — 创建 `.workcopilot/branches/<expert-id>/<branch-id>/`，只保存 overlay
  - `branch status` — 检测 synced/behind/diverged/conflicted/materialized
  - `branch diff` — 生成 diff.json + diff.md
  - `branch rebase` — YAML 字段级三方合并 + Markdown 文本合并
  - `branch materialize` — 物化为完整 Expert Source
- 新建 `schemas/expert-branch-v1.schema.json`
- CLI 新增 `branch` 子命令组（create/status/diff/rebase/materialize）
- Shell wrapper: `scripts/expert/branch-expert.sh`
- Skill 文档: `expert-factory/skills/branch-expert/SKILL.md`

关键文件：
- 新建 `expert-factory/src/workcopilot_expert_factory/services/branch.py`
- 改造 `cli.py` 新增 branch 子命令组
- 新建 `scripts/expert/branch-expert.sh`
- 新建 `expert-factory/skills/branch-expert/SKILL.md`

---

## 阶段三：publish-expert（新增）

实现 Nacos AI Registry 发布能力。

**新增内容**：

- 新建 `publishers/` 目录：
  - `publishers/base.py` — Publisher 抽象基类
  - `publishers/nacos.py` — Nacos 3.x Client（Login、AgentSpec/Skill Upload/Submit/Publish/Labels/Scope）
- 新建 `adapters/`：
  - `adapters/nacos_agentspec.py` — Bundle → Nacos AgentSpec 映射（含 x-workcopilot 扩展字段）
  - `adapters/nacos_skill.py` — Skill → Nacos Skill Package 映射
- 新建 `services/publish.py`：
  - 发布流程编排（校验→上传 Skills→上传 AgentSpec→Submit→Publish→Label→回读→Record）
  - 幂等处理、冲突检测、部分失败 Resume
  - Publish Record 生成
- Target 配置：`.workcopilot/registry/<target>.yaml`
- CLI 新增 `publish` 命令（`--target`、`--stage draft|review|online`、`--dry-run`、`--wait`、`--overwrite-draft`）
- CLI 新增 `publish resume` 子命令
- Shell wrapper: `scripts/expert/publish-expert.sh`
- Skill 文档: `expert-factory/skills/publish-expert/SKILL.md`

关键文件：
- 新建 `expert-factory/src/workcopilot_expert_factory/publishers/__init__.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/publishers/base.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/publishers/nacos.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/adapters/nacos_agentspec.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/adapters/nacos_skill.py`
- 新建 `expert-factory/src/workcopilot_expert_factory/services/publish.py`
- 改造 `cli.py` 新增 publish 命令
- 新建 `scripts/expert/publish-expert.sh`
- 新建 `expert-factory/skills/publish-expert/SKILL.md`

---

## 阶段四：CI/CD Release 链路

**改造内容**：

- 改造 `.github/workflows/expert-release.yml`：
  - 增加 Hermes Runtime Evaluation Job
  - 增加 Bundle Signing Job
  - 增加 Nacos Draft Publish Job
- 新增 `.github/workflows/expert-publish.yml`：
  - `workflow_dispatch` 触发
  - GitHub Environment 审批（nacos-dev/nacos-test/nacos-prod）
  - Release Bundle → Nacos Online
- PR workflow 保持不变（不接触 Nacos）

关键文件：
- 改造 `.github/workflows/expert-release.yml`
- 新建 `.github/workflows/expert-publish.yml`

---

## 横切面改造

### 错误码体系

新建/扩展 `errors.py`：PRD 第 17 节定义的 25 个错误码全部实现。

### 可观测性

新建 `events.py`：统一事件发射（PRD 第 21 节），所有 CLI 命令开始/完成/失败时发射结构化事件。

### 公共 CLI 选项

所有命令支持 `--format text|json|both`、`--trace-id`、`--quiet`、`--verbose`。

### Models 扩展

- `models/__init__.py` 扩展：新增 `BranchManifest`、`PublishRecord`、`EvaluationReportV2` 等 Pydantic Model
- Expert Manifest 增量字段：`release`、`provenance.branch`

### pyproject.toml

- 版本升级到 `2.1.0`
- 新增依赖：`httpx>=0.27`（Nacos HTTP Client）、`cyclonedx-bom>=7.0`（SBOM）

---

## 测试策略

- `expert-factory/tests/unit/` — 各模块单元测试
- `expert-factory/tests/integration/` — 端到端集成测试（Brief→Source→Validate→Evaluate→Build）
- `expert-factory/tests/runtime/` — Hermes Runtime 评测（需要本地 Hermes Gateway）
- `expert-factory/tests/registry/` — Nacos Contract Test（需要测试 Namespace）
- `expert-factory/tests/golden/` — Golden Test（固定 Source Digest/Bundle SHA-256 比对）

---

## 文件变更汇总

| 类别 | 新建 | 改造 |
|------|------|------|
| Python 模块 | ~20 | ~8 |
| JSON Schema | 3 | 0 |
| Shell scripts | 2 | 0 |
| Skill SKILL.md | 2 | 5 |
| CI Workflow | 1 | 1 |
| 测试文件 | ~30 | ~5 |

---

## 实施顺序建议

严格按 PRD 四阶段递进，每阶段完成后运行对应验收清单：

1. **阶段一**（最重）：先 validate 升级 → build 升级 → evaluate 升级 → create 升级 → customize 升级
2. **阶段二**：branch-expert 独立完成
3. **阶段三**：publish-expert 依赖阶段一的 Release Bundle
4. **阶段四**：CI 改造依赖阶段三

每阶段内部按「底层→上层」：Schema → Models → Validators → Builders → Services → CLI → Tests
