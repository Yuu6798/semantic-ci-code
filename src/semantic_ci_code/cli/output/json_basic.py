from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from semantic_ci_code.domain.state_schema import CodeState

SCHEMA_VERSION = "1"
PACKAGE_NAME = "semantic-ci-code"
UNKNOWN_VERSION = "0.0.0+unknown"


def package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def build_observe_payload(state: CodeState) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "subcommand": "observe",
        "verdict": None,
        "intent": None,
        "primary_kind": None,
        "allowed_secondary_kinds": [],
        "summary": None,
        "results": [],
        "repair_plan": None,
        "code_state": state.model_dump(mode="json"),
        "files_touched": 0,
        "loc_delta": {"added": 0, "removed": 0},
        "engine": {
            "extractor_pyver": f"{sys.version_info.major}.{sys.version_info.minor}",
            "package_version": package_version(),
        },
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
