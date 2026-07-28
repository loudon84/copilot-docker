from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

from workcopilot_expert_factory.errors import ExpertSchemaInvalid

# expert-factory/schemas (package lives under expert-factory/src/...)
SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"


@lru_cache(maxsize=16)
def load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    if not path.is_file():
        raise ExpertSchemaInvalid(f"schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_against(schema_name: str, instance: dict) -> list[str]:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    ]
