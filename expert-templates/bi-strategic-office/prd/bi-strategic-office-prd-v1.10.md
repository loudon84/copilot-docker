# PRD v1.10：bi-strategic-office 专家包归集改造

## 1. 文档信息

| 项目     | 内容                                     |
| ------ | -------------------------------------- |
| 项目仓库   | `loudon84/copilot-docker`              |
| 专家模板   | `expert-templates/bi-strategic-office` |
| PRD 版本 | v1.10                                  |
| 改造类型   | 目录归集与生命周期改造                            |
| 实施工具   | Cursor                                 |
| 目标分支   | `master`                               |

---

## 2. 改造背景

当前 `bi-strategic-office` 的实现分散在多个目录：

```text
expert-templates/bi-strategic-office/
asset-bundles/
scripts/
tests/
prd/
```

存在以下问题：

1. 专家角色、插件、语义目录、安装脚本和测试没有统一归档。
2. 修改专家功能时，需要同时修改多个公共目录。
3. 专家安装逻辑与公共实例脚本耦合。
4. 插件、语义目录和专家模板无法作为一个完整版本发布。
5. 新增专家时容易继续向公共脚本添加业务判断。
6. 无法明确判断实例使用的是哪一版专家模板。

本次改造将 `bi-strategic-office` 调整为自包含专家包。

---

## 3. 过渡期约束

本版本处于过渡阶段，公共脚本修改范围严格限制为：

```text
scripts/create-instance.sh
scripts/up-instance.sh
```

本版本不得修改其他公共脚本，包括但不限于：

```text
scripts/inject-expert.sh
scripts/sync-bi-semantic-catalog.sh
scripts/check-finance-bi.sh
scripts/restart-instance.sh
scripts/build-image.sh
scripts/sync-runtime-env.sh
scripts/lib/*
```

处理原则：

* 现有公共脚本保留原状。
* `bi-strategic-office` 新流程不再依赖公共 BI 专属脚本。
* 原公共 BI 脚本作为过渡兼容文件保留。
* 本版本不删除、不重写这些公共脚本。
* 后续版本再统一清理废弃文件。

---

## 4. 产品目标

完成以下结果：

1. `bi-strategic-office` 成为一个完整、自包含的专家包。
2. 专家相关的角色、Skills、插件、语义目录、策略、安装脚本、测试、文档统一放入专家目录。
3. `create-instance.sh` 支持自动识别新专家包。
4. `up-instance.sh` 支持调用专家包的启动后初始化脚本。
5. 现有 `writer`、`finance`、`sale` 模板保持原流程。
6. 现有公共脚本除 `create-instance.sh`、`up-instance.sh` 外不做修改。
7. 新专家包安装过程支持重复执行。
8. 专家模板更新不得覆盖用户运行数据。
9. Finance BI Plugin、Semantic Catalog 和专家模板使用统一版本管理。

---

## 5. 非目标

本版本不处理：

* 清理现有公共 BI 脚本
* 重构所有专家模板
* 修改 `writer`、`finance`、`sale` 目录
* 新增统一的全仓库专家包管理器
* 修改 Docker Compose 架构
* 修改 Hermes Agent 核心代码
* 修改 Hermes Plugin API
* 修改现有实例目录结构
* 修改 BI 查询业务逻辑
* 修复 NL2SemanticQuery、过滤器或 Query State 问题
* 调整模型配置
* 删除旧 `asset-bundles` 内容
* 删除旧根目录测试

本次只处理专家包归集和安装入口。

---

## 6. 设计原则

### 6.1 专家包自包含

`bi-strategic-office` 的新增代码和后续修改，只允许进入：

```text
expert-templates/bi-strategic-office/
```

包括：

* 专家身份
* 团队角色
* Skills
* Plugin
* Semantic Catalog
* Policies
* 安装脚本
* 启动后脚本
* 更新脚本
* 诊断脚本
* 测试
* Fixtures
* 文档
* PRD

### 6.2 公共脚本无业务知识

`create-instance.sh` 和 `up-instance.sh` 中不得出现：

