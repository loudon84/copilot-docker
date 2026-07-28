# Design Decisions

These decisions constrain how Expert Factory evolves without breaking Hermes inject paths or nodeskclaw import contracts.

## Dual Layer Skill and CLI

Each production capability has an Agent Skill (orchestration narrative) and a deterministic Python CLI (file/protocol ops).

Skills live in `expert-factory/skills/<name>/SKILL.md`; CLI is unified as `scripts/expert/expert` → [[expert-factory/src/workcopilot_expert_factory/cli.py#run]]. Agents must not hand-edit `instances/` to “create” experts.

## Default Deny Permissions

Expert permissions default to deny for tools and network; expansion during customize requires `--allow-permission-expansion` and blocks auto-publish.

Rationale: experts are often injected into shared runtimes; accidental allow-all is a supply-chain risk. Diff logic: [[expert-factory/src/workcopilot_expert_factory/validators/permissions.py#permission_expansion_diff]].

## Whitelist Bundle Packaging

Release packaging includes only an explicit whitelist of paths; full-tree-minus-exclude is rejected as release logic.

Source Digest hashes sorted relative paths + contents for release files only ([[expert-factory/src/workcopilot_expert_factory/digest.py#compute_source_digest]]). This enables reproducible Payload Digest under `SOURCE_DATE_EPOCH`.

## Evaluation Binds Source Digest

Release builds refuse evaluation reports whose `source_digest` differs from the current source hash.

Prevents shipping a Bundle that passed eval on different content. Stale eval raises [[expert-factory/src/workcopilot_expert_factory/errors.py#EvaluationStale]].

## Isolated Hermes Eval Harness

Runtime evaluation uses a disposable `.workcopilot/cache/evaluations/<run-id>/` HERMES_HOME and must not mutate `instances/` or user `~/.hermes`.

When live Gateway is unavailable, harness simulates replies but still exercises inject + fixture wiring ([[expert-factory/src/workcopilot_expert_factory/evaluators/hermes_runtime.py#run_hermes_runtime_harness]]). Live mode is opt-in via `HERMES_EVAL_LIVE=1`.

## Nacos as Registry Not Config Dump

Publish maps Expert→AgentSpec and Skill→Skill packages with `x-workcopilot` extensions carrying Bundle digest — not Config Center Base64 blobs.

Supports draft/review/online stages, idempotent same-digest republish, and version+digest conflict hard-fail ([[expert-factory/src/workcopilot_expert_factory/publishers/nacos.py#NacosPublisher]]). Adapters: [[expert-factory/src/workcopilot_expert_factory/adapters/nacos_agentspec.py#prepare_nacos_artifacts]], [[expert-factory/src/workcopilot_expert_factory/adapters/nacos_skill.py#pack_skill]].

## Human-gated Online Publish

Production Online publish must not fire on plain git push; only `workflow_dispatch` plus Environment approval may promote a Release Bundle.

Release tags may auto-draft to Nacos when `NACOS_DRAFT_ON_RELEASE=true`. Online/review for test/prod uses `.github/workflows/expert-publish.yml` with `environment: nacos-*`. Credentials stay in GitHub secrets / env (`NACOS_*`), never in registry YAML.

## Secrets Never in Source or Logs

Templates and Bundles must not ship `.env` or real API keys; scanners cover Bundle candidates including `scripts/` and `config.yaml`.

Docs/prd/tests may mention password fields; example env files are skipped. Structured events redact sensitive keys ([[expert-factory/src/workcopilot_expert_factory/events.py#_redact]]).

## Backward Compatible Protocol Growth

v2.1 adds branch/report/publish schemas without breaking `workcopilot.expert.v1` / `skill.v1` / `expert-bundle.v1`.

Missing Skill `kind` warns; missing registry blocks publish but allows Dev Bundle; old evaluation reports are stale and must be regenerated.
