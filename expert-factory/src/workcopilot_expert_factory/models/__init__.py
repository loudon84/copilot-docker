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


class ReleaseSpec(BaseModel):
    publishable: bool = True
    approval: ReleaseApproval = Field(default_factory=ReleaseApproval)


class DerivedFrom(BaseModel):
    expert_id: str
    version: str


class ProvenanceSpec(BaseModel):
    source_repository: str | None = None
    derived_from: DerivedFrom | None = None


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
    source_commit: str | None = None
    source_path: str
    build_tool_version: str = "2.0.0"
    runtime: dict[str, str] = Field(default_factory=dict)
    dev: bool = False
