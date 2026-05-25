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
    "UnknownCause",
    "Verdict",
    "VerdictResult",
    "evaluate_constraints",
]

E_OPERATOR_TARGET_MISMATCH: Final = "E_OPERATOR_TARGET_MISMATCH"
E_OPERATOR_UNSUPPORTED_P1: Final = "E_OPERATOR_UNSUPPORTED_P1"
E_REPAIR_KIND_UNSUPPORTED_P1: Final = "E_REPAIR_KIND_UNSUPPORTED_P1"
E_DIMENSION_SKIPPED: Final = "E_DIMENSION_SKIPPED"
E_DIMENSION_TIMED_OUT: Final = "E_DIMENSION_TIMED_OUT"
E_HARD_LOCK_SHORT_CIRCUIT: Final = "E_HARD_LOCK_SHORT_CIRCUIT"
_LOCK_SHORT_CIRCUIT_OPERATORS: Final = frozenset(
    {
        Operator.EQUALS_BASELINE,
        Operator.SUPERSET_OF_BASELINE,
        Operator.NO_NEW_ITEMS,
        Operator.NO_REMOVED_ITEMS,
        Operator.UNCHANGED,
    }
)
_DENY_STYLE_LOCK_OPERATORS: Final = frozenset({Operator.EXCLUDES_ALL, Operator.SUBSET_OF})
_DELTA_LOCK_COLLECTION_TARGETS: Final = frozenset(
    {
        "api_surface_delta.added",
        "api_surface_delta.added.fqns",
        "api_surface_delta.removed",
        "api_surface_delta.removed_public",
        "api_surface_delta.changed",
        "effect_changes.added",
        "effect_changes.removed",
        "effect_changes.added.fqns",
        "imports_delta.added",
        "imports_delta.added.modules",
        "imports_delta.removed",
        "test_surface_delta.new_files",
        "test_surface_delta.new_cases",
        "test_surface_delta.removed_cases",
        "type_changes",
    }
)
_EMPTY_EQUALS_LOCK_RECORD_TARGETS: Final = {
    "api_surface_delta": frozenset({"added", "removed", "changed"}),
    "effect_changes": frozenset({"added", "removed"}),
    "imports_delta": frozenset({"added", "removed"}),
    "test_surface_delta": frozenset({"new_files", "new_cases", "removed_cases"}),
}

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


class UnknownCause(StrEnum):
    """Diagnostic cause attached to ``ResultStatus.UNKNOWN`` results.

    Splits the original conflated ``UNKNOWN`` value into a small set of
    diagnosable failure classes (Brief D1-4 of the ResultStatus split
    planning, ``docs/brief_resultstatus_planning.md`` §3 D1):

    - ``AUTHORING`` — the constraint is malformed. After Brief D1-2 and
      D1-3 nearly all authoring errors are rejected at compile time;
      this cause is emitted only by the residual defense-in-depth
      branches in the evaluator and operators (reachable solely from
      direct ``CompiledConstraint`` construction, e.g. evaluator tests).
      Authoring-cause UNKNOWN forces ``VerdictResult.FAIL`` regardless
      of ``unknown_policy`` (planning §3 D2).
    - ``EXTRACTION`` — the extractor produced partial state and a
      schema-valid path resolves to ``None`` at runtime. Routed by
      ``unknown_policy`` (the original intent of that policy per
      ``docs/code_semantic_ci_design.md`` §5.4).
    - ``OPEN_RUNTIME`` — the path lives in an open schema region
      (``python_specific.*`` / ``typescript_specific.*``) and resolves
      to a missing key at runtime. Routed by ``unknown_policy``.
    - ``EVALUATOR_INTERNAL`` — the two defensive ``except TypeError``
      catch-alls in ``evaluator/operators.py`` tripped. Near-bug;
      routed by ``unknown_policy`` for backward compatibility.
    """

    AUTHORING = "authoring"
    EXTRACTION = "extraction"
    OPEN_RUNTIME = "open_runtime"
    EVALUATOR_INTERNAL = "evaluator_internal"


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
    unknown_cause: UnknownCause | None = None


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
    extracted_dimensions: frozenset[str] | None = None,
    baseline_timed_out_dimensions: frozenset[str] | None = None,
    candidate_timed_out_dimensions: frozenset[str] | None = None,
) -> Verdict:
    """Evaluate compiled constraints against baseline/candidate states and delta."""

    results: list[ConstraintResult] = []
    short_circuited = False
    for constraint in compiled.constraints:
        if short_circuited:
            results.append(_short_circuit_skipped_result(constraint))
            continue

        result = _evaluate_constraint(
            constraint,
            delta=delta,
            baseline=baseline,
            candidate=candidate,
            effect_allow_new=compiled.effect_allow_new,
            api_surface_allow_changes=compiled.api_surface_allow_changes,
            extracted_dimensions=extracted_dimensions,
            baseline_timed_out_dimensions=baseline_timed_out_dimensions,
            candidate_timed_out_dimensions=candidate_timed_out_dimensions,
        )
        results.append(result)
        if _should_short_circuit(constraint, result):
            short_circuited = True

    result_tuple = tuple(results)
    return Verdict(result=_aggregate(result_tuple), results=result_tuple)