```text
bi-strategic-office
finance-bi
hermes-finance-bi-plugin
ar_trx_number
semantic catalog
```

公共脚本只能：

* 定位专家目录
* 判断专家是否使用新包格式
* 调用专家包规定的生命周期脚本
* 传递实例路径和 Profile 参数

### 6.3 兼容旧模板

旧专家继续使用原有逻辑。

新旧模板识别规则：

```text
存在 expert.yaml
并且存在 bin/install.sh
→ 使用新专家包模式

否则
→ 使用现有旧模板模式
```

### 6.4 模板和运行数据分离

专家包可以覆盖模板资产，但不得覆盖用户运行数据。

---

## 7. 目标目录结构

```text
expert-templates/
└── bi-strategic-office/
    ├── expert.yaml
    ├── VERSION
    ├── CHANGELOG.md
    ├── README.md
    │
    ├── runtime/
    │   ├── SOUL.md
    │   ├── config.patch.yaml
    │   │
    │   ├── memories/
    │   │   └── MEMORY.md
    │   │
    │   ├── skills/
    │   │   ├── bi-office-orchestration/
    │   │   ├── finance-bi-query/
    │   │   ├── finance-performance-analysis/
    │   │   ├── semantic-governance/
    │   │   ├── data-quality-review/
    │   │   └── management-reporting/
    │   │
    │   ├── team/
    │   │   ├── team.yaml
    │   │   └── roles/
    │   │       ├── bi-query-analyst.md
    │   │       ├── finance-performance-analyst.md
    │   │       ├── semantic-governance-specialist.md
    │   │       └── data-quality-reviewer.md
    │   │
    │   ├── policies/
    │   │   ├── query-policy.yaml
    │   │   ├── row-policy.yaml
    │   │   ├── column-policy.yaml
    │   │   └── masking-policy.yaml
    │   │
    │   └── semantic/
    │       ├── datasources/
    │       ├── datasets/
    │       ├── dimensions/
    │       ├── metrics/
    │       ├── joins/
    │       ├── glossary/
    │       └── examples/
    │
    ├── plugins/
    │   └── hermes-finance-bi-plugin/
    │       ├── plugin.yaml
    │       ├── pyproject.toml
    │       ├── requirements.txt
    │       ├── hermes_finance_bi/
    │       └── tests/
    │
    ├── bin/
    │   ├── install.sh
    │   ├── post-start.sh
    │   ├── update.sh
    │   ├── validate.sh
    │   ├── doctor.sh
    │   ├── test.sh
    │   └── sync-semantic-catalog.sh
    │
    ├── lib/
    │   ├── merge_yaml.py
    │   ├── package_state.py
    │   └── validate_manifest.py
    │
    ├── tests/
    │   ├── unit/
    │   ├── integration/
    │   ├── deployment/
    │   ├── security/
    │   └── fixtures/
    │
    ├── docs/
    │   ├── architecture.md
    │   ├── installation.md
    │   ├── upgrade.md
    │   ├── semantic-catalog.md
    │   └── troubleshooting.md
    │
    └── prd/
        └── bi-strategic-office-prd-v1.10.md
```

---

## 8. 专家包清单

新增：

```text
expert-templates/bi-strategic-office/expert.yaml
```

内容：

```yaml
schema_version: 1

expert:
  id: bi-strategic-office
  name: 财务经营分析办公室
  version: 1.10.0
  type: expert-team
  description: 财务分析、BI智能问数和经营分析专家团队

compatibility:
  python: ">=3.11"

runtime:
  soul: runtime/SOUL.md
  memory: runtime/memories/MEMORY.md
  config_patch: runtime/config.patch.yaml

assets:
  skills:
    source: runtime/skills
    target: skills

  team:
    source: runtime/team
    target: team/bi-strategic-office

  policies:
    source: runtime/policies
    target: finance-bi/policies

  semantic:
    source: runtime/semantic
    target: finance-bi/semantic

plugins:
  - id: hermes-finance-bi-plugin
    source: plugins/hermes-finance-bi-plugin
    target: plugins/hermes-finance-bi-plugin

lifecycle:
  install: bin/install.sh
  post_start: bin/post-start.sh
  update: bin/update.sh
  validate: bin/validate.sh
  doctor: bin/doctor.sh
  test: bin/test.sh

runtime_directories:
  - finance-bi/state
  - finance-bi/cache
  - workspace/exports/bi
  - workspace/uploads

security:
  allow_raw_sql: false
  require_read_only_database: true
  secrets_in_package: false
```

