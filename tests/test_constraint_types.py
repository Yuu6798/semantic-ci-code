from __future__ import annotations

from pydantic import ValidationError

from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    DeltaConstraint,
    Operator,
    Severity,
    StateConstraint,
    UnknownPolicy,
    validate_constraint,
)


def test_enum_values_are_complete():
    assert {item.value for item in ConstraintKind} == {"state", "delta", "repair"}
    assert {item.value for item in Operator} == {
        "equals",
        "not_equals",
        "equals_baseline",
        "not_equals_baseline",
        "includes_all",
        "includes_any",
        "excludes_all",
        "subset_of",
        "superset_of",
        "superset_of_baseline",
        "no_new_items",
        "no_removed_items",
        "less_than",
        "less_than_or_equal",
        "greater_than",
        "greater_than_or_equal",
        "within_range",
        "unchanged",
        "changed",
        "changed_only_in",
    }
    assert {item.value for item in Severity} == {"hard", "soft", "info"}
    assert {item.value for item in UnknownPolicy} == {"fail", "repair", "warn", "ignore"}


def test_constraint_union_dispatches_by_kind():
    constraint = validate_constraint(
        {
            "id": "public_api_preserved",
            "kind": "delta",
            "target": "api_surface.public_symbols",
            "operator": "equals_baseline",
            "expected": "baseline",
            "severity": "hard",
            "unknown_policy": "fail",
        }
    )

    assert isinstance(constraint, DeltaConstraint)
    assert constraint.expected == "baseline"


def test_constraint_union_rejects_unknown_operator():
    try:
        validate_constraint(
            {
                "id": "bad",
                "kind": "state",
                "target": "complexity.cyclomatic",
                "operator": "may_decrease",
            }
        )
    except ValidationError as exc:
        assert "operator" in str(exc)
    else:
        raise AssertionError("unknown operator should be rejected")


def test_constraint_models_are_frozen():
    constraint = StateConstraint(
        id="complexity_budget",
        target="complexity.cyclomatic",
        operator=Operator.LESS_THAN_OR_EQUAL,
        expected=10,
    )

    try:
        constraint.target = "complexity.cognitive"  # type: ignore[misc]
    except ValidationError as exc:
        assert "frozen" in str(exc)
    else:
        raise AssertionError("constraint should be frozen")
