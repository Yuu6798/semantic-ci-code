from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from semantic_ci_code.domain.state_schema import CodeState, CodeStateDelta
from semantic_ci_code.framework.target_svp import TargetSVP

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "src" / "semantic_ci_code" / "schemas"


def schema_documents() -> dict[str, dict[str, Any]]:
    return {
        "target_svp.schema.json": TargetSVP.model_json_schema(),
        "code_state.schema.json": CodeState.model_json_schema(),
        "code_state_delta.schema.json": CodeStateDelta.model_json_schema(),
    }


def render_schema(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_schemas() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, schema in schema_documents().items():
        path = SCHEMA_DIR / filename
        path.write_text(render_schema(schema), encoding="utf-8")


def check_schemas() -> bool:
    for filename, schema in schema_documents().items():
        path = SCHEMA_DIR / filename
        if not path.exists():
            return False
        if path.read_text(encoding="utf-8") != render_schema(schema):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate committed JSON Schema files.")
    parser.add_argument("--check", action="store_true", help="fail when committed schemas drift")
    args = parser.parse_args()

    if args.check:
        return 0 if check_schemas() else 1

    write_schemas()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
