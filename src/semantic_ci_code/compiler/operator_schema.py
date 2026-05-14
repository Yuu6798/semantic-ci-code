"""Static (kind, operator-class, path-domain) compatibility check.

The evaluator emits ``E_OPERATOR_TARGET_MISMATCH`` (status ``UNKNOWN``) for
three classes of authoring mistake:

- state-kind constraint with a baseline operator
  (``evaluator.evaluator._evaluate_state_constraint``)
- delta-kind constraint with a baseline operator on a delta-domain path
  (``evaluator.evaluator._evaluate_delta_constraint``, delta-branch)
- delta-kind constraint with a pure operator on a state-domain path
  (``evaluator.evaluator._evaluate_delta_constraint``, state-branch)

All three are *authoring* errors — the spec is malformed. They were
previously rendered as runtime ``UNKNOWN`` results and routed via
``unknown_policy``, which conflated extractor failures with broken specs
(see ``docs/brief_resultstatus_planning.md`` §1, §2). This module pushes
them back to compile time so that an ``unknown_policy: warn`` on an
unrelated constraint cannot silently swallow a typo'd combination.

This check operates on the (kind, target, operator) triple. The target
path is assumed to be valid for the constraint kind (already enforced by
``path_schema._validate_target_svp_values``); only the operator-class
vs. resolved path-domain alignment is decided here.
"""

from __future__ import annotations

from collections.abc import Mapping
from difflib import get_close_matches

from semantic_ci_code.domain.state_schema import CodeState, CodeStateDelta
from semantic_ci_code.framework.constraint_types import ConstraintKind, Operator

# ``_BASELINE_OPERATORS`` and ``_PURE_OPERATORS`` are duplicated here from
# ``evaluator.operators`` so that compile-time validation does not trigger
# the evaluator package's initialization. ``compiler`` is loaded before
# ``evaluator`` (``evaluator.evaluator`` imports compiled types from this
# package), so importing the evaluator at module top would form a cycle.
# The lists below MUST stay in sync with ``evaluator.operators``;
# ``test_operator_schema_matches_evaluator_operators`` enforces equality.
_BASELINE_OPERATORS: frozenset[Operator] = frozenset(
    {
        Operator.EQUALS_BASELINE,
        Operator.NOT_EQUALS_BASELINE,
        Operator.SUPERSET_OF_BASELINE,
        Operator.NO_NEW_ITEMS,
        Operator.NO_REMOVED_ITEMS,
        Operator.UNCHANGED,
        Operator.CHANGED,
    }
)
_PURE_OPERATORS: frozenset[Operator] = frozenset(
    {
        Operator.EQUALS,
        Operator.NOT_EQUALS,
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.EXCLUDES_ALL,
        Operator.SUBSET_OF,
        Operator.SUPERSET_OF,
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.WITHIN_RANGE,
    }
)

__all__ = [
    "OperatorTargetMismatch",
    "check_operator_target_compatibility",
]


# Mirrors ``evaluator.evaluator._CODE_STATE_FIELDS`` (includes the
# ``api_surface_public`` alias). Keep in sync if the evaluator widens it.
_CODE_STATE_FIELDS: frozenset[str] = frozenset(CodeState.model_fields) | {"api_surface_public"}

# Mirrors ``evaluator.evaluator._CODE_STATE_DELTA_FIELDS``.
_CODE_STATE_DELTA_FIELDS: frozenset[str] = frozenset(CodeStateDelta.model_fields)

# ``changed_only_in`` is SKIPPED at evaluate time before any path-domain
# check (E_OPERATOR_UNSUPPORTED_P1). Leave it past compile so the SKIPPED
# channel remains authored-as-declared.
_P1_UNSUPPORTED_OPERATORS: frozenset[Operator] = frozenset({Operator.CHANGED_ONLY_IN})

# 1:1 swap hints used to render "Did you mean: <op>?" follow-up text.
_BASELINE_TO_PURE_HINT: Mapping[Operator, Operator] = {
    Operator.EQUALS_BASELINE: Operator.EQUALS,
    Operator.NOT_EQUALS_BASELINE: Operator.NOT_EQUALS,
    Operator.SUPERSET_OF_BASELINE: Operator.SUPERSET_OF,
    Operator.UNCHANGED: Operator.EQUALS,
    Operator.CHANGED: Operator.NOT_EQUALS,
}

_PURE_TO_BASELINE_HINT: Mapping[Operator, Operator] = {
    Operator.EQUALS: Operator.EQUALS_BASELINE,
    Operator.NOT_EQUALS: Operator.NOT_EQUALS_BASELINE,
    Operator.SUPERSET_OF: Operator.SUPERSET_OF_BASELINE,
}


