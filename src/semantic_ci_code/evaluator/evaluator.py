"""Deterministic constraint evaluation for compiled Target SVP constraints.

``evaluate_constraints(compiled, delta, *, baseline, candidate)`` is the first
Brief 3 slice that returns an actual semantic verdict. It is a pure function:
no file I/O, network, time, random, environment reads, repair generation, CLI
logic, or git access. Schema-valid inputs are handled as results, not raised
exceptions; unresolved target paths and type mismatches become ``UNKNOWN``.

P1 target paths are dotted-only with no indexes, globs, or wildcards. For
``state`` constraints, the first segment must be a ``CodeState`` field and is
resolved on ``candidate``. For ``delta`` constraints, a ``CodeStateDelta`` first
segment resolves on ``delta``; a ``CodeState`` first segment resolves on both
``baseline`` and ``candidate`` and requires a baseline-aware operator.
``python_specific`` exists on both state and delta models, so ``kind`` decides
the root: ``state`` reads candidate state, while ``delta`` reads delta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from semantic_ci_code.compiler import CompiledConstraint, CompiledTarget, ConstraintSource
from semantic_ci_code.domain.state_schema import CodeState, CodeStateDelta, JsonValue
from semantic_ci_code.evaluator.operators import (
    BASELINE_OPERATORS,
    E_TYPE_MISMATCH,
    PURE_OPERATORS,
    evaluate_baseline_operator,
    evaluate_pure_operator,
)
from semantic_ci_code.evaluator.path_resolver import E_PATH_UNRESOLVED, UNRESOLVED, resolve_path
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)

__all__ = [
    "ConstraintResult",
    "ResultStatus",
    "Verdict",
    "VerdictResult",
    "evaluate_constraints",
]

E_OPERATOR_TARGET_MISMATCH: Final = "E_OPERATOR_TARGET_MISMATCH"
E_OPERATOR_UNSUPPORTED_P1: Final = "E_OPERATOR_UNSUPPORTED_P1"
E_REPAIR_KIND_UNSUPPORTED_P1: Final = "E_REPAIR_KIND_UNSUPPORTED_P1"

_TARGET_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_CODE_STATE_FIELDS = frozenset(CodeState.model_fields)
_CODE_STATE_DELTA_FIELDS = frozenset(CodeStateDelta.model_fields)


class ResultStatus(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"


class VerdictResult(StrEnum):
    PASS = "pass"
    REPAIR = "repair"
    FAIL = "fail"


@dataclass(frozen=True)
class ConstraintResult:
    constraint_id: str
    source: ConstraintSource
    kind: ConstraintKind
    target: str
    operator: Operator
    severity: Severity
    unknown_policy: UnknownPolicy
    tolerance: float | None
    evidence_required: bool
    status: ResultStatus
    error_code: str | None
    evidence: tuple[tuple[str, JsonValue], ...]


@dataclass(frozen=True)
class Verdict:
    result: VerdictResult
    results: tuple[ConstraintResult, ...]

    @property
    def violations(self) -> tuple[ConstraintResult, ...]:
        return tuple(result for result in self.results if result.status is ResultStatus.VIOLATED)

    @property
    def unknowns(self) -> tuple[ConstraintResult, ...]:
        return tuple(result for result in self.results if result.status is ResultStatus.UNKNOWN)

    @property
    def skipped(self) -> tuple[ConstraintResult, ...]:
        return tuple(result for result in self.results if result.status is ResultStatus.SKIPPED)


def evaluate_constraints(
    compiled: CompiledTarget,
    delta: CodeStateDelta,
    *,
    baseline: CodeState,
    candidate: CodeState,
) -> Verdict:
    """Evaluate compiled constraints against baseline/candidate states and delta."""

    results = tuple(
        _evaluate_constraint(
            constraint,
            delta=delta,
            baseline=baseline,
            candidate=candidate,
        )
        for constraint in compiled.constraints
    )
    return Verdict(result=_aggregate(results), results=results)


def _evaluate_constraint(
    constraint: CompiledConstraint,
    *,
    delta: CodeStateDelta,
    baseline: CodeState,
    candidate: CodeState,
) -> ConstraintResult:
    if constraint.kind is ConstraintKind.REPAIR:
        return _result(
            constraint,
            ResultStatus.SKIPPED,
            E_REPAIR_KIND_UNSUPPORTED_P1,
            reason="repair_kind_p1",
        )
    if constraint.operator is Operator.CHANGED_ONLY_IN:
        return _result(
            constraint,
            ResultStatus.SKIPPED,
            E_OPERATOR_UNSUPPORTED_P1,
            reason="changed_only_in_p1",
        )

    segments = _target_segments(constraint.target)
    if segments is None:
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            E_PATH_UNRESOLVED,
            target=constraint.target,
        )

    try:
        if constraint.kind is ConstraintKind.STATE:
            return _evaluate_state_constraint(constraint, segments, candidate=candidate)
        if constraint.kind is ConstraintKind.DELTA:
            return _evaluate_delta_constraint(
                constraint,
                segments,
                delta=delta,
                baseline=baseline,
                candidate=candidate,
            )
    except AssertionError:
        raise
    except Exception as exc:
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            E_TYPE_MISMATCH,
            error=exc.__class__.__name__,
        )

    raise AssertionError(f"Unknown constraint kind: {constraint.kind}")


def _evaluate_state_constraint(
    constraint: CompiledConstraint,
    segments: tuple[str, ...],
    *,
    candidate: CodeState,
) -> ConstraintResult:
    if segments[0] not in _CODE_STATE_FIELDS:
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            E_PATH_UNRESOLVED,
            target=constraint.target,
        )
    if constraint.operator in BASELINE_OPERATORS:
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            E_OPERATOR_TARGET_MISMATCH,
            target=constraint.target,
        )
    if constraint.operator not in PURE_OPERATORS:
        raise AssertionError(f"Unhandled state operator: {constraint.operator}")

    resolved, error_code = resolve_path(candidate, segments)
    if resolved is UNRESOLVED:
        return _result(constraint, ResultStatus.UNKNOWN, error_code, target=constraint.target)
    outcome = evaluate_pure_operator(
        constraint.operator,
        resolved,
        constraint.expected,
        tolerance=constraint.tolerance,
    )
    return _from_operator_outcome(constraint, outcome)


def _evaluate_delta_constraint(
    constraint: CompiledConstraint,
    segments: tuple[str, ...],
    *,
    delta: CodeStateDelta,
    baseline: CodeState,
    candidate: CodeState,
) -> ConstraintResult:
    first = segments[0]
    if first in _CODE_STATE_DELTA_FIELDS:
        if constraint.operator in BASELINE_OPERATORS:
            return _result(
                constraint,
                ResultStatus.UNKNOWN,
                E_OPERATOR_TARGET_MISMATCH,
                target=constraint.target,
            )
        if constraint.operator not in PURE_OPERATORS:
            raise AssertionError(f"Unhandled delta operator: {constraint.operator}")

        resolved, error_code = resolve_path(delta, segments)
        if resolved is UNRESOLVED:
            return _result(constraint, ResultStatus.UNKNOWN, error_code, target=constraint.target)
        outcome = evaluate_pure_operator(
            constraint.operator,
            resolved,
            constraint.expected,
            tolerance=constraint.tolerance,
        )
        return _from_operator_outcome(constraint, outcome)

    if first in _CODE_STATE_FIELDS:
        if constraint.operator not in BASELINE_OPERATORS:
            return _result(
                constraint,
                ResultStatus.UNKNOWN,
                E_OPERATOR_TARGET_MISMATCH,
                target=constraint.target,
            )

        baseline_value, baseline_error = resolve_path(baseline, segments)
        candidate_value, candidate_error = resolve_path(candidate, segments)
        if baseline_value is UNRESOLVED or candidate_value is UNRESOLVED:
            return _result(
                constraint,
                ResultStatus.UNKNOWN,
                baseline_error or candidate_error,
                target=constraint.target,
            )
        outcome = evaluate_baseline_operator(
            constraint.operator,
            baseline_value,
            candidate_value,
            tolerance=constraint.tolerance,
        )
        return _from_operator_outcome(constraint, outcome)

    return _result(constraint, ResultStatus.UNKNOWN, E_PATH_UNRESOLVED, target=constraint.target)


def _from_operator_outcome(
    constraint: CompiledConstraint,
    outcome,
) -> ConstraintResult:
    return _result(
        constraint,
        ResultStatus(outcome.status),
        outcome.error_code,
        evidence=outcome.evidence,
    )


def _aggregate(results: tuple[ConstraintResult, ...]) -> VerdictResult:
    has_repair = False
    for result in results:
        if result.status is ResultStatus.VIOLATED:
            if result.severity is Severity.HARD:
                return VerdictResult.FAIL
            if result.severity is Severity.SOFT:
                has_repair = True
        elif result.status is ResultStatus.UNKNOWN:
            if result.unknown_policy is UnknownPolicy.FAIL:
                return VerdictResult.FAIL
            if result.unknown_policy is UnknownPolicy.REPAIR:
                has_repair = True

    return VerdictResult.REPAIR if has_repair else VerdictResult.PASS


def _result(
    constraint: CompiledConstraint,
    status: ResultStatus,
    error_code: str | None,
    *,
    evidence: tuple[tuple[str, JsonValue], ...] = (),
    **extra_evidence: JsonValue,
) -> ConstraintResult:
    merged_evidence = tuple(
        sorted(
            evidence + tuple(sorted(extra_evidence.items())),
            key=lambda item: item[0],
        )
    )
    return ConstraintResult(
        constraint_id=constraint.id,
        source=constraint.source,
        kind=constraint.kind,
        target=constraint.target,
        operator=constraint.operator,
        severity=constraint.severity,
        unknown_policy=constraint.unknown_policy,
        tolerance=constraint.tolerance,
        evidence_required=constraint.evidence_required,
        status=status,
        error_code=error_code,
        evidence=merged_evidence,
    )


def _target_segments(target: str) -> tuple[str, ...] | None:
    if _TARGET_PATTERN.fullmatch(target) is None:
        return None
    return tuple(target.split("."))
