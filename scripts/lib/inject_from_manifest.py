#!/usr/bin/env python3
"""CLI helper: inject expert template into Hermes data dir via v1 manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running without install
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "expert-factory" / "src"))

from workcopilot_expert_factory.adapters.inject_runtime import inject_from_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--base", type=Path, default=None)
    args = parser.parse_args()
    result = inject_from_manifest(
        template_dir=args.template,
        data_dir=args.data_dir,
        base_dir=args.base,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
