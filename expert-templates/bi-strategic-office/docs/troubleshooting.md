# 故障排查

## 安装失败

```bash
bash expert-templates/bi-strategic-office/bin/validate.sh
bash expert-templates/bi-strategic-office/bin/doctor.sh --package-only
```

检查：`expert.yaml`、`VERSION`、`runtime/`、`plugins/`、生命周期脚本是否完整。

## 插件未加载

Hermes 插件需 opt-in。确认 `config.yaml`：

```yaml
plugins:
  enabled:
    - hermes-finance-bi-plugin
```

重新安装合并配置：

```bash
bash expert-templates/bi-strategic-office/bin/install.sh \
  --profile <profile> \
  --instance-dir instances/<profile> \
  --data-dir instances/<profile>/data/hermes \
  --repo-root .
bash scripts/up-instance.sh <profile>
```

## post-start / pip 失败

- 确认容器运行：`docker inspect hermes-<profile>`
- 确认使用 `/app/venv/bin/python`，不是系统 Python
- 删除 hash 强制重装：`rm instances/<profile>/data/hermes/finance-bi/.requirements.sha256`

## 语义目录不可读

```bash
bash expert-templates/bi-strategic-office/bin/sync-semantic-catalog.sh \
  --profile <profile> \
  --instance-dir instances/<profile> \
  --data-dir instances/<profile>/data/hermes
```

确认存在 `finance-bi/semantic/datasets/`。

## FINANCE_BI_DSN 为空

doctor 会 WARN。问数会返回 `DATASOURCE_UNAVAILABLE`，属预期。配置只读 DSN 后：

```bash
bash scripts/sync-runtime-env.sh <profile>
bash scripts/restart-instance.sh <profile>
```

## 运行数据丢失？

正常安装/更新不应删除 `state`/`uploads`/`exports`/`sessions`。若丢失，检查是否误用了旧的 `rm -rf` 手工清理，或使用了错误的 data-dir。

## 旧公共脚本

过渡期仍保留 `scripts/inject-expert.sh`、`scripts/check-finance-bi.sh` 等；新包流程不再依赖它们。诊断优先用专家包 `bin/doctor.sh`。
