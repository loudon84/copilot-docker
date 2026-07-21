---
name: bi-strategic-office 专家包归集
overview: 按 PRD v1.10 将 bi-strategic-office 改造为自包含专家包：新增 expert.yaml/VERSION/生命周期脚本/lib/tests/docs，把插件·语义目录·策略·角色归集进包内，并让 create-instance.sh / up-instance.sh 以通用方式识别并调用专家包生命周期；旧模板（writer/finance/sale）与其余公共脚本零改动。
todos:
  - id: t01-scaffold
    content: 在 expert-templates/bi-strategic-office/ 下建立 runtime/ plugins/ bin/ lib/ tests/ docs/ prd/ 目录骨架
    status: completed
  - id: t02-manifest
    content: 创建 expert.yaml(按 PRD §8，assets 仅映射真实 skills/semantic/policies)、VERSION(1.10.0)、CHANGELOG.md，并更新 README.md
    status: completed
  - id: t03-runtime
    content: 归集 runtime 资产：复制 SOUL.md/config.patch.yaml/memories/MEMORY.md/skills(6个)/policies/semantic 到 runtime/，零业务改动
    status: completed
  - id: t04-plugin
    content: 复制 hermes-finance-bi-plugin 到 plugins/(含 tests)，补 pyproject.toml，plugin.yaml 版本对齐 1.10.0，校验无需改内部导入
    status: completed
  - id: t05-lib
    content: 实现 lib/merge_yaml.py(深合并+去重并集+原子写+备份)、lib/package_state.py(package-state 原子读写)、lib/validate_manifest.py
    status: completed
  - id: t06-bin
    content: 实现 bin/install.sh(§14 步骤+幂等+数据保护)、post-start.sh(§15 pip+插件校验)、update.sh、validate.sh(§16)、doctor.sh(§17 双模式)、sync-semantic-catalog.sh(§19)、test.sh
    status: completed
  - id: t07-tests
    content: 编写 tests/unit(manifest/config_merge/package_state)、tests/security(secret扫描/数据保护/路径边界) 等专家包测试
    status: completed
  - id: t08-docs
    content: 补 docs/(architecture/installation/upgrade/semantic-catalog/troubleshooting) 与 prd/ 副本
    status: completed
  - id: t09-create-instance
    content: 修改 scripts/create-instance.sh：加入通用 PACKAGE_MODE 识别与 install.sh 调用，旧流程完全保留，无 BI 专属分支
    status: completed
  - id: t10-up-instance
    content: 修改 scripts/up-instance.sh：容器起后读 HERMES_EXPERT，定位并调用 bin/post-start.sh，失败处理，旧行为不变
    status: completed
  - id: t11-verify
    content: 静态/单元验证：validate.sh、doctor.sh --package-only、pytest tests/unit；git diff 确认公共脚本仅改两处；输出 diff --stat 与测试结果
    status: completed
isProject: false
---

# bi-strategic-office 专家包归集改造（PRD v1.10）

## 采用的关键决策（已与用户确认）
- 团队结构：**忠实迁移现状**。当前无 `team.yaml`，4 个角色文件保留在 `skills/bi-office-orchestration/references/roles/` 内，不虚构 `runtime/team/team.yaml`，零业务内容改动。`expert.yaml` 的 `assets` 只映射真实存在的 skills/semantic/policies。
- 验证范围：**实现 + 静态/单元验证**。跑通 `validate.sh`、`doctor.sh --package-only`、专家包 `tests/unit`；docker 运行时回归（up-instance/容器内 `hermes plugins list`/doctor）由用户本地执行。
- 公共脚本：按 PRD §21/§22 仅改 `scripts/create-instance.sh`、`scripts/up-instance.sh`，加入**通用**新包识别与生命周期调用，不含任何 BI 专属字样。

