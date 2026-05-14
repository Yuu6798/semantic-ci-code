"""Static (target, operator, expected) type-compatibility check.

The evaluator emits ``E_TYPE_MISMATCH`` at runtime when (a) the observed
value at the constraint target does not satisfy the operator's required
category (e.g. ``less_than`` on a record_collection), or (b) the
``expected`` literal does not satisfy the operator's required shape (e.g.
``includes_all`` with a scalar expected, or ``within_range`` with a
single number).

Per ``docs/brief_resultstatus_planning.md`` §4.5, the observed-side
category is statically derivable for 30 / 32 delta paths and 11 / 13
state paths (~95% coverage); the expected-side shape is 100% derivable
from the YAML literal. Both checks live here so authoring errors no
longer reach ``unknown_policy`` routing.

This module is paired with ``operator_schema``:

- ``operator_schema``: (kind, target-domain, operator-class) alignment
  (Brief D1-2)
- ``type_schema``: (target-category, operator-category, expected-shape)
  alignment (Brief D1-3)

Open dimensions (``python_specific.*`` / ``typescript_specific.*``) and
``JsonValue`` element shapes inside ``tuple[JsonValue, ...]`` collections
remain runtime-only (``unknown_cause: open_runtime`` after D1-4).
"""

from __future__ import annotations

import inspect
from enum import StrEnum
from functools import lru_cache
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from semantic_ci_code.compiler.path_schema import is_open_path
from semantic_ci_code.domain.state_schema import CodeState, CodeStateDelta
from semantic_ci_code.framework.constraint_types import Operator

__all__ = [
    "TargetCategory",
    "TypeMismatch",
    "TypeMismatchSide",
    "category_for_target",
    "check_type_compatibility",
]


class TargetCategory(StrEnum):
    """Static type category for a constraint target.

    Categories match the planning doc §4.1 taxonomy. ``UNKNOWN_OPEN``
    captures both open-dimension paths and any annotation the walker
    cannot resolve, so compile-time checks safely defer to runtime in
    those cases.
    """

    RECORD = "record"
    RECORD_COLLECTION = "record_collection"
    STRING_COLLECTION = "string_collection"
    NUMBER_COLLECTION = "number_collection"
    SCALAR_STRING = "scalar_string"
    SCALAR_NUMBER = "scalar_number"
    SCALAR_BOOL = "scalar_bool"
    MAPPING_OPEN = "mapping_open"
    UNKNOWN_OPEN = "unknown_open"


# Operators that compare an observed collection to an expected collection.
# All 8 require the observed-side path to resolve a collection category
# and the expected literal (if any) to be a list / tuple.
_COLLECTION_OPERATORS: frozenset[Operator] = frozenset(
    {
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.EXCLUDES_ALL,
        Operator.SUBSET_OF,
        Operator.SUPERSET_OF,
        Operator.SUPERSET_OF_BASELINE,
        Operator.NO_NEW_ITEMS,
        Operator.NO_REMOVED_ITEMS,
    }
)

# Pure collection operators that also accept a user-provided expected list.
_COLLECTION_OPERATORS_WITH_EXPECTED: frozenset[Operator] = frozenset(
    {
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.EXCLUDES_ALL,
        Operator.SUBSET_OF,
        Operator.SUPERSET_OF,
    }
)

# Numeric scalar-only operators (observed must be scalar_number; expected
# must be a real number).
_NUMERIC_OPERATORS: frozenset[Operator] = frozenset(
    {
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
    }
)

_COLLECTION_CATEGORIES: frozenset[TargetCategory] = frozenset(
    {
        TargetCategory.RECORD_COLLECTION,
        TargetCategory.STRING_COLLECTION,
        TargetCategory.NUMBER_COLLECTION,
    }
)


# Synthesized aliases mirroring ``path_schema`` and ``path_resolver``.
_TOP_LEVEL_ALIAS_CATEGORIES: dict[str, TargetCategory] = {
    # ``api_surface_public`` is the visibility-filtered view of ``api_surface``
    # and resolves to a tuple of APISurfaceEntry records.
    "api_surface_public": TargetCategory.RECORD_COLLECTION,
}

_FLAT_PROJECTION_CATEGORIES: dict[str, TargetCategory] = {
    "api_surface_delta.added.fqns": TargetCategory.STRING_COLLECTION,
    "effect_changes.added.fqns": TargetCategory.STRING_COLLECTION,
    "imports_delta.added.modules": TargetCategory.STRING_COLLECTION,
}


