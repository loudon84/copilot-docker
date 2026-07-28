# Production Pipeline

The v2.1 production chain is create → customize/branch → validate → evaluate → build → publish, forming an end-to-end Expert Bundle release path.

## Create Expert

Create compiles requirements or Brief into Plan, discovers reusable components, then scaffolds Expert Source.

Entry: [[expert-factory/src/workcopilot_expert_factory/services/create.py#create_expert]]. Planners: requirement compiler, component catalog, component planner under `planners/`. Output must pass structure validation and contain no secrets.

## Customize Expert

Customize copies a source expert into a new id with structured change specs and permission-expansion gates.

Entry: [[expert-factory/src/workcopilot_expert_factory/services/customize.py#customize_expert]]. Writes customization/permission/component diff docs and provenance.derived_from. Source directory must remain unmodified.

## Branch Expert

Branch stores overlays only, tracks sync against upstream Source Digest, and materializes full sources when needed.

Commands: create/status/diff/rebase/materialize via CLI branch group. Conflicts on protected permission/security fields refuse auto-merge ([[expert-factory/src/workcopilot_expert_factory/services/branch.py#branch_rebase]]).

## Validate Expert

Validate covers structure, schema, security, dependencies, runtime, release, and full — for Source, Branch, or Bundle paths.

Entry: [[expert-factory/src/workcopilot_expert_factory/validators/expert.py#validate_expert]]. Bundle ZIP checks path safety, checksums, bomb limits, and optional re-validation of extracted runtime ([[expert-factory/src/workcopilot_expert_factory/validators/bundle.py#validate_bundle]]).

## Evaluate Expert

Evaluate runs static checks, adversarial security cases, optional isolated Hermes runtime cases, and writes Report v2 with source_digest.

Entry: [[expert-factory/src/workcopilot_expert_factory/services/evaluate.py#evaluate_expert]]. Gate failures (schema/secret/permission/injection/runtime) fail the run regardless of aggregate score.

## Build Expert

Build produces deterministic Dev or Release Bundles with CycloneDX SBOM and signature metadata.

Entry: [[expert-factory/src/workcopilot_expert_factory/builders/bundle.py#build_expert_bundle]]. Release mode requires non-skipped evaluation matching current Source Digest. SBOM: [[expert-factory/src/workcopilot_expert_factory/builders/sbom.py#build_cyclonedx_sbom]]; signatures: [[expert-factory/src/workcopilot_expert_factory/builders/signature.py#sign_digest]]; Nacos ZIP materialization: [[expert-factory/src/workcopilot_expert_factory/builders/nacos_package.py#materialize_nacos_packages]].

## Publish Expert

Publish uploads Skills then AgentSpec to a Nacos target through draft/review/online with resume support.

Entry: [[expert-factory/src/workcopilot_expert_factory/services/publish.py#publish_expert]]. Target configs live in `.workcopilot/registry/<target>.yaml`; credentials only via env (`NACOS_*`). CI wiring: [[architecture#CI Release and Publish]].
