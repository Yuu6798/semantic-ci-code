from __future__ import annotations

from semantic_ci_code.sensor.models import (
    SASTSecurityFinding,
    SCASecurityFinding,
    SensorProvenance,
    SensorState,
    Suppression,
    canonical_id_for_identity,
)


def sast_components(
    rule_id: str = "python.security.eval",
    *,
    sensor_id: str = "semgrep",
    module_path: str = "src/app.py",
    qualified_name: str = "src.app.handler",
    normalized_text: str = "eval(user_input)",
) -> tuple[str, ...]:
    return (
        "v1",
        "sast",
        sensor_id,
        rule_id,
        module_path,
        qualified_name,
        normalized_text,
    )


def sca_components(
    package_name: str = "django",
    *,
    sensor_id: str = "pip-audit",
    installed_version: str = "3.2.0",
    advisory_id: str = "PYSEC-1",
) -> tuple[str, ...]:
    return (
        "v1",
        "sca",
        sensor_id,
        package_name,
        installed_version,
        advisory_id,
    )


def suppression_components(
    finding_canonical_id: str,
    *,
    reason: str = "accepted test fixture",
) -> tuple[str, ...]:
    return ("v1", "suppression", finding_canonical_id, reason)


def sast_finding(
    rule_id: str = "python.security.eval",
    *,
    sensor_id: str = "semgrep",
    severity: str = "high",
    normalized_text: str = "eval(user_input)",
    qualified_name: str = "src.app.handler",
) -> SASTSecurityFinding:
    components = sast_components(
        rule_id,
        sensor_id=sensor_id,
        normalized_text=normalized_text,
        qualified_name=qualified_name,
    )
    return SASTSecurityFinding(
        sensor_id=sensor_id,
        canonical_id=canonical_id_for_identity(components),
        identity_components=components,
        severity=severity,
        rule_id=rule_id,
        module_path="src/app.py",
        qualified_name=qualified_name,
        normalized_text=normalized_text,
        message="finding",
    )


def sca_finding(
    package_name: str = "django",
    *,
    sensor_id: str = "pip-audit",
    severity: str = "high",
    advisory_id: str = "PYSEC-1",
) -> SCASecurityFinding:
    components = sca_components(
        package_name,
        sensor_id=sensor_id,
        advisory_id=advisory_id,
    )
    return SCASecurityFinding(
        sensor_id=sensor_id,
        canonical_id=canonical_id_for_identity(components),
        identity_components=components,
        severity=severity,
        package_name=package_name,
        installed_version="3.2.0",
        advisory_id=advisory_id,
        message="advisory",
    )


def suppression_for(
    finding_canonical_id: str,
    *,
    reason: str = "accepted test fixture",
) -> Suppression:
    components = suppression_components(finding_canonical_id, reason=reason)
    return Suppression(
        canonical_id=canonical_id_for_identity(components),
        identity_components=components,
        finding_canonical_id=finding_canonical_id,
        reason=reason,
    )


def provenance(
    sensor_id: str = "semgrep",
    *,
    ruleset_hash: str | None = "sha256:rules",
    advisory_db_hash: str | None = None,
    adapter_version: str = "adapter-1",
    sensor_version: str = "tool-1",
    status: str = "complete",
    error_message: str | None = None,
) -> SensorProvenance:
    return SensorProvenance(
        sensor_id=sensor_id,
        sensor_version=sensor_version,
        adapter_version=adapter_version,
        ruleset_hash=ruleset_hash,
        advisory_db_hash=advisory_db_hash,
        status=status,
        error_message=error_message,
    )


def sensor_state(
    *,
    provenances: tuple[SensorProvenance, ...] | None = None,
    findings: tuple[SASTSecurityFinding | SCASecurityFinding, ...] = (),
    suppressions: tuple[Suppression, ...] = (),
) -> SensorState:
    if provenances is None:
        sensors = sorted({finding.sensor_id for finding in findings} or {"semgrep"})
        provenances = tuple(provenance(sensor_id=sensor_id) for sensor_id in sensors)
    return SensorState(
        provenance_by_sensor={item.sensor_id: item for item in provenances},
        findings=tuple(sorted(findings, key=lambda finding: finding.canonical_id)),
        suppressions={item.canonical_id: item for item in suppressions},
    )
