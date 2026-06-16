# Hermes Agent API Server

本文档说明 copilot-docker 实例中 Hermes Agent API Server（`hermes gateway`）的端口、配置与 nodeskclaw 接入方式。

## 端口说明

每个实例同时暴露两个服务：

| 服务 | 容器端口 | 宿主机端口 | 说明 |
|------|----------|------------|------|
| Hermes WebUI | 8787 | `HERMES_WEBUI_PORT` | Web 管理界面 |
| Hermes Agent API | 8642 | `HERMES_GATEWAY_PORT` | OpenAI 兼容 API + skills/runs |

端口规则：

```text
HERMES_GATEWAY_PORT = HERMES_BASE_PORT + HERMES_WEBUI_PORT
# 默认 HERMES_BASE_PORT=20000
# 例：WebUI 8900 → Agent API 28900
```

## 环境变量

存在两份 `.env`，职责不同：

| 路径 | 用途 |
|------|------|
| `instances/<profile>/.env` | **运维源**：docker-compose 读取，注入容器环境变量 |
| `instances/<profile>/data/hermes/.env` | **运行时**：Hermes gateway 从 `$HERMES_HOME/.env` 读取 |

修改 `API_SERVER_*` 后需同步到 `data/hermes/.env`：

```bash
bash scripts/sync-runtime-env.sh common-writer
bash scripts/up-instance.sh common-writer   # up 时自动同步
```

容器 entrypoint 启动 gateway 前也会自动同步 compose 环境变量到 `/data/hermes/.env`。

在 `instances/<profile>/.env` 中配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_SERVER_ENABLED` | `true` | 是否启动 Agent API |
| `API_SERVER_KEY` | 自动生成 | Bearer Token（必填） |
| `API_SERVER_HOST` | `0.0.0.0` | 监听地址 |
| `API_SERVER_PORT` | `8642` | 容器内端口 |
| `API_SERVER_MODEL_NAME` | profile 名 | `/v1/models` 返回的模型名 |
| `API_SERVER_CORS_ORIGINS` | 空 | 跨域来源（默认关闭） |
| `GATEWAY_ALLOW_ALL_USERS` | `true` | Gateway 用户策略 |

关闭 Agent API（仅保留 WebUI）：

```env
API_SERVER_ENABLED=false
```

## 启动机制

容器 entrypoint（`docker/entrypoint.sh`）负责：

1. 后台启动 `hermes gateway`（监听 8642）
2. 等待 `/health` 就绪
3. 启动 Hermes WebUI（8787）
4. 任一核心进程退出则容器退出

Gateway 日志：`/data/hermes/logs/hermes-gateway.log`

## nodeskclaw 接入

实例创建后会生成 `instances/<profile>/agent-api.json`（不含 API key 明文）。

nodeskclaw 应从 `.env` 读取 `API_SERVER_KEY`，连接信息示例：

```json
{
  "base_url": "http://127.0.0.1:28900",
  "openai_base_url": "http://127.0.0.1:28900/v1",
  "health_url": "http://127.0.0.1:28900/health"
}
```

支持的 API 端点：

```text
GET  /health
GET  /v1/models
GET  /v1/capabilities
GET  /v1/skills
GET  /v1/toolsets
POST /v1/chat/completions
POST /v1/runs
GET  /v1/runs/{run_id}
GET  /v1/runs/{run_id}/events
POST /v1/runs/{run_id}/stop
```

## 验证命令

```bash
# 新建实例（自动生成 API_SERVER_KEY）
bash scripts/create-instance.sh common-writer 8900 writer

# 重建镜像并启动（Dockerfile 变更后必须 rebuild）
bash scripts/build-image.sh common-writer
bash scripts/up-instance.sh common-writer

# 检查监听
docker exec hermes-common-writer ss -lntp | grep -E '8787|8642'

# 一键验证 Agent API
bash scripts/check-agent-api.sh common-writer

# 查看 gateway 日志
bash scripts/logs.sh common-writer gateway
```

## 已有实例迁移

若 `.env` 缺少 API Server 配置：

```bash
bash scripts/migrate-instance-env.sh common-writer
bash scripts/up-instance.sh common-writer --no-cache
```

迁移脚本不会覆盖已有 `API_SERVER_KEY` 和 WebUI 密码。

## 常见错误

### Connection refused（28900 / 8642）

- 容器内无进程监听 8642 → 检查 `API_SERVER_ENABLED=true` 且 `API_SERVER_KEY` 非空
- **gateway 读 `/data/hermes/.env` 而非 `instances/<profile>/.env`** → 执行 `bash scripts/sync-runtime-env.sh <profile>` 后重启
- 镜像未重建 → 执行 `bash scripts/build-image.sh <profile> --no-cache` 后 `up-instance`
- 查看 gateway 日志：`bash scripts/logs.sh <profile> gateway`

### 401 Unauthorized

受保护接口需 Bearer Token：

```bash
source instances/<profile>/.env
curl -H "Authorization: Bearer ${API_SERVER_KEY}" http://127.0.0.1:${HERMES_GATEWAY_PORT}/v1/models
```

### gbrain MCP 启动失败

gbrain 连接失败不应阻断 API Server。若 gateway 因 gbrain 退出，可临时禁用：

```env
GBRAIN_ENABLED=0
```

## 安全提示

1. `API_SERVER_KEY` 必须使用强随机值，禁止使用 `change-me-local-dev`
2. 绑定 `0.0.0.0` 时务必配置防火墙或内网访问
3. 默认不启用 CORS；浏览器跨域访问需显式配置 `API_SERVER_CORS_ORIGINS`
