# Changelog

## 1.10.0

- 将 Finance BI Plugin 归入专家包 `plugins/hermes-finance-bi-plugin/`
- 将 Semantic Catalog 归入专家包 `runtime/semantic/`
- 将 Policies、Skills、SOUL、MEMORY 归入 `runtime/`
- 将专家专属测试归入专家包 `tests/`
- 增加专家包安装和启动后生命周期（`bin/install.sh`、`bin/post-start.sh` 等）
- `create-instance.sh` 支持新专家包识别与 `bin/install.sh` 调用
- `up-instance.sh` 支持专家启动后初始化（`bin/post-start.sh`）
- 新增 `expert.yaml` / `VERSION` / `package-state.yaml` 统一版本管理
- 过渡期保留旧目录副本与公共 BI 脚本，不删除；新流程不再依赖公共 BI 专属脚本
