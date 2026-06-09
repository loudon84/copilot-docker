# Hermes Asset Bundles

Asset Bundle 用于在多个 Hermes Agent WebUI 实例之间复用 skills、tools、plugins、mcp 配置和相关运行期能力。

典型流程：

```text
成熟 Hermes 实例
    -> 导出 Asset Bundle
    -> 保存到 asset-bundles/
    -> 导入新实例
    -> 自动安装依赖
    -> 重启后可直接使用
```

---

## 路径规则

Asset Bundle 只从 `/data/hermes` 导出，不从以下路径读取：

- `/home/hermeswebui/.hermes/tools`
- `/home/hermeswebui/.hermes/plugins`
- `/opt/hermes-agent/tools`
- `/opt/hermes-agent/plugins`

宿主机导入目标固定为 `instances/<profile>/data/hermes`。`~/.hermes/tools` 与 `~/.hermes/plugins` 由 compose bind mount 提供兼容入口，导入脚本不得删除或重建这些 mountpoint。

如需迁移镜像内历史工具，可先准备白名单文件 `asset-bundles/<bundle>/agent-tools.include`，再执行：

```bash
bash scripts/export-assets.sh <source_profile> <bundle_name> --migrate-agent-tools
```

导出后会自动检测 bundle 中是否存在 `tools/tools` 或 `plugins/plugins` 嵌套路径。

## 可复制内容

- `skills/`
- `tools/`
- `plugins/`
- `mcp/`
- `policies/`
- `skill-bundles/`
- `gbrain/`

## 禁止复制内容

- `.env`
- `config.yaml`
- `memories/`
- `sessions/`
- `logs/`
- `webui/`
- `workspace/`
- `obsidian-vault/`
- `hindsight/`
- `backups/`

---

## 从成熟实例导出

```bash
bash scripts/export-assets.sh writer writer-search-v1
bash scripts/export-assets.sh finance finance-report-v1
```

导出结果位于 `asset-bundles/<bundle_name>/`：

```text
asset-bundles/writer-search-v1/
├── manifest.json
├── data-hermes-assets.tgz
├── requirements.txt
├── npm-global.txt
├── apt-packages.txt
├── pip-freeze.txt
├── verify.sh
└── README.md
```

## 编辑依赖

导出后，根据 bundle 实际需要编辑最小依赖声明：

```bash
vim asset-bundles/writer-search-v1/requirements.txt
vim asset-bundles/writer-search-v1/npm-global.txt
```

`pip-freeze.txt` 是完整环境快照，仅供参考；`requirements.txt` 应只包含 bundle 所需的最小 Python 依赖。

## 导入到新实例

```bash
bash scripts/import-assets.sh writer2 writer-search-v1 --restart
bash scripts/import-assets.sh finance-user-a finance-report-v1 --restart
```

导入会：

1. 解压 `data-hermes-assets.tgz` 到 `instances/<profile>/data/hermes/`
2. 备份已有资产目录到 `.backup/import-<bundle>-<timestamp>/`
3. 修正权限为 `1000:1000`
4. 若容器运行中，安装 Python/npm 依赖并拷贝 `verify.sh`
5. 可选 `--restart` 重启容器

## 安装依赖

### Python

所有 Python 依赖安装到 `/app/venv`：

```bash
/app/venv/bin/python -m pip install -r requirements.txt
```

在 `requirements.txt` 中每行一个包，例如：

```txt
requests
httpx
```

### npm 全局包

在 `npm-global.txt` 中每行一个包：

```txt
@modelcontextprotocol/server-filesystem
```

### apt/system 依赖

`apt-packages.txt` 仅作记录，**不会**由 `import-assets.sh` 自动安装。生产环境应通过 [Dockerfile](Dockerfile) 固化系统依赖。

## 检查导入结果

```bash
bash scripts/list-assets.sh writer2
bash scripts/doctor-paths.sh writer2
```

在容器内运行验证脚本：

```bash
docker exec -it hermes-writer2 bash /tmp/hermes-bundle-verify.sh
```

检查工具路径兼容（示例）：

```bash
docker exec hermes-writer2 bash -lc '
test -f /data/hermes/tools/baidu_search_tool.py
test -f /home/hermeswebui/.hermes/tools/baidu_search_tool.py
/app/venv/bin/python -m py_compile /data/hermes/tools/baidu_search_tool.py
'
```

## 固化到专家模板

将成熟 bundle 沉淀到 `expert-templates/writer` 或 `expert-templates/finance`：

```bash
bash scripts/promote-bundle-to-template.sh writer-search-v1 writer
bash scripts/promote-bundle-to-template.sh finance-report-v1 finance
```

## 新建实例继承模板

```bash
bash scripts/create-instance.sh new-writer 8790 writer
bash scripts/up-instance.sh new-writer
```

新建实例会通过 `inject-expert.sh` 自动注入专家模板中的 skills、tools、plugins 等能力。

---

## 常见问题

### 容器重建后 tools/plugins 会丢失吗？

不会。实例级 `tools/` 和 `plugins/` 已持久化到 `instances/<profile>/data/hermes/`，并通过 docker-compose volume 映射到容器内 `/data/hermes/tools` 和 `~/.hermes/tools`。

### 导出时包含 `/opt/hermes-agent/tools` 吗？

会。导出脚本会合并以下路径的历史工具：

- `/data/hermes/tools`
- `/home/hermeswebui/.hermes/tools`
- `/opt/hermes-agent/tools`

导入后统一落到 `/data/hermes/tools`。

### 可以复制 `.env` 或 `config.yaml` 吗？

不可以。Asset Bundle  deliberately 排除密钥和个人配置。新实例应使用自己的 `.env` 和 `config.yaml`。

### `requirements.txt` 和 `pip-freeze.txt` 有什么区别？

- `pip-freeze.txt`：导出时自动生成的完整 venv 快照
- `requirements.txt`：bundle 最小依赖，需人工确认后填写

### apt 包为什么没有自动安装？

apt 安装会改变容器系统层，容器重建后丢失。系统依赖应写入 Dockerfile 并重新 build 镜像。

---

## 路径规范

### 实例持久化目录

```text
instances/<profile>/data/hermes/
├── skills/
├── tools/
├── plugins/
├── mcp/
├── policies/
├── skill-bundles/
└── gbrain/
```

### 容器内 Hermes 兼容路径

```text
/data/hermes/tools          <->  /home/hermeswebui/.hermes/tools
/data/hermes/plugins        <->  /home/hermeswebui/.hermes/plugins
```

### 镜像内置路径（不建议通过 bundle 修改）

```text
/opt/hermes-agent
/home/hermeswebui/.hermes/hermes-agent
```

通用源码级工具应在 Dockerfile 中固化；实例级工具应放在 `/data/hermes/tools`。

### 环境变量

```text
HERMES_SKILLS_PATH=/data/hermes/skills
HERMES_TOOLS_PATH=/data/hermes/tools
HERMES_PLUGINS_PATH=/data/hermes/plugins
HERMES_WORKSPACE_PATH=/data/hermes/workspace
```
