from __future__ import annotations

from typing import Final

from pydantic import BaseModel

E_PATH_UNRESOLVED: Final = "E_PATH_UNRESOLVED"


class _Unresolved:
    pass


UNRESOLVED: Final = _Unresolved()


def resolve_path(root: object, segments: tuple[str, ...]) -> tuple[object, str | None]:
    """Resolve dotted target path segments on Pydantic models and JSON mappings."""

    current = root
    for segment in segments:
        if current is None:
            return UNRESOLVED, E_PATH_UNRESOLVED

        if isinstance(current, BaseModel):
            if segment not in current.__class__.model_fields:
                return UNRESOLVED, E_PATH_UNRESOLVED
            current = getattr(current, segment)
            continue

        if isinstance(current, dict):
            if segment not in current:
                return UNRESOLVED, E_PATH_UNRESOLVED
            current = current[segment]
            continue

        return UNRESOLVED, E_PATH_UNRESOLVED

    return current, None
