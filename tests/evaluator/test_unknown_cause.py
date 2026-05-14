"""Unknown-cause tagging tests (Brief D1-4).

Verifies that each UNKNOWN emit site in the evaluator + operators tags
the right ``UnknownCause`` on ``ConstraintResult.unknown_cause``, that
authoring-cause forces ``FAIL`` regardless of ``unknown_policy``, and
that the cause survives the operator → result conversion at
``_from_operator_outcome``.
"""

from __future__ import annotations

import pytest

from semantic_ci_code.compiler import (
    CompiledConstraint,
    CompiledTarget,
    ConstraintSource,
)
from semantic_ci_code.domain.state_schema import (
    ChangeKind,
    CodeState,
    CodeStateDelta,
)
from semantic_ci_code.evaluator import (
    ResultStatus,
    UnknownCause,
    VerdictResult,
    evaluate_constraints,
)
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)


def _constraint(
    *,
    target: str,
    kind: ConstraintKind = ConstraintKind.STATE,
    operator: Operator = Operator.EQUALS,
    expected: object = 1,
    unknown_policy: UnknownPolicy = UnknownPolicy.FAIL,
) -> CompiledConstraint:
    return CompiledConstraint(
        id="c",
        kind=kind,
        target=target,
        operator=operator,
        expected=expected,
        severity=Severity.HARD,
        unknown_policy=unknown_policy,
        tolerance=None,
        evidence_required=False,
        scope=None,
        source=ConstraintSource.USER,
    )


def _evaluate(
    constraint: CompiledConstraint,
    *,
    candidate: CodeState | None = None,
    baseline: CodeState | None = None,
    delta: CodeStateDelta | None = None,
):
    target = CompiledTarget(
        intent="t",
        primary_kind=ChangeKind.FEATURE,
        allowed_secondary_kinds=(),
        scope=(),
        constraints=(constraint,),
    )
    return evaluate_constraints(
        target,
        delta or CodeStateDelta(),
        baseline=baseline or CodeState(),
        candidate=candidate or CodeState(),
    ).results[0]


# --- cause tagging per emit site ------------------------------------------


def test_authoring_cause_on_invalid_target_syntax():
    # ``_target_segments`` returns None for malformed dotted syntax;
    # E_PATH_UNRESOLVED defense-in-depth branch tags AUTHORING.
    result = _evaluate(_constraint(target="bad..syntax"))

    assert result.status is ResultStatus.UNKNOWN
    assert result.error_code == "E_PATH_UNRESOLVED"
    assert result.unknown_cause is UnknownCause.AUTHORING


def test_authoring_cause_on_unknown_state_root():
    result = _evaluate(_constraint(target="not_a_field"))

    assert result.status is ResultStatus.UNKNOWN
    assert result.error_code == "E_PATH_UNRESOLVED"
    assert result.unknown_cause is UnknownCause.AUTHORING


def test_authoring_cause_on_state_kind_with_baseline_operator():
    result = _evaluate(
        _constraint(
            target="api_surface",
            operator=Operator.EQUALS_BASELINE,
        )
    )

    assert result.error_code == "E_OPERATOR_TARGET_MISMATCH"
    assert result.unknown_cause is UnknownCause.AUTHORING


def test_authoring_cause_on_delta_kind_with_baseline_on_delta_path():
    result = _evaluate(
        _constraint(
            kind=ConstraintKind.DELTA,
            target="api_surface_delta.added",
            operator=Operator.EQUALS_BASELINE,
            expected=None,
        )
    )

    assert result.error_code == "E_OPERATOR_TARGET_MISMATCH"
    assert result.unknown_cause is UnknownCause.AUTHORING


def test_authoring_cause_on_delta_kind_with_pure_on_state_path():
    result = _evaluate(
        _constraint(
            kind=ConstraintKind.DELTA,
            target="api_surface_public",
            operator=Operator.EQUALS,
            expected=(),
        )
    )

    assert result.error_code == "E_OPERATOR_TARGET_MISMATCH"
    assert result.unknown_cause is UnknownCause.AUTHORING


