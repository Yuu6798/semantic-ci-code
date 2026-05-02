from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.framework.target_svp import TargetSVP, parse_target_svp_yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_SCHEMA_PATH = REPO_ROOT / "src" / "semantic_ci_code" / "schemas" / "target_svp.schema.json"
CODE_STATE_SCHEMA_PATH = (
    REPO_ROOT / "src" / "semantic_ci_code" / "schemas" / "code_state.schema.json"
)

FEATURE_SCHEMA_SAMPLE_YAML = """
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
"""


def test_committed_json_schemas_are_valid_json_schema_documents():
    for path in (TARGET_SCHEMA_PATH, CODE_STATE_SCHEMA_PATH):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)


def test_target_svp_schema_validates_sample_yaml():
    schema = json.loads(TARGET_SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = yaml.safe_load(FEATURE_SCHEMA_SAMPLE_YAML)

    Draft202012Validator(schema).validate(payload)


def test_code_state_json_and_yaml_round_trip():
    state = CodeState(
        api_surface=[
            {
                "fqn": "src.api.users.fetch_user_profile",
                "kind": "function",
                "signature": "() -> UserProfile",
                "visibility": "public",
            }
        ],
        coverage=None,
        python_specific={"decorators": ["router.get"]},
    )

    json_round_trip = CodeState.model_validate_json(state.model_dump_json())
    yaml_round_trip = CodeState.model_validate(
        yaml.safe_load(yaml.safe_dump(state.model_dump(mode="json"), sort_keys=False))
    )

    assert json_round_trip == state
    assert yaml_round_trip == state


def test_target_svp_json_and_yaml_round_trip():
    target_svp = parse_target_svp_yaml(FEATURE_SCHEMA_SAMPLE_YAML)

    json_round_trip = TargetSVP.model_validate_json(target_svp.model_dump_json())
    yaml_round_trip = parse_target_svp_yaml(
        yaml.safe_dump(target_svp.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
    )

    assert json_round_trip == target_svp
    assert yaml_round_trip == target_svp


def test_json_schema_drift_check_passes():
    subprocess.run(
        [sys.executable, "scripts/regen_schemas.py", "--check"],
        cwd=REPO_ROOT,
        check=True,
    )
