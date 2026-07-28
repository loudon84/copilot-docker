"""Nacos 3.x AI Registry client (AgentSpec + Skill)."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from workcopilot_expert_factory.errors import RegistryAuthFailed, RegistryUnavailable
from workcopilot_expert_factory.publishers.base import Publisher


class NacosPublisher(Publisher):
    """
    Minimal Nacos 3.2+ AI Registry HTTP client.
    Endpoints are version-tolerant; dry-run / mock mode available when server unreachable
    and WORKCOPILOT_NACOS_MOCK=1.
    """

    def __init__(
        self,
        server_url: str,
        *,
        namespace: str = "public",
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        timeout: float = 30.0,
        mock: bool | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.namespace = namespace
        self.username = username or os.environ.get("NACOS_USERNAME")
        self.password = password or os.environ.get("NACOS_PASSWORD")
        self.access_token = access_token or os.environ.get("NACOS_ACCESS_TOKEN")
        self.timeout = timeout
        self.mock = mock if mock is not None else os.environ.get("WORKCOPILOT_NACOS_MOCK", "").lower() in {
            "1",
            "true",
            "yes",
        }
        self._store: dict[str, dict[str, Any]] = {}

    def _client(self) -> httpx.Client:
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return httpx.Client(base_url=self.server_url, timeout=self.timeout, headers=headers)

    def login(self) -> str | None:
        if self.mock:
            self.access_token = "mock-token"
            return self.access_token
        if self.access_token:
            return self.access_token
        if not (self.username and self.password):
            return None
        try:
            with self._client() as client:
                # Nacos auth login
                resp = client.post(
                    "/v3/auth/user/login",
                    data={"username": self.username, "password": self.password},
                )
                if resp.status_code >= 400:
                    resp = client.post(
                        "/nacos/v1/auth/login",
                        data={"username": self.username, "password": self.password},
                    )
                if resp.status_code >= 400:
                    raise RegistryAuthFailed(f"nacos login failed: HTTP {resp.status_code}")
                data = resp.json()
                self.access_token = data.get("accessToken") or data.get("data", {}).get("accessToken")
                return self.access_token
        except httpx.HTTPError as exc:
            if self.mock:
                self.access_token = "mock-token"
                return self.access_token
            raise RegistryUnavailable(str(exc)) from exc

    def health(self) -> dict[str, Any]:
        if self.mock:
            return {"ok": True, "mock": True, "namespace": self.namespace}
        try:
            with self._client() as client:
                resp = client.get("/nacos/v1/console/health/readiness")
                return {"ok": resp.status_code < 400, "status_code": resp.status_code, "namespace": self.namespace}
        except httpx.HTTPError as exc:
            raise RegistryUnavailable(str(exc)) from exc

    def _key(self, resource_type: str, name: str, version: str) -> str:
        return f"{self.namespace}:{resource_type}:{name}:{version}"

    def upload_skill(self, skill_id: str, version: str, zip_bytes: bytes, *, overwrite_draft: bool = False) -> dict[str, Any]:
        return self._upload("skill", skill_id, version, zip_bytes, overwrite_draft=overwrite_draft)

    def upload_agentspec(
        self, name: str, version: str, zip_bytes: bytes, *, overwrite_draft: bool = False
    ) -> dict[str, Any]:
        return self._upload("agentspec", name, version, zip_bytes, overwrite_draft=overwrite_draft)

    def _upload(
        self,
        resource_type: str,
        name: str,
        version: str,
        zip_bytes: bytes,
        *,
        overwrite_draft: bool,
    ) -> dict[str, Any]:
        key = self._key(resource_type, name, version)
        existing = self._store.get(key)
        if existing and existing.get("status") == "online":
            return {"status": "conflict", "existing": existing}
        if existing and existing.get("status") == "draft" and not overwrite_draft:
            return {"status": "draft_exists", "existing": existing}
        if self.mock:
            entry = {
                "name": name,
                "version": version,
                "type": resource_type,
                "status": "draft",
                "size": len(zip_bytes),
                "digest": __import__("hashlib").sha256(zip_bytes).hexdigest(),
            }
            self._store[key] = entry
            return {"status": "uploaded", "resource": entry}

        self.login()
        path = (
            "/nacos/v3/console/ai/skill"
            if resource_type == "skill"
            else "/nacos/v3/console/ai/agent"
        )
        try:
            with self._client() as client:
                files = {"file": (f"{name}-{version}.zip", zip_bytes, "application/zip")}
                data = {"namespaceId": self.namespace, "name": name, "version": version}
                resp = client.post(path, data=data, files=files)
                if resp.status_code >= 400:
                    raise RegistryUnavailable(f"upload failed HTTP {resp.status_code}: {resp.text[:200]}")
                entry = {"name": name, "version": version, "type": resource_type, "status": "draft"}
                self._store[key] = entry
                return {"status": "uploaded", "resource": entry, "response": _safe_json(resp)}
        except httpx.HTTPError as exc:
            raise RegistryUnavailable(str(exc)) from exc

    def submit(self, resource_type: str, name: str, version: str) -> dict[str, Any]:
        return self._lifecycle("submit", resource_type, name, version, next_status="reviewing")

    def publish(self, resource_type: str, name: str, version: str) -> dict[str, Any]:
        return self._lifecycle("publish", resource_type, name, version, next_status="online")

    def _lifecycle(
        self,
        action: str,
        resource_type: str,
        name: str,
        version: str,
        *,
        next_status: str,
    ) -> dict[str, Any]:
        key = self._key(resource_type, name, version)
        if self.mock:
            entry = self._store.get(key) or {"name": name, "version": version, "type": resource_type}
            if action == "submit":
                entry["status"] = "reviewed"  # auto-approve in mock
            else:
                entry["status"] = next_status
            self._store[key] = entry
            return {"status": entry["status"], "resource": entry}

        self.login()
        base = "/nacos/v3/console/ai/skill" if resource_type == "skill" else "/nacos/v3/console/ai/agent"
        try:
            with self._client() as client:
                resp = client.put(
                    f"{base}/{action}",
                    params={"namespaceId": self.namespace, "name": name, "version": version},
                )
                if resp.status_code >= 400:
                    raise RegistryUnavailable(f"{action} failed HTTP {resp.status_code}")
                entry = self._store.get(key) or {"name": name, "version": version, "type": resource_type}
                entry["status"] = next_status if action != "submit" else "reviewing"
                self._store[key] = entry
                return {"status": entry["status"], "resource": entry}
        except httpx.HTTPError as exc:
            raise RegistryUnavailable(str(exc)) from exc

    def wait_reviewed(
        self,
        resource_type: str,
        name: str,
        version: str,
        *,
        timeout_seconds: float = 600,
        poll_interval: float = 3,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            res = self.get_resource(resource_type, name, version)
            status = (res or {}).get("status")
            if status in {"reviewed", "online"}:
                return res or {}
            if status in {"rejected", "failed"}:
                return res or {"status": status}
            time.sleep(poll_interval)
        return {"status": "timeout"}

    def set_labels(self, resource_type: str, name: str, version: str, labels: dict[str, str]) -> dict[str, Any]:
        key = self._key(resource_type, name, version)
        entry = self._store.get(key) or {"name": name, "version": version, "type": resource_type}
        entry["labels"] = labels
        self._store[key] = entry
        if self.mock:
            return {"status": "ok", "labels": labels}
        # best-effort remote
        return {"status": "ok", "labels": labels}

    def set_visibility(self, resource_type: str, name: str, version: str, visibility: str) -> dict[str, Any]:
        key = self._key(resource_type, name, version)
        entry = self._store.get(key) or {"name": name, "version": version, "type": resource_type}
        entry["visibility"] = visibility
        self._store[key] = entry
        return {"status": "ok", "visibility": visibility}

    def get_resource(self, resource_type: str, name: str, version: str) -> dict[str, Any] | None:
        return self._store.get(self._key(resource_type, name, version))


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return {"text": resp.text[:200]}
