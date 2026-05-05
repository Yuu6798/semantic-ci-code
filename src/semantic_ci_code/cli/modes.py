from __future__ import annotations

import os
from enum import StrEnum

from semantic_ci_code.pipeline import SMOKE_DIMENSIONS

__all__ = [
    "ExecutionMode",
    "dimensions_for_mode",
    "resolve_execution_mode",
]


class ExecutionMode(StrEnum):
    SMOKE = "smoke"
    FULL = "full"


def resolve_execution_mode(raw_mode: str | None) -> ExecutionMode:
    """Resolve CLI/env execution mode.

    ``--mode`` takes precedence. If it is absent, ``SEMANTIC_CI_MODE`` can
    override the default. The default remains ``full`` for backward
    compatibility.
    """

    selected = raw_mode if raw_mode is not None else os.environ.get("SEMANTIC_CI_MODE")
    if selected is None or selected == "":
        return ExecutionMode.FULL
    try:
        return ExecutionMode(selected)
    except ValueError as exc:
        raise ValueError(
            f"invalid semantic-ci execution mode {selected!r}; expected smoke or full"
        ) from exc


def dimensions_for_mode(mode: ExecutionMode) -> frozenset[str] | None:
    if mode is ExecutionMode.SMOKE:
        return SMOKE_DIMENSIONS
    return None
