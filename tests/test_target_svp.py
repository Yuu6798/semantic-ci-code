from __future__ import annotations

import pytest
from pydantic import ValidationError

from semantic_ci_code.domain.state_schema import ChangeKind, EffectClass
from semantic_ci_code.framework.constraint_types import DeltaConstraint, Operator
from semantic_ci_code.framework.target_svp import (
    TargetSVP,
    parse_target_svp_yaml,
    target_svp_to_yaml,
)

FEATURE_SAMPLE_YAML = """
intent: "fetch_user_profile を追加"
change:
  primary_kind: feature
  scope:
    files: ["src/api/users.py", "tests/test_users.py"]

constraints:
  - id: feature_added
    kind: delta
    target: api_surface_delta.added
    operator: includes_all
    expected: ["src.api.users.fetch_user_profile"]
    severity: hard
    unknown_policy: fail
    evidence_required: true

  - id: no_other_api_changes
    kind: delta
    target: api_surface_public
    operator: superset_of_baseline
    severity: hard
    unknown_policy: fail

  - id: no_new_io_in_models
    kind: delta
    target: effects
    operator: no_new_items
    scope: src.models.*
    severity: hard
    unknown_policy: repair

  - id: complexity_budget
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than_or_equal
    expected: 5
    severity: soft
    unknown_policy: warn

  - id: test_added
    kind: delta
    target: test_surface_delta.new_cases
    operator: not_equals
    expected: []
    severity: hard
    unknown_policy: fail
"""

REFACTOR_SAMPLE_YAML = """
intent: "auth を middleware 化"
change:
  primary_kind: refactor

constraints:
  - id: complexity_should_decrease
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than
    expected: 0
    severity: soft
    unknown_policy: warn
"""


def test_feature_sample_yaml_loads_without_information_loss():
    target_svp = parse_target_svp_yaml(FEATURE_SAMPLE_YAML)

    assert target_svp.intent == "fetch_user_profile を追加"
    assert target_svp.change.primary_kind is ChangeKind.FEATURE
    assert target_svp.change.scope["files"] == ("src/api/users.py", "tests/test_users.py")
    assert len(target_svp.constraints) == 5
    assert all(isinstance(constraint, DeltaConstraint) for constraint in target_svp.constraints)
    assert target_svp.constraints[0].operator is Operator.INCLUDES_ALL
    assert target_svp.constraints[0].expected == ["src.api.users.fetch_user_profile"]


def test_effect_allow_new_policy_loads_without_information_loss():
    target_svp = parse_target_svp_yaml(
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

    assert target_svp.effects is not None
    assert len(target_svp.effects.allow_new) == 1
    assert target_svp.effects.allow_new[0].fqn == "subprocess.run"
    assert target_svp.effects.allow_new[0].effect_class is EffectClass.PROCESS


def test_refactor_sample_yaml_loads_without_information_loss():
    target_svp = parse_target_svp_yaml(REFACTOR_SAMPLE_YAML)

    assert target_svp.intent == "auth を middleware 化"
    assert target_svp.change.primary_kind is ChangeKind.REFACTOR
    assert len(target_svp.constraints) == 1
    assert target_svp.constraints[0].target == "complexity_delta.cyclomatic"
    assert target_svp.constraints[0].operator is Operator.LESS_THAN


def test_invalid_operator_yaml_is_rejected():
    invalid_yaml = FEATURE_SAMPLE_YAML.replace("includes_all", "may_decrease", 1)

    with pytest.raises(ValidationError):
        parse_target_svp_yaml(invalid_yaml)


def test_invalid_change_kind_yaml_is_rejected():
    invalid_yaml = FEATURE_SAMPLE_YAML.replace("primary_kind: feature", "primary_kind: chore")

    with pytest.raises(ValidationError):
        parse_target_svp_yaml(invalid_yaml)


def test_unknown_target_svp_field_is_rejected():
    invalid_yaml = FEATURE_SAMPLE_YAML.replace(
        "constraints:",
        "unexpected_top_level: true\nconstraints:",
    )

    with pytest.raises(ValidationError):
        parse_target_svp_yaml(invalid_yaml)


def test_target_svp_json_round_trip():
    target_svp = parse_target_svp_yaml(FEATURE_SAMPLE_YAML)

    round_tripped = TargetSVP.model_validate_json(target_svp.model_dump_json())

    assert round_tripped == target_svp


def test_target_svp_yaml_round_trip():
    target_svp = parse_target_svp_yaml(REFACTOR_SAMPLE_YAML)

    round_tripped = parse_target_svp_yaml(target_svp_to_yaml(target_svp))

    assert round_tripped == target_svp
