# Writer Workspace Rules

Inherits base document routing from `/data/hermes/workspace/AGENTS.md` policy. Writer-specific paths:

| Output | Directory |
|--------|-----------|
| Source materials, uploads | `/data/hermes/workspace/materials` |
| Outlines, article drafts | `/data/hermes/workspace/drafts` |
| Unreviewed Markdown reports | `/data/hermes/workspace/reports` |
| Final docx/pdf/xlsx/pptx | `/data/hermes/workspace/exports` |
| Helper scripts (e.g. generate-docx.py) | `/data/hermes/workspace/scripts` |
| Reviewed IC spec Markdown | `/data/hermes/obsidian-vault/80-Product-Spec` |

**Never** write scripts, raw materials, or binary exports to `obsidian-vault`.

When generating multiple files, list path, type, purpose, and deliverable status in your reply.
