from __future__ import annotations

import os
import pickle
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.compiler import (
    CompiledAPISurfaceAllowRule,
    CompiledAuthor,
    CompiledAuthorship,
    CompiledConstraint,
    CompiledEffectAllowRule,
    CompiledTarget,
    CompileError,
    ConstraintSource,
    compile_target_svp,
)
from semantic_ci_code.compiler.templates import TEMPLATE_CONSTRAINTS
from semantic_ci_code.domain.state_schema import ChangeKind, EffectClass
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "compiler"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def user_constraint(
    *,
    id: str = "user",
    operator: Operator = Operator.EQUALS,
    target: str = "imports",
    expected: object = None,
) -> CompiledConstraint:
    return CompiledConstraint(
        id=id,
        kind=ConstraintKind.DELTA,
        target=target,
        operator=operator,
        expected=expected,
        severity=Severity.HARD,
        unknown_policy=UnknownPolicy.FAIL,
        tolerance=None,
        evidence_required=False,
        scope=None,
        source=ConstraintSource.USER,
    )


def test_minimal_valid_yaml_expands_templates():
    compiled = compile_target_svp(
        read_fixture("minimal_feature.yaml"), filename="minimal_feature.yaml"
    )

    assert compiled.intent == "add user profile endpoint"
    assert compiled.primary_kind is ChangeKind.FEATURE
    assert compiled.allowed_secondary_kinds == ()
    assert compiled.scope == ()
    assert compiled.constraints == TEMPLATE_CONSTRAINTS[ChangeKind.FEATURE]
    assert hash(compiled)


@pytest.mark.parametrize("primary_kind", tuple(ChangeKind))
def test_each_primary_kind_expands_expected_template_table(primary_kind: ChangeKind):
    yaml_source = f"""
intent: test {primary_kind.value}
change:
  primary_kind: {primary_kind.value}
"""

    compiled = compile_target_svp(yaml_source)

    assert compiled.constraints == TEMPLATE_CONSTRAINTS[primary_kind]


def test_generic_primary_kind_injects_no_template_constraints():
    yaml_source = """
intent: generic security overlay
change:
  primary_kind: generic
constraints:
  - id: deny_pickle
    kind: delta
    target: imports_delta.added
    operator: excludes_all
    expected:
      - module: pickle
"""

    compiled = compile_target_svp(yaml_source)

    assert TEMPLATE_CONSTRAINTS[ChangeKind.GENERIC] == ()
    assert compiled.primary_kind is ChangeKind.GENERIC
    assert len(compiled.constraints) == 1
    assert compiled.constraints[0].id == "deny_pickle"
    assert compiled.constraints[0].source is ConstraintSource.USER


def test_user_constraints_append_after_templates_and_keep_yaml_order():
    yaml_source = """
intent: order test
change:
  primary_kind: bugfix
constraints:
  - id: first_user
    kind: delta
    target: imports
    operator: superset_of_baseline
  - id: second_user
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than_or_equal
    expected: 10
"""

    compiled = compile_target_svp(yaml_source)

    ids = tuple(constraint.id for constraint in compiled.constraints)
    assert ids == (
        "template:bugfix:api_surface_unchanged",
        "template:bugfix:no_new_effects",
        "first_user",
        "second_user",
    )
    assert tuple(constraint.source for constraint in compiled.constraints) == (
        ConstraintSource.TEMPLATE,
        ConstraintSource.TEMPLATE,
        ConstraintSource.USER,
        ConstraintSource.USER,
    )