公共脚本本版本不解析完整 YAML。

公共脚本只通过以下固定路径判断新包：

```text
expert.yaml
bin/install.sh
bin/post-start.sh
```

---

## 9. 版本文件

新增：

```text
expert-templates/bi-strategic-office/VERSION
```

内容：

```text
1.10.0
```

新增：

```text
expert-templates/bi-strategic-office/CHANGELOG.md
```

至少记录：

```markdown
# 1.10.0

- 将 Finance BI Plugin 归入专家包
- 将 Semantic Catalog 归入专家包
- 将专家专属测试归入专家包
- 增加专家包安装和启动后生命周期
- create-instance.sh 支持新专家包
- up-instance.sh 支持专家启动后初始化
```

---

## 10. 文件迁移规则

### 10.1 迁入专家包

将现有实现复制到以下新位置，并将新位置设为后续唯一维护位置。

| 当前内容              | 新位置                                                                      |
| ----------------- | ------------------------------------------------------------------------ |
| Finance BI Plugin | `expert-templates/bi-strategic-office/plugins/hermes-finance-bi-plugin/` |
| Semantic Catalog  | `expert-templates/bi-strategic-office/runtime/semantic/`                 |
| BI Policies       | `expert-templates/bi-strategic-office/runtime/policies/`                 |
| BI Skills         | `expert-templates/bi-strategic-office/runtime/skills/`                   |
| 专家团队角色            | `expert-templates/bi-strategic-office/runtime/team/`                     |
| BI 注入测试           | `expert-templates/bi-strategic-office/tests/deployment/`                 |
| BI Plugin 测试      | 插件目录 `tests/` 或专家包 `tests/integration/`                                  |
| Semantic 同步脚本     | `expert-templates/bi-strategic-office/bin/sync-semantic-catalog.sh`      |
| BI 检查脚本           | `expert-templates/bi-strategic-office/bin/doctor.sh`                     |
| PRD               | `expert-templates/bi-strategic-office/prd/`                              |

### 10.2 过渡期旧文件处理

v1.10 不删除以下旧文件：

```text
scripts/inject-expert.sh
scripts/sync-bi-semantic-catalog.sh
scripts/check-finance-bi.sh
asset-bundles 中现有 Finance BI 内容
根目录现有 BI 测试
```

要求：

* 不修改旧文件。
* 新流程不再依赖旧文件。
* 新增文档标明新位置为主版本。
* 后续修改只允许修改专家包内的新版本。
* 旧文件在 v1.11 或以后清理。

### 10.3 禁止双向同步

不得实现：

```text
专家包 → asset-bundles
asset-bundles → 专家包
```

新专家包为唯一源代码来源。

旧目录仅保留静态兼容副本。

---

## 11. 实例目标目录

专家包安装到实例后：

```text
instances/<profile>/data/hermes/
├── SOUL.md
├── config.yaml
├── memories/
│   └── MEMORY.md
├── skills/
├── plugins/
│   └── hermes-finance-bi-plugin/
├── team/
│   └── bi-strategic-office/
├── finance-bi/
│   ├── semantic/
│   ├── policies/
│   ├── state/
│   ├── cache/
│   └── package-state.yaml
└── workspace/
    ├── uploads/
    └── exports/
        └── bi/
```

---

## 12. 运行数据保护规则

以下文件可以由专家安装脚本覆盖：

```text
SOUL.md
模板 Skills
模板 Team Roles
Finance BI Plugin
Semantic Catalog
Policies
```

