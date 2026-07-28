from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ComponentRef(BaseModel):
    id: str
    path: str
    required: bool = True
    version: str | None = None


class PolicyRef(BaseModel):
    path: str


class ExpertMetadata(BaseModel):
    id: str
    name: str
    version: str
    description: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    language: str = "zh-CN"
    owner: str | None = None


class RuntimeEntrypoints(BaseModel):
    soul: str = "SOUL.md"
    agents: str | None = None
    config_patch: str | None = None
    team: str | None = None


class RuntimeSpec(BaseModel):
    engine: Literal["hermes"] = "hermes"
    mode: Literal["single", "team"] = "single"
    compatibility: dict[str, str] = Field(default_factory=dict)
    entrypoints: RuntimeEntrypoints = Field(default_factory=RuntimeEntrypoints)


class ComponentsSpec(BaseModel):
    skills: list[ComponentRef] = Field(default_factory=list)
    tools: list[ComponentRef] = Field(default_factory=list)
    plugins: list[ComponentRef] = Field(default_factory=list)
    policies: list[PolicyRef] = Field(default_factory=list)


class ConnectorAuth(BaseModel):
    mode: str = "managed-secret"
    required_fields: list[str] = Field(default_factory=list)


class ConnectorHealthcheck(BaseModel):
    tool: str | None = None
    timeout_seconds: int = 30


class ConnectorSlot(BaseModel):
    id: str
    name: str
    type: Literal["mcp", "http", "internal-tool"]
    category: str
    required: bool = True
    access_mode: Literal["read-only", "read-write", "write"] = "read-only"
    capabilities: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    auth: ConnectorAuth | None = None
    healthcheck: ConnectorHealthcheck | None = None
    data_classification: str | None = None


class ToolPermissions(BaseModel):
    default: Literal["deny", "allow"] = "deny"
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class NetworkPermissions(BaseModel):
    default: Literal["deny", "allow"] = "deny"
    connector_slots: list[str] = Field(default_factory=list)


class DataPermissions(BaseModel):
    maximum_classification: str = "internal"
    export_allowed: bool = False


class PermissionsSpec(BaseModel):
    tools: ToolPermissions = Field(default_factory=ToolPermissions)
    network: NetworkPermissions = Field(default_factory=NetworkPermissions)
    data: DataPermissions = Field(default_factory=DataPermissions)


class EvaluationsSpec(BaseModel):
    suite: str = "evaluations/cases.yaml"
    minimum_score: float = 0.9
    required_gates: list[str] = Field(default_factory=lambda: ["schema", "security"])


class ReleaseApproval(BaseModel):
    business: str = "required"
    security: str = "required"


class ReleaseRegistry(BaseModel):
    provider: str = "nacos"
    visibility: Literal["PRIVATE", "PUBLIC"] = "PRIVATE"
    labels: dict[str, str] = Field(default_factory=dict)


class ReleaseSpec(BaseModel):
    publishable: bool = True
    registry: ReleaseRegistry | None = None
    approval: ReleaseApproval = Field(default_factory=ReleaseApproval)


class DerivedFrom(BaseModel):
    expert_id: str
    version: str


class ProvenanceBranch(BaseModel):
    branch_id: str | None = None
    base_version: str | None = None
    base_digest: str | None = None


class ProvenanceSpec(BaseModel):
    source_repository: str | None = None
    source_digest: str | None = None
    derived_from: DerivedFrom | None = None
    branch: ProvenanceBranch | None = None


class ExpertManifest(BaseModel):
    schema_version: Literal["workcopilot.expert.v1"] = "workcopilot.expert.v1"
    kind: Literal["expert"] = "expert"
    metadata: ExpertMetadata
    runtime: RuntimeSpec
    components: ComponentsSpec = Field(default_factory=ComponentsSpec)
    connector_slots: list[ConnectorSlot] = Field(default_factory=list)
    permissions: PermissionsSpec = Field(default_factory=PermissionsSpec)
    evaluations: EvaluationsSpec = Field(default_factory=EvaluationsSpec)
    release: ReleaseSpec = Field(default_factory=ReleaseSpec)
    provenance: ProvenanceSpec = Field(default_factory=ProvenanceSpec)

    def to_yaml_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude_none=True)


SkillKind = Literal["procedural", "general", "tool", "connector", "policy"]