def _yaml_block_for_operator(operator: Operator) -> str:
    """Produce a constraint YAML block compatible with this operator.

    After Brief D1-2 (operator-target alignment) and Brief D1-3
    (operator-category + expected-shape alignment), every operator has
    a narrow set of valid (kind, target, expected) combinations. This
    helper picks one valid triple per operator so the parametrized
    "every operator compiles" smoke test still exercises all 20
    Operator enum values.

    The exact triple per operator is irrelevant — only that it satisfies
    both compile-time checks. Runtime evaluation semantics are tested
    elsewhere.
    """

    # Pure collection operators (need record/string/number_collection
    # observed + list expected).
    if operator in {
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.EXCLUDES_ALL,
        Operator.SUBSET_OF,
        Operator.SUPERSET_OF,
    }:
        return (
            f"  - id: op_{operator.value}\n"
            f"    kind: delta\n"
            f"    target: api_surface_delta.added\n"
            f"    operator: {operator.value}\n"
            f"    expected:\n"
            f"      - fqn: 'sample.x'\n"
        )
    # Baseline collection operators (state-domain path, no expected).
    if operator in {
        Operator.SUPERSET_OF_BASELINE,
        Operator.NO_NEW_ITEMS,
        Operator.NO_REMOVED_ITEMS,
    }:
        return (
            f"  - id: op_{operator.value}\n"
            f"    kind: delta\n"
            f"    target: imports\n"
            f"    operator: {operator.value}\n"
        )
    # Numeric scalar operators (need scalar_number observed + number
    # expected).
    if operator in {
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
    }:
        return (
            f"  - id: op_{operator.value}\n"
            f"    kind: delta\n"
            f"    target: complexity_delta.cyclomatic\n"
            f"    operator: {operator.value}\n"
            f"    expected: 5\n"
        )
    # within_range requires a [low, high] pair of numbers.
    if operator is Operator.WITHIN_RANGE:
        return (
            f"  - id: op_{operator.value}\n"
            f"    kind: delta\n"
            f"    target: complexity_delta.cyclomatic\n"
            f"    operator: {operator.value}\n"
            f"    expected: [0, 10]\n"
        )
    # Pure category-agnostic operators (equals / not_equals): scalar
    # number target is the simplest valid combination.
    if operator in {Operator.EQUALS, Operator.NOT_EQUALS}:
        return (
            f"  - id: op_{operator.value}\n"
            f"    kind: delta\n"
            f"    target: complexity_delta.cyclomatic\n"
            f"    operator: {operator.value}\n"
            f"    expected: 0\n"
        )
    # Baseline category-agnostic operators (equals_baseline /
    # not_equals_baseline / unchanged / changed): state path, no expected.
    if operator in {
        Operator.EQUALS_BASELINE,
        Operator.NOT_EQUALS_BASELINE,
        Operator.UNCHANGED,
        Operator.CHANGED,
    }:
        return (
            f"  - id: op_{operator.value}\n"
            f"    kind: delta\n"
            f"    target: imports\n"
            f"    operator: {operator.value}\n"
        )
    # changed_only_in is SKIPPED unconditionally; any path/expected works.
    if operator is Operator.CHANGED_ONLY_IN:
        return (
            f"  - id: op_{operator.value}\n"
            f"    kind: delta\n"
            f"    target: imports\n"
            f"    operator: {operator.value}\n"
        )
    raise AssertionError(f"Unhandled operator in fixture helper: {operator}")


@pytest.mark.parametrize("operator", tuple(Operator))
def test_all_operator_enum_values_compile(operator: Operator):
    yaml_source = (
        "intent: operator test\n"
        "change:\n"
        "  primary_kind: feature\n"
        "constraints:\n"
        f"{_yaml_block_for_operator(operator)}"
    )

    compiled = compile_target_svp(yaml_source)

    assert compiled.constraints[-1].operator is operator


def test_missing_intent_raises_compile_error():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp("change:\n  primary_kind: feature\n")

    assert exc_info.value.path == "intent"


def test_missing_change_primary_kind_raises_compile_error():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp("intent: missing primary\nchange: {}\n")

    assert exc_info.value.path == "change.primary_kind"


def test_root_unknown_field_raises_compile_error():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(read_fixture("invalid_root_unknown_field.yaml"))

    assert exc_info.value.path == "unexpected"


def test_constraint_unknown_field_raises_compile_error():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(read_fixture("invalid_constraint_unknown_field.yaml"))

    assert exc_info.value.path == "constraints[0].extra_field"


def test_unknown_constraint_target_path_raises_compile_error_with_suggestion():
    yaml_source = """
intent: typo path
change:
  primary_kind: feature
constraints:
  - id: typo_path
    kind: delta
    target: api_surface.public_symbols
    operator: superset_of_baseline
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].target"
    assert "api_surface.public_symbols" in exc_info.value.message
    assert "api_surface_public" in exc_info.value.message


def test_unknown_target_subfield_raises_compile_error_with_suggestion():
    yaml_source = """
intent: typo subfield
change:
  primary_kind: feature
constraints:
  - id: typo_subfield
    kind: delta
    target: test_surface_delta.new_test_cases
    operator: not_equals
    expected: []
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].target"
    assert "test_surface_delta.new_cases" in exc_info.value.message