以下文件只能合并：

```text
config.yaml
用户自定义 Semantic Override
用户自定义 Policy Override
```

以下文件不得覆盖：

```text
.env
sessions/
logs/
workspace/uploads/
workspace/exports/
finance-bi/state/
finance-bi/cache/
用户 memory
审计数据
数据库连接配置
```

---

## 13. 包状态文件

安装完成后写入：

```text
/data/hermes/finance-bi/package-state.yaml
```

内容：

```yaml
expert_id: bi-strategic-office
expert_version: 1.10.0
plugin:
  id: hermes-finance-bi-plugin
  version: 1.10.0
semantic_catalog_version: 1.10.0
installed_at: "2026-07-21T00:00:00Z"
package_source: expert-templates/bi-strategic-office
package_hash: ""
```

要求：

* 每次安装或更新后刷新。
* 不包含密码。
* 使用原子写入。
* 安装失败时不得写入成功状态。

---

## 14. 专家安装脚本

文件：

```text
expert-templates/bi-strategic-office/bin/install.sh
```

调用方式：

```bash
install.sh \
  --profile <profile> \
  --instance-dir <instance-dir> \
  --data-dir <data-dir> \
  --repo-root <repo-root>
```

### 14.1 install.sh 职责

1. 校验参数。
2. 定位专家包根目录。
3. 执行 `bin/validate.sh`。
4. 创建运行目录。
5. 备份现有模板资产。
6. 安装 `SOUL.md`。
7. 安装默认 `MEMORY.md`。
8. 安装 Skills。
9. 安装 Team Roles。
10. 安装 Policies。
11. 安装 Semantic Catalog。
12. 安装 Plugin 源码。
13. 深度合并 `config.patch.yaml`。
14. 写入 package-state。
15. 不启动容器。
16. 不执行容器内命令。

### 14.2 install.sh 幂等要求

重复执行必须满足：

* 不重复追加 YAML 配置。
* 不重复创建相同目录。
* 不覆盖 `.env`。
* 不清空 state。
* 不清空 exports。
* 不清空 uploads。
* 不清空 sessions。
* 同版本重复安装结果一致。

### 14.3 install.sh 失败处理

任一步骤失败：

* 返回非零状态码。
* 输出明确失败步骤。
* 不写成功状态文件。
* 已有实例数据不得删除。
* 临时文件必须清理。

---

## 15. 启动后脚本

文件：

```text
expert-templates/bi-strategic-office/bin/post-start.sh
```

调用方式：

```bash
post-start.sh \
  --profile <profile> \
  --instance-dir <instance-dir> \
  --data-dir <data-dir> \
  --repo-root <repo-root> \
  --container <container-name>
```

### 15.1 post-start.sh 职责

容器启动并通过基础健康检查后执行：

1. 检查容器是否运行。
2. 检查 `/data/hermes` 是否正确挂载。
3. 安装 Plugin Python 依赖。
4. 检查插件目录权限。
5. 启用 `hermes-finance-bi-plugin`。
6. 检查 `Finance-Bi` Toolset。
7. 检查 Semantic Catalog 路径。
8. 检查 state 目录可写。
9. 执行 `bin/doctor.sh`。
10. 输出安装结果。

### 15.2 依赖安装策略

优先使用：

```bash
/app/venv/bin/python -m pip install \
  -r /data/hermes/plugins/hermes-finance-bi-plugin/requirements.txt
```

要求：

* 使用 Hermes 当前 Python 环境。
* 不使用系统 Python。
* 不执行无版本约束的依赖安装。
* 不启用运行时懒安装。
* 同一 requirements hash 不重复安装。

建议记录依赖 hash：

```text
/data/hermes/finance-bi/.requirements.sha256
```

### 15.3 插件检查

至少执行：

```bash
hermes plugins list
hermes tools --summary
```

必须确认：

```text
插件：hermes-finance-bi-plugin
Toolset：Finance-Bi
```

插件名称和 Toolset 名称允许不同。

---

## 16. validate.sh

