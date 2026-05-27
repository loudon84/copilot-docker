# Hermes Workspace Rules

## 允许写入

- /data/hermes/workspace
- /data/hermes/obsidian-vault

## 禁止写入

- /data/hermes/.env
- /data/hermes/config.yaml
- /root
- /etc
- /usr
- /var/lib

## Hindsight 规则

允许写入：长期偏好、确认过的事实口径、可复用流程、复盘结论。
禁止写入：API Key、Token、密码、客户敏感明细、未确认事实、用户明确要求不记忆的内容。

## Obsidian 规则

产出可长期复用的文档时，优先保存为 Markdown，并带 YAML frontmatter。