def test_malformed_open_dimension_path_raises_compile_error():
    yaml_source = """
intent: bad open prefix syntax
change:
  primary_kind: feature
constraints:
  - id: bad_hyphen
    kind: delta
    target: python_specific.bad-key
    operator: equals
    expected: 0
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].target"
    assert "python_specific.bad-key" in exc_info.value.message


def test_empty_segment_open_dimension_path_raises_compile_error():
    yaml_source = """
intent: empty segment under open prefix
change:
  primary_kind: feature
constraints:
  - id: bad_double_dot
    kind: delta
    target: python_specific..foo
    operator: equals
    expected: 0
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].target"
    assert "python_specific..foo" in exc_info.value.message


def test_open_dimension_paths_compile_without_schema_check():
    yaml_source = """
intent: open dim ok
change:
  primary_kind: feature
constraints:
  - id: open_dim
    kind: delta
    target: python_specific.module_graph_delta.cycles
    operator: equals
    expected: []
  - id: open_ts
    kind: delta
    target: typescript_specific.anything.deep
    operator: equals
    expected: []
"""

    compiled = compile_target_svp(yaml_source, filename="target.yaml")
    user_targets = [c.target for c in compiled.constraints if c.source.value == "user"]
    assert "python_specific.module_graph_delta.cycles" in user_targets
    assert "typescript_specific.anything.deep" in user_targets


def test_state_kind_with_delta_path_raises_compile_error():
    yaml_source = """
intent: state-kind constraint with a delta-only path
change:
  primary_kind: feature
constraints:
  - id: state_with_delta_path
    kind: state
    target: api_surface_delta.removed
    operator: equals
    expected: []
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.path == "constraints[0].target"
    assert "api_surface_delta.removed" in exc_info.value.message
    # Domain label is the narrower CodeState, not the union.
    assert "does not exist on CodeState." in exc_info.value.message
    # Suggestions should come from the state-kind corpus, not the union.
    assert "api_surface_delta" not in exc_info.value.message.split("Did you mean:")[1]


def test_delta_kind_with_state_path_compiles():
    yaml_source = """
intent: delta-kind with state path uses baseline operator semantics
change:
  primary_kind: feature
constraints:
  - id: delta_state_baseline
    kind: delta
    target: api_surface_public
    operator: superset_of_baseline
    severity: hard
    unknown_policy: fail
"""

    compiled = compile_target_svp(yaml_source, filename="target.yaml")
    user_constraints = [c for c in compiled.constraints if c.source.value == "user"]
    assert any(c.target == "api_surface_public" for c in user_constraints)


def test_repair_kind_constraint_skips_path_schema_check():
    yaml_source = """
intent: repair-kind constraints are skipped at evaluate
change:
  primary_kind: feature
constraints:
  - id: repair_placeholder
    kind: repair
    target: repair
    operator: equals
    expected: 0
"""

    compiled = compile_target_svp(yaml_source, filename="target.yaml")
    user_constraints = [c for c in compiled.constraints if c.source.value == "user"]
    assert len(user_constraints) == 1
    assert user_constraints[0].id == "repair_placeholder"
    assert user_constraints[0].target == "repair"


def test_alias_paths_compile_without_error():
    yaml_source = """
intent: aliases ok
change:
  primary_kind: feature
constraints:
  - id: alias_public
    kind: delta
    target: api_surface_public
    operator: superset_of_baseline
  - id: alias_removed_public
    kind: delta
    target: api_surface_delta.removed_public
    operator: equals
    expected: []
"""

    compiled = compile_target_svp(yaml_source, filename="target.yaml")
    targets = [c.target for c in compiled.constraints if c.source.value == "user"]
    assert "api_surface_public" in targets
    assert "api_surface_delta.removed_public" in targets


def test_unknown_operator_raises_compile_error_with_constraint_path():
    yaml_source = """
intent: bad operator
change:
  primary_kind: feature
constraints:
  - id: bad_operator
    kind: delta
    target: imports
    operator: made_up
