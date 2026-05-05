from __future__ import annotations

from typing import Any


def find_file_line(value: Any) -> tuple[str, int | None] | None:
    """Find file/line metadata in JSON evidence, including sorted pair lists."""

    if isinstance(value, dict):
        if isinstance(value.get("file"), str):
            line_value = value.get("line")
            return value["file"], line_value if isinstance(line_value, int) else None
        for item in value.values():
            found = find_file_line(item)
            if found is not None:
                return found
        return None

    if isinstance(value, list):
        pair_mapping = _pair_list_mapping(value)
        if pair_mapping is not None:
            found = find_file_line(pair_mapping)
            if found is not None:
                return found
        for item in value:
            found = find_file_line(item)
            if found is not None:
                return found

    return None


def _pair_list_mapping(value: list[Any]) -> dict[str, Any] | None:
    if not value:
        return None
    if not all(isinstance(item, list | tuple) and len(item) == 2 for item in value):
        return None
    pairs: dict[str, Any] = {}
    for key, item_value in value:
        if not isinstance(key, str):
            return None
        pairs[key] = item_value
    return pairs