class SkillScope(BaseModel):
    includes: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)


class SkillInputs(BaseModel):
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class SkillOutputs(BaseModel):
    format: str = "structured-markdown"
    contract: str | None = None


class SkillPermissions(BaseModel):
    access_mode: str = "read-only"
    data_classification: str = "internal"


class SkillFrontmatter(BaseModel):
    schema_version: Literal["workcopilot.skill.v1"] = "workcopilot.skill.v1"
    id: str
    name: str
    version: str
    description: str
    kind: SkillKind | None = None
    triggers: list[str] = Field(default_factory=list)
    scope: SkillScope = Field(default_factory=SkillScope)
    inputs: SkillInputs = Field(default_factory=SkillInputs)
    outputs: SkillOutputs = Field(default_factory=SkillOutputs)
    tool_requirements: list[str] = Field(default_factory=list)
    connector_requirements: list[str] = Field(default_factory=list)
    permissions: SkillPermissions = Field(default_factory=SkillPermissions)
    references: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)


class BundleManifest(BaseModel):
    schema_version: Literal["workcopilot.expert-bundle.v1"] = "workcopilot.expert-bundle.v1"
    expert_id: str
    expert_version: str
    bundle_format: Literal["zip"] = "zip"
    payload_digest: str
    source_digest: str | None = None
    source_commit: str | None = None
    source_path: str | None = None
    build_tool_version: str = "2.1.0"
    runtime: dict[str, Any] = Field(default_factory=dict)
    evaluation_digest: str | None = None
    signature_mode: str = "none"
    dev: bool = False


SyncState = Literal["synced", "behind", "diverged", "conflicted", "materialized"]


class BranchSource(BaseModel):
    expert_id: str
    version: str
    source_digest: str


class BranchTarget(BaseModel):
    expert_id: str
    version: str = "1.0.0"


class BranchState(BaseModel):
    sync_state: SyncState = "synced"
    base_digest: str
    head_digest: str


class BranchOverlay(BaseModel):
    files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)


class BranchPermissions(BaseModel):
    allow_expansion: bool = False


class BranchManifest(BaseModel):
    schema_version: Literal["workcopilot.expert-branch.v1"] = "workcopilot.expert-branch.v1"
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: BranchSource
    target: BranchTarget
    state: BranchState
    overlay: BranchOverlay = Field(default_factory=BranchOverlay)
    permissions: BranchPermissions = Field(default_factory=BranchPermissions)

    def to_yaml_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude_none=True)


class EvaluationSource(BaseModel):
    expert_id: str
    expert_version: str
    source_digest: str
    git_commit: str | None = None
    branch_id: str | None = None


class EvaluationRuntimeInfo(BaseModel):
    engine: str = "hermes"
    hermes_version: str | None = None
    model: str | None = None
    connector_fixture_set: str | None = None


class EvaluationCost(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    duration_ms: int = 0


class EvaluationDecision(BaseModel):
    passed: bool
    score: float
    gate_failures: list[str] = Field(default_factory=list)


class EvaluationReportV2(BaseModel):
    schema_version: Literal["workcopilot.evaluation-report.v2"] = "workcopilot.evaluation-report.v2"
    source: EvaluationSource
    runtime: EvaluationRuntimeInfo = Field(default_factory=EvaluationRuntimeInfo)
    results: dict[str, Any] = Field(default_factory=dict)
    cost: EvaluationCost = Field(default_factory=EvaluationCost)
    decision: EvaluationDecision
    factory_version: str = "2.1.0"
    fixture_digest: str | None = None
    generated_at: str | None = None


class PublishSkillRecord(BaseModel):
    id: str
    version: str
    digest: str | None = None
    status: str = "draft"


class PublishRecord(BaseModel):
    schema_version: Literal["workcopilot.publish-record.v1"] = "workcopilot.publish-record.v1"
    publish_id: str
    expert: dict[str, Any] = Field(default_factory=dict)
    registry: dict[str, Any] = Field(default_factory=dict)
    skills: list[PublishSkillRecord] = Field(default_factory=list)
    publication: dict[str, Any] = Field(default_factory=dict)
    stage: Literal["draft", "review", "online"] = "draft"
    status: str = "started"
    resume_token: str | None = None

    def to_yaml_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude_none=True)
