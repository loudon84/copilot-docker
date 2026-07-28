---
name: validate-expert
description: 调用 Expert Factory CLI 校验专家源码。
version: 2.0.0
---

# validate-expert

```bash
bash scripts/expert/expert validate <path> --level structure|schema|security|full --format both
```

Legacy（无 v1 `expert.yaml`）在 structure 级给出警告，不强制失败（除非结构本身损坏）。
