from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.compiler import (
    CompiledConstraint,
    CompiledTarget,
    ConstraintSource,
    compile_target_svp,
)
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.domain.state_schema import (
    APISurfaceEntry,
    ChangeKind,
    CodeState,
    CodeStateDelta,
    ComplexityDelta,
    EffectChanges,
    EffectClass,
    EffectEntry,
    SymbolDelta,
)
from semantic_ci_code.evaluator import (
    ConstraintResult,
    ResultStatus,
    Verdict,
    VerdictResult,
    evaluate_constraints,
)
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.pipeline import extract_python_code_state

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "evaluator"


def constraint(
    *,
    id: str = "c",
    kind: ConstraintKind = ConstraintKind.STATE,
    target: str = "python_specific.value",
    operator: Operator = Operator.EQUALS,
    expected: object = None,
    severity: Severity = Severity.HARD,
    unknown_policy: UnknownPolicy = UnknownPolicy.FAIL,
    tolerance: float | None = None,
    evidence_required: bool = False,
    source: ConstraintSource = ConstraintSource.USER,
) -> CompiledConstraint:
    return CompiledConstraint(
        id=id,
        kind=kind,
        target=target,
        operator=operator,
        expected=expected,
        severity=severity,
        unknown_policy=unknown_policy,
        tolerance=tolerance,
        evidence_required=evidence_required,
        scope=None,
        source=source,
    )


def compiled_target(*constraints: CompiledConstraint) -> CompiledTarget:
    return CompiledTarget(
        intent="test",
        primary_kind=ChangeKind.FEATURE,
        allowed_secondary_kinds=(),
        scope=(),
        constraints=constraints,
    )


def api(name: str, *, signature: str | None = "def f():\n    ...") -> APISurfaceEntry:
    return APISurfaceEntry(fqn=name, kind="function", signature=signature, visibility="public")


def evaluate_one(
    item: CompiledConstraint,
    *,
    baseline: CodeState | None = None,
    candidate: CodeState | None = None,
    delta: CodeStateDelta | None = None,
) -> ConstraintResult:
    verdict = evaluate_constraints(
        compiled_target(item),
        delta or CodeStateDelta(),
        baseline=baseline or CodeState(),
        candidate=candidate or CodeState(),
    )
    assert len(verdict.results) == 1
    return verdict.results[0]


def evaluate_verdict(
    *constraints: CompiledConstraint,
    baseline: CodeState | None = None,
    candidate: CodeState | None = None,
    delta: CodeStateDelta | None = None,
) -> Verdict:
    return evaluate_constraints(
        compiled_target(*constraints),
        delta or CodeStateDelta(),
        baseline=baseline or CodeState(),
        candidate=candidate or CodeState(),
    )


def state_value_constraint(
    *,
    id: str = "c",
    operator: Operator = Operator.EQUALS,
    expected: object = 1,
    severity: Severity = Severity.HARD,
    unknown_policy: UnknownPolicy = UnknownPolicy.FAIL,
    tolerance: float | None = None,
) -> CompiledConstraint:
    return constraint(
        id=id,
        target="python_specific.value",
        operator=operator,
        expected=expected,
        severity=severity,
        unknown_policy=unknown_policy,
        tolerance=tolerance,
    )


def delta_value_constraint(
    *,
    id: str = "c",
    target: str = "complexity_delta.cyclomatic",
    operator: Operator = Operator.EQUALS,
    expected: object = 1,
    severity: Severity = Severity.HARD,
    unknown_policy: UnknownPolicy = UnknownPolicy.FAIL,
    tolerance: float | None = None,
) -> CompiledConstraint:
    return constraint(
        id=id,
        kind=ConstraintKind.DELTA,
        target=target,
        operator=operator,
        expected=expected,
        severity=severity,
        unknown_policy=unknown_policy,
        tolerance=tolerance,
    )


def delta_collection_constraint(
    *,
    operator: Operator,
    expected: object,
    target: str = "api_surface_delta.added",
) -> CompiledConstraint:
    return delta_value_constraint(target=target, operator=operator, expected=expected)


def baseline_constraint(
    *,
    operator: Operator,
    target: str = "api_surface",
) -> CompiledConstraint:
    return constraint(
        kind=ConstraintKind.DELTA,
        target=target,
        operator=operator,
    )


def test_equals_satisfied():
    result = evaluate_one(
        state_value_constraint(expected=1),
        candidate=CodeState(python_specific={"value": 1}),
    )

    assert result.status is ResultStatus.SATISFIED
    assert result.error_code is None


