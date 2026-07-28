# nodeskclaw Expert Package API 契约（预留）

本文件固定 `copilot-docker`（Expert Factory）与 `nodeskclaw`（Expert Control Plane）之间的 Bundle 导入边界。  
**本仓库不实现这些服务端 API。**

## 职责边界

| 能力 | copilot-docker | nodeskclaw |
|------|:--------------:|:----------:|
| 专家源码生成 / 校验 / 构建 | 主责 | 验证与导入 |
| Expert Registry / 审批 / 授权 | 不负责 | 主责 |
| Connector / Secret 绑定 | 只声明 Slot | 主责 |
| 实例部署与审计 | 不负责 | 主责 |

## Bundle 导入

```http
POST /api/v1/expert-packages/import
Content-Type: multipart/form-data
```

请求字段：`bundle=<expert-id>-<version>.expert.bundle`

成功响应示例：

```json
{
  "success": true,
  "package_id": "finance-receivable-risk",
  "version": "1.0.0",
  "digest": "sha256:...",
  "status": "imported",
  "validation": {
    "schema": "passed",
    "checksum": "passed",
    "compatibility": "passed"
  }
}
```

冲突：

```json
{
  "success": false,
  "error": {
    "code": "EXPERT_VERSION_ALREADY_EXISTS",
    "message": "专家 finance-receivable-risk 的 1.0.0 版本已经存在。"
  }
}
```

## 其他预留端点

```http
GET  /api/v1/expert-packages
GET  /api/v1/expert-packages/{expert_id}
GET  /api/v1/expert-packages/{expert_id}/versions/{version}
GET  /api/v1/expert-packages/{expert_id}/versions/{version}/download
POST /api/v1/expert-packages/{expert_id}/versions/{version}/submit-review
POST /api/v1/expert-packages/{expert_id}/versions/{version}/publish
POST /api/v1/expert-packages/{expert_id}/versions/{version}/deprecate
POST /api/v1/expert-packages/{expert_id}/versions/{version}/deploy
```

## Bundle 内容约定

Expert Bundle 为 ZIP，扩展名 `.expert.bundle`，至少包含：

- `manifest/expert.yaml`
- `manifest/bundle.json`（`schema_version: workcopilot.expert-bundle.v1`）
- `manifest/checksums.sha256`
- `manifest/evaluation.json`
- `manifest/source.json`
- `runtime/`（专家运行文件）
- `docs/`
- `dependencies/`
- `sbom/components.json`

导入方必须校验：`payload_digest`、文件 checksum、无 Secret、`connector_slots` 未含生产绑定。

## CI / GitHub Release 产物对接

`copilot-docker` 通过 CI 产出可导入包：

1. **主分支 Artifact**：`expert-bundles-dev`（`build --dev`，可含 skipped evaluation）
2. **Release Tag** `expert/<expert-id>/v<version>`：正式 `.expert.bundle` + `.sha256` + `.build.json`（`build --release`，内嵌通过的 `manifest/evaluation.json`）

nodeskclaw 导入时取 Release 附件中的 `.expert.bundle`，调用：

```http
POST /api/v1/expert-packages/import
```

字段 `bundle=<file>`。导入后按 Bundle 内 `connector_slots` 做部门级 Connector / Secret 绑定（模板侧仅有 `connectors/<slot>.example.yaml` 映射，无明文密钥）。
