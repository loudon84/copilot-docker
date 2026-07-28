"""Publisher abstract base."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Publisher(ABC):
    @abstractmethod
    def health(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def upload_skill(self, skill_id: str, version: str, zip_bytes: bytes, *, overwrite_draft: bool = False) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def upload_agentspec(self, name: str, version: str, zip_bytes: bytes, *, overwrite_draft: bool = False) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def submit(self, resource_type: str, name: str, version: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def publish(self, resource_type: str, name: str, version: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def set_labels(self, resource_type: str, name: str, version: str, labels: dict[str, str]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def set_visibility(self, resource_type: str, name: str, version: str, visibility: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_resource(self, resource_type: str, name: str, version: str) -> dict[str, Any] | None:
        raise NotImplementedError
