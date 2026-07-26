# 安装说明（v1.11.1）

## 前置条件

1. 已部署并可访问的 SQLBot 服务（含 **MCP SSE** 端点）
2. SQLBot 中已配置财务工作空间、只读数据源、表字段/关系/术语/SQL 示例
3. 已准备 Hermes 专用 SQLBot 服务账号（固定工作空间）
4. Docker 与本仓库 `scripts/create-instance.sh` / `up-instance.sh` 可用

## 步骤

### 1. 校验专家包

```bash
bash expert-templates/bi-strategic-office/bin/validate.sh
bash expert-templates/bi-strategic-office/bin/doctor.sh --package-only
```

### 2. 创建实例

```bash
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office
```

> `create-instance.sh` 会调用可执行的 `bin/install.sh`，创建 `sqlbot-adapter/state|audit`、初始化 SQLite，并写 `package-state.yaml`。

### 3. 填写 SQLBot 环境变量

编辑 `instances/<profile>/.env`，参考：

```text
expert-templates/bi-strategic-office/config/sqlbot.example.env
```

必填：

- `SQLBOT_MCP_URL`
- `SQLBOT_USERNAME`
- `SQLBOT_PASSWORD`
- `SQLBOT_WORKSPACE_ID`
- `SQLBOT_DEFAULT_DATASOURCE_ID`
- `SQLBOT_SESSION_ENCRYPTION_KEY`（Fernet key 或口令派生；**禁止为空**）

生成示例：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4. 同步并启动

```bash
bash scripts/sync-runtime-env.sh <profile>
bash scripts/up-instance.sh <profile>
```

`post-start.sh` 会：

1. 安装并校验依赖版本（`mcp==1.26.0` 等）
2. 初始化 Schema
3. 启用插件
4. MCP initialize + ping（**默认不** `mcp_start`）
5. 跑 `doctor.sh`

SQLBot 不可用时返回非零，但**容器保持运行**，不会回退旧自研插件。

### 5. 验证

```bash
bash expert-templates/bi-strategic-office/bin/doctor.sh --profile <profile>
# 可选深度（会登录）
bash expert-templates/bi-strategic-office/bin/doctor.sh --profile <profile> --deep
```

预期目录：

```text
instances/<profile>/data/hermes/sqlbot-adapter/
  state/sqlbot_sessions.db
  audit/
  package-state.yaml   # schema_version: 2, expert_version: 1.11.1
```

### 6. 记录 SQLBot 实施结果

按 [sqlbot-example.md](sqlbot-example.md) 填写工作空间、数据源、表字段、术语与验收问题。

## 从 v1.11.0 升级

```bash
bash expert-templates/bi-strategic-office/bin/update.sh \
  --profile <p> --instance-dir ... --data-dir ... --repo-root ...
bash scripts/up-instance.sh <p>
```

`update.sh` 会备份 plugin + SQLite；失败可从 `.backup/update-*` 回滚插件。补齐 `SQLBOT_SESSION_ENCRYPTION_KEY` 后重启。

## 从 v1.10 升级

见 [upgrade.md](upgrade.md)。
