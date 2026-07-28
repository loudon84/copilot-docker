---
lat:
  require-code-mention: true
---

# Tests

Expert Factory automated tests cover protocol scaffolding, scoring invariants, branch CoW, bundle digests, Nacos mock publish, and template runtime harness smoke.

## Unit Core

Unit tests exercise planners, scoring, create/customize, branch, digest stability, and Nacos mock client without live Hermes or Nacos.

### Requirement compiler extracts capabilities

Markdown PRD sections for capabilities/external systems/constraints compile into a structured Expert Brief.

### Missing score dimensions are zero

Aggregate scoring must assign 0.0 to dimensions with no evidence instead of treating them as full marks.

### Create scaffolds full skills

Creating from Brief produces expert.yaml, skills with kind and nine sections, and structure validation pass.

### Branch create status materialize

Asset branch create stores overlay-only state, status reports sync_state, and materialize writes a full Expert Source.

### Dev bundle omits absolute source path

Dev Bundle source.json uses relative_source and includes CycloneDX SBOM without local drive absolute authority paths.

### Source digest is stable

Computing Source Digest twice on unchanged Expert Source yields identical sha256 digests.

### Nacos mock publish flow

Mock Nacos publisher can upload, submit, and publish a skill to online status.

## Integration Pipeline

Integration tests run create → validate → evaluate → release build → publish against a temporary expert.

### End to end release publish

A temporary expert completes full validation, full evaluation, release build, and mock Nacos online publish.

## Runtime Templates

Runtime tests ensure migrated writer/finance templates validate and the isolated Hermes harness returns a reply.

### Writer and finance harness smoke

Parametrized writer/finance templates pass structure validation and produce runtime-smoke harness results with a reply.

## Registry Contract

Registry tests cover Nacos client lifecycle in mock mode (live optional via WORKCOPILOT_NACOS_LIVE).

### Login upload submit publish labels

Publisher health, skill/agentspec upload, submit, wait, publish, labels, and visibility complete in mock mode.

## Golden Digests

Golden tests lock Source Digest stability for a fixed scaffolded sample expert.

### Golden sample digest roundtrip

Scaffolded golden-sample expert yields a repeatable Source Digest string.
