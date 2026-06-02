from __future__ import annotations

import json
from pathlib import Path

from semantic_ci_code.sensor.adapters.pip_audit_adapter import (
    PIP_AUDIT_SENSOR_ADAPTER_VERSION,
    sensor_state_from_pip_audit_json,
    sensor_state_from_pip_audit_scan,
)
from semantic_ci_code.sensor.models import (
    SCASecurityFinding,
    SensorState,
    canonical_id_for_identity,
)
from semantic_ci_code.ssp.adapters.pip_audit import PipAuditScanResult
from semantic_ci_code.ssp.models import SensorOutput, SensorSpec

FIXTURES = Path(__file__).parents[2] / "ssp" / "adapters" / "fixtures"
FIXTURE = FIXTURES / "pip_audit_output_basic.json"


def _basic_payload() -> object:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _state_from_basic_payload() -> SensorState:
    return sensor_state_from_pip_audit_json(
        _basic_payload(),
        requirements=None,
        repo_root=FIXTURES,
        version="2.8.0",
        advisory_db_hash="sha256:advisory-db",
    )


def test_pip_audit_from_json_translates_fixture_to_sensor_state():
    state = _state_from_basic_payload()

    provenance = state.provenance_by_sensor["pip-audit"]
    assert provenance.sensor_id == "pip-audit"
    assert provenance.sensor_version == "2.8.0"
    assert provenance.adapter_version == PIP_AUDIT_SENSOR_ADAPTER_VERSION
    assert provenance.identity_algorithm_version == "v1"
    assert provenance.advisory_db_hash == "sha256:advisory-db"
    assert provenance.status == "complete"
    assert provenance.error_message is None
    assert len(state.findings) == 3

    finding = next(
        item
        for item in state.findings
        if isinstance(item, SCASecurityFinding) and item.advisory_id == "PYSEC-2021-9"
    )
    assert finding.package_name == "django"
    assert finding.installed_version == "3.2.0"
    assert finding.severity == "critical"
    assert finding.identity_components == (
        "v1",
        "sca",
        "pip-audit",
        finding.package_name,
        finding.installed_version,
        finding.advisory_id,
    )
    assert finding.canonical_id == canonical_id_for_identity(finding.identity_components)


def test_pip_audit_error_output_translates_to_error_provenance_and_empty_findings():
    result = PipAuditScanResult(
        output=SensorOutput(
            sensor_id="pip-audit",
            sensor_version="2.8.0",
            status="error",
            findings=(),
            error_message="pip-audit failed",
        ),
        sensor_spec=SensorSpec(
            id="pip-audit",
            version="2.8.0",
            advisory_db_hash="sha256:db",
        ),
    )

    state = sensor_state_from_pip_audit_scan(result)

    provenance = state.provenance_by_sensor["pip-audit"]
    assert provenance.status == "error"
    assert provenance.error_message == "pip-audit failed"
    assert provenance.advisory_db_hash == "sha256:db"
    assert state.findings == ()


def test_pip_audit_translation_is_deterministic_for_same_json():
    first = _state_from_basic_payload().model_dump(mode="json")
    second = _state_from_basic_payload().model_dump(mode="json")

    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(
        second,
        sort_keys=True,
        ensure_ascii=False,
    )
