# Domain

WorkCopilot domain objects are Expert Source, Skill, Connector Slot, Evaluation, Expert Bundle, Asset Branch, and Publish Record — the vocabulary shared by Factory, Nacos, and Runtime.

## Product Boundaries

copilot-docker produces and packages experts; nodeskclaw governs runtime binding; Hermes executes conversations.

| System | Owns | Does not own |
|--------|------|----------------|
| copilot-docker | Source, validate, evaluate, bundle, publish adapters, Hermes image/instances | Org RBAC, secret vault UI, marketplace |
| Nacos AI Registry | AgentSpec/Skill version lifecycle | Bundle authoring |
| Hermes | Skill/tool/plugin execution | Expert schema design |

Non-goals for Factory v2.1 include modifying Hermes core, auto-approving business publish, and storing production secrets in Git.

## Expert Source

An Expert Source is a versioned directory under `expert-templates/<id>/` described by `workcopilot.expert.v1` Manifest (`expert.yaml`).

Required shape includes SOUL entrypoint, skills/policies references, default-deny permissions, and an evaluation suite. Single mode uses top-level `SOUL.md`; team mode uses `team.yaml` + `root/` + `profiles/`. Models: [[expert-factory/src/workcopilot_expert_factory/models/__init__.py#ExpertManifest]].

Infrastructure templates `base/` and `default/` are scaffolds for inject scripts, not publishable business experts.

## Skill

A Skill is a procedural unit with `workcopilot.skill.v1` frontmatter and nine Chinese body sections under `skills/**/SKILL.md`.

`kind` may be procedural, general, tool, connector, or policy. Missing `kind` is a publish warning. Skills declare tool/connector requirements but never embed production URLs or secrets.

## Connector Slot

Connector Slots declare required external capabilities (MCP/HTTP/tool) without binding instance credentials.

Binding happens at deploy time via instance `.env`; Factory only checks slot completeness with `bind-check`. Access mode defaults to read-only; write expansion is a governance event.

## Evaluation Suite and Report

Evaluation suites (`evaluations/cases.yaml`) define task/policy/security/runtime cases; reports bind to Source Digest so stale results cannot release.

Report v2 fields include source digest, runtime info, cost, and decision gates. Aggregation lives in [[expert-factory/src/workcopilot_expert_factory/evaluators/scoring.py#aggregate]]; missing score dimensions contribute 0, not 1.0.

## Expert Bundle

An Expert Bundle is an immutable ZIP (`.expert.bundle`) with whitelist runtime payload, SBOM, checksums, evaluation binding, and optional signature.

Built by [[expert-factory/src/workcopilot_expert_factory/builders/bundle.py#build_expert_bundle]]. Dev bundles may skip full eval; Release bundles require matching evaluation digest and `dev: false`. Absolute local paths and `built_at` must not enter the deterministic payload.

## Expert Asset Branch

An Asset Branch is Copy-on-Write overlay storage under `.workcopilot/branches/<expert-id>/<branch-id>/`, not a Git branch.

It records base Source Digest, overlay files, and sync_state (`synced|behind|diverged|conflicted|materialized`). Materialize produces a full Expert Source. Implementation: [[expert-factory/src/workcopilot_expert_factory/services/branch.py#create_branch]].

## Publish Record

A Publish Record maps a Release Bundle digest to Nacos AgentSpec/Skill versions, stage, and resume metadata.

Stored under `.workcopilot/publish/<id>/`. Publishing converts Bundle → AgentSpec ZIP + per-skill ZIPs; it does not Base64-stuff bundles into Nacos config center. See [[expert-factory/src/workcopilot_expert_factory/services/publish.py#publish_expert]].
