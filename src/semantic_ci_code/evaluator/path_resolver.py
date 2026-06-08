from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from semantic_ci_code.domain.state_schema import CodeState

E_PATH_UNRESOLVED: Final = "E_PATH_UNRESOLVED"


class _Unresolved:
    pass


UNRESOLVED: Final = _Unresolved()

_FLAT_PROJECTION_ALIASES: Final = {
    ("api_surface_delta", "added", "fqns"): "fqn",
    ("effect_changes", "added", "fqns"): "fqn",
    ("imports_delta", "added", "modules"): "module",
}


def resolve_path(root: object, segments: tuple[str, ...]) -> tuple[object, str | None]:
    """Resolve dotted target path segments on Pydantic models and JSON mappings."""

    current = root
    for index, segment in enumerate(segments):
        if current is None:
            return UNRESOLVED, E_PATH_UNRESOLVED

        if isinstance(current, CodeState) and segment == "api_surface_public":
            current = _public_api_entries(current.api_surface)
            continue

        if (
            segment == "removed_public"
            and segments[: index + 1] == ("api_surface_delta", "removed_public")
            and hasattr(current, "removed")
        ):
            current = _public_api_entries(current.removed)
            continue

        projection_key = _FLAT_PROJECTION_ALIASES.get(segments[: index + 1])
        if projection_key is not None:
            current = _project_field(current, projection_key)
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
    return _field(entry, "visibility")


def _project_field(entries: object, key: str) -> tuple[str, ...]:
    if not isinstance(entries, tuple | list):
        return ()
    return tuple(value for entry in entries if isinstance((value := _field(entry, key)), str))


def _field(entry: object, key: str) -> object:
    if isinstance(entry, BaseModel):
        return getattr(entry, key, None)
    if isinstance(entry, dict):
        return entry.get(key)
    if isinstance(entry, tuple | list):
        for item in entry:
            if isinstance(item, tuple | list) and len(item) == 2 and item[0] == key:
                return item[1]
    return getattr(entry, key, None)