def test_equals_violated_hard_fails_verdict():
    verdict = evaluate_verdict(
        state_value_constraint(expected=2),
        candidate=CodeState(python_specific={"value": 1}),
    )

    assert verdict.result is VerdictResult.FAIL
    assert verdict.violations[0].error_code == "E_VIOLATION"


def test_equals_violated_soft_repairs_verdict():
    verdict = evaluate_verdict(
        state_value_constraint(expected=2, severity=Severity.SOFT),
        candidate=CodeState(python_specific={"value": 1}),
    )

    assert verdict.result is VerdictResult.REPAIR


def test_equals_violated_info_does_not_affect_verdict():
    verdict = evaluate_verdict(
        state_value_constraint(expected=2, severity=Severity.INFO),
        candidate=CodeState(python_specific={"value": 1}),
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.violations[0].severity is Severity.INFO


@pytest.mark.parametrize(
    ("operator", "constraint_item", "baseline", "candidate", "delta"),
    [
        (
            Operator.EQUALS,
            delta_value_constraint(operator=Operator.EQUALS, expected=1),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            Operator.NOT_EQUALS,
            delta_value_constraint(operator=Operator.NOT_EQUALS, expected=2),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            Operator.EQUALS_BASELINE,
            baseline_constraint(operator=Operator.EQUALS_BASELINE),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeStateDelta(),
        ),
        (
            Operator.NOT_EQUALS_BASELINE,
            baseline_constraint(operator=Operator.NOT_EQUALS_BASELINE),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.b"),)),
            CodeStateDelta(),
        ),
        (
            Operator.INCLUDES_ALL,
            delta_collection_constraint(operator=Operator.INCLUDES_ALL, expected=("a",)),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            Operator.INCLUDES_ANY,
            delta_collection_constraint(operator=Operator.INCLUDES_ANY, expected=("z", "b")),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            Operator.EXCLUDES_ALL,
            delta_collection_constraint(operator=Operator.EXCLUDES_ALL, expected=("z",)),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            Operator.SUBSET_OF,
            delta_collection_constraint(operator=Operator.SUBSET_OF, expected=("a", "b", "c")),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            Operator.SUPERSET_OF,
            delta_collection_constraint(operator=Operator.SUPERSET_OF, expected=("a",)),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            Operator.SUPERSET_OF_BASELINE,
            baseline_constraint(operator=Operator.SUPERSET_OF_BASELINE),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.a"), api("pkg.b"))),
            CodeStateDelta(),
        ),
        (
            Operator.NO_NEW_ITEMS,
            baseline_constraint(operator=Operator.NO_NEW_ITEMS),
            CodeState(api_surface=(api("pkg.a"), api("pkg.b"))),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeStateDelta(),
        ),
        (
            Operator.NO_REMOVED_ITEMS,
            baseline_constraint(operator=Operator.NO_REMOVED_ITEMS),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.a"), api("pkg.b"))),
            CodeStateDelta(),
        ),
        (
            Operator.LESS_THAN,
            delta_value_constraint(operator=Operator.LESS_THAN, expected=2),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            Operator.LESS_THAN_OR_EQUAL,
            delta_value_constraint(operator=Operator.LESS_THAN_OR_EQUAL, expected=1),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            Operator.GREATER_THAN,
            delta_value_constraint(operator=Operator.GREATER_THAN, expected=0),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            Operator.GREATER_THAN_OR_EQUAL,
            delta_value_constraint(operator=Operator.GREATER_THAN_OR_EQUAL, expected=1),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            Operator.WITHIN_RANGE,
            delta_value_constraint(operator=Operator.WITHIN_RANGE, expected=(0, 2)),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            Operator.UNCHANGED,
            baseline_constraint(operator=Operator.UNCHANGED),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeStateDelta(),
        ),
        (
            Operator.CHANGED,
            baseline_constraint(operator=Operator.CHANGED),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.b"),)),
            CodeStateDelta(),
        ),
        (
            Operator.CHANGED_ONLY_IN,
            baseline_constraint(operator=Operator.CHANGED_ONLY_IN),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.b"),)),
            CodeStateDelta(),
        ),
    ],
)
def test_all_operator_satisfied_or_skipped_cases(
    operator: Operator,
    constraint_item: CompiledConstraint,
    baseline: CodeState,
    candidate: CodeState,
    delta: CodeStateDelta,
):
    result = evaluate_one(
        constraint_item,
        baseline=baseline,
        candidate=candidate,
        delta=delta,
    )

    if operator is Operator.CHANGED_ONLY_IN:
        assert result.status is ResultStatus.SKIPPED
        assert result.error_code == "E_OPERATOR_UNSUPPORTED_P1"
    else:
        assert result.status is ResultStatus.SATISFIED


@pytest.mark.parametrize(
    ("constraint_item", "baseline", "candidate", "delta"),
    [
        (
            delta_value_constraint(operator=Operator.EQUALS, expected=2),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            delta_value_constraint(operator=Operator.NOT_EQUALS, expected=1),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            baseline_constraint(operator=Operator.EQUALS_BASELINE),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.b"),)),
            CodeStateDelta(),
        ),
        (
            baseline_constraint(operator=Operator.NOT_EQUALS_BASELINE),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeStateDelta(),
        ),
        (
            delta_collection_constraint(operator=Operator.INCLUDES_ALL, expected=("z",)),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            delta_collection_constraint(operator=Operator.INCLUDES_ANY, expected=("z",)),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            delta_collection_constraint(operator=Operator.EXCLUDES_ALL, expected=("a",)),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            delta_collection_constraint(operator=Operator.SUBSET_OF, expected=("a",)),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            delta_collection_constraint(operator=Operator.SUPERSET_OF, expected=("z",)),
            CodeState(),
            CodeState(),
            CodeStateDelta(api_surface_delta=SymbolDelta(added=("a", "b"))),
        ),
        (
            baseline_constraint(operator=Operator.SUPERSET_OF_BASELINE),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=()),
            CodeStateDelta(),
        ),
        (
            baseline_constraint(operator=Operator.NO_NEW_ITEMS),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.a"), api("pkg.b"))),
            CodeStateDelta(),
        ),
        (
            baseline_constraint(operator=Operator.NO_REMOVED_ITEMS),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=()),
            CodeStateDelta(),
        ),
        (
            delta_value_constraint(operator=Operator.LESS_THAN, expected=1),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            delta_value_constraint(operator=Operator.LESS_THAN_OR_EQUAL, expected=0),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            delta_value_constraint(operator=Operator.GREATER_THAN, expected=1),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            delta_value_constraint(operator=Operator.GREATER_THAN_OR_EQUAL, expected=2),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            delta_value_constraint(operator=Operator.WITHIN_RANGE, expected=(2, 3)),
            CodeState(),
            CodeState(),
            CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
        ),
        (
            baseline_constraint(operator=Operator.UNCHANGED),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.b"),)),
            CodeStateDelta(),
        ),
        (
            baseline_constraint(operator=Operator.CHANGED),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeState(api_surface=(api("pkg.a"),)),
            CodeStateDelta(),
        ),
    ],
)
def test_operator_violated_cases(
    constraint_item: CompiledConstraint,
    baseline: CodeState,
    candidate: CodeState,
    delta: CodeStateDelta,
):
    result = evaluate_one(
        constraint_item,
        baseline=baseline,
        candidate=candidate,
        delta=delta,
    )

    assert result.status is ResultStatus.VIOLATED
    assert result.error_code == "E_VIOLATION"