class OperatorTargetMismatch(Exception):
    """Raised when the (kind, target, operator) triple is incompatible.

    Carries a rendered message; the compiler wraps it as a
    ``CompileError`` with the constraint path so authoring tools surface
    a precise location.
    """


def check_operator_target_compatibility(
    *,
    kind: ConstraintKind,
    target: str,
    operator: Operator,
) -> None:
    """Validate the (kind, target, operator) triple.

    The target must already have passed path-domain validation (so its
    first segment is on the appropriate domain for the constraint kind,
    or on an open dimension). Repair-kind constraints are unconditionally
    SKIPPED by the evaluator in P1 and bypass this check.

    Raises ``OperatorTargetMismatch`` with a renderable message — including
    a "Did you mean: <op>?" hint when an obvious 1:1 swap exists — when
    the evaluator would emit ``E_OPERATOR_TARGET_MISMATCH`` for this
    constraint.
    """

    if kind is ConstraintKind.REPAIR:
        return
    if operator in _P1_UNSUPPORTED_OPERATORS:
        return

    first_segment = target.partition(".")[0]

    if kind is ConstraintKind.STATE:
        if operator in _BASELINE_OPERATORS:
            raise OperatorTargetMismatch(_state_with_baseline_message(target, operator))
        return

    # ConstraintKind.DELTA: branch depends on which domain the path resolves
    # against — the evaluator checks CodeStateDelta first, then CodeState.
    if first_segment in _CODE_STATE_DELTA_FIELDS:
        if operator in _BASELINE_OPERATORS:
            raise OperatorTargetMismatch(_delta_path_with_baseline_message(target, operator))
        return

    if first_segment in _CODE_STATE_FIELDS:
        if operator in _PURE_OPERATORS:
            raise OperatorTargetMismatch(_state_path_with_pure_message(target, operator))
        return


def _state_with_baseline_message(target: str, operator: Operator) -> str:
    base = (
        f"operator {operator.value!r} compares baseline to candidate and "
        f"requires a delta-kind constraint. It cannot be applied to a state-kind "
        f"constraint at target {target!r}."
    )
    hint = _BASELINE_TO_PURE_HINT.get(operator)
    if hint is not None:
        return (
            f"{base} Did you mean operator {hint.value!r} (state semantics) or "
            f"change kind to 'delta' to keep baseline-vs-candidate semantics?"
        )
    return f"{base} {_fallback_hint(_pure_operator_suggestions(operator))}"


def _delta_path_with_baseline_message(target: str, operator: Operator) -> str:
    base = (
        f"operator {operator.value!r} compares baseline to candidate and cannot "
        f"be applied to delta target {target!r}, which is itself a single "
        f"computed value rather than a paired state."
    )
    hint = _BASELINE_TO_PURE_HINT.get(operator)
    if hint is not None:
        return (
            f"{base} Did you mean operator {hint.value!r} on the same delta "
            f"path, or retarget at a CodeState path to keep baseline semantics?"
        )
    return f"{base} {_fallback_hint(_pure_operator_suggestions(operator))}"


def _state_path_with_pure_message(target: str, operator: Operator) -> str:
    base = (
        f"operator {operator.value!r} is a pure operator and reads a single value, "
        f"but target {target!r} is a CodeState path on a delta-kind constraint, "
        f"which requires comparing baseline against candidate."
    )
    hint = _PURE_TO_BASELINE_HINT.get(operator)
    if hint is not None:
        return (
            f"{base} Did you mean operator {hint.value!r}, or retarget at a "
            f"CodeStateDelta path (e.g. one of api_surface_delta / effect_changes / "
            f"imports_delta / complexity_delta / test_surface_delta) to keep pure "
            f"semantics?"
        )
    return f"{base} {_fallback_hint(_baseline_operator_suggestions(operator))}"


def _pure_operator_suggestions(operator: Operator) -> tuple[str, ...]:
    return tuple(
        get_close_matches(
            operator.value,
            [op.value for op in _PURE_OPERATORS],
            n=3,
            cutoff=0.4,
        )
    )


def _baseline_operator_suggestions(operator: Operator) -> tuple[str, ...]:
    return tuple(
        get_close_matches(
            operator.value,
            [op.value for op in _BASELINE_OPERATORS],
            n=3,
            cutoff=0.4,
        )
    )


def _fallback_hint(suggestions: tuple[str, ...]) -> str:
    if not suggestions:
        return "Pick a compatible operator from the constraint's allowed set."
    return f"Did you mean one of: {', '.join(suggestions)}?"
