---
name: build-expert
description: 将通过校验的专家构建为 Expert Bundle。
version: 2.0.0
---

# build-expert

```bash
bash scripts/expert/expert build <path> --output dist/experts --dev --skip-runtime-evaluation
```

核心版本允许 `--dev` 跳过 evaluation。正式发布：

```bash
bash scripts/expert/expert evaluate <path> --mode full
bash scripts/expert/expert build <path> --output dist/experts --release
```