@pytest.mark.parametrize(
    "operator",
    tuple(op for op in Operator if op is not Operator.CHANGED_ONLY_IN),
)
def test_each_operator_can_report_unknown_path_unresolved(operator: Operator):
    item = constraint(kind=ConstraintKind.STATE, target="missing_field", operator=operator)

    result = evaluate_one(item)

    assert result.status is ResultStatus.UNKNOWN
    assert result.error_code == "E_PATH_UNRESOLVED"


def test_unchanged_and_changed_are_baseline_aliases():
    unchanged = evaluate_one(
        baseline_constraint(operator=Operator.UNCHANGED),
        baseline=CodeState(api_surface=(api("pkg.a"),)),
        candidate=CodeState(api_surface=(api("pkg.a"),)),
    )
    changed = evaluate_one(
        baseline_constraint(operator=Operator.CHANGED),
        baseline=CodeState(api_surface=(api("pkg.a"),)),
        candidate=CodeState(api_surface=(api("pkg.b"),)),
    )

    assert unchanged.status is ResultStatus.SATISFIED
    assert changed.status is ResultStatus.SATISFIED


def test_state_path_resolves_from_candidate():
    result = evaluate_one(
        constraint(kind=ConstraintKind.STATE, target="api_surface", operator=Operator.EQUALS),
        candidate=CodeState(api_surface=(api("pkg.a"),)),
    )

    assert result.status is ResultStatus.VIOLATED
    assert any(key == "observed" for key, _value in result.evidence)


