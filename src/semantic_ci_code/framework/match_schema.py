from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from enum import Enum
from typing import Any

from pydantic import BaseModel

from semantic_ci_code.framework.constraint_types import Operator

COLLECTION_OPERATORS = frozenset(
    {
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.EXCLUDES_ALL,
        Operator.SUBSET_OF,
        Operator.SUPERSET_OF,
    }
)


@dataclass(frozen=True)
class MatchSchema:
    target: str
    required_key: str
    optional_keys: frozenset[str]
    forbidden_keys: dict[str, str]

    @property
    def allowed_keys(self) -> frozenset[str]:
        return frozenset({self.required_key}) | self.optional_keys


@dataclass(frozen=True)
class MatchSchemaError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


_API_SCHEMA = MatchSchema(
    target="api_surface",
    required_key="fqn",
    optional_keys=frozenset({"kind", "visibility"}),
    forbidden_keys={
        "signature": "signature is extractor-format coupling and is not stable policy input",
    },
)
_EFFECT_SCHEMA = MatchSchema(
    target="effects",
    required_key="fqn",
    optional_keys=frozenset({"effect_class"}),
    forbidden_keys={
        "confidence": "confidence is an extractor-dependent score; exact equality is unsafe",
        "evidence": "evidence is extractor-format coupling and is not stable policy input",
    },
)
_IMPORT_SCHEMA = MatchSchema(
    target="imports",
    required_key="module",
    optional_keys=frozenset({"from"}),
    forbidden_keys={
        "symbols": "symbols is list-valued; exact equality is a partial-match footgun",
    },
)

_SCHEMAS: dict[str, MatchSchema] = {
    "api_surface": _API_SCHEMA,
    "api_surface_public": _API_SCHEMA,
    "api_surface_delta.added": _API_SCHEMA,
    "api_surface_delta.removed": _API_SCHEMA,
    "api_surface_delta.changed": _API_SCHEMA,
    "effects": _EFFECT_SCHEMA,
    "effect_changes.added": _EFFECT_SCHEMA,
    "effect_changes.removed": _EFFECT_SCHEMA,
    "imports": _IMPORT_SCHEMA,
    "imports_delta.added": _IMPORT_SCHEMA,
    "imports_delta.removed": _IMPORT_SCHEMA,
}


def schema_for_target(target: str) -> MatchSchema | None:
    return _SCHEMAS.get(target)


def normalize_collection_expected(target: str, operator: Operator, expected: Any) -> Any:
    if operator not in COLLECTION_OPERATORS:
        return expected

    if _is_empty_collection(expected):
        if operator is Operator.EXCLUDES_ALL:
            raise MatchSchemaError("excludes_all with empty expected is a no-op deny gate")
        if operator is Operator.INCLUDES_ANY:
            raise MatchSchemaError("includes_any with empty expected can never be satisfied")
        return expected

    schema = schema_for_target(target)
    if isinstance(expected, dict):
        if schema is None:
            raise MatchSchemaError(
                f"partial dict expected is not supported for target {target!r}; "
                "no Match Schema is registered"
            )
        return (_normalize_record(target, schema, expected),)

    if not isinstance(expected, list | tuple):
        return expected

    normalized: list[Any] = []
    for item in expected:
        if isinstance(item, dict):
            if schema is None:
                raise MatchSchemaError(
                    f"partial dict expected is not supported for target {target!r}; "
                    "no Match Schema is registered"
                )
            normalized.append(_normalize_record(target, schema, item))
            continue
        if isinstance(item, str) and schema is not None:
            normalized.append({schema.required_key: item})
            continue
        normalized.append(item)
    return normalized


def match_item(expected: object, observed: object) -> bool:
    expected_map = mapping_view(expected)
    observed_map = mapping_view(observed)
    if expected_map is not None and observed_map is not None:
        return all(
            key in observed_map and observed_map[key] == value
            for key, value in expected_map.items()
        )
    return expected == observed


def mapping_view(value: object) -> dict[str, object] | None:
    if isinstance(value, BaseModel):
        return _normalized_mapping(value.model_dump(mode="json", by_alias=True))
    if isinstance(value, dict):
        return _normalized_mapping(value)
    if isinstance(value, tuple | list) and _looks_like_pairs(value):
        return _normalized_mapping(dict(value))
    return None


def _normalize_record(target: str, schema: MatchSchema, item: dict[str, Any]) -> dict[str, Any]:
    keys = set(item)
    forbidden = sorted(keys & set(schema.forbidden_keys))
    if forbidden:
        key = forbidden[0]
        raise MatchSchemaError(
            f"forbidden match key {key!r} for target {target!r}: {schema.forbidden_keys[key]}"
        )

    unknown = sorted(keys - set(schema.allowed_keys))
    if unknown:
        key = unknown[0]
        allowed = tuple(sorted(schema.allowed_keys))
        suggestions = get_close_matches(key, allowed, n=3, cutoff=0.4)
        message = (
            f"unknown match key {key!r} for target {target!r}. Allowed keys: {', '.join(allowed)}."
        )
        if suggestions:
            message += f" Did you mean: {', '.join(suggestions)}?"
        raise MatchSchemaError(message)

    if schema.required_key not in item:
        raise MatchSchemaError(
            f"partial match for target {target!r} requires key {schema.required_key!r}"
        )

    return {key: item[key] for key in sorted(item)}


def _is_empty_collection(value: Any) -> bool:
    return isinstance(value, list | tuple) and len(value) == 0


def _normalized_mapping(mapping: dict[str, object]) -> dict[str, object]:
    normalized = {key: _normalize_value(value) for key, value in mapping.items()}
    if "from_" in normalized and "from" not in normalized:
        normalized["from"] = normalized["from_"]
    return normalized


def _normalize_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return _normalized_mapping(value.model_dump(mode="json", by_alias=True))
    if isinstance(value, dict):
        return _normalized_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_normalize_value(item) for item in value)
    return value


def _looks_like_pairs(value: tuple[object, ...] | list[object]) -> bool:
    return bool(value) and all(isinstance(item, tuple | list) and len(item) == 2 for item in value)
