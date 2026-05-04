from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from semantic_ci_code.domain.state_schema import CodeState

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

        if isinstance(current, CodeState) and segment == "api_surface_public":
            current = _public_api_entries(current.api_surface)
            continue

        if segment == "removed_public" and hasattr(current, "removed"):
            current = _public_api_entries(current.removed)
            continue

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


def _public_api_entries(entries: object) -> tuple[object, ...]:
    if not isinstance(entries, tuple | list):
        return ()
    return tuple(entry for entry in entries if _api_visibility(entry) == "public")


def _api_visibility(entry: object) -> object:
    if isinstance(entry, BaseModel):
        return getattr(entry, "visibility", None)
    if isinstance(entry, dict):
        return entry.get("visibility")
    if isinstance(entry, tuple | list):
        for item in entry:
            if isinstance(item, tuple | list) and len(item) == 2 and item[0] == "visibility":
                return item[1]
    return getattr(entry, "visibility", None)
