"""`authorship.generation_metadata` builder for recipe paths."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

PACKAGE_NAME = "semantic-ci-code"
TOOL_NAME = "semantic-ci-init"
UNKNOWN_VERSION = "0.0.0+unknown"


def _resolved_tool_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def build_generation_metadata(
    *,
    recipe_id: str,
    source_surfaces: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "tool": TOOL_NAME,
        "tool_version": _resolved_tool_version(),
        "recipe": recipe_id,
        "source_surfaces": list(source_surfaces),
        "candidate_code_used": False,
        "llm_used": False,
    }