def test_delta_path_resolves_from_delta():
    result = evaluate_one(
        delta_value_constraint(
            target="api_surface_delta.added",
            operator=Operator.EQUALS,
            expected=("x",),
        ),
        delta=CodeStateDelta(api_surface_delta=SymbolDelta(added=("x",))),
    )

    assert result.status is ResultStatus.SATISFIED


def test_delta_python_specific_dotted_json_access_resolves_from_delta():
    item = delta_value_constraint(
        target="python_specific.module_graph_delta.added_edges",
        operator=Operator.EQUALS,
        expected=(("alpha", "gamma"),),
    )
    delta = CodeStateDelta(
        python_specific={"module_graph_delta": {"added_edges": [["alpha", "gamma"]]}}
    )

    result = evaluate_one(item, delta=delta)

    assert result.status is ResultStatus.SATISFIED


def test_delta_codestate_field_with_baseline_operator_resolves_baseline_and_candidate():
    result = evaluate_one(
        baseline_constraint(operator=Operator.EQUALS_BASELINE, target="api_surface"),
        baseline=CodeState(api_surface=(api("pkg.a"),)),
        candidate=CodeState(api_surface=(api("pkg.a"),)),
    )

    assert result.status is ResultStatus.SATISFIED


def test_missing_field_returns_unknown_path_unresolved():
    result = evaluate_one(
        constraint(kind=ConstraintKind.STATE, target="not_a_field", operator=Operator.EQUALS)
    )

    assert result.status is ResultStatus.UNKNOWN
    assert result.error_code == "E_PATH_UNRESOLVED"


def test_python_specific_none_dotted_access_returns_unknown_path_unresolved():
    result = evaluate_one(
        constraint(
            kind=ConstraintKind.STATE,
            target="python_specific.module_graph_delta",
            operator=Operator.EQUALS,
        ),
        candidate=CodeState(python_specific=None),
    )

    assert result.status is ResultStatus.UNKNOWN
    assert result.error_code == "E_PATH_UNRESOLVED"


def test_baseline_operator_on_delta_field_returns_operator_target_mismatch():
    result = evaluate_one(
        delta_value_constraint(
            target="api_surface_delta.added",
            operator=Operator.EQUALS_BASELINE,
        )
    )

    assert result.status is ResultStatus.UNKNOWN
    assert result.error_code == "E_OPERATOR_TARGET_MISMATCH"


