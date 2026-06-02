from __future__ import annotations

import pytest
from pydantic import ValidationError

from semantic_ci_code.sensor.models import (
    PerSensorDelta,
    SASTSecurityFinding,
    SCASecurityFinding,
    SecurityDelta,
    SensorProvenance,
    SensorState,
    SourceSpan,
    canonical_id_for_identity,
)

from .helpers import (
    provenance,
    sast_components,
    sast_finding,
    sca_components,
    sca_finding,
    sensor_state,
)


def test_sensor_provenance_accepts_complete_without_error():
    assert provenance().status == "complete"


@pytest.mark.parametrize(
    "payload",
    [
        {"sensor_id": "semgrep", "status": "complete", "error_message": "boom"},
        {"sensor_id": "semgrep", "status": "error"},
        {"sensor_id": "semgrep", "status": "timeout"},
        {"sensor_id": "semgrep", "status": "skipped"},
    ],
)
def test_sensor_provenance_status_error_message_invariant_rejects(payload: dict[str, str]):
    with pytest.raises(ValidationError):
        SensorProvenance.model_validate(payload)


def test_security_finding_accepts_sast_and_sca_identity_shapes():
    assert sast_finding().identity_components == sast_components()
    assert sca_finding().identity_components == sca_components()


def test_sast_finding_accepts_optional_source_span():
    finding = sast_finding()
    payload = finding.model_dump(mode="json")
    payload["source_span"] = {
        "start_line": 10,
        "end_line": 11,
        "start_col": 0,
        "end_col": 8,
    }

    parsed = SASTSecurityFinding.model_validate(payload)

    assert parsed.source_span == SourceSpan(
        start_line=10,
        end_line=11,
        start_col=0,
        end_col=8,
    )


def test_source_span_rejects_invalid_bounds():
    with pytest.raises(ValidationError):
        SourceSpan(start_line=0, end_line=1, start_col=0, end_col=0)
    with pytest.raises(ValidationError):
        SourceSpan(start_line=1, end_line=1, start_col=-1, end_col=0)


def test_security_finding_rejects_field_identity_mismatch():
    finding = sast_finding()
    payload = finding.model_dump(mode="json")
    payload["rule_id"] = "different"

    with pytest.raises(ValidationError, match="identity_components"):
        SASTSecurityFinding.model_validate(payload)


def test_security_finding_rejects_canonical_id_tampering():
    finding = sca_finding()
    payload = finding.model_dump(mode="json")
    payload["canonical_id"] = canonical_id_for_identity(sca_components("flask"))

    with pytest.raises(ValidationError, match="canonical_id"):
        SCASecurityFinding.model_validate(payload)


def test_security_finding_rejects_version_prefix_tampering():
    finding = sast_finding()
    payload = finding.model_dump(mode="json")
    payload["canonical_id"] = "v2:" + finding.canonical_id.split(":", 1)[1]

    with pytest.raises(ValidationError):
        SASTSecurityFinding.model_validate(payload)


def test_sast_finding_normalizes_windows_module_path_before_identity_validation():
    raw_components = sast_components(module_path="src\\app.py")
    normalized_components = sast_components(module_path="src/app.py")
    payload = {
        "category": "sast",
        "sensor_id": "semgrep",
        "canonical_id": canonical_id_for_identity(normalized_components),
        "identity_components": raw_components,
        "severity": "high",
        "message": "finding",
        "rule_id": "python.security.eval",
        "module_path": "src\\app.py",
        "qualified_name": "src.app.handler",
        "normalized_text": "eval(user_input)",
        "ordinal": 0,
    }

    finding = SASTSecurityFinding.model_validate(payload)

    assert finding.module_path == "src/app.py"
    assert finding.identity_components == normalized_components


def test_sast_finding_rejects_canonical_id_hashed_from_windows_module_path():
    raw_components = sast_components(module_path="src\\app.py")
    payload = {
        "category": "sast",
        "sensor_id": "semgrep",
        "canonical_id": canonical_id_for_identity(raw_components),
        "identity_components": raw_components,
        "severity": "high",
        "message": "finding",
        "rule_id": "python.security.eval",
        "module_path": "src\\app.py",
        "qualified_name": "src.app.handler",
        "normalized_text": "eval(user_input)",
        "ordinal": 0,
    }

    with pytest.raises(ValidationError, match="canonical_id"):
        SASTSecurityFinding.model_validate(payload)


