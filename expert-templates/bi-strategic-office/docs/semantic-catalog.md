# Semantic Catalog

## 源位置（唯一维护）

```text
expert-templates/bi-strategic-office/runtime/semantic/
├── datasources/
├── datasets/
├── dimensions/
├── metrics/
├── joins/
├── glossary/
└── examples/
```

## 实例目标

```text
instances/<profile>/data/hermes/finance-bi/semantic/
```

由 `bin/sync-semantic-catalog.sh` / `bin/install.sh` 同步。环境变量：

```text
FINANCE_BI_CATALOG_PATH=/data/hermes/finance-bi/semantic
FINANCE_BI_POLICY_PATH=/data/hermes/finance-bi/policies
```

## 同步命令

```bash
bash expert-templates/bi-strategic-office/bin/sync-semantic-catalog.sh \
  --profile <profile> \
  --instance-dir instances/<profile> \
  --data-dir instances/<profile>/data/hermes
```

同步前会备份现有 Catalog；失败时尝试恢复备份。

## 过渡说明

模板根目录下的 `semantic/` 与公共 `scripts/sync-bi-semantic-catalog.sh` 仍为过渡兼容副本；**后续修改只改 `runtime/semantic/`**。
