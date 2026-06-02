"""Canonical-id based security sensor delta engine."""

from __future__ import annotations

from semantic_ci_code.sensor.models import (
    PerSensorDelta,
    SecurityDelta,
    SecurityFinding,
    SensorProvenance,
    SensorState,
    aggregate_status,
)


def compute_security_delta(baseline: SensorState, candidate: SensorState) -> SecurityDelta:
    """Compute a security delta from two hand-built SensorState values."""

    deltas: dict[str, PerSensorDelta] = {}
    for sensor_id in sorted(
        set(baseline.provenance_by_sensor) | set(candidate.provenance_by_sensor)
    ):
        baseline_provenance = baseline.provenance_by_sensor.get(sensor_id)
        candidate_provenance = candidate.provenance_by_sensor.get(sensor_id)
        deltas[sensor_id] = _per_sensor_delta(
            sensor_id,
            baseline_provenance=baseline_provenance,
            candidate_provenance=candidate_provenance,
            baseline_findings=_findings_for_sensor(baseline, sensor_id),
            candidate_findings=_findings_for_sensor(candidate, sensor_id),
        )
    return SecurityDelta(
        per_sensor=deltas,
        aggregate_status=aggregate_status(delta.status for delta in deltas.values()),
    )


def _per_sensor_delta(
    sensor_id: str,
    *,
    baseline_provenance: SensorProvenance | None,
    candidate_provenance: SensorProvenance | None,
    baseline_findings: tuple[SecurityFinding, ...],
    candidate_findings: tuple[SecurityFinding, ...],
) -> PerSensorDelta:
    # G-1 uses the default Phase G policy: ruleset/advisory DB/adapter/identity
    # drift is comparison-blocking, while sensor_version drift is tolerated.
    drift_reason = _provenance_drift_reason(baseline_provenance, candidate_provenance)
    if drift_reason is not None:
        return PerSensorDelta(
            sensor_id=sensor_id,
            status="unknown",
            added=(),
            removed=(),
            unchanged_count=0,
            provenance_changed=True,
            error_message=drift_reason,
        )
    if baseline_provenance.status != "complete" or candidate_provenance.status != "complete":
        return PerSensorDelta(
            sensor_id=sensor_id,
            status="unknown",
            unchanged_count=0,
            error_message=(
                candidate_provenance.error_message
                or baseline_provenance.error_message
                or "sensor did not complete"
            ),
        )

    baseline_by_id = {finding.canonical_id: finding for finding in baseline_findings}
    candidate_by_id = {finding.canonical_id: finding for finding in candidate_findings}
    baseline_ids = set(baseline_by_id)
    candidate_ids = set(candidate_by_id)
    added = tuple(candidate_by_id[item] for item in sorted(candidate_ids - baseline_ids))
    removed = tuple(baseline_by_id[item] for item in sorted(baseline_ids - candidate_ids))
    status = "fail" if any(finding.severity != "info" for finding in added) else "pass"
    return PerSensorDelta(
        sensor_id=sensor_id,
        status=status,
        added=added,
        removed=removed,
        unchanged_count=len(baseline_ids & candidate_ids),
    )


def _findings_for_sensor(state: SensorState, sensor_id: str) -> tuple[SecurityFinding, ...]:
    return tuple(finding for finding in state.findings if finding.sensor_id == sensor_id)


def _provenance_drift_reason(
    baseline: SensorProvenance | None,
    candidate: SensorProvenance | None,
) -> str | None:
    if baseline is None or candidate is None:
        return "sensor exists on only one side"
    drift_fields = (
        "ruleset_hash",
        "advisory_db_hash",
        "adapter_version",
        "identity_algorithm_version",
    )
    changed = [
        field for field in drift_fields if getattr(baseline, field) != getattr(candidate, field)
    ]
    if not changed:
        return None
    return "sensor provenance changed: " + ", ".join(changed)