文件：

```text
expert-templates/bi-strategic-office/bin/validate.sh
```

检查：

* `expert.yaml` 存在。
* `VERSION` 存在。
* `SOUL.md` 存在。
* `MEMORY.md` 存在。
* Plugin 目录存在。
* `plugin.yaml` 存在。
* `requirements.txt` 存在。
* Skills 目录存在。
* Semantic 目录存在。
* Policies 目录存在。
* 生命周期脚本存在。
* Shell 脚本具有执行权限。
* YAML 文件可以解析。
* 专家包不包含 `.env`。
* 专家包不包含数据库密码。
* 专家包不包含运行状态数据库。
* 专家包不包含用户上传文件。

失败时返回非零状态码。

---

## 17. doctor.sh

文件：

```text
expert-templates/bi-strategic-office/bin/doctor.sh
```

支持两种模式：

```bash
doctor.sh --package-only
```

检查源码包。

```bash
doctor.sh --profile <profile> --container <container>
```

检查运行实例。

运行检查包括：

* 容器状态
* 数据目录挂载
* 插件加载
* Toolset 注册
* Semantic Catalog
* Policies
* Python 依赖
* state 目录权限
* export 目录权限
* 必需环境变量是否存在
* 不打印变量值
* 数据库连接可选检查

---

## 18. update.sh

文件：

```text
expert-templates/bi-strategic-office/bin/update.sh
```

本版本不由公共脚本自动调用。

手工调用：

```bash
update.sh \
  --profile <profile> \
  --instance-dir <instance-dir> \
  --data-dir <data-dir> \
  --repo-root <repo-root>
```

职责：

1. 读取当前 package-state。
2. 比较版本。
3. 备份模板资产。
4. 更新 Plugin。
5. 更新 Skills。
6. 更新 Team Roles。
7. 更新 Policies。
8. 更新 Semantic Catalog。
9. 深度合并配置。
10. 保留运行数据。
11. 更新 package-state。
12. 提示重新执行 `up-instance.sh`。

---

## 19. sync-semantic-catalog.sh

文件：

```text
expert-templates/bi-strategic-office/bin/sync-semantic-catalog.sh
```

调用：

```bash
sync-semantic-catalog.sh \
  --profile <profile> \
  --instance-dir <instance-dir> \
  --data-dir <data-dir>
```

职责：

* 校验源 Semantic Catalog。
* 备份实例现有 Catalog。
* 将专家包 Catalog 同步到实例。
* 不修改其他专家实例。
* 不调用公共 `scripts/sync-bi-semantic-catalog.sh`。
* 同步失败时保留旧 Catalog。
* 同步后执行 Catalog 校验。

---

## 20. config.patch.yaml

路径：

```text
expert-templates/bi-strategic-office/runtime/config.patch.yaml
```

配置只包含专家默认值。

不得包含：

* 模型 API Key
* BI DSN
* 数据库密码
* 用户权限列表
* 实例端口
* 容器名称

示例：

```yaml
plugins:
  enabled:
    - hermes-finance-bi-plugin

toolsets:
  - file
  - terminal
  - skills
  - session_search
  - todo
  - delegation
  - finance-bi

agent:
  max_turns: 24
  gateway_timeout: 600
  gateway_timeout_warning: 300
  environment_probe: false

delegation:
  max_iterations: 20
  max_concurrent_children: 3
  max_spawn_depth: 1
  orchestrator_enabled: true

memory:
  nudge_interval: 0

privacy:
  redact_pii: true
```

配置合并要求：

* 字典递归合并。
* 标量由专家配置覆盖。
* 列表按字段规则处理。
* `plugins.enabled` 去重合并。
* `toolsets` 去重合并。
* 不整体替换用户 `config.yaml`。
* 合并前创建备份。

---

## 21. create-instance.sh 修改要求

允许修改：

```text
scripts/create-instance.sh
```

禁止在脚本中增加任何 BI 专属逻辑。

### 21.1 新增专家包识别

增加：