def _should_short_circuit(constraint: CompiledConstraint, result: ConstraintResult) -> bool:
    if not _is_user_lock_result(constraint, result):
        return False
    if result.status is ResultStatus.VIOLATED:
        return True
    return result.status is ResultStatus.UNKNOWN and result.unknown_cause is UnknownCause.AUTHORING


def _is_user_lock_result(constraint: CompiledConstraint, result: ConstraintResult) -> bool:
    # The current TargetSVP model has no distinct ``lock`` operator. The
    # explicit lock slice is user-authored preserve/deny invariants; template
    # hard invariants and positive change requirements continue to evaluate
    # fully so multi-violation repair guidance is not hidden by the first
    # non-lock failure.
    if result.source is not ConstraintSource.USER or result.severity is not Severity.HARD:
        return False
    return (
        result.operator in _LOCK_SHORT_CIRCUIT_OPERATORS
        or _is_equals_empty_delta_lock(constraint)
        or _is_deny_style_delta_lock(constraint)
    )


def _is_equals_empty_delta_lock(constraint: CompiledConstraint) -> bool:
    if constraint.kind is not ConstraintKind.DELTA or constraint.operator is not Operator.EQUALS:
        return False
    if constraint.target in _DELTA_LOCK_COLLECTION_TARGETS:
        return _is_empty_collection_literal(constraint.expected)
    return _is_full_zero_record_lock_literal(constraint.target, constraint.expected)


def _is_deny_style_delta_lock(constraint: CompiledConstraint) -> bool:
    return (
        constraint.kind is ConstraintKind.DELTA
        and constraint.operator in _DENY_STYLE_LOCK_OPERATORS
        and constraint.target in _DELTA_LOCK_COLLECTION_TARGETS
    )


def _is_full_zero_record_lock_literal(target: str, value: JsonValue) -> bool:
    expected_keys = _EMPTY_EQUALS_LOCK_RECORD_TARGETS.get(target)
    if expected_keys is None or not isinstance(value, dict):
        return False
    return frozenset(value) == expected_keys and all(
        _is_empty_collection_literal(item) for item in value.values()
    )


def _is_empty_collection_literal(value: JsonValue) -> bool:
    return isinstance(value, list | tuple | set | frozenset) and len(value) == 0


def _short_circuit_skipped_result(constraint: CompiledConstraint) -> ConstraintResult:
    return _result(
        constraint,
        ResultStatus.SKIPPED,
        E_HARD_LOCK_SHORT_CIRCUIT,
        reason="hard_lock_short_circuit",
    )