def test_no_violations_or_unknowns_passes():
    verdict = evaluate_verdict(
        state_value_constraint(expected=1),
        candidate=CodeState(python_specific={"value": 1}),
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.unknowns == ()
    assert verdict.skipped == ()


def test_hard_and_soft_violations_aggregate_to_fail():
    verdict = evaluate_verdict(
        state_value_constraint(id="hard", expected=2),
        state_value_constraint(id="soft", expected=3, severity=Severity.SOFT),
        candidate=CodeState(python_specific={"value": 1}),
    )

    assert verdict.result is VerdictResult.FAIL


def test_soft_violation_only_aggregates_to_repair():
    verdict = evaluate_verdict(
        state_value_constraint(expected=2, severity=Severity.SOFT),
        candidate=CodeState(python_specific={"value": 1}),
    )

    assert verdict.result is VerdictResult.REPAIR


def test_unknown_policy_fail_aggregates_to_fail():
    verdict = evaluate_verdict(
        constraint(
            kind=ConstraintKind.STATE,
            target="missing",
            operator=Operator.EQUALS,
            unknown_policy=UnknownPolicy.FAIL,
        )
    )

    assert verdict.result is VerdictResult.FAIL


def test_unknown_policy_repair_aggregates_to_repair():
    verdict = evaluate_verdict(
        constraint(
            kind=ConstraintKind.STATE,
            target="missing",
            operator=Operator.EQUALS,
            unknown_policy=UnknownPolicy.REPAIR,
        )
    )

    assert verdict.result is VerdictResult.REPAIR


@pytest.mark.parametrize("policy", (UnknownPolicy.WARN, UnknownPolicy.IGNORE))
def test_unknown_policy_warn_and_ignore_do_not_affect_verdict(policy: UnknownPolicy):
    verdict = evaluate_verdict(
        constraint(
            kind=ConstraintKind.STATE,
            target="missing",
            operator=Operator.EQUALS,
            unknown_policy=policy,
        )
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.unknowns[0].unknown_policy is policy


def test_skipped_only_passes():
    verdict = evaluate_verdict(
        constraint(kind=ConstraintKind.REPAIR, target="repair", operator=Operator.EQUALS)
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.skipped[0].error_code == "E_REPAIR_KIND_UNSUPPORTED_P1"


def test_less_than_or_equal_tolerance_satisfies_near_upper_bound():
    result = evaluate_one(
        delta_value_constraint(
            target="python_specific.value",
            operator=Operator.LESS_THAN_OR_EQUAL,
            expected=5,
            tolerance=0.5,
        ),
        delta=CodeStateDelta(python_specific={"value": 5.4}),
    )

    assert result.status is ResultStatus.SATISFIED


def test_less_than_or_equal_tolerance_violates_past_upper_bound():
    result = evaluate_one(
        delta_value_constraint(
            target="python_specific.value",
            operator=Operator.LESS_THAN_OR_EQUAL,
            expected=5,
            tolerance=0.5,
        ),
        delta=CodeStateDelta(python_specific={"value": 5.6}),
    )

    assert result.status is ResultStatus.VIOLATED


def test_tolerance_is_ignored_for_equals():
    result = evaluate_one(
        delta_value_constraint(operator=Operator.EQUALS, expected=5, tolerance=99),
        delta=CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=6)),
    )

    assert result.status is ResultStatus.VIOLATED


def test_numeric_operator_on_collection_returns_type_mismatch():
    result = evaluate_one(
        delta_value_constraint(
            target="api_surface_delta.added",
            operator=Operator.LESS_THAN_OR_EQUAL,
            expected=1,
        ),
        delta=CodeStateDelta(api_surface_delta=SymbolDelta(added=("a",))),
    )

    assert result.status is ResultStatus.UNKNOWN
    assert result.error_code == "E_TYPE_MISMATCH"


def test_collection_operator_on_scalar_returns_type_mismatch():
    result = evaluate_one(
        delta_value_constraint(operator=Operator.INCLUDES_ALL, expected=("a",)),
        delta=CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
    )

    assert result.status is ResultStatus.UNKNOWN
    assert result.error_code == "E_TYPE_MISMATCH"


def test_within_range_with_wrong_expected_shape_returns_type_mismatch():
    result = evaluate_one(
        delta_value_constraint(operator=Operator.WITHIN_RANGE, expected=(1,)),
        delta=CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=1)),
    )

    assert result.status is ResultStatus.UNKNOWN
    assert result.error_code == "E_TYPE_MISMATCH"


def test_refactor_template_passes_when_baseline_and_candidate_match():
    compiled = compile_target_svp("intent: refactor\nchange:\n  primary_kind: refactor\n")
    state = CodeState(api_surface=(api("pkg.a"),))
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(),
        baseline=state,
        candidate=state,
    )

    assert verdict.result is VerdictResult.PASS
    assert {result.status for result in verdict.results} == {ResultStatus.SATISFIED}


def test_refactor_template_fails_when_api_surface_changes():
    compiled = compile_target_svp("intent: refactor\nchange:\n  primary_kind: refactor\n")
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(),
        baseline=CodeState(api_surface=(api("pkg.a"),)),
        candidate=CodeState(api_surface=(api("pkg.a", signature="def f(x):\n    ..."),)),
    )

    assert verdict.result is VerdictResult.FAIL
    assert verdict.results[0].status is ResultStatus.VIOLATED


def test_refactor_template_ignores_private_api_surface_changes():
    compiled = compile_target_svp("intent: refactor\nchange:\n  primary_kind: refactor\n")
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(),
        baseline=CodeState(
            api_surface=(APISurfaceEntry(fqn="pkg._helper", kind="function", visibility="private"),)
        ),
        candidate=CodeState(
            api_surface=(
                APISurfaceEntry(
                    fqn="pkg._helper",
                    kind="function",
                    signature="def _helper(x):\n    ...",
                    visibility="private",
                ),
                APISurfaceEntry(fqn="pkg._new_helper", kind="function", visibility="private"),
            )
        ),
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[0].status is ResultStatus.SATISFIED


