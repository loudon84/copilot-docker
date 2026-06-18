# Workspace Agent Rules

Profile: __PROFILE__
Expert: __EXPERT__

## Allowed roots

- `/data/hermes/workspace`
- `/data/hermes/obsidian-vault`
- `/data/hermes/skills`
- `/data/hermes/evolution`

Do not read or write host files outside these roots unless the user explicitly provides task-specific approval.

## File operation contract

**Before every file write**, classify the file:

1. **Materials** — user uploads, external downloads → `workspace/materials`
2. **References** — extracted specs, web summaries, OCR text → `workspace/references`
3. **Drafts** — outlines, PRD drafts, article drafts → `workspace/drafts`
4. **Reports** — unreviewed Markdown reports → `workspace/reports`
5. **Final exports** — `.docx`, `.pdf`, `.xlsx`, `.pptx` for user delivery → `workspace/exports`
6. **Artifacts** — HTML UI, charts, Mermaid, visual prototypes → `workspace/artifacts`
7. **Scripts** — `.py`, `.sh`, `.js`, `.ts`, `.mjs`, `.ps1` helper scripts → `workspace/scripts`
8. **Temp** — cache, conversion intermediates → `workspace/tmp`
9. **Runtime** — run logs, job/pipeline state → `workspace/runtime`
10. **Knowledge** — reviewed Markdown for long-term retention → `obsidian-vault/<category>` only
11. **Skills** — Hermes `SKILL.md` and skill assets → `skills/<category>/<skill-name>`

## Hard rules

1. **Executable scripts must not be written to Obsidian.** Use `workspace/scripts`.
2. **Final export files must go to `workspace/exports`.** Never default to Obsidian for `.docx`, `.pdf`, `.xlsx`, `.pptx`.
3. **Drafts go to `workspace/drafts`.** Not Obsidian until reviewed and explicitly archived.
4. **Raw materials go to `workspace/materials`.** Not Obsidian.
5. **Only reviewed Markdown knowledge** may enter `obsidian-vault`. IC product specs → `80-Product-Spec`; archived reports → `60-Reports`.
6. **Skills** belong under `skills/` only — not workspace or Obsidian (except readable skill docs in `obsidian-vault/40-Skills`).

## Obsidian write restrictions

**Forbidden in obsidian-vault:** `.py`, `.sh`, `.js`, `.ts`, `.docx`, `.pdf`, `.xlsx`, `.pptx`, `.zip`, `.tmp`, `.log`, binaries.

**Allowed:** `.md`, `.txt`, `.yaml`, `.yml`, knowledge-index `.json`/`.csv` (not runtime cache).

## Multi-file output

When generating multiple files in one task:

1. Route each file to the correct subdirectory.
2. In your reply, list: **path**, **type**, **purpose**, **final deliverable (yes/no)**, **Obsidian archive (yes/no)**.
3. Optionally write a manifest: `workspace/artifacts/<task-name>.manifest.json`.

Full policy: `/data/hermes/policies/document-routing.yaml`
