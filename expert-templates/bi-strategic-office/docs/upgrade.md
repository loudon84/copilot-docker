# 升级指南

## 版本文件

- 包版本：`VERSION` / `expert.yaml` → `expert.version`
- 插件版本：`plugins/hermes-finance-bi-plugin/plugin.yaml`
- 实例状态：`data/hermes/finance-bi/package-state.yaml`

## 升级步骤

1. 更新专家包源码（本仓库 `expert-templates/bi-strategic-office/`）。
2. 执行：

```bash
bash expert-templates/bi-strategic-office/bin/update.sh \
  --profile <profile> \
  --instance-dir instances/<profile> \
  --data-dir instances/<profile>/data/hermes \
  --repo-root .
```

3. 重新启动以刷新容器内依赖：

```bash
bash scripts/up-instance.sh <profile>
```

## 保护规则

升级会覆盖模板资产（SOUL、Skills、Plugin、Semantic、Policies），但**不会**：

- 覆盖 `.env` 中已有 DSN/密码（仅补齐缺失键；部分策略键会 upsert）
- 清空 `finance-bi/state` / `cache`
- 删除 `workspace/uploads` / `workspace/exports`
- 删除 `sessions` / `logs`
- 覆盖用户已有 `memories/MEMORY.md`

## 回滚建议

安装前自动写入 `data/hermes/.backup/<timestamp>/`。必要时可从备份恢复 `config.yaml`、skills、semantic。