def _evaluate_constraint(
    constraint: CompiledConstraint,
    *,
    delta: CodeStateDelta,
    baseline: CodeState,
    candidate: CodeState,
    effect_allow_new: tuple[CompiledEffectAllowRule, ...],
    api_surface_allow_changes: tuple[CompiledAPISurfaceAllowRule, ...],
    extracted_dimensions: frozenset[str] | None,
    baseline_timed_out_dimensions: frozenset[str] | None,
    candidate_timed_out_dimensions: frozenset[str] | None,
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
        # Defense-in-depth: the syntactic ``_TARGET_PATTERN`` check is
        # also enforced at compile time. Authoring cause.
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            E_PATH_UNRESOLVED,
            target=constraint.target,
            unknown_cause=UnknownCause.AUTHORING,
        )
    skipped_dimension = _skipped_dimension(segments, extracted_dimensions)
    if skipped_dimension is not None:
        return _result(
            constraint,
            ResultStatus.SKIPPED,
            E_DIMENSION_SKIPPED,
            reason="partial_code_state",
            dimension=skipped_dimension,
        )
    timed_out_dimension = _timed_out_dimension(
        constraint,
        segments,
        baseline_timed_out_dimensions=baseline_timed_out_dimensions,
        candidate_timed_out_dimensions=candidate_timed_out_dimensions,
    )
    if timed_out_dimension is not None:
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            E_DIMENSION_TIMED_OUT,
            reason="extractor_timeout",
            dimension=timed_out_dimension,
            unknown_cause=UnknownCause.EXTRACTION,
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
        # Defensive catch-all for evaluator-internal raises; near-bug.
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            E_TYPE_MISMATCH,
            error=exc.__class__.__name__,
            unknown_cause=UnknownCause.EVALUATOR_INTERNAL,
        )

    raise AssertionError(f"Unknown constraint kind: {constraint.kind}")


def _evaluate_state_constraint(
    constraint: CompiledConstraint,
    segments: tuple[str, ...],
    *,
    candidate: CodeState,
) -> ConstraintResult:
    if segments[0] not in _CODE_STATE_FIELDS:
        # Defense-in-depth: path-domain check is also enforced at
        # compile time by ``compiler.path_schema``. Authoring cause.
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            E_PATH_UNRESOLVED,
            target=constraint.target,
            unknown_cause=UnknownCause.AUTHORING,
        )
    # Defense-in-depth: this combination (state-kind + baseline operator) is
    # rejected at compile time by ``compiler.operator_schema``. The branch
    # remains so direct ``CompiledConstraint`` construction (e.g. evaluator
    # unit tests) still gets a structured UNKNOWN result instead of an
    # AssertionError. Behavior is unchanged for the compiled path.
    if constraint.operator in BASELINE_OPERATORS:
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            E_OPERATOR_TARGET_MISMATCH,
            target=constraint.target,
            unknown_cause=UnknownCause.AUTHORING,
        )
    if constraint.operator not in PURE_OPERATORS:
        raise AssertionError(f"Unhandled state operator: {constraint.operator}")

    resolved, error_code = resolve_path(candidate, segments)
    if resolved is UNRESOLVED:
        # Runtime path resolution failure on a schema-valid path means
        # the extractor didn't populate this branch (or it was an open
        # dimension with a missing key).
        return _result(
            constraint,
            ResultStatus.UNKNOWN,
            error_code,
            target=constraint.target,
            unknown_cause=_resolved_unknown_cause(constraint.target),
        )
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
        # Defense-in-depth: this combination (delta-kind + delta-domain path
        # + baseline operator) is rejected at compile time by
        # ``compiler.operator_schema``. Direct ``CompiledConstraint``
        # construction in evaluator unit tests still routes here. Behavior
        # is unchanged for the compiled path.
        if constraint.operator in BASELINE_OPERATORS:
            return _result(
                constraint,
                ResultStatus.UNKNOWN,
                E_OPERATOR_TARGET_MISMATCH,
                target=constraint.target,
                unknown_cause=UnknownCause.AUTHORING,
            )
        if constraint.operator not in PURE_OPERATORS:
            raise AssertionError(f"Unhandled delta operator: {constraint.operator}")

        resolved, error_code = resolve_path(delta, segments)
        if resolved is UNRESOLVED:
            return _result(
                constraint,
                ResultStatus.UNKNOWN,
                error_code,
                target=constraint.target,
                unknown_cause=_resolved_unknown_cause(constraint.target),
            )
        outcome = evaluate_pure_operator(
            constraint.operator,
            resolved,
            constraint.expected,
            tolerance=constraint.tolerance,
        )
        return _from_operator_outcome(constraint, outcome)

    if first in _CODE_STATE_FIELDS:
        # Defense-in-depth: this combination (delta-kind + state-domain path
        # + pure operator) is rejected at compile time by
        # ``compiler.operator_schema``. Direct ``CompiledConstraint``
        # construction in evaluator unit tests still routes here. Behavior
        # is unchanged for the compiled path.
        if constraint.operator not in BASELINE_OPERATORS:
            return _result(
                constraint,
                ResultStatus.UNKNOWN,
                E_OPERATOR_TARGET_MISMATCH,
                target=constraint.target,
                unknown_cause=UnknownCause.AUTHORING,
            )

        baseline_value, baseline_error = resolve_path(baseline, segments)
        candidate_value, candidate_error = resolve_path(candidate, segments)
        if baseline_value is UNRESOLVED or candidate_value is UNRESOLVED:
            return _result(
                constraint,
                ResultStatus.UNKNOWN,
                baseline_error or candidate_error,
                target=constraint.target,
                unknown_cause=_resolved_unknown_cause(constraint.target),
            )
        outcome = evaluate_baseline_operator(
            constraint.operator,
            baseline_value,
            candidate_value,
            tolerance=constraint.tolerance,
        )
        return _from_operator_outcome(constraint, outcome)

    # Defense-in-depth: target's first segment is on neither domain.
    # Compile catches this; reach implies direct CompiledConstraint use.
    return _result(
        constraint,
        ResultStatus.UNKNOWN,
        E_PATH_UNRESOLVED,
        target=constraint.target,
        unknown_cause=UnknownCause.AUTHORING,
    )


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
    effect_resolved_call = _effect_resolved_call(effect)
    effect_class = _effect_field(effect, "effect_class")
    effect_class_value = getattr(effect_class, "value", effect_class)

    for rule in rules:
        if rule.fqn is not None and rule.fqn not in {effect_fqn, effect_resolved_call}:
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