def test_feature_template_fails_on_removed_api():
    compiled = compile_target_svp("intent: feature\nchange:\n  primary_kind: feature\n")
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(
            api_surface_delta=SymbolDelta(removed=({"fqn": "pkg.removed", "visibility": "public"},))
        ),
        baseline=CodeState(),
        candidate=CodeState(),
    )

    assert verdict.result is VerdictResult.FAIL
    assert verdict.results[0].constraint_id == "template:feature:no_removed_api"


def test_feature_template_ignores_removed_private_api():
    compiled = compile_target_svp("intent: feature\nchange:\n  primary_kind: feature\n")
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(
            api_surface_delta=SymbolDelta(
                removed=({"fqn": "pkg._removed", "visibility": "private"},)
            )
        ),
        baseline=CodeState(),
        candidate=CodeState(),
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[0].status is ResultStatus.SATISFIED


def test_refactor_template_allows_declared_api_surface_changes():
    compiled = compile_target_svp(
        """
intent: refactor test helper plumbing
change:
  primary_kind: refactor
api_surface:
  allow_changes:
    - fqn: git_helpers.run_semantic_ci
    - fqn_prefix: helpers.
"""
    )
    baseline = CodeState(
        api_surface=(
            api("git_helpers.run_semantic_ci"),
            api("stable.public_api"),
        )
    )
    candidate = CodeState(
        api_surface=(
            api("helpers.run_semantic_ci"),
            api("helpers.payload"),
            api("stable.public_api"),
        )
    )

    verdict = evaluate_constraints(
        compiled,
        compute_code_state_delta(baseline, candidate),
        baseline=baseline,
        candidate=candidate,
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[0].constraint_id == "template:refactor:api_surface_unchanged"
    assert verdict.results[0].status is ResultStatus.SATISFIED


def test_feature_template_allows_declared_removed_api_surface():
    compiled = compile_target_svp(
        """
intent: move test helper internals
change:
  primary_kind: feature
api_surface:
  allow_changes:
    - fqn_prefix: test_helpers.
"""
    )
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(
            api_surface_delta=SymbolDelta(
                removed=({"fqn": "test_helpers.run_cli", "visibility": "public"},)
            )
        ),
        baseline=CodeState(),
        candidate=CodeState(),
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[0].constraint_id == "template:feature:no_removed_api"
    assert verdict.results[0].status is ResultStatus.SATISFIED


def test_api_surface_allow_changes_does_not_hide_user_constraints():
    compiled = compile_target_svp(
        """
intent: refactor test helper plumbing
change:
  primary_kind: refactor
api_surface:
  allow_changes:
    - fqn: git_helpers.run_semantic_ci
    - fqn_prefix: helpers.
constraints:
  - id: user_still_checks_api
    kind: delta
    target: api_surface_public
    operator: equals_baseline
"""
    )
    baseline = CodeState(api_surface=(api("git_helpers.run_semantic_ci"),))
    candidate = CodeState(api_surface=(api("helpers.run_semantic_ci"),))

    verdict = evaluate_constraints(
        compiled,
        compute_code_state_delta(baseline, candidate),
        baseline=baseline,
        candidate=candidate,
    )

    assert verdict.result is VerdictResult.FAIL
    assert verdict.results[-1].constraint_id == "user_still_checks_api"
    assert verdict.results[-1].status is ResultStatus.VIOLATED


def test_bugfix_template_fails_on_new_effect():
    compiled = compile_target_svp("intent: bugfix\nchange:\n  primary_kind: bugfix\n")
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(
            effect_changes=EffectChanges(
                added=({"fqn": "pkg.write", "effect_class": "fs"},),
            )
        ),
        baseline=CodeState(effects=()),
        candidate=CodeState(effects=(EffectEntry(fqn="pkg.write", effect_class=EffectClass.FS),)),
    )

    assert verdict.result is VerdictResult.FAIL
    assert verdict.results[1].constraint_id == "template:bugfix:no_new_effects"


def test_feature_template_allows_declared_new_effect():
    compiled = compile_target_svp(
        """
intent: add git-backed check command
change:
  primary_kind: feature
effects:
  allow_new:
    - fqn: subprocess.run
      effect_class: process
"""
    )
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(
            effect_changes=EffectChanges(
                added=({"fqn": "subprocess.run", "effect_class": "process"},),
            )
        ),
        baseline=CodeState(),
        candidate=CodeState(),
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[1].constraint_id == "template:feature:no_new_effects"
    assert verdict.results[1].status is ResultStatus.SATISFIED