## 现状要点（已核实）
- 专家目录 [expert-templates/bi-strategic-office](expert-templates/bi-strategic-office)：`SOUL.md`/`GUIDE.md`/`README.md`/`config.yaml`/`config.patch.yaml`、`skills/`（6 个）、`semantic/`、`policies/query-policy.yaml`、`memories/`、`workspace/AGENTS.md`；无 `team.yaml` → 走单专家路径。
- 插件源码在 [asset-bundles/hermes-finance-bi-plugin](asset-bundles/hermes-finance-bi-plugin)：`__init__.py`(register)、`schemas.py`、`finance_bi/` 包、`plugin.yaml`(v1.0.0)、`requirements.txt`；靠环境变量 `FINANCE_BI_CATALOG_PATH`/`FINANCE_BI_POLICY_PATH` 定位资产，**无硬编码内部相对路径**，`__init__.py` 用 `sys.path` 自举，迁移后无需改导入。无 `pyproject.toml`。
- 现有安装逻辑：[scripts/inject-expert.sh](scripts/inject-expert.sh) 先 `cp base` 再 `cp expert`，其中 76-156 行是 BI 专属分支（同步语义/策略、装插件、`enable_finance_bi_plugin.py`、写 `FINANCE_BI_*` 到实例 `.env`、建 finance-bi 运行目录、容器内 pip）。语义同步另有 [scripts/sync-bi-semantic-catalog.sh](scripts/sync-bi-semantic-catalog.sh)，诊断在 [scripts/check-finance-bi.sh](scripts/check-finance-bi.sh)。
- 复用逻辑：`config.patch.yaml` 深合并见 [scripts/lib/merge_config_patch.py](scripts/lib/merge_config_patch.py)（保护 model/providers、`enabled` 并集）；插件启用见 [scripts/lib/enable_finance_bi_plugin.py](scripts/lib/enable_finance_bi_plugin.py)。这些是「不修改的公共脚本」，包内 `lib/` 需自带等价实现。
- [scripts/create-instance.sh](scripts/create-instance.sh)：第 47 行写 `HERMES_EXPERT=$EXPERT`；第 85 行 `inject-expert.sh`；`INSTANCE_DIR`/`DATA_DIR` 已定义。
- [scripts/up-instance.sh](scripts/up-instance.sh)：`docker compose ... up -d`（77 行）后无专家钩子；容器名 `hermes-$PROFILE`。

## 核心设计
- 识别规则（PRD §6.3）：`expert.yaml` 存在 且 `bin/install.sh` 可执行 → 新包模式；否则旧模式。
- 包内脚本**允许**含 BI 知识（插件名/语义路径/env 键）；公共脚本保持通用。`install.sh` 是 (base 复制) + (expert runtime 覆盖) + (原 inject-expert BI 分支) + (sync-bi-semantic) 的自包含移植，资产读自包内 `runtime/`，base 读自 `--repo-root/expert-templates/base`。
- 职责切分：`install.sh` 只落盘、合并配置、写 env 占位、建运行目录、写 package-state；**不**启容器、**不** pip。容器内 pip 依赖安装移到 `post-start.sh`（PRD §15.2）。

## 目录/文件产出（全部在 expert-templates/bi-strategic-office/ 内）
- 清单：`expert.yaml`（PRD §8，assets 仅映射真实 skills/semantic/policies）、`VERSION`(1.10.0)、`CHANGELOG.md`、更新 `README.md` 指明包内为唯一维护位置。
- `runtime/`：`SOUL.md`、`config.patch.yaml`、`memories/MEMORY.md`、`skills/`（复制 6 个 skill，含编排 skill 内角色）、`policies/`、`semantic/`。以「复制到新位置、新位置为唯一维护点」方式归集，旧目录副本按 PRD §10.2 过渡保留、不删。
- `plugins/hermes-finance-bi-plugin/`：从 asset-bundles 复制全量源码 + `tests/`；补 `pyproject.toml`；`plugin.yaml` 版本对齐 1.10.0。
- `bin/`：`install.sh`、`post-start.sh`、`update.sh`、`validate.sh`、`doctor.sh`、`test.sh`、`sync-semantic-catalog.sh`（全部 `set -euo pipefail`、支持空格路径、幂等、明确退出码、`--profile/--instance-dir/--data-dir/--repo-root[/--container]` 参数）。
- `lib/`：`merge_yaml.py`（移植 merge_config_patch 逻辑：递归合并、`enabled`/`toolsets` 去重并集、保护 model/providers、原子写入、合并前备份）、`package_state.py`（读写 `finance-bi/package-state.yaml`，原子写、失败不写成功态）、`validate_manifest.py`。
- `tests/unit/`（`test_manifest.py`/`test_config_merge.py`/`test_package_state.py`）、`tests/security/`（secret 扫描、运行数据保护、路径边界）、`tests/deployment/`、`tests/integration/`、`tests/fixtures/`；插件测试放 `plugins/.../tests/`。
- `docs/`：`architecture.md`/`installation.md`/`upgrade.md`/`semantic-catalog.md`/`troubleshooting.md`。
- `prd/`：放入 v1.10 PRD 副本。

