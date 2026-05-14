"""Compile-time (kind, operator-class, path-domain) compatibility tests.

Brief D1-2 pushes ``E_OPERATOR_TARGET_MISMATCH`` from the evaluator
(runtime ``UNKNOWN``) to the compiler (``CompileError``). These tests
exercise both the unit-level ``check_operator_target_compatibility``
contract and the integration through ``compile_target_svp``.
"""

from __future__ import annotations

import pytest

from semantic_ci_code.compiler import CompileError, compile_target_svp, operator_schema
from semantic_ci_code.compiler.operator_schema import (
    OperatorTargetMismatch,
    check_operator_target_compatibility,
)
from semantic_ci_code.evaluator.operators import BASELINE_OPERATORS, PURE_OPERATORS
from semantic_ci_code.framework.constraint_types import ConstraintKind, Operator

# --- sync invariant ---------------------------------------------------------


def test_operator_schema_matches_evaluator_operators():
    # ``compiler.operator_schema`` duplicates ``BASELINE_OPERATORS`` and
    # ``PURE_OPERATORS`` to avoid a circular import. The two sets MUST stay
    # in lock-step; this test fails loudly if the evaluator-side set is
    # widened or narrowed without updating the compiler-side copy.
    assert operator_schema._BASELINE_OPERATORS == BASELINE_OPERATORS
    assert operator_schema._PURE_OPERATORS == PURE_OPERATORS


# --- unit contract -----------------------------------------------------------


def test_state_kind_with_baseline_operator_raises():
    with pytest.raises(OperatorTargetMismatch) as exc_info:
        check_operator_target_compatibility(
            kind=ConstraintKind.STATE,
            target="api_surface",
            operator=Operator.EQUALS_BASELINE,
        )

    message = str(exc_info.value)
    assert "equals_baseline" in message
    assert "state-kind" in message
    # 1:1 swap hint maps equals_baseline → equals.
    assert "'equals'" in message


def test_state_kind_with_changed_operator_suggests_not_equals():
    # Asymmetry guard: BASELINE_TO_PURE_HINT must contain both UNCHANGED
    # and CHANGED so the two baseline boolean operators get parallel
    # "Did you mean" hints.
    with pytest.raises(OperatorTargetMismatch) as exc_info:
        check_operator_target_compatibility(
            kind=ConstraintKind.STATE,
            target="api_surface",
            operator=Operator.CHANGED,
        )

    message = str(exc_info.value)
    assert "'changed'" in message
    assert "'not_equals'" in message


def test_delta_kind_with_baseline_operator_on_delta_path_raises():
    with pytest.raises(OperatorTargetMismatch) as exc_info:
        check_operator_target_compatibility(
            kind=ConstraintKind.DELTA,
            target="api_surface_delta.added",
            operator=Operator.EQUALS_BASELINE,
        )

    message = str(exc_info.value)
    assert "equals_baseline" in message
    assert "api_surface_delta.added" in message
    assert "'equals'" in message


def test_delta_kind_with_pure_operator_on_state_path_raises():
    with pytest.raises(OperatorTargetMismatch) as exc_info:
        check_operator_target_compatibility(
            kind=ConstraintKind.DELTA,
            target="api_surface_public",
            operator=Operator.EQUALS,
        )

    message = str(exc_info.value)
    assert "'equals'" in message
    assert "api_surface_public" in message
    assert "'equals_baseline'" in message


def test_state_kind_with_pure_operator_passes():
    check_operator_target_compatibility(
        kind=ConstraintKind.STATE,
        target="api_surface",
        operator=Operator.EQUALS,
    )


def test_delta_kind_with_baseline_on_state_path_passes():
    check_operator_target_compatibility(
        kind=ConstraintKind.DELTA,
        target="api_surface_public",
        operator=Operator.SUPERSET_OF_BASELINE,
    )


def test_delta_kind_with_pure_on_delta_path_passes():
    check_operator_target_compatibility(
        kind=ConstraintKind.DELTA,
        target="api_surface_delta.added",
        operator=Operator.INCLUDES_ALL,
    )