def _effect_resolved_call(effect: object) -> object:
    evidence = _effect_field(effect, "evidence")
    if isinstance(evidence, dict):
        return evidence.get("resolved_call")
    if isinstance(evidence, tuple | list):
        for item in evidence:
            if isinstance(item, tuple | list) and len(item) == 2 and item[0] == "resolved_call":
                return item[1]
    return None


def _from_operator_outcome(
    constraint: CompiledConstraint,
    outcome,
) -> ConstraintResult:
    # operators.py uses string causes (it cannot import UnknownCause from
    # this module without forming a cycle); convert to the enum at the
    # boundary.
    if outcome.unknown_cause is None:
        cause: UnknownCause | None = None
    else:
        cause = UnknownCause(outcome.unknown_cause)
        # ``_unknown_type_mismatch`` defaults to ``authoring`` because the
        # 11 user-facing emit sites are unreachable from a typed path
        # post-D1-3. Open-dimension targets are intentionally exempted
        # from the type-schema check (their value shape cannot be proven
        # at compile), so a runtime shape mismatch on them DOES come from
        # well-formed target.yaml input. Re-tag those as ``open_runtime``
        # so they keep ``unknown_policy`` routing per planning §3 D2.
        if cause is UnknownCause.AUTHORING and _is_open_target(constraint.target):
            cause = UnknownCause.OPEN_RUNTIME
    return _result(
        constraint,
        ResultStatus(outcome.status),
        outcome.error_code,
        evidence=outcome.evidence,
        unknown_cause=cause,
    )


def _aggregate(results: tuple[ConstraintResult, ...]) -> VerdictResult:
    has_repair = False
    for result in results:
        if result.status is ResultStatus.VIOLATED:
            if result.severity is Severity.HARD:
                return VerdictResult.FAIL
            elif result.severity is Severity.SOFT:
                has_repair = True
            elif result.severity is Severity.INFO:
                pass
            else:
                raise NotImplementedError(f"unhandled severity: {result.severity!r}")
        elif result.status is ResultStatus.UNKNOWN:
            # Authoring-cause UNKNOWN is invalid input, not undecided
            # judgment, so it forces FAIL irrespective of unknown_policy
            # (planning §3 D2). After Brief D1-2 / D1-3 this path is
            # only reachable via direct CompiledConstraint construction
            # (e.g. evaluator tests).
            if result.unknown_cause is UnknownCause.AUTHORING:
                return VerdictResult.FAIL
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
    unknown_cause: UnknownCause | None = None,
    **extra_evidence: JsonValue,
) -> ConstraintResult:
    merged_evidence = tuple(
        sorted(
            evidence + tuple(sorted(extra_evidence.items())),
            key=lambda item: item[0],
        )
    )
    # unknown_cause is meaningful only when status is UNKNOWN.
    cause = unknown_cause if status is ResultStatus.UNKNOWN else None
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
        unknown_cause=cause,
    )


