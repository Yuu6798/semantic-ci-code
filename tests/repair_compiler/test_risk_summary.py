from __future__ import annotations

from semantic_ci_code.domain.state_schema import APISurfaceEntry, CodeState
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair_compiler.risk_summary import compute_risk_summary


def test_would_violate_reports_user_constraints_that_fail_on_baseline_self_compare():
    summary = compute_risk_summary(risk_target(), baseline_state())

    assert summary["would_violate"] == ["require_missing_api"]


def test_forbidden_zones_reports_baseline_guard_constraints():
    summary = compute_risk_summary(risk_target(), baseline_state())

    assert {
        "constraint_id": "lock_api_surface",
        "source": "user",
        "target": "api_surface",
        "operator": "equals_baseline",
    } in summary["forbidden_zones"]
    assert {
        "constraint_id": "require_missing_api",
        "source": "user",
        "target": "api_surface",
        "operator": "includes_all",
    } not in summary["forbidden_zones"]


def test_required_additions_flattens_includes_expected_values():
    summary = compute_risk_summary(risk_target(), baseline_state())

    assert summary["required_additions"] == [
        {
            "constraint_id": "require_missing_api",
            "source": "user",
            "target": "api_surface",
            "operator": "includes_all",
            "expected": "pkg.profile",
        }
    ]


def test_required_additions_keeps_includes_any_as_alternative_group():
    summary = compute_risk_summary(includes_any_target(), baseline_state())

    assert summary["required_additions"] == [
        {
            "constraint_id": "require_one_entrypoint",
            "source": "user",
            "target": "api_surface",
            "operator": "includes_any",
            "expected_any_of": ["pkg.profile", "pkg.account"],
        }
    ]


def test_template_implications_report_template_constraint_ids_in_order():
    summary = compute_risk_summary(risk_target(), baseline_state())

    assert summary["template_implications"] == [
        "template:refactor:api_surface_unchanged",
        "template:refactor:type_relations_unchanged",
        "template:refactor:effects_unchanged",
        "template:refactor:test_surface_unchanged",
    ]


def test_risk_summary_is_deterministic_for_same_input():
    first = compute_risk_summary(risk_target(), baseline_state())
    second = compute_risk_summary(risk_target(), baseline_state())

    assert first == second
    assert tuple(first) == (
        "would_violate",
        "forbidden_zones",
        "required_additions",
        "template_implications",
    )


def baseline_state() -> CodeState:
    return CodeState(
        api_surface=(
            APISurfaceEntry(
                fqn="pkg.existing",
                kind="function",
                signature="def existing() -> int: ...",
                visibility="public",
            ),
        )
    )


def risk_target():
    return parse_target_svp_yaml(
        """
intent: validate profile endpoint plan
change:
  primary_kind: refactor
constraints:
  - id: lock_api_surface
    kind: delta
    target: api_surface
    operator: equals_baseline
  - id: require_missing_api
    kind: state
    target: api_surface
    operator: includes_all
    expected:
      - pkg.profile
"""
    )


def includes_any_target():
    return parse_target_svp_yaml(
        """
intent: validate alternative entrypoint plan
change:
  primary_kind: feature
constraints:
  - id: require_one_entrypoint
    kind: state
    target: api_surface
    operator: includes_any
    expected:
      - pkg.profile
      - pkg.account
"""
    )