"""

    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(yaml_source, filename="target.yaml")

    assert exc_info.value.filename == "target.yaml"
    assert exc_info.value.path == "constraints[0].operator"


def test_unknown_change_kind_raises_compile_error():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp("intent: bad kind\nchange:\n  primary_kind: chore\n")

    assert exc_info.value.path == "change.primary_kind"


def test_yaml_syntax_error_raises_compile_error_with_line_and_column():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(read_fixture("invalid_syntax.yaml"), filename="invalid_syntax.yaml")

    assert exc_info.value.filename == "invalid_syntax.yaml"
    assert exc_info.value.line is not None
    assert exc_info.value.column is not None


def test_non_mapping_root_raises_compile_error():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp("- not\n- a\n- mapping\n")

    assert exc_info.value.path is None
    assert "root must be a mapping" in str(exc_info.value)


def test_duplicate_user_constraint_id_raises_compile_error():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(read_fixture("duplicate_user.yaml"))

    message = str(exc_info.value)
    assert "duplicate" in message
    assert "user[0]" in message
    assert "user[1]" in message


def test_duplicate_user_vs_template_constraint_id_raises_compile_error():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(read_fixture("duplicate_template.yaml"))

    message = str(exc_info.value)
    assert "template:feature:no_removed_api" in message
    assert "template[0]" in message
    assert "user[0]" in message


def test_compile_error_round_trips_through_pickle():
    error = CompileError(
        "bad target",
        filename="target.yaml",
        path="constraints[0].target",
        line=4,
        column=9,
    )

    restored = pickle.loads(pickle.dumps(error))

    assert restored.message == "bad target"
    assert restored.filename == "target.yaml"
    assert restored.path == "constraints[0].target"
    assert restored.line == 4
    assert restored.column == 9
    assert str(restored) == "target.yaml:4:9: bad target at constraints[0].target"


def test_empty_constraint_target_raises_compile_error():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(read_fixture("empty_target.yaml"))

    assert exc_info.value.path == "constraints[0].target"


def test_empty_intent_is_allowed_for_init_scaffold():
    compiled = compile_target_svp(read_fixture("empty_intent.yaml"))

    assert compiled.intent == ""


def test_design_feature_sample_compiles_and_preserves_optional_fields():
    compiled = compile_target_svp(read_fixture("design_feature.yaml"))

    assert compiled.primary_kind is ChangeKind.FEATURE
    assert compiled.allowed_secondary_kinds == (ChangeKind.TEST_UPDATE,)
    assert compiled.scope == (("files", ("src/api/users.py", "tests/test_users.py")),)

    complexity_budget = next(
        constraint for constraint in compiled.constraints if constraint.id == "complexity_budget"
    )
    no_new_io = next(
        constraint for constraint in compiled.constraints if constraint.id == "no_new_io_in_models"
    )
    feature_added = next(
        constraint for constraint in compiled.constraints if constraint.id == "feature_added"
    )

    assert complexity_budget.severity is Severity.SOFT
    assert complexity_budget.unknown_policy is UnknownPolicy.WARN
    assert complexity_budget.tolerance == 0.5
    assert no_new_io.unknown_policy is UnknownPolicy.REPAIR
    assert no_new_io.scope == "src.models.*"
    assert feature_added.expected == ({"fqn": "src.api.users.fetch_user_profile"},)
    assert hash(compiled)


def test_effect_allow_new_policy_compiles_to_frozen_rules():
    compiled = compile_target_svp(
        """
intent: allow git subprocess
change:
  primary_kind: feature
effects:
  allow_new:
    - fqn: subprocess.run
      effect_class: process
"""
    )

    assert compiled.effect_allow_new == (
        CompiledEffectAllowRule(fqn="subprocess.run", effect_class=EffectClass.PROCESS),
    )
    assert hash(compiled)


def test_api_surface_allow_changes_policy_compiles_to_frozen_rules():
    compiled = compile_target_svp(
        """
intent: allow test helper movement
change:
  primary_kind: refactor
api_surface:
  allow_changes:
    - fqn: git_helpers.run_semantic_ci
    - fqn_prefix: helpers.
"""
    )

    assert compiled.api_surface_allow_changes == (
        CompiledAPISurfaceAllowRule(fqn="git_helpers.run_semantic_ci"),
        CompiledAPISurfaceAllowRule(fqn_prefix="helpers."),
    )
    assert hash(compiled)


def test_authorship_compiles_to_frozen_metadata():
    compiled = compile_target_svp(
        """
intent: authorship anchor
change:
  primary_kind: feature
