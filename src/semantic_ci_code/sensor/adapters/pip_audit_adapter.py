"""Translate SSP pip-audit scan results into core SensorState values."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from semantic_ci_code.sensor.models import (
    SCASecurityFinding,
    SensorProvenance,
    SensorState,
    canonical_id_for_identity,
)
from semantic_ci_code.ssp.adapters.pip_audit import PipAuditAdapter, PipAuditScanResult
from semantic_ci_code.ssp.models import SCAFinding, SensorOutput, SensorSpec

PIP_AUDIT_SENSOR_ADAPTER_VERSION = "sensor-pip-audit-adapter-1"


def sensor_state_from_pip_audit_json(
    payload: Any,
    *,
    requirements: Path | None,
    repo_root: Path,
    version: str = "",
    advisory_db_hash: str | None = None,
) -> SensorState:
    """Build SensorState from recorded pip-audit JSON via the SSP adapter."""

    result = PipAuditAdapter().from_json(
        payload,
        requirements=requirements,
        repo_root=repo_root,
        version=version,
        advisory_db_hash=advisory_db_hash,
    )
    return sensor_state_from_pip_audit_scan(result)


def sensor_state_from_pip_audit_scan(result: PipAuditScanResult) -> SensorState:
    """Translate an SSP pip-audit scan result into SensorState."""

    return _sensor_state_from_output(
        result.output,
        sensor_spec=result.sensor_spec,
    )


def _sensor_state_from_output(output: SensorOutput, *, sensor_spec: SensorSpec) -> SensorState:
    provenance = _provenance_from_pip_audit(output, sensor_spec=sensor_spec)
    if provenance.status != "complete":
        findings: tuple[SCASecurityFinding, ...] = ()
    else:
        findings = _dedup_by_canonical_id(
            _finding_from_sca(finding, sensor_id=output.sensor_id)
            for finding in output.findings
            if isinstance(finding, SCAFinding)
        )
    return SensorState(
        provenance_by_sensor={output.sensor_id: provenance},
        findings=findings,
    )


def _provenance_from_pip_audit(
    output: SensorOutput,
    *,
    sensor_spec: SensorSpec,
) -> SensorProvenance:
    if output.status == "error":
        return SensorProvenance(
            sensor_id=output.sensor_id,
            sensor_version=output.sensor_version,
            adapter_version=PIP_AUDIT_SENSOR_ADAPTER_VERSION,
            identity_algorithm_version="v1",
            ruleset_hash=sensor_spec.ruleset_hash,
            advisory_db_hash=sensor_spec.advisory_db_hash,
            status="error",
            error_message=output.error_message or "pip-audit sensor error",
        )
    return SensorProvenance(
        sensor_id=output.sensor_id,
        sensor_version=output.sensor_version,
        adapter_version=PIP_AUDIT_SENSOR_ADAPTER_VERSION,
        identity_algorithm_version="v1",
        ruleset_hash=sensor_spec.ruleset_hash,
        advisory_db_hash=sensor_spec.advisory_db_hash,
        status="complete",
        error_message=None,
    )


def _finding_from_sca(finding: SCAFinding, *, sensor_id: str) -> SCASecurityFinding:
    identity_components = (
        "v1",
        "sca",
        sensor_id,
        finding.package_name,
        finding.installed_version,
        finding.advisory_id,
    )
    return SCASecurityFinding(
        category="sca",
        sensor_id=sensor_id,
        canonical_id=canonical_id_for_identity(identity_components),
        identity_components=identity_components,
        severity=finding.severity,
        message=finding.message,
        package_name=finding.package_name,
        installed_version=finding.installed_version,
        advisory_id=finding.advisory_id,
    )


def _dedup_by_canonical_id(
    findings: Iterable[SCASecurityFinding],
) -> tuple[SCASecurityFinding, ...]:
    by_id: dict[str, SCASecurityFinding] = {}
    for finding in findings:
        by_id.setdefault(finding.canonical_id, finding)
    return tuple(sorted(by_id.values(), key=lambda finding: finding.canonical_id))