```bash
EXPERT_DIR="$BASE_DIR/expert-templates/$EXPERT"
EXPERT_MANIFEST="$EXPERT_DIR/expert.yaml"
EXPERT_INSTALLER="$EXPERT_DIR/bin/install.sh"
```

判断：

```bash
if [[ -f "$EXPERT_MANIFEST" && -x "$EXPERT_INSTALLER" ]]; then
    PACKAGE_MODE=true
else
    PACKAGE_MODE=false
fi
```

### 21.2 新包安装流程

当 `PACKAGE_MODE=true`：

```bash
"$EXPERT_INSTALLER" \
  --profile "$PROFILE" \
  --instance-dir "$INSTANCE_DIR" \
  --data-dir "$DATA_DIR" \
  --repo-root "$BASE_DIR"
```

### 21.3 旧模板流程

当 `PACKAGE_MODE=false`：

* 完整保留当前创建逻辑。
* 完整保留当前 `inject-expert.sh` 调用。
* 不改变参数。
* 不改变目录。
* 不改变 Writer、Finance、Sale 行为。

### 21.4 禁止事项

`create-instance.sh` 中不得出现：

```bash
if [[ "$EXPERT" == "bi-strategic-office" ]]
```

不得增加：

```bash
case "$EXPERT" in
```

不得直接复制：

```text
Finance BI Plugin
Semantic Catalog
Policies
BI Skills
```

这些均由专家包 `install.sh` 处理。

---

## 22. up-instance.sh 修改要求

允许修改：

```text
scripts/up-instance.sh
```

### 22.1 读取专家名称

从实例 `.env` 读取：

```text
HERMES_EXPERT
```

若当前变量名称不同，以现有变量为准，不新增重复字段。

### 22.2 定位专家包

```bash
EXPERT_DIR="$BASE_DIR/expert-templates/$HERMES_EXPERT"
POST_START="$EXPERT_DIR/bin/post-start.sh"
```

### 22.3 调用时机

原有 Docker 启动流程完成后：

1. 容器已启动。
2. 基础健康检查通过。
3. `/data/hermes` 已挂载。
4. 再执行 `post-start.sh`。

调用：

```bash
if [[ -f "$EXPERT_DIR/expert.yaml" && -x "$POST_START" ]]; then
    "$POST_START" \
      --profile "$PROFILE" \
      --instance-dir "$INSTANCE_DIR" \
      --data-dir "$DATA_DIR" \
      --repo-root "$BASE_DIR" \
      --container "$CONTAINER_NAME"
fi
```

### 22.4 旧专家行为

没有 `expert.yaml` 或没有 `post-start.sh` 时：

* 跳过专家包启动后步骤。
* 保持现有流程。
* 不产生错误。
* 不改变现有实例。

### 22.5 失败策略

新专家包 `post-start.sh` 失败时：

* `up-instance.sh` 返回非零。
* 不停止已经运行的容器。
* 输出明确修复命令。
* 提示执行专家包 `doctor.sh`。
* 不静默忽略插件安装失败。

---

## 23. 本版本不修改的公共脚本

以下脚本必须保持 Git 内容不变：

```text
scripts/inject-expert.sh
scripts/sync-bi-semantic-catalog.sh
scripts/check-finance-bi.sh
scripts/restart-instance.sh
scripts/build-image.sh
scripts/sync-runtime-env.sh
```

Cursor 完成后执行：

```bash
git diff --name-only
```

公共 `scripts/` 目录中只允许出现：

```text
scripts/create-instance.sh
scripts/up-instance.sh
```

如出现其他公共脚本变动，本任务不通过。

---

## 24. 测试目录

所有新增 BI 专家测试放入：

```text
expert-templates/bi-strategic-office/tests/
```

目录：

```text
tests/
├── unit/
│   ├── test_manifest.py
│   ├── test_config_merge.py
│   └── test_package_state.py
│
├── deployment/
│   ├── test_install.py
│   ├── test_install_idempotent.py
│   ├── test_post_start.py
│   └── test_update.py
│
├── integration/
│   ├── test_plugin_registration.py
│   ├── test_toolset_registration.py
│   └── test_semantic_catalog_sync.py
│
├── security/
│   ├── test_secret_scan.py
│   ├── test_runtime_data_preservation.py
│   └── test_path_boundaries.py
│
└── fixtures/
```

