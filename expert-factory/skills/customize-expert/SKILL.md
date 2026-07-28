---
name: customize-expert
description: 从已有专家派生定制版本，不修改源专家。
version: 2.0.0
---

# customize-expert

## CLI

```bash
bash scripts/expert/expert customize expert-templates/<source> \
  --output expert-templates/<new-id> \
  --notes "组织定制说明"
```

## 规则

- 必须复制到新目录；禁止原地改源专家
- 写入 `provenance.derived_from`
- 更新 `metadata.id` 与目录名一致
- 生成 `docs/customization-report.md`
- 结束后 `validate --level structure`
