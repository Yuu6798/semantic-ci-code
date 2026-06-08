"""Compile-time (target-category, operator-category, expected-shape) tests.

Brief D1-3 pushes ``E_TYPE_MISMATCH`` from the evaluator (runtime
``UNKNOWN``) to the compiler (``CompileError``) for any combination where
the operator's required category does not match the static target type,
or where the expected literal does not satisfy the operator's required
shape.
"""

from __future__ import annotations

import pytest

from semantic_ci_code.compiler import CompileError, compile_target_svp
from semantic_ci_code.compiler.path_schema import valid_delta_target_paths
from semantic_ci_code.compiler.type_schema import (
    TargetCategory,
    TypeMismatch,
    TypeMismatchSide,
    category_for_target,
    check_type_compatibility,
)
from semantic_ci_code.framework.constraint_types import Operator

# --- category resolution ----------------------------------------------------


@pytest.mark.parametrize(
    "target,category",
    [
        ("api_surface", TargetCategory.RECORD_COLLECTION),
        ("api_surface_public", TargetCategory.RECORD_COLLECTION),
        ("type_relations", TargetCategory.RECORD_COLLECTION),
        ("effects", TargetCategory.RECORD_COLLECTION),
        ("imports", TargetCategory.RECORD_COLLECTION),
        ("module_graph", TargetCategory.RECORD_COLLECTION),
        ("api_surface_delta.added", TargetCategory.RECORD_COLLECTION),
        ("api_surface_delta.removed", TargetCategory.RECORD_COLLECTION),
        ("api_surface_delta.removed_public", TargetCategory.RECORD_COLLECTION),
        ("api_surface_delta.changed", TargetCategory.RECORD_COLLECTION),
        ("decorators_delta.added", TargetCategory.RECORD_COLLECTION),
        ("decorators_delta.removed", TargetCategory.RECORD_COLLECTION),
        ("effect_changes.added", TargetCategory.RECORD_COLLECTION),
        ("effect_changes.removed", TargetCategory.RECORD_COLLECTION),
        ("imports_delta.added", TargetCategory.RECORD_COLLECTION),
        ("type_changes", TargetCategory.RECORD_COLLECTION),
        ("test_surface_delta.new_files", TargetCategory.STRING_COLLECTION),
        ("test_surface_delta.new_cases", TargetCategory.STRING_COLLECTION),
        ("test_surface_delta.removed_cases", TargetCategory.STRING_COLLECTION),
        ("api_surface_delta.added.fqns", TargetCategory.STRING_COLLECTION),
        ("effect_changes.added.fqns", TargetCategory.STRING_COLLECTION),
        ("imports_delta.added.modules", TargetCategory.STRING_COLLECTION),
        ("cfg_delta.new_branches", TargetCategory.SCALAR_NUMBER),
        ("complexity_delta.cyclomatic", TargetCategory.SCALAR_NUMBER),
        ("coverage_delta.line", TargetCategory.SCALAR_NUMBER),
        ("coverage_delta.branch", TargetCategory.SCALAR_NUMBER),
        ("files_touched", TargetCategory.SCALAR_NUMBER),
        ("loc_delta.added", TargetCategory.SCALAR_NUMBER),
        ("api_surface_delta", TargetCategory.RECORD),
        ("decorators_delta", TargetCategory.RECORD),
        ("effect_changes", TargetCategory.RECORD),
        ("cfg_delta", TargetCategory.RECORD),
        ("imports_delta", TargetCategory.RECORD),
        ("complexity_delta", TargetCategory.RECORD),
        ("test_surface_delta", TargetCategory.RECORD),
        ("coverage_delta", TargetCategory.RECORD),
        ("loc_delta", TargetCategory.RECORD),
        ("python_specific", TargetCategory.UNKNOWN_OPEN),
        ("python_specific.module_graph_delta", TargetCategory.UNKNOWN_OPEN),
        ("typescript_specific.complexity", TargetCategory.UNKNOWN_OPEN),
        ("not_a_field", TargetCategory.UNKNOWN_OPEN),
    ],
)
def test_category_for_target_resolves_static_type(target: str, category: TargetCategory):
    assert category_for_target(target) is category


def test_decorators_delta_paths_are_schema_reflected():
    paths = valid_delta_target_paths()
    assert "decorators_delta.added" in paths
    assert "decorators_delta.removed" in paths


# --- observed-side rejections ----------------------------------------------


