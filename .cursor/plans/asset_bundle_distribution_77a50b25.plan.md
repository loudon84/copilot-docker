---
name: Asset Bundle Distribution
overview: 按 PRD v1.2 实现 Hermes Agent 实例能力包（Asset Bundle）的导出、导入、查看与模板固化机制，包括 docker-compose volume 标准化、4 个新脚本、2 个脚本增强和文档更新。
todos:
  - id: commit1-compose
    content: "Commit 1: 修改 docker-compose.yml（tools/plugins volume + 环境变量）"
    status: completed
  - id: commit1-create
    content: "Commit 1: 修改 create-instance.sh（新增 tools/plugins 目录 + 权限修正）"
    status: completed
  - id: commit1-inject
    content: "Commit 1: 修改 inject-expert.sh（资产目录备份 + tools/plugins 目录创建）"
    status: completed
  - id: commit2-export
    content: "Commit 2: 新增 export-assets.sh"
    status: completed
  - id: commit2-import
    content: "Commit 2: 新增 import-assets.sh + asset-bundles/.gitkeep"
    status: completed
  - id: commit3-list
    content: "Commit 3: 新增 list-assets.sh"
    status: completed
  - id: commit3-promote
    content: "Commit 3: 新增 promote-bundle-to-template.sh"
    status: completed
  - id: commit4-docs
    content: "Commit 4: 新增 README_ASSET_BUNDLES.md + 修改 README.md + 修改 .gitignore"
    status: completed
isProject: false
---

# Asset Bundle 导出/导入/复用 实施计划

按 [prd/v1.2_asset-bundle-distribution.md](prd/v1.2_asset-bundle-distribution.md) 分 4 个 commit 实施。

---

## Commit 1：目录与 compose 标准化

### 1.1 修改 [docker-compose.yml](docker-compose.yml)

- `volumes` 新增 tools/plugins 映射（子路径 bind-mount 覆盖容器默认路径）：

```yaml
volumes:
  - ./instances/${HERMES_PROFILE:-default}/data/hermes:/data/hermes
  - ./instances/${HERMES_PROFILE:-default}/data/hermes/tools:/home/hermeswebui/.hermes/tools
  - ./instances/${HERMES_PROFILE:-default}/data/hermes/plugins:/home/hermeswebui/.hermes/plugins
```

- `environment` 新增 2 个环境变量：

```yaml
HERMES_TOOLS_PATH: /data/hermes/tools
HERMES_PLUGINS_PATH: /data/hermes/plugins
```

### 1.2 修改 [scripts/create-instance.sh](scripts/create-instance.sh)

- 在 `mkdir -p` 列表中新增 `"$DATA_DIR/tools"` 和 `"$DATA_DIR/plugins"`
- 脚本末尾（`inject-expert.sh` 调用之前）增加权限修正：

```bash
chown -R 1000:1000 "$DATA_DIR" 2>/dev/null || true
chmod -R u+rwX,g+rwX "$DATA_DIR" 2>/dev/null || true
chmod 600 "$INSTANCE_DIR/.env" 2>/dev/null || true
```

### 1.3 修改 [scripts/inject-expert.sh](scripts/inject-expert.sh)

- 在 `cp -R` 复制模板之前，增加 skills/tools/plugins/mcp/policies/skill-bundles 的备份逻辑
- 在脚本末尾 `mkdir -p` 列表中补充 `"$DATA_DIR/tools"` 和 `"$DATA_DIR/plugins"`

---

## Commit 2：导出与导入脚本

### 2.1 新增 [scripts/export-assets.sh](scripts/export-assets.sh)

- 用法：`bash scripts/export-assets.sh <source_profile> <bundle_name>`
- 从运行容器 `/data/hermes/` + 兼容路径（`~/.hermes/tools`、`/opt/hermes-agent/tools` 等）收集 7 个资产目录
- 打包输出到 `asset-bundles/<bundle_name>/`（含 `data-hermes-assets.tgz`、`manifest.json`、`requirements.txt`、`npm-global.txt`、`apt-packages.txt`、`verify.sh`、`README.md`、`pip-freeze.txt`）
- 参考实现直接采用 PRD 第 10.5 节

### 2.2 新增 [scripts/import-assets.sh](scripts/import-assets.sh)

- 用法：`bash scripts/import-assets.sh <target_profile> <bundle_name> [--restart]`
- 解压 bundle 到目标实例 `data/hermes/`，备份已有目录
- 若容器运行中：创建 symlink、安装 Python/npm 依赖、拷贝 verify.sh
- 可选 `--restart` 重启容器
- 参考实现直接采用 PRD 第 11.3 节

### 2.3 新增 `asset-bundles/.gitkeep`

- 创建空目录占位

---

## Commit 3：列表与模板固化脚本

### 3.1 新增 [scripts/list-assets.sh](scripts/list-assets.sh)

- 用法：`bash scripts/list-assets.sh <profile>`
- 列出容器内 7 个资产目录内容 + 兼容路径 symlink 状态
- 参考实现直接采用 PRD 第 12.3 节

### 3.2 新增 [scripts/promote-bundle-to-template.sh](scripts/promote-bundle-to-template.sh)

- 用法：`bash scripts/promote-bundle-to-template.sh <bundle_name> <expert>`
- 将 bundle 解压到 `expert-templates/<expert>/`，先备份
- 参考实现直接采用 PRD 第 13.4 节

---

## Commit 4：文档与 gitignore

### 4.1 新增 [README_ASSET_BUNDLES.md](README_ASSET_BUNDLES.md)

- 包含 PRD 第 14 节要求的 10 个章节

### 4.2 修改 [README.md](README.md)

- 在末尾新增 `## Hermes Asset Bundles` 章节，链接到 `README_ASSET_BUNDLES.md`

### 4.3 修改 [.gitignore](.gitignore)

- 新增以下规则：

```gitignore
# Asset bundles - exclude binary archives and pip freeze snapshots
asset-bundles/*/*.tgz
asset-bundles/*/pip-freeze.txt
```

---

## 关键设计决策

- **Volume 策略**：通过 docker-compose 的子路径 bind-mount（tools/plugins）覆盖容器内 `~/.hermes/tools` 和 `~/.hermes/plugins`，无需在容器内创建 symlink（compose 层面解决）。但 `import-assets.sh` 仍会在容器内创建 symlink 作为安全回退，以兼容容器已经运行（未重启）的场景。
- **备份策略**：inject-expert 和 import-assets 都在写入前备份到 `.backup/<timestamp>/`
- **依赖安装**：Python 安装到 `/app/venv`，npm 全局安装；apt 仅记录不自动安装
- **tgz 不入库**：导出的二进制包通过 `.gitignore` 排除，只保留 manifest/requirements 等声明文件
