# WorkCopilot Expert Factory

`copilot-docker` 的专家源码生产工具包：统一协议、校验、脚手架创建/定制与 Expert Bundle 构建。

## 安装

```bash
cd expert-factory
pip install -e ".[dev]"
```

或直接通过仓库入口（自动设置 `PYTHONPATH`）：

```bash
bash scripts/expert/expert --help
```

## 协议

| 协议 | Schema |
|------|--------|
| `workcopilot.expert.v1` | `schemas/expert-v1.schema.json` |
| `workcopilot.skill.v1` | `schemas/skill-v1.schema.json` |
| Connector Slot | `schemas/connector-slot-v1.schema.json` |
| Evaluation Suite | `schemas/evaluation-suite-v1.schema.json` |
| Expert Bundle | `schemas/expert-bundle-v1.schema.json` |

## CLI

```bash
bash scripts/expert/expert create --brief path/to/brief.yaml --output expert-templates/my-expert
bash scripts/expert/expert customize expert-templates/writer --output expert-templates/writer-acme --notes "组织定制"
bash scripts/expert/expert validate --all --level full
bash scripts/expert/expert evaluate --all --mode static
bash scripts/expert/expert build --all --dev --output dist/experts
bash scripts/expert/expert bind-check expert-templates/bi-strategic-office \
  --env-file instances/bi-strategic-office/.env
```

`evaluate` 支持 `--mode static|runtime|full`；结果写入 `evaluations/results/<id>/<version>/`。

```bash
bash scripts/expert/expert evaluate expert-templates/writer --mode static
bash scripts/expert/expert build expert-templates/writer --output dist/experts --release
```

`--release` 要求已有通过的 evaluation 报告；`--dev` 可跳过评测门禁。

## CI / 发布

| 触发 | 行为 |
|------|------|
| PR / push（路径过滤） | `validate --all` + `evaluate --all --mode static` + pytest |
| push `master`/`main` | 额外 `build --all --dev`，上传 Artifact `expert-bundles-dev` |
| Tag `expert/<id>/v<version>` | validate + evaluate full + `build --release` → GitHub Release 附件 |

本地模拟 Release：

```bash
bash scripts/expert/expert evaluate expert-templates/writer --mode full
bash scripts/expert/expert build expert-templates/writer --release --output dist/experts
```

## 注入

v1 单专家由 `inject-expert.sh` 调用 Manifest 精确注入（不拷贝 docs/prd/evaluations/bin 等）。团队专家仍走 `inject-expert-team.sh`。

## 与 Asset Bundle 的区别

- **Asset Bundle**：实例间迁移运行资产（skills/tools/plugins…）
- **Expert Bundle**：可注册、可审核的专家产品发布包（含 Manifest / checksum / SBOM）

详见 [docs/nodeskclaw-api.md](docs/nodeskclaw-api.md)。

## Factory Skills

`skills/create-expert` 等为 **Cursor Agent 生产流程** Skill，不是 Hermes 运行时 Skill。
