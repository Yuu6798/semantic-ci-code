from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from semantic_ci_code.compiler import path_schema
from semantic_ci_code.compiler.operator_schema import (
    _BASELINE_OPERATORS,
    _P1_UNSUPPORTED_OPERATORS,
    _PURE_OPERATORS,
    OperatorTargetMismatch,
    check_operator_target_compatibility,
)
from semantic_ci_code.compiler.templates import TEMPLATE_CONSTRAINTS
from semantic_ci_code.compiler.type_schema import (
    TargetCategory,
    TypeMismatch,
    category_for_target,
    check_type_compatibility,
)
from semantic_ci_code.domain.state_schema import ChangeKind
from semantic_ci_code.framework.constraint_types import ConstraintKind, Operator
from semantic_ci_code.framework.match_schema import schema_for_target

CATALOG_SCHEMA_VERSION = "catalog-1"


class CatalogUsageError(ValueError):
    """Raised when a catalog filter cannot be applied."""


def build_catalog(
    *,
    kind_filter: ChangeKind | None = None,
    target_path_filter: str | None = None,
) -> dict[str, Any]:
    valid_targets = set(path_schema.valid_target_paths())
    if (
        target_path_filter is not None
        and target_path_filter not in valid_targets
        and not path_schema.is_open_path(target_path_filter)
    ):
        suggestions = path_schema.suggest_targets(target_path_filter, sorted(valid_targets))
        message = f"unknown target path: {target_path_filter!r}"
        if suggestions:
            message += f". Did you mean: {', '.join(suggestions)}?"
        raise CatalogUsageError(message)

    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "subcommand": "target-catalog",
        "primary_kinds": sorted(kind.value for kind in ChangeKind),
        "targets": _targets(target_path_filter=target_path_filter),
        "templates": _templates(kind_filter=kind_filter),
        "operators": _operators(),
    }


def _targets(*, target_path_filter: str | None) -> dict[str, Any]:
    target_paths = (
        (target_path_filter,)
        if target_path_filter is not None
        else tuple(sorted(path_schema.valid_target_paths()))
    )
    return {target: _target_entry(target) for target in target_paths}


def _target_entry(target: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "kind": _target_kind(target),
        "category": category_for_target(target).value,
        "operators": _valid_operators_for_target(target),
    }
    match_schema = schema_for_target(target)
    if match_schema is not None:
        entry["match_schema"] = {
            "required_key": match_schema.required_key,
            "optional_keys": sorted(match_schema.optional_keys),
            "forbidden_keys": {
                key: match_schema.forbidden_keys[key] for key in sorted(match_schema.forbidden_keys)
            },
        }
    return entry


def _target_kind(target: str) -> str:
    if path_schema.is_open_path(target):
        return "open"
    if target in path_schema.valid_state_target_paths():
        return "state"
    return "delta"


def _valid_operators_for_target(target: str) -> list[str]:
    values: list[str] = []
    for operator in sorted(Operator, key=lambda item: item.value):
        if operator in _P1_UNSUPPORTED_OPERATORS:
            continue
        if _operator_passes_for_target(target, operator):
            values.append(operator.value)
    return values


def _operator_passes_for_target(target: str, operator: Operator) -> bool:
    expected = _canonical_expected_for_operator(operator)
    for kind in _candidate_constraint_kinds(target):
        try:
            check_operator_target_compatibility(kind=kind, target=target, operator=operator)
            check_type_compatibility(target=target, operator=operator, expected=expected)
        except (OperatorTargetMismatch, TypeMismatch):
            continue
        return True
    return False


def _candidate_constraint_kinds(target: str) -> tuple[ConstraintKind, ...]:
    if path_schema.is_open_path(target):
        return (ConstraintKind.STATE, ConstraintKind.DELTA)
    if target in path_schema.valid_state_target_paths():
        return (ConstraintKind.STATE, ConstraintKind.DELTA)
    if target in path_schema.valid_delta_target_paths():
        return (ConstraintKind.DELTA,)
    return ()


def _canonical_expected_for_operator(operator: Operator) -> Any:
    if operator is Operator.WITHIN_RANGE:
        return (0, 1)
    if operator in {
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
    }:
        return 0
    if operator in {
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.EXCLUDES_ALL,
        Operator.SUBSET_OF,
        Operator.SUPERSET_OF,
    }:
        return ("placeholder",)
    return None


def _templates(*, kind_filter: ChangeKind | None) -> dict[str, Any]:
    kinds = (kind_filter,) if kind_filter is not None else tuple(sorted(ChangeKind, key=str))
    return {
        kind.value: {
            "expanded_constraints": [
                _template_constraint_payload(constraint)
                for constraint in TEMPLATE_CONSTRAINTS[kind]
            ]
        }
        for kind in kinds
    }


def _template_constraint_payload(constraint: Any) -> dict[str, Any]:
    return {
        "kind": constraint.kind.value,
        "target": constraint.target,
        "operator": constraint.operator.value,
        "expected": _json_value(constraint.expected),
        "severity": constraint.severity.value,
        "unknown_policy": constraint.unknown_policy.value,
    }