class TypeMismatchSide(StrEnum):
    """Which side of the constraint triple the mismatch is attributed to.

    Used by the compiler to point ``CompileError.path`` at the right YAML
    field (``constraints[i].target`` vs ``constraints[i].expected``).
    """

    OBSERVED = "observed"
    EXPECTED = "expected"


class TypeMismatch(Exception):
    """Raised when (target, operator, expected) types are incompatible.

    Carries a rendered message plus a ``side`` attribute marking whether
    the mismatch came from the observed (target-category) side or the
    expected-literal side. The compiler uses ``side`` to attach the right
    YAML path to ``CompileError``.
    """

    def __init__(self, message: str, *, side: TypeMismatchSide) -> None:
        super().__init__(message)
        self.side = side


def category_for_target(target: str) -> TargetCategory:
    """Resolve the static type category for a constraint target path.

    Open dimensions and unknown paths return ``UNKNOWN_OPEN`` so callers
    can defer their type checks to runtime instead of inventing a static
    answer the schema does not justify.
    """

    if is_open_path(target):
        return TargetCategory.UNKNOWN_OPEN
    return _category_map().get(target, TargetCategory.UNKNOWN_OPEN)


def check_type_compatibility(
    *,
    target: str,
    operator: Operator,
    expected: Any,
) -> None:
    """Validate the (target, operator, expected) triple against static type.

    Categories on open dimensions (UNKNOWN_OPEN) bypass the check; element
    matching inside ``tuple[JsonValue, ...]`` is intentionally out of
    scope (planning §4.6 Q3: shallow check only).
    """

    category = category_for_target(target)
    if category is TargetCategory.UNKNOWN_OPEN:
        return

    if operator in _COLLECTION_OPERATORS and category not in _COLLECTION_CATEGORIES:
        raise TypeMismatch(
            _observed_collection_message(target, operator, category),
            side=TypeMismatchSide.OBSERVED,
        )

    if (
        operator in _NUMERIC_OPERATORS or operator is Operator.WITHIN_RANGE
    ) and category is not TargetCategory.SCALAR_NUMBER:
        raise TypeMismatch(
            _observed_numeric_message(target, operator, category),
            side=TypeMismatchSide.OBSERVED,
        )

    _check_expected_shape(target=target, operator=operator, expected=expected)


def _check_expected_shape(*, target: str, operator: Operator, expected: Any) -> None:
    if operator in _COLLECTION_OPERATORS_WITH_EXPECTED:
        if not _looks_like_list_or_tuple(expected):
            raise TypeMismatch(
                _expected_collection_message(target, operator, expected),
                side=TypeMismatchSide.EXPECTED,
            )
        return
    if operator in _NUMERIC_OPERATORS:
        if not _is_real_number(expected):
            raise TypeMismatch(
                _expected_numeric_message(target, operator, expected),
                side=TypeMismatchSide.EXPECTED,
            )
        return
    if operator is Operator.WITHIN_RANGE:
        if (
            not _looks_like_list_or_tuple(expected)
            or len(expected) != 2
            or not all(_is_real_number(item) for item in expected)
        ):
            raise TypeMismatch(
                _expected_within_range_message(target, operator, expected),
                side=TypeMismatchSide.EXPECTED,
            )


# --- internals -------------------------------------------------------------


@lru_cache(maxsize=1)
def _category_map() -> dict[str, TargetCategory]:
    mapping: dict[str, TargetCategory] = {}
    for field_name, info in CodeState.model_fields.items():
        _walk(field_name, info.annotation, mapping)
    for field_name, info in CodeStateDelta.model_fields.items():
        # CodeStateDelta sometimes redefines fields already on CodeState
        # (e.g. python_specific). The CodeStateDelta annotation wins for
        # delta-kind constraints; CodeState entries remain reachable
        # through the separate state-domain walker call above. The map
        # is keyed by path string, so the second pass overwrites only
        # paths shared between models — fine because the open-dimension
        # ones share their category (MAPPING_OPEN) and the closed-model
        # roots are disjoint.
        _walk(field_name, info.annotation, mapping)
    mapping.update(_TOP_LEVEL_ALIAS_CATEGORIES)
    mapping.update(_FLAT_PROJECTION_CATEGORIES)
    return mapping


