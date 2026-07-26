# 安装说明（v1.11）

## 前置条件

1. 已部署并可访问的 SQLBot 服务（含 MCP 端点）
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

### 3. 填写 SQLBot 环境变量

编辑 `instances/bi-strategic-office/.env`，参考：

```text
expert-templates/bi-strategic-office/config/sqlbot.example.env
```

必填：

- `SQLBOT_MCP_URL`
- `SQLBOT_USERNAME`
- `SQLBOT_PASSWORD`
- `SQLBOT_WORKSPACE_ID`
- `SQLBOT_DEFAULT_DATASOURCE_ID`

### 4. 同步并启动

```bash
bash scripts/sync-runtime-env.sh bi-strategic-office
bash scripts/up-instance.sh bi-strategic-office
```

`post-start.sh` 会安装 Adapter 依赖、启用插件，并对 SQLBot MCP 做连通性探测。SQLBot 不可用时返回非零，但**容器保持运行**，不会回退旧自研插件。

### 5. 验证

```bash
docker exec hermes-bi-strategic-office hermes plugins list
docker exec hermes-bi-strategic-office hermes tools --summary
```

预期出现：

- `hermes-sqlbot-adapter`
- `Finance-Bi` / `finance-bi`

不应出现：

- `hermes-finance-bi-plugin`

### 6. 记录 SQLBot 实施结果

按 [sqlbot-example.md](sqlbot-example.md) 填写工作空间、数据源、表字段、术语与验收问题。

## 从 v1.10 升级

见 [upgrade.md](upgrade.md)。
