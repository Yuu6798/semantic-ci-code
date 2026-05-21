from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from semantic_ci_code.authoring.catalog import build_catalog
from semantic_ci_code.compiler import path_schema
from semantic_ci_code.compiler.operator_schema import (
    _BASELINE_OPERATORS,
    _P1_UNSUPPORTED_OPERATORS,
    _PURE_OPERATORS,
)
from semantic_ci_code.compiler.templates import TEMPLATE_CONSTRAINTS
from semantic_ci_code.domain.state_schema import ChangeKind
from semantic_ci_code.framework.constraint_types import Operator
from semantic_ci_code.framework.match_schema import _SCHEMAS

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_catalog_target_operator_template_key_sets_mirror_registries():
    catalog = build_catalog()
    assert set(catalog["targets"]) == set(path_schema.valid_target_paths())
    assert set(catalog["operators"]) == {operator.value for operator in Operator}
    assert set(catalog["templates"]) == {kind.value for kind in ChangeKind}


def test_catalog_match_schema_entries_mirror_registry():
    catalog = build_catalog()
    for target, schema in _SCHEMAS.items():
        assert catalog["targets"][target]["match_schema"] == {
            "required_key": schema.required_key,
            "optional_keys": sorted(schema.optional_keys),
            "forbidden_keys": {
                key: schema.forbidden_keys[key] for key in sorted(schema.forbidden_keys)
            },
        }
    for target, entry in catalog["targets"].items():
        if target not in _SCHEMAS:
            assert "match_schema" not in entry


def test_catalog_templates_mirror_template_constraints():
    catalog = build_catalog()
    for kind in ChangeKind:
        expected = [
            {
                "kind": constraint.kind.value,
                "target": constraint.target,
                "operator": constraint.operator.value,
                "expected": _json_value(constraint.expected),
                "severity": constraint.severity.value,
                "unknown_policy": constraint.unknown_policy.value,
            }
            for constraint in TEMPLATE_CONSTRAINTS[kind]
        ]
        assert catalog["templates"][kind.value]["expanded_constraints"] == expected


def test_catalog_operator_classes_mirror_operator_schema_sets():
    catalog = build_catalog()
    for operator in Operator:
        entry = catalog["operators"][operator.value]
        if operator in _P1_UNSUPPORTED_OPERATORS:
            assert entry["class"] == "skipped_in_p1"
            assert entry["applies_to_collection"] == []
        elif operator in _PURE_OPERATORS:
            assert entry["class"] == "pure"
        elif operator in _BASELINE_OPERATORS:
            assert entry["class"] == "baseline"
        else:  # pragma: no cover - enum drift guard
            raise AssertionError(f"unclassified operator: {operator!r}")


def test_catalog_operator_evidence_entries_are_derived_from_operator_module_ast():
    catalog = build_catalog()
    source = (REPO_ROOT / "src" / "semantic_ci_code" / "evaluator" / "operators.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    evidence_helpers = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "_evidence"
            for child in ast.walk(node)
        )
    }
    assert {
        "_boolean_outcome",
        "_baseline_boolean_outcome",
        "_set_outcome",
        "_baseline_set_outcome",
        "_unknown_type_mismatch",
    }.issubset(evidence_helpers)
    assert catalog["operators"]["excludes_all"]["evidence_emits"] == [
        "expected",
        "matched",
        "observed",
    ]
    assert catalog["operators"]["within_range"]["evidence_emits"] == [
        "expected",
        "lower",
        "observed",
        "tolerance",
        "upper",
    ]


def test_dogfooding_tc1_authoring_paths_are_representable_from_catalog():
    catalog = build_catalog(kind_filter=ChangeKind.REFACTOR)
    target = catalog["targets"]["api_surface_public"]
    assert "equals_baseline" in target["operators"]
    assert target["match_schema"]["required_key"] == "fqn"
    constraints = catalog["templates"]["refactor"]["expanded_constraints"]
    assert {item["target"] for item in constraints} <= set(catalog["targets"])
    assert all(
        item["operator"] in catalog["targets"][item["target"]]["operators"] for item in constraints
    )


def _json_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in sorted(value.items())}
    return value