def _walk(prefix: str, annotation: Any, mapping: dict[str, TargetCategory]) -> None:
    category = _category_for_annotation(annotation)
    mapping[prefix] = category

    if category is TargetCategory.MAPPING_OPEN:
        return

    model = _model_class(annotation)
    if model is None:
        return
    for sub_name, sub_info in model.model_fields.items():
        sub_path = f"{prefix}.{sub_name}"
        _walk(sub_path, sub_info.annotation, mapping)

    # ``removed_public`` is a visibility-filtered view of ``removed``;
    # in every registered case it is itself a record_collection.
    if "removed" in model.model_fields:
        mapping[f"{prefix}.removed_public"] = TargetCategory.RECORD_COLLECTION


def _category_for_annotation(annotation: Any) -> TargetCategory:
    annotation = _unwrap_nullable(annotation)

    if _is_dict_type(annotation):
        return TargetCategory.MAPPING_OPEN
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return TargetCategory.RECORD

    origin = get_origin(annotation)
    if origin in (tuple, list):
        return _collection_category_from_args(get_args(annotation))

    if annotation is int or annotation is float:
        return TargetCategory.SCALAR_NUMBER
    if annotation is bool:
        return TargetCategory.SCALAR_BOOL
    if annotation is str:
        return TargetCategory.SCALAR_STRING

    return TargetCategory.UNKNOWN_OPEN


def _collection_category_from_args(args: tuple[Any, ...]) -> TargetCategory:
    if not args:
        return TargetCategory.RECORD_COLLECTION
    element = _unwrap_nullable(args[0])
    if element is str:
        return TargetCategory.STRING_COLLECTION
    if element is int or element is float:
        return TargetCategory.NUMBER_COLLECTION
    if inspect.isclass(element) and issubclass(element, BaseModel):
        return TargetCategory.RECORD_COLLECTION
    # ``tuple[JsonValue, ...]`` (JsonValue = Any) and similar opaque element
    # types: container category is known (a collection of records-or-values),
    # element shape is out of scope. Treat as RECORD_COLLECTION so dict-based
    # match-schema and ``includes_*`` operators still apply.
    return TargetCategory.RECORD_COLLECTION


def _unwrap_nullable(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation


def _model_class(annotation: Any) -> type[BaseModel] | None:
    annotation = _unwrap_nullable(annotation)
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _is_dict_type(annotation: Any) -> bool:
    return get_origin(annotation) is dict


def _looks_like_list_or_tuple(value: Any) -> bool:
    return isinstance(value, list | tuple) and not isinstance(value, str | bytes)


def _is_real_number(value: Any) -> bool:
    # Bool is a subclass of int in Python; exclude it so ``less_than: true``
    # is not silently accepted as 0/1.
    return isinstance(value, int | float) and not isinstance(value, bool)


def _format_expected(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, list | tuple):
        try:
            return repr(list(value))
        except (TypeError, ValueError):
            return type(value).__name__
    return repr(value)


def _observed_collection_message(
    target: str,
    operator: Operator,
    category: TargetCategory,
) -> str:
    return (
        f"operator {operator.value!r} requires a collection target "
        f"(record_collection / string_collection / number_collection), but "
        f"target {target!r} is statically typed as {category.value!r}. "
        f"Use a collection target or pick a category-compatible operator."
    )


def _observed_numeric_message(
    target: str,
    operator: Operator,
    category: TargetCategory,
) -> str:
    return (
        f"operator {operator.value!r} reads a scalar number, but target "
        f"{target!r} is statically typed as {category.value!r}. Use a "
        f"numeric target (e.g. complexity_delta.cyclomatic) or switch to "
        f"a category-compatible operator."
    )


def _expected_collection_message(
    target: str,
    operator: Operator,
    expected: Any,
) -> str:
    return (
        f"operator {operator.value!r} compares observed against an expected "
        f"list of items, but expected is {_format_expected(expected)} for "
        f"target {target!r}. Provide a YAML list (e.g. expected: [...] or "
        f"a sequence of dicts)."
    )


def _expected_numeric_message(
    target: str,
    operator: Operator,
    expected: Any,
) -> str:
    return (
        f"operator {operator.value!r} compares to a numeric literal, but "
        f"expected is {_format_expected(expected)} for target {target!r}. "
        f"Provide an int or float."
    )


def _expected_within_range_message(
    target: str,
    operator: Operator,
    expected: Any,
) -> str:
    return (
        f"operator {operator.value!r} requires expected as a [low, high] "
        f"pair of numbers, but expected is {_format_expected(expected)} "
        f"for target {target!r}."
    )
