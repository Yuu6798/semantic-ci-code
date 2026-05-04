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

Target SVP ``api_surface.allow_changes`` is a narrow policy escape hatch for
template API checks. Matching FQNs are removed from the template's comparison
view only; user constraints still see the original api surface and delta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from semantic_ci_code.compiler import (
    CompiledAPISurfaceAllowRule,
    CompiledConstraint,
    CompiledEffectAllowRule,
    CompiledTarget,
    ConstraintSource,
)
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
_CODE_STATE_FIELDS = frozenset(CodeState.model_fields) | {"api_surface_public"}
_CODE_STATE_DELTA_FIELDS = frozenset(CodeStateDelta.model_fields)
_NO_NEW_EFFECTS_TEMPLATE_IDS: Final = frozenset(
    {
        "template:bugfix:no_new_effects",
        "template:feature:no_new_effects",
    }
)
_API_SURFACE_UNCHANGED_TEMPLATE_IDS: Final = frozenset(
    {
        "template:refactor:api_surface_unchanged",
        "template:bugfix:api_surface_unchanged",
        "template:test_update:api_surface_unchanged",
    }
)
_API_SURFACE_REMOVED_TEMPLATE_IDS: Final = frozenset(
    {
        "template:feature:no_removed_api",
    }
)


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
            effect_allow_new=compiled.effect_allow_new,
            api_surface_allow_changes=compiled.api_surface_allow_changes,
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
    effect_allow_new: tuple[CompiledEffectAllowRule, ...],
    api_surface_allow_changes: tuple[CompiledAPISurfaceAllowRule, ...],
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
            delta = _delta_for_constraint(
                constraint,
                delta=delta,
                effect_allow_new=effect_allow_new,
                api_surface_allow_changes=api_surface_allow_changes,
            )
            baseline, candidate = _states_for_constraint(
                constraint,
                baseline=baseline,
                candidate=candidate,
                api_surface_allow_changes=api_surface_allow_changes,
            )
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


def _delta_for_constraint(
    constraint: CompiledConstraint,
    *,
    delta: CodeStateDelta,
    effect_allow_new: tuple[CompiledEffectAllowRule, ...],
    api_surface_allow_changes: tuple[CompiledAPISurfaceAllowRule, ...],
) -> CodeStateDelta:
    """Return the delta view used by this constraint.

    Target SVP ``api_surface.allow_changes`` is a narrow policy escape hatch for
    template API removal checks.

    Target SVP ``effects.allow_new`` is a narrow policy escape hatch for
    feature/bugfix template ``no_new_effects`` checks. User constraints still
    see the original api surface and effect delta tuples.
    """

    delta_view = delta

    if (
        api_surface_allow_changes
        and constraint.source is ConstraintSource.TEMPLATE
        and constraint.id in _API_SURFACE_REMOVED_TEMPLATE_IDS
        and constraint.target == "api_surface_delta.removed_public"
        and constraint.operator is Operator.EQUALS
    ):
        removed = _filter_api_surface_entries(
            delta_view.api_surface_delta.removed,
            api_surface_allow_changes,
        )
        if removed != delta_view.api_surface_delta.removed:
            delta_view = delta_view.model_copy(
                update={
                    "api_surface_delta": delta_view.api_surface_delta.model_copy(
                        update={"removed": removed}
                    ),
                }
            )

    if (
        effect_allow_new
        and constraint.source is ConstraintSource.TEMPLATE
        and constraint.id in _NO_NEW_EFFECTS_TEMPLATE_IDS
        and constraint.target == "effect_changes.added"
        and constraint.operator is Operator.EQUALS
    ):
        added = tuple(
            effect
            for effect in delta_view.effect_changes.added
            if not _effect_matches_allow_rule(effect, effect_allow_new)
        )
        if added != delta_view.effect_changes.added:
            delta_view = delta_view.model_copy(
                update={
                    "effect_changes": delta_view.effect_changes.model_copy(update={"added": added}),
                }
            )

    return delta_view


def _states_for_constraint(
    constraint: CompiledConstraint,
    *,
    baseline: CodeState,
    candidate: CodeState,
    api_surface_allow_changes: tuple[CompiledAPISurfaceAllowRule, ...],
) -> tuple[CodeState, CodeState]:
    """Return baseline/candidate views used by this constraint."""

    if (
        not api_surface_allow_changes
        or constraint.source is not ConstraintSource.TEMPLATE
        or constraint.id not in _API_SURFACE_UNCHANGED_TEMPLATE_IDS
        or constraint.target != "api_surface_public"
        or constraint.operator is not Operator.EQUALS_BASELINE
    ):
        return baseline, candidate

    return (
        _filter_code_state_api_surface(baseline, api_surface_allow_changes),
        _filter_code_state_api_surface(candidate, api_surface_allow_changes),
    )


def _filter_code_state_api_surface(
    state: CodeState,
    rules: tuple[CompiledAPISurfaceAllowRule, ...],
) -> CodeState:
    api_surface = _filter_api_surface_entries(state.api_surface, rules)
    if api_surface == state.api_surface:
        return state
    return state.model_copy(update={"api_surface": api_surface})


def _filter_api_surface_entries(
    entries: tuple[object, ...],
    rules: tuple[CompiledAPISurfaceAllowRule, ...],
) -> tuple[object, ...]:
    return tuple(entry for entry in entries if not _api_surface_matches_allow_rule(entry, rules))


def _api_surface_matches_allow_rule(
    entry: object,
    rules: tuple[CompiledAPISurfaceAllowRule, ...],
) -> bool:
    fqn = _api_surface_field(entry, "fqn")
    if not isinstance(fqn, str):
        return False
    for rule in rules:
        if rule.fqn is not None and fqn == rule.fqn:
            return True
        if rule.fqn_prefix is not None and fqn.startswith(rule.fqn_prefix):
            return True
    return False


def _api_surface_field(entry: object, key: str) -> object:
    if isinstance(entry, dict):
        return entry.get(key)
    if isinstance(entry, tuple | list):
        for item in entry:
            if isinstance(item, tuple | list) and len(item) == 2 and item[0] == key:
                return item[1]
    return getattr(entry, key, None)


def _effect_matches_allow_rule(
    effect: object,
    rules: tuple[CompiledEffectAllowRule, ...],
) -> bool:
    effect_fqn = _effect_field(effect, "fqn")
    effect_class = _effect_field(effect, "effect_class")
    effect_class_value = getattr(effect_class, "value", effect_class)

    for rule in rules:
        if rule.fqn is not None and effect_fqn != rule.fqn:
            continue
        if rule.effect_class is not None and effect_class_value != rule.effect_class.value:
            continue
        return True
    return False


def _effect_field(effect: object, key: str) -> object:
    if isinstance(effect, dict):
        return effect.get(key)
    if isinstance(effect, tuple | list):
        for item in effect:
            if isinstance(item, tuple | list) and len(item) == 2 and item[0] == key:
                return item[1]
    return getattr(effect, key, None)


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