def test_per_sensor_delta_accepts_pass_fail_and_unknown_shapes():
    info = sast_finding("info.rule", severity="info")
    failing = sast_finding("fail.rule", severity="high")

    assert PerSensorDelta(
        sensor_id="semgrep",
        status="pass",
        added=(info,),
        unchanged_count=0,
    )
    assert PerSensorDelta(
        sensor_id="semgrep",
        status="fail",
        added=(failing,),
        unchanged_count=0,
    )
    assert PerSensorDelta(
        sensor_id="semgrep",
        status="unknown",
        unchanged_count=0,
        provenance_changed=True,
        error_message="ruleset changed",
    )


@pytest.mark.parametrize(
    "delta",
    [
        {
            "sensor_id": "semgrep",
            "status": "pass",
            "added": (sast_finding(severity="high"),),
            "unchanged_count": 0,
        },
        {
            "sensor_id": "semgrep",
            "status": "fail",
            "added": (sast_finding(severity="info"),),
            "unchanged_count": 0,
        },
        {
            "sensor_id": "semgrep",
            "status": "unknown",
            "unchanged_count": 0,
        },
        {
            "sensor_id": "semgrep",
            "status": "pass",
            "unchanged_count": 0,
            "provenance_changed": True,
        },
        {
            "sensor_id": "semgrep",
            "status": "pass",
            "added": (sast_finding(sensor_id="other"),),
            "unchanged_count": 0,
        },
    ],
)
def test_per_sensor_delta_rejects_invalid_policy_floor_and_references(
    delta: dict[str, object],
):
    with pytest.raises(ValidationError):
        PerSensorDelta(**delta)


def test_security_delta_accepts_aggregate_precedence():
    delta = SecurityDelta(
        deltas_by_sensor={
            "semgrep": PerSensorDelta(
                sensor_id="semgrep",
                status="unknown",
                unchanged_count=0,
                error_message="sensor error",
            ),
            "pip-audit": PerSensorDelta(
                sensor_id="pip-audit",
                status="fail",
                added=(sca_finding(),),
                unchanged_count=0,
            ),
        },
        aggregate_status="unknown",
    )

    assert delta.aggregate_status == "unknown"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "deltas_by_sensor": {
                "wrong": {
                    "sensor_id": "semgrep",
                    "status": "pass",
                    "unchanged_count": 0,
                }
            },
            "aggregate_status": "pass",
        },
        {
            "deltas_by_sensor": {
                "semgrep": {
                    "sensor_id": "semgrep",
                    "status": "fail",
                    "added": (sast_finding(),),
                    "unchanged_count": 0,
                }
            },
            "aggregate_status": "pass",
        },
    ],
)
def test_security_delta_rejects_key_or_aggregate_mismatch(payload: dict[str, object]):
    with pytest.raises(ValidationError):
        SecurityDelta.model_validate(payload)


def test_sensor_state_accepts_sorted_findings():
    finding = sast_finding()
    state = sensor_state(findings=(finding,))

    assert state.findings == (finding,)


def test_sensor_state_rejects_provenance_key_mismatch():
    with pytest.raises(ValidationError, match="provenance_by_sensor"):
        SensorState(provenance_by_sensor={"wrong": provenance()}, findings=())


def test_sensor_state_rejects_unknown_finding_sensor():
    with pytest.raises(ValidationError, match="unknown sensor_id"):
        SensorState(provenance_by_sensor={}, findings=(sast_finding(),))


def test_sensor_state_rejects_identity_algorithm_mismatch():
    finding = sast_finding()
    with pytest.raises(ValidationError, match="identity_algorithm_version"):
        SensorState(
            identity_algorithm_version="v1",
            provenance_by_sensor={
                "semgrep": provenance(sensor_id="semgrep").model_copy(
                    update={"identity_algorithm_version": "v2"}
                )
            },
            findings=(finding,),
        )


def test_sensor_state_rejects_unsorted_findings():
    first = sast_finding("z.rule")
    second = sast_finding("a.rule")
    findings = tuple(sorted((first, second), key=lambda finding: finding.canonical_id))

    with pytest.raises(ValidationError, match="sorted"):
        SensorState(
            provenance_by_sensor={"semgrep": provenance()},
            findings=tuple(reversed(findings)),
        )


def test_sensor_state_rejects_duplicate_canonical_ids():
    finding = sast_finding()

    with pytest.raises(ValidationError, match="unique"):
        SensorState(
            provenance_by_sensor={"semgrep": provenance()},
            findings=(finding, finding),
        )


def test_sensor_state_rejects_findings_for_non_complete_sensor():
    finding = sast_finding()

    with pytest.raises(ValidationError, match="non-complete"):
        SensorState(
            provenance_by_sensor={
                "semgrep": provenance(status="error", error_message="tool failed")
            },
            findings=(finding,),
        )
