# Protocols

Factory protocols are versioned YAML/JSON contracts validated by JSON Schema under `expert-factory/schemas/` and Pydantic models in the package.

## Expert Manifest v1

`workcopilot.expert.v1` is the authoritative expert identity: metadata, runtime, components, connector_slots, permissions, evaluations, release, provenance.

Schema file: `expert-factory/schemas/expert-v1.schema.json`. Directory name must equal `metadata.id`. Team mode requires `team.yaml`, `root/`, and `profiles/`.

## Skill v1

`workcopilot.skill.v1` frontmatter plus nine required Chinese sections defines executable skill docs.

Schema: `expert-factory/schemas/skill-v1.schema.json`. Component id must match frontmatter id. Publish warns if `kind` is absent.

## Connector Slot v1

Slots describe external system needs with access_mode and allowed_tools without embedding secrets.

Schema: `expert-factory/schemas/connector-slot-v1.schema.json`. Network permission lists must reference declared slot ids.

## Evaluation Suite v1

Suites list cases with types spanning task, policy, security, resilience, injection, regression, and team-delegation.

Schema: `expert-factory/schemas/evaluation-suite-v1.schema.json`. Case `prompt` plus `expected` drive static and runtime runners.

## Evaluation Report v2

Report v2 binds results to `source_digest` and records runtime/cost/decision for release gates.

Schema: `expert-factory/schemas/evaluation-report-v2.schema.json`. Model: [[expert-factory/src/workcopilot_expert_factory/models/__init__.py#EvaluationReportV2]].

## Expert Branch v1

Branch manifests record source/target ids, digests, overlay file lists, and sync_state.

Schema: `expert-factory/schemas/expert-branch-v1.schema.json`. Model: [[expert-factory/src/workcopilot_expert_factory/models/__init__.py#BranchManifest]].

## Expert Bundle v1

Bundle metadata (`manifest/bundle.json`) carries payload_digest, source_digest, evaluation_digest, signature_mode, and dev flag.

Schema: `expert-factory/schemas/expert-bundle-v1.schema.json`. Model: [[expert-factory/src/workcopilot_expert_factory/models/__init__.py#BundleManifest]].

## Publish Record v1

Publish records audit Nacos mapping for an expert version and skill list with resume tokens.

Schema: `expert-factory/schemas/publish-record-v1.schema.json`. Model: [[expert-factory/src/workcopilot_expert_factory/models/__init__.py#PublishRecord]].
