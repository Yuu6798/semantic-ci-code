from __future__ import annotations

from typing import Any

from semantic_ci_code.cli.output.json_formatter import (
    PACKAGE_NAME as _PACKAGE_NAME,
)
from semantic_ci_code.cli.output.json_formatter import (
    SCHEMA_VERSION as _SCHEMA_VERSION,
)
from semantic_ci_code.cli.output.json_formatter import (
    UNKNOWN_VERSION as _UNKNOWN_VERSION,
)
from semantic_ci_code.cli.output.json_formatter import (
    build_observe_payload as _build_observe_payload,
)
from semantic_ci_code.cli.output.json_formatter import (
    dump_json as _dump_json,
)
from semantic_ci_code.cli.output.json_formatter import (
    package_version as _package_version,
)
from semantic_ci_code.domain.state_schema import CodeState

SCHEMA_VERSION = _SCHEMA_VERSION
PACKAGE_NAME = _PACKAGE_NAME
UNKNOWN_VERSION = _UNKNOWN_VERSION


def package_version() -> str:
    return _package_version()


def build_observe_payload(state: CodeState) -> dict[str, Any]:
    return _build_observe_payload(state)


def dump_json(payload: dict[str, Any]) -> str:
    return _dump_json(payload)


__all__ = [
    "PACKAGE_NAME",
    "SCHEMA_VERSION",
    "UNKNOWN_VERSION",
    "build_observe_payload",
    "dump_json",
    "package_version",
]
