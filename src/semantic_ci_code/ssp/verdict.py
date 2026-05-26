"""SSP v0.1 verdict aggregation."""

from __future__ import annotations

from collections.abc import Iterable

from semantic_ci_code.ssp.models import SSPDelta, SSPResult, SSPVerdict

_FAIL_SEVERITIES = frozenset({"critical", "high", "medium", "low"})


def verdict_for_delta(delta: SSPDelta) -> SSPResult:
    if delta.status == "unknown":
        return "unknown"
    if any(finding.severity in _FAIL_SEVERITIES for finding in delta.added):
        return "fail"
    return "pass"


def aggregate_verdict(verdicts: Iterable[SSPResult]) -> SSPResult:
    values = tuple(verdicts)
    if "unknown" in values:
        return "unknown"
    if "fail" in values:
        return "fail"
    return "pass"


def build_verdict(deltas: Iterable[SSPDelta]) -> SSPVerdict:
    sensor_verdicts = {
        delta.sensor_id: delta.status for delta in sorted(deltas, key=lambda item: item.sensor_id)
    }
    return SSPVerdict(
        sensor_verdicts=sensor_verdicts,
        aggregate_verdict=aggregate_verdict(sensor_verdicts.values()),
    )