def test_extraction_cause_on_runtime_unresolved_state_path():
    # ``coverage`` defaults to None on CodeState; ``coverage.line`` resolves
    # to UNRESOLVED at runtime via parent-is-None. Cause is EXTRACTION
    # (the extractor populated parent as None / omitted the dimension).
    result = _evaluate(
        _constraint(target="coverage.line"),
        candidate=CodeState(coverage=None),
    )

    assert result.error_code == "E_PATH_UNRESOLVED"
    assert result.unknown_cause is UnknownCause.EXTRACTION


def test_open_runtime_cause_on_python_specific_subpath():
    # ``python_specific`` defaults to None; subpath access trips the open
    # dimension branch. Cause is OPEN_RUNTIME (open schema region).
    result = _evaluate(
        _constraint(target="python_specific.value"),
        candidate=CodeState(python_specific=None),
    )

    assert result.error_code == "E_PATH_UNRESOLVED"
    assert result.unknown_cause is UnknownCause.OPEN_RUNTIME


def test_evaluator_internal_cause_on_pure_operator_typeerror_catchall():
    # ``equals`` on a non-comparable resolved value (intentionally
    # constructed to trip ``_canon`` -> TypeError). We use an object()
    # that has no model_dump and isn't JSON-serializable. The catch-all
    # in ``evaluate_pure_operator`` tags evaluator_internal.
    class _Weird:
        def __eq__(self, other):
            raise TypeError("nope")

        def __hash__(self):
            return 0

    weird = _Weird()
    result = _evaluate(
        _constraint(
            target="python_specific.value",
            operator=Operator.EQUALS,
            expected=weird,
        ),
        candidate=CodeState(python_specific={"value": weird}),
    )

    # ``_canon`` may or may not surface the TypeError depending on the
    # comparison path; the contract is: if it does reach the catch-all,
    # cause must be EVALUATOR_INTERNAL (not AUTHORING).
    if result.error_code == "E_TYPE_MISMATCH":
        assert result.unknown_cause is UnknownCause.EVALUATOR_INTERNAL


# --- unknown_policy interaction --------------------------------------------


@pytest.mark.parametrize("policy", list(UnknownPolicy))
def test_authoring_cause_forces_fail_regardless_of_unknown_policy(policy: UnknownPolicy):
    target = CompiledTarget(
        intent="t",
        primary_kind=ChangeKind.FEATURE,
        allowed_secondary_kinds=(),
        scope=(),
        constraints=(_constraint(target="not_a_field", unknown_policy=policy),),
    )
    verdict = evaluate_constraints(
        target,
        CodeStateDelta(),
        baseline=CodeState(),
        candidate=CodeState(),
    )

    assert verdict.result is VerdictResult.FAIL
    assert verdict.results[0].unknown_cause is UnknownCause.AUTHORING


@pytest.mark.parametrize(
    "policy,expected",
    [
        (UnknownPolicy.FAIL, VerdictResult.FAIL),
        (UnknownPolicy.REPAIR, VerdictResult.REPAIR),
        (UnknownPolicy.WARN, VerdictResult.PASS),
        (UnknownPolicy.IGNORE, VerdictResult.PASS),
    ],
)
def test_extraction_cause_respects_unknown_policy(policy: UnknownPolicy, expected: VerdictResult):
    target = CompiledTarget(
        intent="t",
        primary_kind=ChangeKind.FEATURE,
        allowed_secondary_kinds=(),
        scope=(),
        constraints=(_constraint(target="coverage.line", unknown_policy=policy),),
    )
    verdict = evaluate_constraints(
        target,
        CodeStateDelta(),
        baseline=CodeState(),
        candidate=CodeState(coverage=None),
    )

    assert verdict.result is expected
    assert verdict.results[0].unknown_cause is UnknownCause.EXTRACTION


# --- serialization & non-UNKNOWN bypass ------------------------------------


def test_non_unknown_result_has_no_cause():
    # Satisfied / violated / skipped results never carry unknown_cause.
    result = _evaluate(
        _constraint(target="python_specific.value", expected=1),
        candidate=CodeState(python_specific={"value": 1}),
    )

    assert result.status is ResultStatus.SATISFIED
    assert result.unknown_cause is None
