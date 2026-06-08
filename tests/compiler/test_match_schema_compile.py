from __future__ import annotations

import pytest

from semantic_ci_code.compiler import CompileError, compile_target_svp


def _compile_constraint(
    *,
    target: str,
    operator: str = "includes_all",
    expected: str,
    kind: str = "delta",
):
    yaml_source = f"""
intent: match schema
change:
  primary_kind: feature
constraints:
  - id: match_schema
    kind: {kind}
    target: {target}
    operator: {operator}
    expected:
{expected}
"""
    return compile_target_svp(yaml_source, filename="target.yaml").constraints[-1]


def test_bare_string_desugars_to_required_key_record_for_dict_collection_target():
    constraint = _compile_constraint(
        target="api_surface_delta.added",
        expected='      - "myapi.foo"',
    )

    assert constraint.expected == ({"fqn": "myapi.foo"},)


def test_removed_public_alias_uses_api_match_schema():
    constraint = _compile_constraint(
        target="api_surface_delta.removed_public",
        expected='      - "myapi.public_removed"',
    )

    assert constraint.expected == ({"fqn": "myapi.public_removed"},)


def test_bare_string_is_not_desugared_for_flat_projection_target():
    constraint = _compile_constraint(
        target="api_surface_delta.added.fqns",
        expected='      - "myapi.foo"',
    )

    assert constraint.expected == ("myapi.foo",)


def test_full_allowed_record_compiles():
    constraint = _compile_constraint(
        target="api_surface_delta.added",
        expected="""
      - fqn: myapi.foo
        kind: function
        visibility: public""",
    )

    assert constraint.expected == (
        {"fqn": "myapi.foo", "kind": "function", "visibility": "public"},
    )


def test_api_surface_changed_allows_only_top_level_identity_keys():
    constraint = _compile_constraint(
        target="api_surface_delta.changed",
        expected="""
      - fqn: myapi.foo
        kind: function""",
    )

    assert constraint.expected == ({"fqn": "myapi.foo", "kind": "function"},)


def test_api_surface_changed_rejects_visibility_key_with_reason():
    with pytest.raises(CompileError) as exc_info:
        _compile_constraint(
            target="api_surface_delta.changed",
            expected="""
      - fqn: myapi.foo
        visibility: private""",
        )

    assert exc_info.value.path == "constraints[0].expected"
    assert "forbidden match key 'visibility'" in exc_info.value.message
    assert "nested under before/after" in exc_info.value.message


def test_signature_key_is_forbidden_with_reason_and_allowed_key_suggestions():
    with pytest.raises(CompileError) as exc_info:
        _compile_constraint(
            target="api_surface_delta.added",
            expected="""
      - fqn: myapi.foo
        signature: "def foo(): ..." """,
        )

    assert exc_info.value.path == "constraints[0].expected"
    assert "forbidden match key 'signature'" in exc_info.value.message
    assert "extractor-format coupling" in exc_info.value.message


def test_effect_confidence_key_is_forbidden():
    with pytest.raises(CompileError) as exc_info:
        _compile_constraint(
            target="effect_changes.added",
            expected="""
      - fqn: pkg.call
        confidence: 0.8""",
        )

    assert "forbidden match key 'confidence'" in exc_info.value.message


def test_effect_class_only_partial_match_compiles_for_effect_targets():
    constraint = _compile_constraint(
        target="effect_changes.added",
        operator="excludes_all",
        expected="""
      - effect_class: process""",
    )

    assert constraint.expected == ({"effect_class": "process"},)


def test_decorator_only_partial_match_compiles_for_decorators_delta():
    constraint = _compile_constraint(
        target="decorators_delta.removed",
        operator="excludes_all",
        expected="""
      - decorator: login_required""",
    )

    assert constraint.expected == ({"decorator": "login_required"},)


def test_decorator_bare_string_desugars_to_decorator_key():
    constraint = _compile_constraint(
        target="decorators_delta.removed",
        operator="excludes_all",
        expected='      - "login_required"',
    )

    assert constraint.expected == ({"decorator": "login_required"},)


def test_import_symbols_key_is_forbidden():
    with pytest.raises(CompileError) as exc_info:
        _compile_constraint(
            target="imports_delta.added",
            expected="""
      - module: requests
        symbols: [get]""",
        )

    assert "forbidden match key 'symbols'" in exc_info.value.message
    assert "list-valued" in exc_info.value.message


def test_unknown_key_and_forbidden_key_have_distinct_messages():
    with pytest.raises(CompileError) as unknown_info:
        _compile_constraint(
            target="api_surface_delta.added",
            expected="""
      - fqnn: myapi.foo""",
        )
    with pytest.raises(CompileError) as forbidden_info:
        _compile_constraint(
            target="api_surface_delta.added",
            expected="""
      - signature: "def foo(): ..." """,
        )

    assert "unknown match key 'fqnn'" in unknown_info.value.message
    assert "Allowed keys: fqn, kind, visibility" in unknown_info.value.message
    assert "Did you mean: fqn" in unknown_info.value.message
    assert "forbidden match key 'signature'" in forbidden_info.value.message


def test_required_key_missing_is_compile_error():
    with pytest.raises(CompileError) as exc_info:
        _compile_constraint(
            target="api_surface_delta.added",
            expected="""
      - kind: function""",
        )

    assert "requires key 'fqn'" in exc_info.value.message


@pytest.mark.parametrize(
    ("operator", "message"),
    [
        ("excludes_all", "no-op deny gate"),
        ("includes_any", "can never be satisfied"),
    ],
)
def test_empty_expected_rejected_for_dangerous_or_unsatisfiable_set_operators(
    operator: str,
    message: str,
):
    with pytest.raises(CompileError) as exc_info:
        _compile_constraint(
            target="api_surface_delta.added",
            operator=operator,
            expected="      []",
        )

    assert message in exc_info.value.message


def test_empty_includes_all_is_allowed():
    constraint = _compile_constraint(
        target="api_surface_delta.added",
        operator="includes_all",
        expected="      []",
    )

    assert constraint.expected == ()


def test_module_graph_partial_dict_is_rejected_as_unregistered_match_schema_target():
    # ``module_graph`` is a CodeState path; pair it with kind=state so the
    # (kind, target, operator) triple passes the operator-schema check and
    # the failure remains the match-schema rejection under test.
    with pytest.raises(CompileError) as exc_info:
        _compile_constraint(
            kind="state",
            target="module_graph",
            expected="""
      - module: pkg.a""",
        )

    assert "no Match Schema is registered" in exc_info.value.message


def test_dict_expected_on_numeric_target_is_rejected_as_type_domain_mismatch():
    # After Brief D1-3, the type-schema check fires before match-schema for
    # this combination: ``includes_all`` (collection operator) on
    # ``complexity_delta.cyclomatic`` (scalar_number) is rejected on
    # observed-side category alone, regardless of what ``expected`` looks
    # like. Keep the same fixture shape so the test still documents the
    # numeric-target rejection — only the error wording changes.
    with pytest.raises(CompileError) as exc_info:
        _compile_constraint(
            target="complexity_delta.cyclomatic",
            expected="""
      - fqn: pkg.a""",
        )

    message = exc_info.value.message
    assert "complexity_delta.cyclomatic" in message
    assert "scalar_number" in message
    assert "includes_all" in message
