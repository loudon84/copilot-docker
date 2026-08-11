# Architecture

copilot-docker is the WorkCopilot Expert Factory plus Hermes runtime kit: produce expert source, validate, evaluate, build bundles, publish to Nacos, and run multi-instance Hermes agents.

This repository owns expert source production and local/server Hermes deployment. Production control-plane concerns (org authz, secret binding UI, marketplace) live in nodeskclaw and related systems — see [[domain#Product Boundaries]].

## System Overview

Three cooperating layers form the product: Factory (source/governance), Registry (Nacos publish), and Runtime (Hermes instances).

```text
Brief/PRD → create/customize/branch
         → validate → evaluate → build (.expert.bundle)
         → publish (Nacos AgentSpec + Skills)
         → inject-expert → Hermes container instance
```

Factory CLI entry is [[expert-factory/src/workcopilot_expert_factory/cli.py#run]]. Instance lifecycle uses `scripts/create-instance.sh`, `scripts/inject-expert.sh`, `scripts/clone-instance.sh` ([[runtime#Runtime Deployment#Instance Capability Clone]]), and Docker Compose.

## Package Layout

The Python package `workcopilot-expert-factory` (2.1.0) under `expert-factory/` implements the factory; templates live in `expert-templates/`; runtime scripts live in `scripts/`.

| Area | Path | Role |
|------|------|------|
| Factory CLI / lib | `expert-factory/src/workcopilot_expert_factory/` | create→publish pipeline |
| Planners | `…/planners/` | requirement compiler, catalog, plan |
| Validators | `…/validators/` | structure→release + bundle/security |
| Evaluators | `…/evaluators/` | static, scenario, security, Hermes harness |
| Builders | `…/builders/` | bundle, SBOM, signature, Nacos packages |
| Adapters / publishers | `…/adapters/`, `…/publishers/` | AgentSpec/Skill pack + Nacos client |
| Schemas | `expert-factory/schemas/` | JSON Schema for protocols |
| Factory Skills | `expert-factory/skills/` | Agent-facing SOP for each CLI |
| Expert Source | `expert-templates/<id>/` | Business expert templates |
| Instances | `instances/<profile>/` | Per-profile Hermes data mounts |
| Work state | `.workcopilot/` | drafts, branches, publish records, cache |
| CI | `.github/workflows/expert-*.yml` | tag release + gated publish |

## CI Release and Publish

Tag-driven release builds Release Bundles; online Nacos publish is a separate human-gated workflow.

`expert-release.yml` runs on tags `expert/<id>/v*`: full validate → full evaluate → release build → optional Nacos draft → GitHub Release assets. `expert-publish.yml` is `workflow_dispatch` only, binds GitHub Environment `${{ inputs.target }}`, and never runs on plain push — see [[decisions#Human-gated Online Publish]].

## Runtime Kit

Docker Compose runs Hermes WebUI + Agent API with per-profile volume mounts under `instances/${HERMES_PROFILE}/data/hermes`.

Image build and instance create/up/restart remain shell-script driven (`scripts/build-image.sh`, `scripts/create-instance.sh`). Expert injection maps Manifest components into `HERMES_HOME` without copying secrets from templates. Create-only capability cloning between instances is [[runtime#Runtime Deployment#Instance Capability Clone]].

## Observability and Errors

Factory operations emit structured stderr JSON events via [[expert-factory/src/workcopilot_expert_factory/events.py#emit]] and fail with stable codes from [[expert-factory/src/workcopilot_expert_factory/errors.py#ExpertFactoryError]].

Events must never log tokens, passwords, or raw auth headers. CLI supports `--trace-id`, `--quiet`, and `--format text|json|both` for CI and Agent orchestration.

## CI Release and Publish

Tag-driven release builds Release Bundles; Online Nacos publish is manual via workflow_dispatch and GitHub Environments.

- `expert-release.yml` — on `expert/<id>/v*` tags: validate full → evaluate full → build `--release` → optional Nacos draft → GitHub Release assets.
- `expert-publish.yml` — `workflow_dispatch` only; `environment: <target>` gates credentials; never runs on plain push.

See [[decisions#Human-gated Online Publish]] and [[pipeline#Publish Expert]].
