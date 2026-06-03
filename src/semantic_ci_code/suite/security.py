"""Suite-level security policy evaluation."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from semantic_ci_code.framework.security_policy import ScannerPolicy, SecurityPolicy, Suppression
from semantic_ci_code.sensor.delta import compute_security_delta
from semantic_ci_code.sensor.models import (
    _FAIL_SEVERITIES,
    SASTSecurityFinding,
    SecurityDeltaStatus,
    SecurityFinding,
    SensorState,
    aggregate_status,
    canonical_id_for_identity,
)

_ALWAYS_DRIFT_FIELDS = frozenset({"adapter_version", "identity_algorithm_version"})
_DEFAULT_DRIFT_FIELDS = frozenset(
    {
        "adapter_version",
        "identity_algorithm_version",
        "ruleset_hash",
        "advisory_db_hash",
    }
)


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
        statuses.append(_status_for_added(policy, added))
    return aggregate_status(statuses)


def _drift_fields_for_scanner(scanner: ScannerPolicy | None) -> frozenset[str]:
    if scanner is None:
        return _DEFAULT_DRIFT_FIELDS

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
    if _has_user_gate(policy):
        return "fail" if _violates_user_policy(policy, added) else "pass"
    return "fail" if any(finding.severity in _FAIL_SEVERITIES for finding in added) else "pass"


def _has_user_gate(policy: SecurityPolicy | None) -> bool:
    if policy is None:
        return False
    added = policy.findings.added if policy.findings is not None else None
    severity = added.severity if added is not None else None
    return bool(
        (severity is not None and severity.not_in)
        or (added is not None and added.max_count is not None)
        or (policy.rules is not None and policy.rules.deny_added)
    )


def _violates_user_policy(
    policy: SecurityPolicy | None,
    added: tuple[SecurityFinding, ...],
) -> bool:
    if policy is None:
        return False

    added_policy = policy.findings.added if policy.findings is not None else None
    if added_policy is not None:
        severity = added_policy.severity
        if severity is not None and any(finding.severity in severity.not_in for finding in added):
            return True
        if added_policy.max_count is not None and len(added) > added_policy.max_count:
            return True

    denied = policy.rules.deny_added if policy.rules is not None else ()
    if denied and any(
        isinstance(finding, SASTSecurityFinding) and finding.rule_id in denied for finding in added
    ):
        return True
    return False