@pytest.mark.parametrize(
    "operator",
    [
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.EXCLUDES_ALL,
        Operator.SUBSET_OF,
        Operator.SUPERSET_OF,
        Operator.SUPERSET_OF_BASELINE,
        Operator.NO_NEW_ITEMS,
        Operator.NO_REMOVED_ITEMS,
    ],
)
def test_collection_operator_on_scalar_number_is_rejected(operator: Operator):
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="complexity_delta.cyclomatic",
            operator=operator,
            expected=[{"fqn": "x"}]
            if operator
            not in {
                Operator.SUPERSET_OF_BASELINE,
                Operator.NO_NEW_ITEMS,
                Operator.NO_REMOVED_ITEMS,
            }
            else None,
        )

    assert exc_info.value.side is TypeMismatchSide.OBSERVED
    assert "scalar_number" in str(exc_info.value)
    assert operator.value in str(exc_info.value)


@pytest.mark.parametrize(
    "operator",
    [
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.WITHIN_RANGE,
    ],
)
def test_numeric_operator_on_record_collection_is_rejected(operator: Operator):
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="api_surface",
            operator=operator,
            expected=5 if operator is not Operator.WITHIN_RANGE else [0, 10],
        )

    assert exc_info.value.side is TypeMismatchSide.OBSERVED
    assert "record_collection" in str(exc_info.value)


def test_collection_operator_on_record_is_rejected():
    # ``api_surface_delta`` is the whole SymbolDelta record, not a collection.
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="api_surface_delta",
            operator=Operator.INCLUDES_ALL,
            expected=[{"fqn": "x"}],
        )

    assert exc_info.value.side is TypeMismatchSide.OBSERVED


# --- expected-side rejections ----------------------------------------------


@pytest.mark.parametrize(
    "operator",
    [
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.EXCLUDES_ALL,
        Operator.SUBSET_OF,
        Operator.SUPERSET_OF,
    ],
)
def test_collection_operator_with_scalar_expected_is_rejected(operator: Operator):
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="api_surface_delta.added",
            operator=operator,
            expected=5,
        )

    assert exc_info.value.side is TypeMismatchSide.EXPECTED


@pytest.mark.parametrize(
    "operator",
    [
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
    ],
)
def test_numeric_operator_with_string_expected_is_rejected(operator: Operator):
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="complexity_delta.cyclomatic",
            operator=operator,
            expected="five",
        )

    assert exc_info.value.side is TypeMismatchSide.EXPECTED


def test_numeric_operator_with_bool_expected_is_rejected():
    # ``isinstance(True, int)`` is True in Python; guard so ``less_than: true``
    # is not silently accepted as 1.
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="complexity_delta.cyclomatic",
            operator=Operator.LESS_THAN,
            expected=True,
        )

    assert exc_info.value.side is TypeMismatchSide.EXPECTED


def test_within_range_with_single_number_expected_is_rejected():
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="complexity_delta.cyclomatic",
            operator=Operator.WITHIN_RANGE,
            expected=5,
        )

    assert exc_info.value.side is TypeMismatchSide.EXPECTED


def test_within_range_with_three_element_list_is_rejected():
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="complexity_delta.cyclomatic",
            operator=Operator.WITHIN_RANGE,
            expected=[0, 5, 10],
        )

    assert exc_info.value.side is TypeMismatchSide.EXPECTED


def test_within_range_with_non_numeric_bounds_is_rejected():
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="complexity_delta.cyclomatic",
            operator=Operator.WITHIN_RANGE,
            expected=["low", "high"],
        )

    assert exc_info.value.side is TypeMismatchSide.EXPECTED


# --- valid combinations pass through ---------------------------------------


def test_collection_operator_on_record_collection_passes():
    check_type_compatibility(
        target="api_surface_delta.added",
        operator=Operator.INCLUDES_ALL,
        expected=[{"fqn": "x"}],
    )


def test_collection_operator_on_string_collection_passes():
    check_type_compatibility(
        target="test_surface_delta.new_cases",
        operator=Operator.INCLUDES_ALL,
        expected=["test_x"],
    )


def test_baseline_collection_operator_with_no_expected_passes():
    check_type_compatibility(
        target="imports",
        operator=Operator.SUPERSET_OF_BASELINE,
        expected=None,
    )


def test_numeric_operator_with_integer_expected_passes():
    check_type_compatibility(
        target="complexity_delta.cyclomatic",
        operator=Operator.LESS_THAN_OR_EQUAL,
        expected=5,
    )


def test_numeric_operator_with_float_expected_passes():
    check_type_compatibility(
        target="coverage_delta.line",
        operator=Operator.GREATER_THAN_OR_EQUAL,
        expected=0.8,
    )


def test_within_range_with_numeric_pair_passes():
    check_type_compatibility(
        target="complexity_delta.cyclomatic",
        operator=Operator.WITHIN_RANGE,
        expected=[0, 10],
    )


def test_equals_with_any_expected_passes():
    # equals / not_equals are category-agnostic and have no expected-shape
    # constraint.
    check_type_compatibility(
        target="api_surface",
        operator=Operator.EQUALS,
        expected=5,
    )
    check_type_compatibility(
        target="complexity_delta.cyclomatic",
        operator=Operator.NOT_EQUALS,
        expected={"weird": "shape"},
    )


