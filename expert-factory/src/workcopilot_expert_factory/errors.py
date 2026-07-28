"""Factory error codes (PRD §16)."""

from __future__ import annotations


class ExpertFactoryError(Exception):
    code: str = "EXPERT_FACTORY_ERROR"
    exit_code: int = 1

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.message = message


class ExpertNotFound(ExpertFactoryError):
    code = "EXPERT_NOT_FOUND"
    exit_code = 2


class ExpertSchemaInvalid(ExpertFactoryError):
    code = "EXPERT_SCHEMA_INVALID"
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
    code = "SECRET_DETECTED"
    exit_code = 4


class PathUnsafe(ExpertFactoryError):
    code = "PATH_UNSAFE"
    exit_code = 4


class ValidationFailed(ExpertFactoryError):
    code = "VALIDATION_FAILED"
    exit_code = 1


class LegacyExpert(ExpertFactoryError):
    code = "LEGACY_EXPERT"
    exit_code = 0