def test_open_path_state_kind_with_baseline_still_rejected():
    # ``python_specific`` is in both CodeState and CodeStateDelta, so under a
    # state-kind constraint the evaluator routes through the state branch and
    # rejects baseline operators. The compile check mirrors that.
    with pytest.raises(OperatorTargetMismatch):
        check_operator_target_compatibility(
            kind=ConstraintKind.STATE,
            target="python_specific.value",
            operator=Operator.UNCHANGED,
        )


def test_open_path_delta_kind_routes_to_delta_branch():
    # ``python_specific`` is a CodeStateDelta field, so the evaluator's
    # delta-branch (PURE required) governs the operator class. Baseline
    # operators must be rejected at compile time.
    with pytest.raises(OperatorTargetMismatch):
        check_operator_target_compatibility(
            kind=ConstraintKind.DELTA,
            target="python_specific.value",
            operator=Operator.SUPERSET_OF_BASELINE,
        )

    # Pure operator on the same open delta path is accepted.
    check_operator_target_compatibility(
        kind=ConstraintKind.DELTA,
        target="python_specific.value",
        operator=Operator.EQUALS,
    )


def test_changed_only_in_bypasses_check():
    # Operator is SKIPPED unconditionally at evaluate time; compile should
    # let any kind/target combination through without raising.
    check_operator_target_compatibility(
        kind=ConstraintKind.STATE,
        target="api_surface",
        operator=Operator.CHANGED_ONLY_IN,
    )
    check_operator_target_compatibility(
        kind=ConstraintKind.DELTA,
        target="api_surface_delta.added",
        operator=Operator.CHANGED_ONLY_IN,
    )


def test_repair_kind_bypasses_check():
    # Repair-kind constraints are unconditionally SKIPPED in P1
    # (E_REPAIR_KIND_UNSUPPORTED_P1); target/operator validation is deferred.
    check_operator_target_compatibility(
        kind=ConstraintKind.REPAIR,
        target="repair",
        operator=Operator.EQUALS_BASELINE,
    )


# --- integration through compile_target_svp ---------------------------------


def test_compile_state_kind_with_baseline_operator_raises_compile_error():
    yaml_source = """
intent: state-kind constraint with a baseline operator
change:
  primary_kind: feature
constraints:
  - id: state_with_baseline_op
    kind: state
    target: api_surface
    operator: equals_baseline
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].operator"
    assert "equals_baseline" in exc_info.value.message
    assert "'equals'" in exc_info.value.message


def test_compile_delta_kind_with_baseline_op_on_delta_path_raises_compile_error():
    yaml_source = """
intent: delta path with a baseline operator
change:
  primary_kind: feature
constraints:
  - id: delta_path_baseline
    kind: delta
    target: api_surface_delta.added
    operator: equals_baseline
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].operator"
    assert "equals_baseline" in exc_info.value.message
    assert "api_surface_delta.added" in exc_info.value.message


def test_compile_delta_kind_with_pure_op_on_state_path_raises_compile_error():
    yaml_source = """
intent: state path with a pure operator under delta kind
change:
  primary_kind: feature
constraints:
  - id: state_path_pure
    kind: delta
    target: api_surface_public
    operator: equals
    expected: []
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].operator"
    assert "'equals'" in exc_info.value.message
    assert "'equals_baseline'" in exc_info.value.message


def test_compile_changed_only_in_compiles_without_operator_check():
    yaml_source = """
intent: changed_only_in is SKIPPED unconditionally at evaluate
change:
  primary_kind: feature
constraints:
  - id: skipped_op
    kind: state
    target: api_surface
    operator: changed_only_in
"""

    compiled = compile_target_svp(yaml_source, filename="target.yaml")
    user_constraints = [c for c in compiled.constraints if c.source.value == "user"]
    assert len(user_constraints) == 1
    assert user_constraints[0].operator is Operator.CHANGED_ONLY_IN


def test_compile_design_feature_fixture_still_compiles():
    # Sanity check: the documented design.md §4.5 feature fixture mixes
    # delta-kind constraints with state-path baseline ops, delta-path pure
    # ops, scalar numeric ops, and bare-string desugar paths. After D1-2 it
    # must still compile without raising.
    from pathlib import Path

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "compiler" / "design_feature.yaml"
    compile_target_svp(fixture.read_text(), filename=str(fixture))