# --- open-dimension partial bypass ----------------------------------------


@pytest.mark.parametrize(
    "operator,expected",
    [
        (Operator.INCLUDES_ALL, [{"k": "v"}]),
        (Operator.LESS_THAN, 5),
        (Operator.WITHIN_RANGE, [0, 10]),
    ],
)
def test_open_path_observed_side_check_is_bypassed(operator: Operator, expected: object):
    # ``python_specific.*`` is UNKNOWN_OPEN by category, so the observed-
    # side category check is bypassed (the runtime shape cannot be
    # proven at compile). With a valid expected literal, compile passes.
    check_type_compatibility(
        target="python_specific.something",
        operator=operator,
        expected=expected,
    )


@pytest.mark.parametrize(
    "operator,expected",
    [
        (Operator.INCLUDES_ALL, "scalar_string_not_a_list"),
        (Operator.LESS_THAN, "not_a_number"),
        (Operator.WITHIN_RANGE, [0, 5, 10]),
        (Operator.WITHIN_RANGE, [0]),
    ],
)
def test_open_path_expected_side_check_still_runs(operator: Operator, expected: object):
    # Regression for PR #78 Codex P2 review (3rd round): the expected
    # literal shape is independent of the observed target category, so
    # it must be validated even for open dimensions. Without this, a
    # malformed expected reached ``_unknown_type_mismatch`` at runtime
    # and was retagged ``open_runtime`` — letting ``unknown_policy:
    # warn`` / ``ignore`` pass a malformed spec.
    with pytest.raises(TypeMismatch) as exc_info:
        check_type_compatibility(
            target="python_specific.something",
            operator=operator,
            expected=expected,
        )
    assert exc_info.value.side is TypeMismatchSide.EXPECTED


# --- integration through compile_target_svp --------------------------------


def test_compile_collection_op_on_scalar_target_raises_compile_error():
    yaml_source = """
intent: collection op on numeric target
change:
  primary_kind: feature
constraints:
  - id: bad_op
    kind: delta
    target: complexity_delta.cyclomatic
    operator: includes_all
    expected:
      - fqn: 'x'
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].target"
    assert "scalar_number" in exc_info.value.message


def test_compile_numeric_op_on_collection_target_raises_compile_error():
    yaml_source = """
intent: numeric op on collection target
change:
  primary_kind: feature
constraints:
  - id: bad_op
    kind: delta
    target: api_surface_delta.added
    operator: less_than
    expected: 5
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].target"
    assert "record_collection" in exc_info.value.message


def test_compile_collection_op_with_scalar_expected_raises_compile_error():
    yaml_source = """
intent: collection op with scalar expected
change:
  primary_kind: feature
constraints:
  - id: bad_expected
    kind: delta
    target: api_surface_delta.added
    operator: includes_all
    expected: 5
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].expected"
    assert "includes_all" in exc_info.value.message


def test_compile_within_range_with_three_element_list_raises_compile_error():
    yaml_source = """
intent: within_range with bad bounds
change:
  primary_kind: feature
constraints:
  - id: bad_range
    kind: delta
    target: complexity_delta.cyclomatic
    operator: within_range
    expected: [0, 5, 10]
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].expected"
    assert "within_range" in exc_info.value.message


def test_compile_open_path_with_valid_expected_compiles():
    # python_specific bypasses the observed-side type check; with a valid
    # expected literal, the constraint compiles. Observed-side runtime
    # mismatches are then routed as ``open_runtime`` UNKNOWN
    # (``evaluator._from_operator_outcome``).
    yaml_source = """
intent: open path bypass
change:
  primary_kind: feature
constraints:
  - id: open_bypass
    kind: delta
    target: python_specific.value
    operator: less_than
    expected: 5
"""

    compiled = compile_target_svp(yaml_source, filename="target.yaml")
    user_constraints = [c for c in compiled.constraints if c.source.value == "user"]
    assert any(c.id == "open_bypass" for c in user_constraints)


def test_compile_open_path_with_malformed_expected_is_rejected():
    # PR #78 Codex P2 (3rd round): expected-side validation runs even
    # for open dimensions so a malformed literal cannot reach runtime
    # and slip through ``unknown_policy: warn`` / ``ignore``.
    yaml_source = """
intent: open path with malformed expected
change:
  primary_kind: feature
constraints:
  - id: open_bad_expected
    kind: delta
    target: python_specific.value
    operator: less_than
    expected: "not_a_number"
    unknown_policy: warn
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].expected"
    assert "less_than" in exc_info.value.message


def test_compile_design_feature_fixture_still_compiles():
    # Sanity check: the design.md §4.5 feature fixture must still compile
    # after D1-3.
    from pathlib import Path

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "compiler" / "design_feature.yaml"
    compile_target_svp(fixture.read_text(), filename=str(fixture))
