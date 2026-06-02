"""Translate SSP Semgrep scan results into core SensorState values."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from semantic_ci_code.sensor.models import (
    SASTSecurityFinding,
    SensorProvenance,
    SensorState,
    SourceSpan,
    canonical_id_for_identity,
)
from semantic_ci_code.ssp.adapters.semgrep import SemgrepAdapter, SemgrepScanResult
from semantic_ci_code.ssp.delta import assign_sast_ordinals
from semantic_ci_code.ssp.models import SASTFinding, SensorOutput, SensorSpec

SEMGREP_SENSOR_ADAPTER_VERSION = "sensor-semgrep-adapter-1"


def sensor_state_from_semgrep_json(
    payload: Mapping[str, Any],
    *,
    target_dir: Path,
    ruleset: Path,
    repo_root: Path,
    ruleset_hash: str | None = None,
) -> SensorState:
    """Build SensorState from recorded Semgrep JSON via the SSP adapter."""

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=target_dir,
        ruleset=ruleset,
        repo_root=repo_root,
        ruleset_hash=ruleset_hash,
    )
    return sensor_state_from_semgrep_scan(result)


def sensor_state_from_semgrep_scan(result: SemgrepScanResult) -> SensorState:
    """Translate an SSP Semgrep scan result into SensorState."""

    return _sensor_state_from_output(
        result.output,
        sensor_spec=result.sensor_spec,
    )


def _sensor_state_from_output(output: SensorOutput, *, sensor_spec: SensorSpec) -> SensorState:
    provenance = _provenance_from_semgrep(output, sensor_spec=sensor_spec)
    if provenance.status != "complete":
        findings: tuple[SASTSecurityFinding, ...] = ()
    else:
        sast_findings = tuple(
            finding for finding in output.findings if isinstance(finding, SASTFinding)
        )
        assigned = assign_sast_ordinals(sast_findings)
        findings = tuple(
            sorted(
                (_finding_from_sast(finding, sensor_id=output.sensor_id) for finding in assigned),
                key=lambda finding: finding.canonical_id,
            )
        )
    return SensorState(
        provenance_by_sensor={output.sensor_id: provenance},
        findings=findings,
    )


def _provenance_from_semgrep(
    output: SensorOutput,
    *,
    sensor_spec: SensorSpec,
) -> SensorProvenance:
    if output.status == "error":
        return SensorProvenance(
            sensor_id=output.sensor_id,
            sensor_version=output.sensor_version,
            adapter_version=SEMGREP_SENSOR_ADAPTER_VERSION,
            identity_algorithm_version="v1",
            ruleset_hash=sensor_spec.ruleset_hash,
            advisory_db_hash=sensor_spec.advisory_db_hash,
            status="error",
            error_message=output.error_message or "semgrep sensor error",
        )
    return SensorProvenance(
        sensor_id=output.sensor_id,
        sensor_version=output.sensor_version,
        adapter_version=SEMGREP_SENSOR_ADAPTER_VERSION,
        identity_algorithm_version="v1",
        ruleset_hash=sensor_spec.ruleset_hash,
        advisory_db_hash=sensor_spec.advisory_db_hash,
        status="complete",
        error_message=None,
    )


def _finding_from_sast(finding: SASTFinding, *, sensor_id: str) -> SASTSecurityFinding:
    ordinal = finding.ordinal if finding.ordinal is not None else 0
    identity_components = (
        "v1",
        "sast",
        sensor_id,
        finding.rule_id,
        finding.module_path.replace("\\", "/"),
        finding.qualified_name,
        finding.normalized_text,
        str(ordinal),
    )
    return SASTSecurityFinding(
        category="sast",
        sensor_id=sensor_id,
        canonical_id=canonical_id_for_identity(identity_components),
        identity_components=identity_components,
        severity=finding.severity,
        message=finding.message,
        rule_id=finding.rule_id,
        module_path=finding.module_path,
        qualified_name=finding.qualified_name,
        normalized_text=finding.normalized_text,
        ordinal=ordinal,
        source_span=_source_span(finding),
    )


def _source_span(finding: SASTFinding) -> SourceSpan | None:
    if finding.source_span is None:
        return None
    return SourceSpan(
        start_line=finding.source_span.start_line,
        end_line=finding.source_span.end_line,
        start_col=finding.source_span.start_col,
        end_col=finding.source_span.end_col,
    )