def _operators() -> dict[str, Any]:
    evidence_map = _operator_evidence_emits()
    return {
        operator.value: {
            "applies_to_collection": _operator_applies_to_categories(operator),
            "evidence_emits": list(evidence_map.get(operator, ())),
            "class": _operator_class(operator),
        }
        for operator in sorted(Operator, key=lambda item: item.value)
    }


def _operator_class(operator: Operator) -> str:
    if operator in _P1_UNSUPPORTED_OPERATORS:
        return "skipped_in_p1"
    if operator in _PURE_OPERATORS:
        return "pure"
    if operator in _BASELINE_OPERATORS:
        return "baseline"
    raise AssertionError(f"unclassified operator: {operator!r}")


def _operator_applies_to_categories(operator: Operator) -> list[str]:
    if operator in _P1_UNSUPPORTED_OPERATORS:
        return []
    categories: set[str] = set()
    for target in path_schema.valid_target_paths():
        if not _operator_passes_for_target(target, operator):
            continue
        category = _category_label(category_for_target(target))
        if category is not None:
            categories.add(category)
    return sorted(categories)


def _category_label(category: TargetCategory) -> str | None:
    if category is TargetCategory.RECORD_COLLECTION or category is TargetCategory.RECORD:
        return "record"
    if category is TargetCategory.STRING_COLLECTION:
        return "string"
    if category is TargetCategory.NUMBER_COLLECTION:
        return "number"
    if category is TargetCategory.SCALAR_NUMBER:
        return "scalar_number"
    if category is TargetCategory.SCALAR_STRING:
        return "scalar_string"
    if category is TargetCategory.SCALAR_BOOL:
        return "scalar_bool"
    return None


@lru_cache(maxsize=1)
def _operator_evidence_emits() -> dict[Operator, tuple[str, ...]]:
    from semantic_ci_code.evaluator import operators as operator_module

    tree = ast.parse(Path(operator_module.__file__).read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    result: dict[Operator, tuple[str, ...]] = {}
    for function_name in ("evaluate_pure_operator", "evaluate_baseline_operator"):
        for node in ast.walk(functions[function_name]):
            if not isinstance(node, ast.If):
                continue
            operators = _operators_from_test(node.test)
            if not operators:
                continue
            keys = _evidence_keys_from_statements(node.body, functions, visited=set())
            for operator in operators:
                result[operator] = tuple(sorted(keys))
    result.setdefault(Operator.CHANGED_ONLY_IN, ())
    return result


def _operators_from_test(test: ast.expr) -> tuple[Operator, ...]:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return ()
    if not isinstance(test.left, ast.Name) or test.left.id != "operator":
        return ()
    comparator = test.comparators[0]
    if isinstance(test.ops[0], ast.Is):
        operator = _operator_from_ast(comparator)
        return (operator,) if operator is not None else ()
    if isinstance(test.ops[0], ast.In) and isinstance(comparator, ast.Set):
        operators = tuple(
            operator
            for item in comparator.elts
            if (operator := _operator_from_ast(item)) is not None
        )
        return operators
    return ()


def _operator_from_ast(node: ast.expr) -> Operator | None:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Operator"
    ):
        return Operator[node.attr]
    return None


def _evidence_keys_from_statements(
    statements: list[ast.stmt],
    functions: dict[str, ast.FunctionDef],
    *,
    visited: set[str],
) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(ast.Module(body=statements, type_ignores=[])):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            keys.update(_evidence_keys_from_call(node.value, functions, visited=visited))
    return keys


def _evidence_keys_from_function(
    name: str,
    functions: dict[str, ast.FunctionDef],
    *,
    visited: set[str],
) -> set[str]:
    if name in visited:
        return set()
    function = functions.get(name)
    if function is None:
        return set()
    visited.add(name)
    try:
        return _evidence_keys_from_statements(function.body, functions, visited=visited)
    finally:
        visited.remove(name)


def _evidence_keys_from_call(
    call: ast.Call,
    functions: dict[str, ast.FunctionDef],
    *,
    visited: set[str],
) -> set[str]:
    if not isinstance(call.func, ast.Name):
        return set()
    name = call.func.id
    keyword_names = {kw.arg for kw in call.keywords if kw.arg is not None}
    if name == "_boolean_outcome":
        return keyword_names
    if name == "_baseline_boolean_outcome":
        return {"baseline", "candidate"}
    if name == "_set_outcome":
        return {"observed", "expected", *keyword_names}
    if name == "_baseline_set_outcome":
        return {"baseline", "candidate", *keyword_names}
    if name == "_unknown_type_mismatch":
        return {key for key in keyword_names if key != "cause"}
    return _evidence_keys_from_function(name, functions, visited=visited)


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _json_value(value.model_dump(mode="json"))
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in sorted(value.items())}
    return value
