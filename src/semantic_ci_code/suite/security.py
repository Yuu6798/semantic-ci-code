"""Suite-level security policy evaluation."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from semantic_ci_code.framework.security_policy import ScannerPolicy, SecurityPolicy, Suppression
from semantic_ci_code.sensor.delta import DEFAULT_DRIFT_FIELDS, compute_security_delta
from semantic_ci_code.sensor.models import (
    FAIL_SEVERITIES,
    SASTSecurityFinding,
    SecurityDeltaStatus,
    SecurityFinding,
    SensorState,
    aggregate_status,
    canonical_id_for_identity,
)

_ALWAYS_DRIFT_FIELDS = frozenset({"adapter_version", "identity_algorithm_version"})


def evaluate_security(
    policy: SecurityPolicy | None,
    baseline: SensorState,
    candidate: SensorState,
    *,
    as_of: dt.date,
) -> SecurityDeltaStatus:
    """Evaluate security policy against two SensorState values."""

    suppressions = policy.suppressions if policy is not None else ()
    _validate_suppressions(suppressions)
    active_suppression_ids = _active_suppression_ids(suppressions, as_of=as_of)
    delta = compute_security_delta(
        baseline,
        candidate,
        drift_fields=_drift_fields_for_scanner(policy.scanner if policy is not None else None),
    )

    statuses: list[SecurityDeltaStatus] = []
    total_added_count = 0
    for sensor_id in sorted(delta.deltas_by_sensor):
        per_sensor = delta.deltas_by_sensor[sensor_id]
        if per_sensor.status == "unknown":
            statuses.append("unknown")
            continue
        added = tuple(
            finding
            for finding in per_sensor.added
            if finding.canonical_id not in active_suppression_ids
        )
        total_added_count += len(added)
        statuses.append(_status_for_added(policy, added))

    if _violates_global_count_policy(policy, total_added_count):
        statuses.append("fail")
    return aggregate_status(statuses)


def _drift_fields_for_scanner(scanner: ScannerPolicy | None) -> frozenset[str]:
    if scanner is None:
        return DEFAULT_DRIFT_FIELDS

    fields = set(_ALWAYS_DRIFT_FIELDS)
    if scanner.require_same_ruleset:
        fields.add("ruleset_hash")
    if scanner.require_same_sensor_version:
        fields.add("sensor_version")
    if scanner.require_same_advisory_db:
        fields.add("advisory_db_hash")
    return frozenset(fields)


def _validate_suppressions(suppressions: Iterable[Suppression]) -> None:
    for suppression in suppressions:
        expected = canonical_id_for_identity(suppression.identity_components)
        if suppression.canonical_id != expected:
            raise ValueError("suppression canonical_id does not match identity_components")


def _active_suppression_ids(
    suppressions: Iterable[Suppression],
    *,
    as_of: dt.date,
) -> frozenset[str]:
    return frozenset(
        suppression.canonical_id for suppression in suppressions if suppression.expires >= as_of
    )


def _status_for_added(
    policy: SecurityPolicy | None,
    added: tuple[SecurityFinding, ...],
) -> SecurityDeltaStatus:
    return "fail" if _violates_finding_policy(policy, added) else "pass"


def _violates_finding_policy(
    policy: SecurityPolicy | None,
    added: tuple[SecurityFinding, ...],
) -> bool:
    if any(finding.severity in _effective_fail_severities(policy) for finding in added):
        return True

    denied = policy.rules.deny_added if policy is not None and policy.rules is not None else ()
    if denied and any(
        isinstance(finding, SASTSecurityFinding) and finding.rule_id in denied for finding in added
    ):
        return True
    return False


def _effective_fail_severities(policy: SecurityPolicy | None) -> frozenset[str]:
    if policy is None:
        return FAIL_SEVERITIES
    added_policy = policy.findings.added if policy.findings is not None else None
    if added_policy is not None:
        severity = added_policy.severity
        if severity is not None and severity.not_in:
            return frozenset(severity.not_in)
    return FAIL_SEVERITIES


def _violates_global_count_policy(policy: SecurityPolicy | None, total_added_count: int) -> bool:
    if policy is None or policy.findings is None or policy.findings.added is None:
        return False
    max_count = policy.findings.added.max_count
    return max_count is not None and total_added_count > max_count