authorship:
  authors:
    - identity: alice@example.com
      signature: sig-1
    - identity: bot:semantic-ci
  declared_at: "2026-05-05T12:00:00Z"
  generation_metadata:
    tool: codex
    model: gpt-test
"""
    )

    assert compiled.authorship == CompiledAuthorship(
        authors=(
            CompiledAuthor(identity="alice@example.com", signature="sig-1"),
            CompiledAuthor(identity="bot:semantic-ci"),
        ),
        declared_at="2026-05-05T12:00:00Z",
        generation_metadata={"tool": "codex", "model": "gpt-test"},
    )
    assert hash(compiled)


def test_api_surface_allow_changes_rule_requires_fqn_or_prefix():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(
            """
intent: invalid api allow
change:
  primary_kind: refactor
api_surface:
  allow_changes:
    - {}
"""
        )

    assert exc_info.value.path == "api_surface.allow_changes[0]"


def test_effect_allow_new_rule_requires_fqn_or_effect_class():
    with pytest.raises(CompileError) as exc_info:
        compile_target_svp(
            """
intent: invalid effect allow
change:
  primary_kind: feature
effects:
  allow_new:
    - {}
"""
        )

    assert exc_info.value.path == "effects.allow_new[0]"


def test_design_refactor_sample_compiles():
    compiled = compile_target_svp(read_fixture("design_refactor.yaml"))

    assert compiled.primary_kind is ChangeKind.REFACTOR
    assert compiled.constraints[:4] == TEMPLATE_CONSTRAINTS[ChangeKind.REFACTOR]
    assert compiled.constraints[-1].id == "complexity_should_decrease"
    assert compiled.constraints[-1].operator is Operator.LESS_THAN
    assert compiled.constraints[-1].severity is Severity.SOFT


def test_same_process_determinism():
    yaml_source = read_fixture("design_feature.yaml")

    assert compile_target_svp(yaml_source) == compile_target_svp(yaml_source)


def test_subprocess_determinism_across_hash_seeds():
    yaml_source = read_fixture("design_feature.yaml")
    script = """
import sys
from semantic_ci_code.compiler import compile_target_svp

compiled = compile_target_svp(sys.stdin.read())
print(repr(compiled))
"""

    first = _run_compile_subprocess(script, yaml_source, hash_seed="1")
    second = _run_compile_subprocess(script, yaml_source, hash_seed="2")

    assert first == second


def _run_compile_subprocess(script: str, yaml_source: str, *, hash_seed: str) -> str:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=yaml_source,
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return result.stdout


def test_hand_built_compiled_target_engine_contract():
    constraint = user_constraint(id="manual", operator=Operator.NO_NEW_ITEMS)
    compiled = CompiledTarget(
        intent="manual engine test",
        primary_kind=ChangeKind.BUGFIX,
        allowed_secondary_kinds=(ChangeKind.TEST_UPDATE,),
        scope=(("files", ("src/a.py",)),),
        constraints=(constraint,),
    )

    assert compiled.constraints == (constraint,)
    assert hash(compiled)


def test_expected_lists_are_recursively_normalized_to_tuples():
    yaml_source = """
intent: freeze expected
change:
  primary_kind: feature
constraints:
  - id: expected_list
    kind: delta
    target: api_surface_delta.added
    operator: includes_all
    expected:
      - a
      - [b]
"""

    compiled = compile_target_svp(yaml_source)

    assert compiled.constraints[-1].expected == ({"fqn": "a"}, ("b",))
    assert hash(compiled.constraints[-1])


def test_expected_dict_is_preserved_but_compiled_constraint_remains_hashable():
    yaml_source = """
intent: preserve dict expected
change:
  primary_kind: feature
constraints:
  - id: expected_dict
    kind: delta
    target: python_specific
    operator: equals
    expected:
      names: [a, b]
    scope:
      files: [src/a.py]
"""

    compiled = compile_target_svp(yaml_source)
    constraint = compiled.constraints[-1]

    assert constraint.expected == {"names": ["a", "b"]}
    assert constraint.scope == {"files": ["src/a.py"]}
    assert hash(constraint)
    assert hash(compiled)


def test_constraint_source_is_set_for_template_and_user_constraints():
    compiled = compile_target_svp(read_fixture("design_refactor.yaml"))

    assert {constraint.source for constraint in compiled.constraints[:4]} == {
        ConstraintSource.TEMPLATE
    }
    assert compiled.constraints[-1].source is ConstraintSource.USER
