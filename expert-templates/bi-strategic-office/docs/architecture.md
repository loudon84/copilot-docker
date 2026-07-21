# 架构说明（v1.10 专家包）

## 目标

`bi-strategic-office` 从分散的公共目录，归集为自包含专家包：

```text
expert-templates/bi-strategic-office/
├── expert.yaml          # 包清单
├── VERSION              # 1.10.0
├── runtime/             # SOUL / skills / semantic / policies / config.patch
├── plugins/             # hermes-finance-bi-plugin
├── bin/                 # install / post-start / update / validate / doctor
├── lib/                 # merge_yaml / package_state / validate_manifest
├── tests/
├── docs/
└── prd/
```

## 生命周期

```text
create-instance.sh
  └─ 若存在 expert.yaml + bin/install.sh（可执行）
       → 调用专家包 install.sh
     否则
       → 旧模板 inject-expert.sh

up-instance.sh
  └─ 容器启动 + 健康检查后
       若存在 expert.yaml + bin/post-start.sh
         → 调用 post-start.sh（pip / 插件校验 / doctor）
```

公共脚本只做「识别 + 调用」，不含 BI 专属分支。

## 实例落盘

```text
instances/<profile>/data/hermes/
├── SOUL.md
├── config.yaml                 # 深度合并 config.patch
├── skills/
├── plugins/hermes-finance-bi-plugin/
├── finance-bi/
│   ├── semantic/
│   ├── policies/
│   ├── state/                  # 用户运行数据，安装不得清空
│   ├── cache/
│   └── package-state.yaml
└── workspace/uploads|exports/bi/
```

## 版本

`VERSION`、`plugin.yaml`、`semantic_catalog_version`、`package-state.yaml` 统一为 `1.10.0`。

## 过渡期

旧路径（`asset-bundles/hermes-finance-bi-plugin`、模板根下 `semantic/`/`skills/`、公共 `scripts/sync-bi-semantic-catalog.sh` 等）保留兼容副本，**新流程以专家包内文件为唯一维护来源**。
