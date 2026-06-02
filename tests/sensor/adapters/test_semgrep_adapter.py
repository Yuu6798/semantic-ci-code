from __future__ import annotations

import json
from pathlib import Path

from semantic_ci_code.sensor.adapters.semgrep_adapter import (
    SEMGREP_SENSOR_ADAPTER_VERSION,
    sensor_state_from_semgrep_json,
)
from semantic_ci_code.sensor.models import (
    SASTSecurityFinding,
    SensorState,
    canonical_id_for_identity,
)

FIXTURES = Path(__file__).parents[2] / "ssp" / "adapters" / "fixtures"
RULESET = FIXTURES / "rules.yml"


def _basic_payload() -> dict[str, object]:
    return json.loads((FIXTURES / "semgrep_output_basic.json").read_text(encoding="utf-8"))


def _state_from_basic_payload() -> SensorState:
    return sensor_state_from_semgrep_json(
        _basic_payload(),
        target_dir=FIXTURES / "src",
        ruleset=RULESET,
        repo_root=FIXTURES,
    )


def test_semgrep_from_json_translates_fixture_to_sensor_state():
    state = _state_from_basic_payload()

    provenance = state.provenance_by_sensor["semgrep"]
    assert provenance.sensor_id == "semgrep"
    assert provenance.sensor_version == "1.80.0"
    assert provenance.adapter_version == SEMGREP_SENSOR_ADAPTER_VERSION
    assert provenance.identity_algorithm_version == "v1"
    assert provenance.status == "complete"
    assert provenance.error_message is None
    assert provenance.ruleset_hash is not None
    assert len(state.findings) == 3

    finding = next(
        item
        for item in state.findings
        if isinstance(item, SASTSecurityFinding)
        and item.rule_id == "python.security.hardcoded-password"
    )
    assert finding.module_path == "src/app.py"
    assert finding.qualified_name == "src.app.UserService.create_user"
    assert finding.normalized_text == "password ='hunter2'"
    assert finding.severity == "medium"
    assert finding.ordinal == 0
    assert finding.source_span is not None
    assert finding.source_span.start_line == 3
    assert finding.identity_components == (
        "v1",
        "sast",
        "semgrep",
        finding.rule_id,
        finding.module_path,
        finding.qualified_name,
        finding.normalized_text,
        str(finding.ordinal),
    )
    assert finding.canonical_id == canonical_id_for_identity(finding.identity_components)


def test_semgrep_duplicate_group_gets_distinct_ordinals_and_canonical_ids(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text(
        "def handler():\n    danger()\n    danger()\n",
        encoding="utf-8",
    )
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {
        "version": "1.80.0",
        "paths": {"scanned": ["src/app.py"]},
        "results": [
            {
                "check_id": "python.security.danger",
                "path": "src/app.py",
                "start": {"line": 3, "col": 5},
                "end": {"line": 3, "col": 13},
                "extra": {"severity": "ERROR", "lines": "danger()"},
            },
            {
                "check_id": "python.security.danger",
                "path": "src/app.py",
                "start": {"line": 2, "col": 5},
                "end": {"line": 2, "col": 13},
                "extra": {"severity": "ERROR", "lines": "danger()"},
            },
        ],
    }

    state = sensor_state_from_semgrep_json(
        payload,
        target_dir=src,
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    findings = tuple(item for item in state.findings if isinstance(item, SASTSecurityFinding))
    assert len(findings) == 2
    assert sorted(finding.ordinal for finding in findings) == [0, 1]
    assert len({finding.canonical_id for finding in findings}) == 2
    assert all(finding.identity_components[-1] == str(finding.ordinal) for finding in findings)


def test_semgrep_error_output_translates_to_error_provenance_and_empty_findings(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {
        "version": "1.80.0",
        "errors": [{"message": "failed to parse"}],
        "results": [],
    }

    state = sensor_state_from_semgrep_json(
        payload,
        target_dir=src,
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    provenance = state.provenance_by_sensor["semgrep"]
    assert provenance.status == "error"
    assert "failed to parse" in (provenance.error_message or "")
    assert state.findings == ()


def test_semgrep_translation_is_deterministic_for_same_json():
    first = _state_from_basic_payload().model_dump(mode="json")
    second = _state_from_basic_payload().model_dump(mode="json")

    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(
        second,
        sort_keys=True,
        ensure_ascii=False,
    )