## install.sh 关键步骤（PRD §14，幂等 + 数据保护）
1. 校验参数 → 定位包根 → 跑 `validate.sh`。
2. 创建运行目录：`finance-bi/{semantic,policies,state,cache}`、`workspace/{uploads,exports/bi}`。
3. 备份现有模板资产到 `.backup/<ts>`（不动 state/uploads/exports/sessions/.env）。
4. 铺 base 基座（SOUL/config.yaml/memories/workspace/hindsight，来自 repo-root/expert-templates/base）→ 覆盖 `runtime/` 资产（SOUL/MEMORY/skills/policies/semantic）→ 复制插件到 `plugins/hermes-finance-bi-plugin`。
5. 语义/策略同步到 `finance-bi/{semantic,policies}`（等价 sync-bi-semantic-catalog，包内实现）。
6. `lib/merge_yaml.py` 深合并 `runtime/config.patch.yaml` → 实例 `config.yaml`（合并前备份，保护 model/providers）；启用插件 + `finance-bi` toolset。
7. 幂等写 `FINANCE_BI_*` 占位到实例 `.env`（沿用 inject-expert 的 ensure/upsert 键集与默认值）。
8. `lib/package_state.py` 写 `finance-bi/package-state.yaml`（PRD §13 字段）。
- 覆盖/合并/禁止覆盖清单严格按 PRD §12：`.env`/sessions/logs/uploads/exports/state/cache/user memory 绝不覆盖。

## post-start.sh（PRD §15）
容器已起且 `/data/hermes` 挂载后：检查容器运行 → 用 `/app/venv/bin/python -m pip install -r .../requirements.txt`（带 requirements sha256 去重，写 `finance-bi/.requirements.sha256`）→ 启用/校验插件与 `Finance-Bi` toolset → 校验语义路径/state 可写 → 调 `doctor.sh` → 失败返回非零并输出修复命令，不停已运行容器。

## 公共脚本改动（仅两处，通用无 BI 字样）
- [scripts/create-instance.sh](scripts/create-instance.sh)：在第 85 行 `inject-expert.sh` 之前加入
  `EXPERT_DIR/EXPERT_MANIFEST/EXPERT_INSTALLER` 探测 → `PACKAGE_MODE` 判断；`true` 则调用 `"$EXPERT_INSTALLER" --profile ... --instance-dir ... --data-dir ... --repo-root ...` 并跳过 `inject-expert.sh`；`false` 保持原有 `inject-expert.sh` 调用完全不变。禁止 `if [[ "$EXPERT" == ... ]]`/`case`。
- [scripts/up-instance.sh](scripts/up-instance.sh)：容器 up + 健康检查（现第 77-88 行）之后，从 `.env` 读 `HERMES_EXPERT` → 定位 `EXPERT_DIR/bin/post-start.sh` → 若 `expert.yaml` 存在且 `post-start.sh` 可执行则带 `--container hermes-$PROFILE` 调用；失败 up-instance 返回非零、不停容器、提示 doctor；无包时静默跳过、旧行为不变。

## 不改动项（PRD §23/§27）
`inject-expert.sh`、`sync-bi-semantic-catalog.sh`、`check-finance-bi.sh`、`restart-instance.sh`、`build-image.sh`、`sync-runtime-env.sh`、`scripts/lib/*` 及其它专家模板一律不动；不删旧 asset-bundles/根目录测试；不改 Hermes 源码/Compose/查询业务。

## 验收自检
- `git diff --name-only`：`scripts/` 下仅 `create-instance.sh`、`up-instance.sh` 变更；其余新增文件均在 `expert-templates/bi-strategic-office/`。
- 跑 `bin/validate.sh`、`bin/doctor.sh --package-only`、`python -m pytest expert-templates/bi-strategic-office/tests/unit`。
- 输出 `git diff --stat` 与测试结果。