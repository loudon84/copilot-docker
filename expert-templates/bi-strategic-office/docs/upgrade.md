# 升级说明

## v1.11.0 → v1.11.1（SSE Client Hotfix）

### 变更摘要

- MCP 改为官方 SSE Client（`mcp==1.26.0`）
- 新增必填 `SQLBOT_SESSION_ENCRYPTION_KEY`（Fernet；禁止明文 Token）
- Session schema v2；`package-state.yaml` 记录 `schema_version: 2`
- Doctor 默认 initialize/ping；`--deep` 才 `mcp_start`

### 升级步骤

1. 在实例 `.env` 增加 `SQLBOT_SESSION_ENCRYPTION_KEY`
2. 执行 `bin/update.sh`（会备份 plugin + SQLite）
3. `bash scripts/up-instance.sh <profile>`（刷新依赖并 post-start）
4. `bash bin/doctor.sh --profile <profile>`；可选 `--deep`

失败时从 `data/hermes/.backup/update-*` 回滚插件。

---

## v1.10 → v1.11（SQLBot Adapter）

### 变更摘要

- 问数核心从自研 `hermes-finance-bi-plugin` 切换为 `hermes-sqlbot-adapter` + 外部 SQLBot
- 删除本地 Semantic Catalog / Policies 安装路径
- 环境变量从 `FINANCE_BI_*` 切换为 `SQLBOT_*`
- 工具从 6 个收敛为 4 个（去掉 catalog/validate/export，新增 reset）

### 升级步骤

1. **备份** v1.10 实例目录与 `config.yaml` / `.env`
2. 在 SQLBot 完成工作空间与元数据配置，填写 `docs/sqlbot-example.md`
3. 拉取含 v1.11 专家包的代码
4. 更新实例 `.env`：新增 `SQLBOT_*`（可保留旧 `FINANCE_BI_*` 但不再使用）
5. 执行专家包更新：

```bash
bash expert-templates/bi-strategic-office/bin/update.sh \
  --profile <profile> \
  --instance-dir instances/<profile> \
  --data-dir instances/<profile>/data/hermes \
  --repo-root .
```

6. 启动并 doctor：

```bash
bash scripts/up-instance.sh <profile>
bash expert-templates/bi-strategic-office/bin/doctor.sh \
  --profile <profile> \
  --data-dir instances/<profile>/data/hermes \
  --container hermes-<profile>
```

7. 执行 Golden Questions（见 `evaluations/`）

### 回滚

1. 停止实例
2. 恢复 Git tag `v1.10` 专家包与实例备份
3. 恢复 v1.10 `config.yaml` / `.env`（`FINANCE_BI_*`）
4. 重新 `up-instance.sh`
5. **不要**修改 SQLBot 内部数据

v1.11 运行目录中不同时保留新旧插件。
