"""Factory error codes (PRD v2.1 §17)."""

from __future__ import annotations

from typing import Any


# Stable error codes for CLI / CI / nodeskclaw
ERROR_CODES = frozenset(
    {
        "E_BRIEF_INVALID",
        "E_PLAN_INVALID",
        "E_COMPONENT_DUPLICATE",
        "E_CUSTOMIZE_PERMISSION_EXPANSION",
        "E_BRANCH_NOT_FOUND",
        "E_BRANCH_BEHIND",
        "E_BRANCH_CONFLICT",
        "E_BRANCH_NOT_MATERIALIZED",
        "E_SCHEMA_INVALID",
        "E_SECRET_DETECTED",
        "E_PATH_UNSAFE",
        "E_DEPENDENCY_INVALID",
        "E_LICENSE_DENIED",
        "E_VULNERABILITY_GATE",
        "E_EVALUATION_REQUIRED",
        "E_EVALUATION_STALE",
        "E_EVALUATION_FAILED",
        "E_SECURITY_GATE_FAILED",
        "E_BUNDLE_INVALID",
        "E_BUNDLE_DIGEST_MISMATCH",
        "E_BUNDLE_SIGNATURE_INVALID",
        "E_RELEASE_BUNDLE_REQUIRED",
        "E_REGISTRY_UNAVAILABLE",
        "E_REGISTRY_AUTH_FAILED",
        "E_PUBLISH_VERSION_CONFLICT",
        "E_PUBLISH_REVIEW_FAILED",
        "E_PUBLISH_TIMEOUT",
        "E_PUBLISH_PARTIAL",
        # v2.0 compatibility aliases
        "EXPERT_NOT_FOUND",
        "EXPERT_SCHEMA_INVALID",
        "EXPERT_ID_MISMATCH",
        "EXPERT_VERSION_INVALID",
        "SKILL_SCHEMA_INVALID",
        "COMPONENT_MISSING",
        "SECRET_DETECTED",
        "PATH_UNSAFE",
        "VALIDATION_FAILED",
        "LEGACY_EXPERT",
        "BRIEF_INVALID",
        "OUTPUT_EXISTS",
    }
)


class ExpertFactoryError(Exception):
    code: str = "EXPERT_FACTORY_ERROR"
    exit_code: int = 1
    payload: dict[str, Any] | None = None

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        exit_code: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        if code:
            self.code = code
        if exit_code is not None:
            self.exit_code = exit_code
        self.message = message
        self.payload = payload


class ExpertNotFound(ExpertFactoryError):
    code = "EXPERT_NOT_FOUND"
    exit_code = 2


class ExpertSchemaInvalid(ExpertFactoryError):
    code = "E_SCHEMA_INVALID"
    exit_code = 1


class ExpertIdMismatch(ExpertFactoryError):
    code = "EXPERT_ID_MISMATCH"
    exit_code = 1


class ExpertVersionInvalid(ExpertFactoryError):
    code = "EXPERT_VERSION_INVALID"
    exit_code = 1


class SkillSchemaInvalid(ExpertFactoryError):
    code = "SKILL_SCHEMA_INVALID"
    exit_code = 1


class ComponentMissing(ExpertFactoryError):
    code = "COMPONENT_MISSING"
    exit_code = 1


class SecretDetected(ExpertFactoryError):
    code = "E_SECRET_DETECTED"
    exit_code = 4


class PathUnsafe(ExpertFactoryError):
    code = "E_PATH_UNSAFE"
    exit_code = 4


class ValidationFailed(ExpertFactoryError):
    code = "VALIDATION_FAILED"
    exit_code = 1


class LegacyExpert(ExpertFactoryError):
    code = "LEGACY_EXPERT"
    exit_code = 0


class BriefInvalid(ExpertFactoryError):
    code = "E_BRIEF_INVALID"
    exit_code = 1


class PlanInvalid(ExpertFactoryError):
    code = "E_PLAN_INVALID"
    exit_code = 1


class ComponentDuplicate(ExpertFactoryError):
    code = "E_COMPONENT_DUPLICATE"
    exit_code = 1


class PermissionExpansion(ExpertFactoryError):
    code = "E_CUSTOMIZE_PERMISSION_EXPANSION"
    exit_code = 1


class BranchNotFound(ExpertFactoryError):
    code = "E_BRANCH_NOT_FOUND"
    exit_code = 2


class BranchBehind(ExpertFactoryError):
    code = "E_BRANCH_BEHIND"
    exit_code = 1


class BranchConflict(ExpertFactoryError):
    code = "E_BRANCH_CONFLICT"
    exit_code = 1


class BranchNotMaterialized(ExpertFactoryError):
    code = "E_BRANCH_NOT_MATERIALIZED"
    exit_code = 1


class EvaluationRequired(ValidationFailed):
    code = "E_EVALUATION_REQUIRED"
    exit_code = 1


class EvaluationStale(ValidationFailed):
    code = "E_EVALUATION_STALE"
    exit_code = 1


class EvaluationFailed(ExpertFactoryError):
    code = "E_EVALUATION_FAILED"
    exit_code = 1


class BundleInvalid(ExpertFactoryError):
    code = "E_BUNDLE_INVALID"
    exit_code = 1


class BundleDigestMismatch(ExpertFactoryError):
    code = "E_BUNDLE_DIGEST_MISMATCH"
    exit_code = 1


class BundleSignatureInvalid(ExpertFactoryError):
    code = "E_BUNDLE_SIGNATURE_INVALID"
    exit_code = 4


class ReleaseBundleRequired(ExpertFactoryError):
    code = "E_RELEASE_BUNDLE_REQUIRED"
    exit_code = 1


class RegistryUnavailable(ExpertFactoryError):
    code = "E_REGISTRY_UNAVAILABLE"
    exit_code = 1


class RegistryAuthFailed(ExpertFactoryError):
    code = "E_REGISTRY_AUTH_FAILED"
    exit_code = 1


class PublishVersionConflict(ExpertFactoryError):
    code = "E_PUBLISH_VERSION_CONFLICT"
    exit_code = 1


class PublishReviewFailed(ExpertFactoryError):
    code = "E_PUBLISH_REVIEW_FAILED"
    exit_code = 1


class PublishTimeout(ExpertFactoryError):
    code = "E_PUBLISH_TIMEOUT"
    exit_code = 1


class PublishPartial(ExpertFactoryError):
    code = "E_PUBLISH_PARTIAL"
    exit_code = 1