def test_feature_template_allows_declared_new_effect_by_resolved_call():
    compiled = compile_target_svp(
        """
intent: add git-backed check command
change:
  primary_kind: feature
effects:
  allow_new:
    - fqn: subprocess.run
      effect_class: process
"""
    )
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(
            effect_changes=EffectChanges(
                added=(
                    {
                        "fqn": "build",
                        "effect_class": "process",
                        "evidence": {"resolved_call": "subprocess.run"},
                    },
                ),
            )
        ),
        baseline=CodeState(),
        candidate=CodeState(),
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[1].constraint_id == "template:feature:no_new_effects"
    assert verdict.results[1].status is ResultStatus.SATISFIED


def test_effect_allow_new_keeps_unallowed_effects_visible_to_template():
    compiled = compile_target_svp(
        """
intent: add git-backed check command
change:
  primary_kind: feature
effects:
  allow_new:
    - fqn: subprocess.run
      effect_class: process
"""
    )
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(
            effect_changes=EffectChanges(
                added=(
                    {"fqn": "subprocess.run", "effect_class": "process"},
                    {"fqn": "pathlib.Path.write_text", "effect_class": "fs"},
                ),
            )
        ),
        baseline=CodeState(),
        candidate=CodeState(),
    )

    result = verdict.results[1]
    observed = dict(result.evidence)["observed"]

    assert verdict.result is VerdictResult.FAIL
    assert result.status is ResultStatus.VIOLATED
    assert "pathlib.Path.write_text" in repr(observed)
    assert "subprocess.run" not in repr(observed)


def test_effect_allow_new_does_not_hide_effects_from_user_constraints():
    compiled = compile_target_svp(
        """
intent: add git-backed check command
change:
  primary_kind: feature
effects:
  allow_new:
    - fqn: subprocess.run
      effect_class: process
constraints:
  - id: user_can_still_see_process_effect
    kind: delta
    target: effect_changes.added
    operator: includes_any
    expected:
      - fqn: subprocess.run
        effect_class: process
"""
    )
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(
            effect_changes=EffectChanges(
                added=({"fqn": "subprocess.run", "effect_class": "process"},),
            )
        ),
        baseline=CodeState(),
        candidate=CodeState(),
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[-1].constraint_id == "user_can_still_see_process_effect"
    assert verdict.results[-1].status is ResultStatus.SATISFIED


def test_feature_no_new_effects_ignores_absolute_evidence_path_changes():
    compiled = compile_target_svp("intent: feature\nchange:\n  primary_kind: feature\n")
    baseline = CodeState(
        effects=(
            EffectEntry(
                fqn="print",
                effect_class=EffectClass.STDOUT,
                confidence=1.0,
                evidence={"file": "C:/tmp/baseline/pkg/mod.py", "line": 1},
            ),
        )
    )
    candidate = CodeState(
        effects=(
            EffectEntry(
                fqn="print",
                effect_class=EffectClass.STDOUT,
                confidence=1.0,
                evidence={"file": "C:/repo/candidate/pkg/mod.py", "line": 1},
            ),
        )
    )

    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(effect_changes=EffectChanges()),
        baseline=baseline,
        candidate=candidate,
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[1].constraint_id == "template:feature:no_new_effects"
    assert verdict.results[1].status is ResultStatus.SATISFIED


def test_refactor_effects_unchanged_uses_effect_changes_not_raw_evidence_paths():
    compiled = compile_target_svp("intent: refactor\nchange:\n  primary_kind: refactor\n")
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(effect_changes=EffectChanges()),
        baseline=CodeState(
            effects=(
                EffectEntry(
                    fqn="print",
                    effect_class=EffectClass.STDOUT,
                    evidence={"file": "C:/tmp/baseline/pkg/mod.py"},
                ),
            )
        ),
        candidate=CodeState(
            effects=(
                EffectEntry(
                    fqn="print",
                    effect_class=EffectClass.STDOUT,
                    evidence={"file": "C:/repo/candidate/pkg/mod.py"},
                ),
            )
        ),
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[2].constraint_id == "template:refactor:effects_unchanged"
    assert verdict.results[2].status is ResultStatus.SATISFIED


