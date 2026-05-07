from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from semantic_ci_code.compiler import (
    CompiledConstraint,
    CompiledTarget,
    ConstraintSource,
    compile_target_svp,
)
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.domain.state_schema import CodeState, JsonValue
from semantic_ci_code.evaluator import ResultStatus, evaluate_constraints
from semantic_ci_code.framework.constraint_types import Operator
from semantic_ci_code.framework.target_svp import TargetSVP, target_svp_to_yaml
from semantic_ci_code.repair_compiler.types import (
    RISK_SUMMARY_KEYS,
    RiskSummary,
    empty_risk_summary,
)

_FORBIDDEN_ZONE_OPERATORS = frozenset(
    {
        Operator.EQUALS_BASELINE,
        Operator.SUPERSET_OF_BASELINE,
        Operator.NO_NEW_ITEMS,
        Operator.NO_REMOVED_ITEMS,
        Operator.UNCHANGED,
    }
)
_REQUIRED_ADDITION_OPERATORS = frozenset({Operator.INCLUDES_ALL, Operator.INCLUDES_ANY})


def compute_risk_summary(target: TargetSVP, baseline_state: CodeState) -> RiskSummary:
    """Compute deterministic pre-generation risk summary projections."""

    # compile_target_svp currently accepts YAML text only. Round-trip TargetSVP
    # through YAML to reuse the established compiler without changing engine API.
    compiled = compile_target_svp(target_svp_to_yaml(target), filename="<target_svp>")
    return {
        "would_violate": _would_violate(compiled, baseline_state),
        "forbidden_zones": _forbidden_zones(compiled.constraints),
        "required_additions": _required_additions(compiled.constraints),
        "template_implications": _template_implications(compiled.constraints),
    }


def normalize_risk_summary(summary: dict[str, Any] | None) -> RiskSummary:
    if summary is None:
        return empty_risk_summary()
    return {key: list(summary.get(key, ())) for key in RISK_SUMMARY_KEYS}


def _would_violate(
    compiled: CompiledTarget,
    baseline_state: CodeState,
) -> list[JsonValue]:
    delta = compute_code_state_delta(baseline_state, baseline_state)
    verdict = evaluate_constraints(
        compiled,
        delta,
        baseline=baseline_state,
        candidate=baseline_state,
    )
    return [
        result.constraint_id
        for result in verdict.results
        if result.source is ConstraintSource.USER and result.status is ResultStatus.VIOLATED
    ]


def _forbidden_zones(constraints: tuple[CompiledConstraint, ...]) -> list[JsonValue]:
    return [
        {
            "constraint_id": constraint.id,
            "source": constraint.source.value,
            "target": constraint.target,
            "operator": constraint.operator.value,
        }
        for constraint in constraints
        if constraint.operator in _FORBIDDEN_ZONE_OPERATORS
    ]


def _required_additions(constraints: tuple[CompiledConstraint, ...]) -> list[JsonValue]:
    required: list[JsonValue] = []
    for constraint in constraints:
        if constraint.operator is Operator.INCLUDES_ALL:
            for expected in _expected_items(constraint.expected):
                required.append(
                    {
                        "constraint_id": constraint.id,
                        "source": constraint.source.value,
                        "target": constraint.target,
                        "operator": constraint.operator.value,
                        "expected": _jsonable(expected),
                    }
                )
            continue

        if constraint.operator is Operator.INCLUDES_ANY:
            required.append(
                {
                    "constraint_id": constraint.id,
                    "source": constraint.source.value,
                    "target": constraint.target,
                    "operator": constraint.operator.value,
                    "expected_any_of": [
                        _jsonable(item) for item in _expected_items(constraint.expected)
                    ],
                }
            )
    return required


def _template_implications(constraints: tuple[CompiledConstraint, ...]) -> list[JsonValue]:
    return [
        constraint.id
        for constraint in constraints
        if constraint.source is ConstraintSource.TEMPLATE
    ]


def _expected_items(expected: JsonValue) -> tuple[JsonValue, ...]:
    if isinstance(expected, tuple | list):
        return tuple(expected)
    if expected is None:
        return ()
    return (expected,)


def _jsonable(value: JsonValue) -> JsonValue:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value