---

## 25. 必须覆盖的测试

### 25.1 安装测试

验证：

* 新实例目录可以安装专家包。
* SOUL 正确复制。
* Skills 正确复制。
* Plugin 正确复制。
* Semantic Catalog 正确复制。
* Policies 正确复制。
* package-state 正确生成。

### 25.2 幂等测试

连续执行两次 `install.sh`：

* 无重复配置。
* 无重复插件。
* 无异常退出。
* 用户数据未删除。

### 25.3 数据保护测试

安装前创建：

```text
.env
sessions/test.json
workspace/uploads/test.xlsx
workspace/exports/bi/report.xlsx
finance-bi/state/finance_bi.db
```

安装后必须全部保留。

### 25.4 配置合并测试

原配置：

```yaml
model:
  default: local-model

plugins:
  enabled:
    - existing-plugin
```

安装后：

```yaml
model:
  default: local-model

plugins:
  enabled:
    - existing-plugin
    - hermes-finance-bi-plugin
```

不得覆盖模型配置。

### 25.5 旧专家回归

至少验证：

```bash
bash scripts/create-instance.sh writer-test 9787 writer
bash scripts/create-instance.sh finance-test 9788 finance
bash scripts/create-instance.sh sale-test 9789 sale
```

执行路径保持原样。

### 25.6 新专家验收

```bash
bash scripts/create-instance.sh \
  bi-strategic-office-test \
  9790 \
  bi-strategic-office

bash scripts/up-instance.sh \
  bi-strategic-office-test
```

必须完成：

* 容器启动
* Plugin 启用
* Toolset 注册
* Semantic Catalog 可读取
* doctor 通过

---

## 26. Cursor 实施任务

### T01：建立目标目录

创建：

```text
expert-templates/bi-strategic-office/runtime/
expert-templates/bi-strategic-office/plugins/
expert-templates/bi-strategic-office/bin/
expert-templates/bi-strategic-office/lib/
expert-templates/bi-strategic-office/tests/
expert-templates/bi-strategic-office/docs/
expert-templates/bi-strategic-office/prd/
```

### T02：创建专家清单和版本

创建：

```text
expert.yaml
VERSION
CHANGELOG.md
README.md
```

### T03：归集 Runtime 资产

将当前专家角色、Skills、Team、Semantic 和 Policies 复制到 `runtime/`。

不修改业务内容。

### T04：归集 Plugin

将当前 `hermes-finance-bi-plugin` 复制到：

```text
plugins/hermes-finance-bi-plugin/
```

修正插件内部相对路径。

新目录成为后续唯一修改位置。

### T05：建立生命周期脚本

实现：

```text
bin/install.sh
bin/post-start.sh
bin/update.sh
bin/validate.sh
bin/doctor.sh
bin/test.sh
bin/sync-semantic-catalog.sh
```

### T06：实现配置合并

实现：

```text
lib/merge_yaml.py
```

要求：

* 支持递归字典合并。
* 支持列表去重。
* 原子写入。
* 合并前备份。
* 不处理 secrets。

### T07：实现包状态

实现：

```text
lib/package_state.py
```

管理：

```text
finance-bi/package-state.yaml
```

### T08：修改 create-instance.sh

只增加：

* 新包识别。
* 新包安装器调用。
* 旧流程回退。

不得增加 BI 专属分支。

### T09：修改 up-instance.sh

只增加：

* 专家包定位。
* `post-start.sh` 调用。
* 失败状态处理。

不得增加 BI 专属命令。

### T10：迁移测试

将新增和后续 BI 专属测试放入专家包。

旧测试本版本不删除。

### T11：补充文档

完成：

```text
docs/architecture.md
docs/installation.md
docs/upgrade.md
docs/troubleshooting.md
```

