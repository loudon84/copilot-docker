# 协议摘要

- Expert Manifest：`expert-templates/<id>/expert.yaml`，`schema_version: workcopilot.expert.v1`
- Skill：`skills/<skill-id>/SKILL.md` frontmatter `workcopilot.skill.v1` + 九个标准章节
- Connector Slot：只声明能力，不绑定生产 Endpoint/Secret
- Expert Bundle：由 `build` 产出 `.expert.bundle`，与 Asset Bundle 分离