def _is_open_target(target: str) -> bool:
    """Return True for ``python_specific.*`` / ``typescript_specific.*``."""

    head = target.partition(".")[0]
    return head in {"python_specific", "typescript_specific"}


def _is_schema_valid_target(target: str) -> bool:
    """Return True when ``target`` appears in the static schema corpus.

    Both state and delta path domains are considered because a delta-kind
    constraint may legitimately reference a CodeState path (baseline
    operator semantics). Open-prefix matches are owned by
    ``_is_open_target`` instead.

    Imported lazily to keep ``evaluator.evaluator`` import-light at module
    load (path_schema reflects on Pydantic models on first use).
    """

    from semantic_ci_code.compiler.path_schema import (
        valid_delta_target_paths,
        valid_state_target_paths,
    )

    return target in valid_state_target_paths() or target in valid_delta_target_paths()


def _resolved_unknown_cause(target: str) -> UnknownCause:
    """Cause for runtime path-resolution failures at evaluate time.

    Three-way classification (planning §3 D1):

    - Open-dimension paths (``python_specific.*`` / ``typescript_specific.*``)
      → ``OPEN_RUNTIME`` (resolves to a missing key in an intentionally
      open schema region; routed by ``unknown_policy``).
    - Schema-valid paths that resolved to ``UNRESOLVED`` → ``EXTRACTION``
      (the extractor populated parent as ``None`` or omitted the key the
      constraint reads; routed by ``unknown_policy``).
    - Schema-invalid paths reaching evaluate-time → ``AUTHORING``.
      ``compiler.path_schema`` rejects these at compile, so they can
      only arrive via direct ``CompiledConstraint`` construction. Per
      planning §3 D1 / D2 these are malformed input and must force
      ``FAIL`` regardless of ``unknown_policy``.
    """

    if _is_open_target(target):
        return UnknownCause.OPEN_RUNTIME
    if _is_schema_valid_target(target):
        return UnknownCause.EXTRACTION
    return UnknownCause.AUTHORING


def _target_segments(target: str) -> tuple[str, ...] | None:
    if _TARGET_PATTERN.fullmatch(target) is None:
        return None
    return tuple(target.split("."))


def _skipped_dimension(
    segments: tuple[str, ...],
    extracted_dimensions: frozenset[str] | None,
) -> str | None:
    if extracted_dimensions is None:
        return None
    dimension = _dimension_for_target(segments)
    if dimension is None or dimension in extracted_dimensions:
        return None
    return dimension


def _timed_out_dimension(
    constraint: CompiledConstraint,
    segments: tuple[str, ...],
    *,
    baseline_timed_out_dimensions: frozenset[str] | None,
    candidate_timed_out_dimensions: frozenset[str] | None,
) -> str | None:
    dimension = _dimension_for_target(segments)
    if dimension is None:
        return None
    if constraint.kind is ConstraintKind.STATE:
        timed_out_dimensions = candidate_timed_out_dimensions or frozenset()
    elif constraint.kind is ConstraintKind.DELTA:
        timed_out_dimensions = (baseline_timed_out_dimensions or frozenset()) | (
            candidate_timed_out_dimensions or frozenset()
        )
    else:
        return None
    if dimension not in timed_out_dimensions:
        return None
    return dimension


def _dimension_for_target(segments: tuple[str, ...]) -> str | None:
    first = segments[0]
    if first in {"api_surface", "api_surface_public", "api_surface_delta"}:
        return "api_surface"
    if first in {"effects", "effect_changes"}:
        return "effects"
    if first in {"imports", "imports_delta"}:
        return "imports"
    if first in {"complexity", "complexity_delta"}:
        return "complexity"
    if first in {"test_surface", "test_surface_delta"}:
        return "test_surface"
    if first == "module_graph":
        return "module_graph"
    if first in {"type_relations", "type_changes"}:
        return "type_relations"
    if first in {"control_flow", "cfg_delta"}:
        return "control_flow"
    if first == "data_flow":
        return "data_flow"
    if first in {"coverage", "coverage_delta"}:
        return "coverage"
    if first == "python_specific" and len(segments) > 1:
        if segments[1] == "module_graph_delta":
            return "module_graph"
        if segments[1] == "complexity_changes":
            return "complexity"
        if segments[1] == "test_surface_changes":
            return "test_surface"
    if first == "typescript_specific":
        return "typescript_specific"
    return None