def test_dict_valued_expected_is_canonical_between_yaml_and_hand_built():
    yaml_compiled = compile_target_svp(
        """
intent: dict expected
change:
  primary_kind: feature
constraints:
  - id: dict_expected
    kind: state
    target: python_specific.payload
    operator: equals
    expected:
      names: [a, b]
"""
    )
    hand_built = compiled_target(
        constraint(
            id="dict_expected",
            kind=ConstraintKind.STATE,
            target="python_specific.payload",
            operator=Operator.EQUALS,
            expected={"names": ("a", "b")},
        )
    )
    candidate = CodeState(python_specific={"payload": {"names": ("a", "b")}})

    yaml_result = evaluate_constraints(
        yaml_compiled,
        CodeStateDelta(),
        baseline=CodeState(),
        candidate=candidate,
    ).results[-1]
    hand_result = evaluate_constraints(
        hand_built,
        CodeStateDelta(),
        baseline=CodeState(),
        candidate=candidate,
    ).results[0]

    assert yaml_result.status is ResultStatus.SATISFIED
    assert hand_result.status is ResultStatus.SATISFIED


def test_hand_built_engine_contract():
    baseline = CodeState(api_surface=(api("pkg.a"),))
    candidate = CodeState(api_surface=(api("pkg.a"), api("pkg.b")))
    delta = CodeStateDelta(api_surface_delta=SymbolDelta(added=({"fqn": "pkg.b"},)))
    compiled = compiled_target(
        baseline_constraint(operator=Operator.NO_REMOVED_ITEMS),
        delta_value_constraint(
            target="api_surface_delta.added",
            operator=Operator.INCLUDES_ANY,
            expected=({"fqn": "pkg.b"},),
            severity=Severity.SOFT,
        ),
    )

    verdict = evaluate_constraints(compiled, delta, baseline=baseline, candidate=candidate)

    assert verdict.result is VerdictResult.PASS
    assert len(verdict.results) == 2


def test_same_process_determinism_and_result_order():
    compiled = compiled_target(
        state_value_constraint(id="first", expected=1),
        state_value_constraint(id="second", expected=2, severity=Severity.SOFT),
    )
    candidate = CodeState(python_specific={"value": 1})

    first = evaluate_constraints(
        compiled,
        CodeStateDelta(),
        baseline=CodeState(),
        candidate=candidate,
    )
    second = evaluate_constraints(
        compiled,
        CodeStateDelta(),
        baseline=CodeState(),
        candidate=candidate,
    )

    assert first == second
    assert repr(first) == repr(second)
    assert tuple(result.constraint_id for result in first.results) == ("first", "second")
    assert hash(first)


def test_subprocess_determinism_across_hash_seeds():
    script = """
from semantic_ci_code.compiler import CompiledConstraint, CompiledTarget, ConstraintSource
from semantic_ci_code.domain.state_schema import CodeState, CodeStateDelta, ChangeKind
from semantic_ci_code.evaluator import evaluate_constraints
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)

constraint = CompiledConstraint(
    id="deterministic",
    kind=ConstraintKind.STATE,
    target="python_specific.value",
    operator=Operator.EQUALS,
    expected={"names": ("a", "b")},
    severity=Severity.HARD,
    unknown_policy=UnknownPolicy.FAIL,
    tolerance=None,
    evidence_required=False,
    scope=None,
    source=ConstraintSource.USER,
)
compiled = CompiledTarget(
    intent="deterministic",
    primary_kind=ChangeKind.FEATURE,
    allowed_secondary_kinds=(),
    scope=(),
    constraints=(constraint,),
)
candidate = CodeState(python_specific={"value": {"names": ["a", "b"]}})
verdict = evaluate_constraints(
    compiled,
    CodeStateDelta(),
    baseline=CodeState(),
    candidate=candidate,
)
print(repr(verdict))
"""

    first = _run_subprocess(script, hash_seed="1")
    second = _run_subprocess(script, hash_seed="2")

    assert first == second


def _run_subprocess(script: str, *, hash_seed: str) -> str:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return result.stdout


def test_pipeline_delta_compiler_evaluator_integration():
    baseline = extract_python_code_state(FIXTURES / "baseline_pkg")
    candidate = extract_python_code_state(FIXTURES / "candidate_pkg")
    delta = compute_code_state_delta(baseline, candidate)
    compiled = compile_target_svp((FIXTURES / "integration.yaml").read_text(encoding="utf-8"))

    verdict = evaluate_constraints(compiled, delta, baseline=baseline, candidate=candidate)

    assert verdict.result is VerdictResult.PASS
    assert tuple(result.constraint_id for result in verdict.results) == (
        "template:feature:no_removed_api",
        "template:feature:no_new_effects",
        "complexity_increased",
    )