### T12：执行回归

执行：

* 专家包单元测试
* 专家包部署测试
* Writer 创建测试
* Finance 创建测试
* Sale 创建测试
* BI 创建和启动测试

---

## 27. Cursor 修改限制

Cursor 必须遵守：

1. 修改前先读取现有目录和脚本。
2. 不修改 Hermes Agent 源码。
3. 不修改除 `create-instance.sh`、`up-instance.sh` 之外的公共脚本。
4. 不在公共脚本写专家名称。
5. 不在公共脚本写插件名称。
6. 不改变旧专家安装流程。
7. 不删除旧兼容文件。
8. 不提交 `.env`。
9. 不提交数据库密码。
10. 不覆盖实例运行数据。
11. 不用提示词修改代替目录改造。
12. 不顺带修改 Finance BI 查询业务。
13. 不新增根目录 BI 专属脚本。
14. 不新增根目录 BI 专属测试。
15. 所有新增 BI 文件必须位于专家包目录。
16. 所有 Shell 脚本使用：

```bash
set -euo pipefail
```

17. 所有脚本必须支持路径中包含空格。
18. 所有脚本必须返回明确状态码。
19. 所有安装操作必须幂等。
20. 完成后输出完整 `git diff --stat` 和测试结果。

---

## 28. 验收标准

### 28.1 目录验收

新增 BI 专属文件全部位于：

```text
expert-templates/bi-strategic-office/
```

### 28.2 公共脚本验收

公共脚本只有以下两个发生修改：

```text
scripts/create-instance.sh
scripts/up-instance.sh
```

### 28.3 兼容验收

以下模板继续使用旧流程：

```text
writer
finance
sale
```

### 28.4 新包验收

`bi-strategic-office` 使用新包流程：

```text
create-instance.sh
→ expert.yaml
→ bin/install.sh

up-instance.sh
→ bin/post-start.sh
```

### 28.5 数据保护验收

重新安装和重新启动不得删除：

```text
.env
sessions
memory
uploads
exports
state
logs
audit
```

### 28.6 插件验收

容器内：

```bash
hermes plugins list
```

显示：

```text
hermes-finance-bi-plugin
```

执行：

```bash
hermes tools --summary
```

显示：

```text
Finance-Bi
```

### 28.7 变更范围验收

执行：

```bash
git diff --name-only
```

公共脚本目录中只允许：

```text
scripts/create-instance.sh
scripts/up-instance.sh
```

### 28.8 完成标准

同时满足以下条件才算完成：

1. 新专家包目录完整。
2. 新包安装成功。
3. 新包启动后初始化成功。
4. Plugin 注册成功。
5. Toolset 注册成功。
6. Semantic Catalog 安装成功。
7. 安装过程可重复执行。
8. 用户运行数据未丢失。
9. 旧专家未受影响。
10. 其他公共脚本没有变动。
11. 测试通过。
12. 文档完成。

---

## 29. 后续版本计划

v1.10 完成后，后续版本再处理：

### v1.11

* 清理旧公共 BI 脚本
* 删除旧 `asset-bundles` 重复内容
* 删除旧根目录 BI 测试
* 增加通用专家包命令

### v1.12

* 将 Writer、Finance、Sale 逐步迁移为新专家包
* 建立统一专家包契约测试
* 建立专家包版本升级和回滚命令

v1.10 不提前实施上述内容。

---

## 30. 最终代码边界

```text
scripts/
├── create-instance.sh     # 允许修改
├── up-instance.sh         # 允许修改
└── 其他公共脚本           # 不修改

expert-templates/
└── bi-strategic-office/
    ├── expert.yaml
    ├── runtime/
    ├── plugins/
    ├── bin/
    ├── lib/
    ├── tests/
    ├── docs/
    └── prd/
```

本版本的固定规则：

> `create-instance.sh` 和 `up-instance.sh` 只负责识别并调用专家包生命周期；`bi-strategic-office` 的全部实现、插件、脚本、测试和文档归入自己的专家目录。
