"""Mock connector fixtures for isolated evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


STANDARD_FIXTURES = (
    "mock-finance-query",
    "mock-erp-read",
    "mock-erp-write-denied",
    "mock-email",
    "mock-search",
    "mock-github",
    "mock-timeout",
    "mock-invalid-response",
)


@dataclass
class FixtureCall:
    name: str
    input: Any
    output: Any
    forbidden: bool = False


@dataclass
class ConnectorFixtureSet:
    name: str = "default"
    calls: list[FixtureCall] = field(default_factory=list)
    datasets: dict[str, Any] = field(default_factory=dict)

    def record(self, name: str, input_data: Any, output: Any, *, forbidden: bool = False) -> Any:
        if name == "mock-erp-write-denied" or forbidden:
            self.calls.append(FixtureCall(name=name, input=input_data, output={"error": "denied"}, forbidden=True))
            return {"error": "write denied"}
        if name == "mock-timeout":
            self.calls.append(FixtureCall(name=name, input=input_data, output={"error": "timeout"}, forbidden=False))
            return {"error": "timeout"}
        if name == "mock-invalid-response":
            self.calls.append(FixtureCall(name=name, input=input_data, output=None, forbidden=False))
            return None
        result = output if output is not None else self.datasets.get(name, {"ok": True})
        self.calls.append(FixtureCall(name=name, input=input_data, output=result, forbidden=False))
        return result

    def forbidden_occurred(self) -> bool:
        return any(c.forbidden for c in self.calls)

    def digest_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "call_count": len(self.calls),
            "calls": [{"name": c.name, "forbidden": c.forbidden} for c in self.calls],
        }


def load_fixture_dataset(path: Path) -> Any:
    if not path.is_file():
        return {}
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")
