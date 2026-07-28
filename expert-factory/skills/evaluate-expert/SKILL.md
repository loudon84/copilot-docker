---
name: evaluate-expert
description: 对专家源码执行静态评测、结构型 Runtime Smoke 与安全 Gate。
version: 2.0.0
---

# evaluate-expert

## CLI

```bash
bash scripts/expert/expert evaluate <path> --mode static
bash scripts/expert/expert evaluate <path> --mode full
bash scripts/expert/expert evaluate <path> --mode runtime --runtime-profile <instance>
```

## 输出

```text
evaluations/results/<expert-id>/<version>/evaluation.json
evaluations/results/<expert-id>/<version>/evaluation.md
```

## 规则

- 不修改 `instances/` 生产数据
- 安全 Gate 失败则整体失败（退出码 4）
- `build --release` 必须读取通过的 evaluation 结果
- 场景用例为确定性静态判定，不调用 LLM
