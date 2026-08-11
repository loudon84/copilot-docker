# Hermes Docker 实例能力克隆 v1

## 目标

将 `instances/A` 中已经形成的 Hermes Agent 能力复制到一个**全新的** `instances/B`：

- root Profile 配置
- 多 Profile 拓扑
- `config.yaml`
- `SOUL.md`
- `team.yaml`
- `profile.yaml`
- `workspace/AGENTS.md`
- `skills/`
- `tools/`
- `plugins/`
- `mcp/`
- `policies/`
- `skill-bundles/`
- `cron/`
- `agent-hooks/`
- `team-shared/`

明确不复制：

- sessions
- memories
- logs
- webui state
- Hindsight 本地状态
- workspace 用户文档（仅保留 `workspace/AGENTS.md`）
- obsidian-vault
- backups / `.backup`
- attachments
- checkpoints
- evolution state
- SQLBot session/audit state

## 最重要约束

`clone-instance.sh` 是 **create-only** 操作。

以下任一条件成立时必须失败：

1. `instances/<target>` 已存在；
2. `hermes-<target>` Docker 容器已存在；
3. 同名 clone lock 已存在。

脚本不提供：

- `--force`
- `--overwrite`
- `--merge`
- `--repair`

因此它不能被用来给已经初始化的实例覆盖能力。

## 使用

```bash
bash scripts/clone-instance.sh A B 8791
bash scripts/up-instance.sh B
bash scripts/check-agent-api.sh B
```

默认不复制 secret-like `.env` 值。

如果 A/B 位于同一可信部署域，并且确实要复用 Provider/Connector Secret：

```bash
bash scripts/clone-instance.sh A B 8791 --copy-secrets
```

即使启用 `--copy-secrets`，以下 B 实例身份字段仍不会复制：

- `HERMES_PROFILE`
- `HERMES_WEBUI_PORT`
- `HERMES_GATEWAY_PORT`
- `HERMES_WEBUI_PASSWORD`
- `API_SERVER_KEY`
- `API_SERVER_MODEL_NAME`
- `HINDSIGHT_BANK_ID`

B 会生成新的 WebUI password、Agent API key、端口和 Hindsight namespace。

## 为什么不能继续使用 import-assets.sh

现有 `import-assets.sh` 是 Legacy Runtime Asset Flow：

- 允许目标目录已经存在；
- 导入前备份目标资产；
- 再覆盖 `skills/tools/plugins/mcp/...`。

它适合“给已有实例安装资产”，不适合“实例克隆”。

新的 clone flow 必须与 Asset Bundle 保持边界：

```text
Asset Bundle:
existing instance -> merge/import assets

Instance Clone:
existing A -> create brand-new B only
```

## Hindsight 隔离

能力克隆后会强制把：

```text
A root:     hermes-A
A member x: hermes-A-x
```

重绑定为：

```text
B root:     hermes-B
B member x: hermes-B-x
```

否则虽然没有复制 session 文件，B 仍可能通过外部 Hindsight 服务读到 A 的长期记忆。

## Dry-run

```bash
bash scripts/clone-instance.sh A B 8791 --dry-run
```

只验证：

- A 可克隆；
- 能力 bundle 中没有禁止路径；
- B 当前不存在。

不会创建 B。
