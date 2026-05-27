"""Human-readable formatting for SSP envelopes."""

from __future__ import annotations

from semantic_ci_code.ssp.models import Finding, SASTFinding, SCAFinding, SSPEnvelope


def format_human(envelope: SSPEnvelope) -> str:
    lines: list[str] = [
        "SSP summary",
        f"aggregate verdict: {envelope.aggregate_verdict}",
        "",
    ]
    for sensor_id in sorted(envelope.deltas_by_sensor):
        delta = envelope.deltas_by_sensor[sensor_id]
        lines.extend(
            [
                f"sensor: {sensor_id}",
                f"  verdict: {delta.status}",
                f"  added: {len(delta.added)}",
                f"  removed: {len(delta.removed)}",
                f"  unchanged: {delta.unchanged_count}",
            ]
        )
        if delta.error_message:
            lines.append(f"  error: {delta.error_message}")
        if delta.added:
            lines.append("  added findings:")
            lines.extend(f"    - {_finding_label(finding)}" for finding in delta.added)
        if delta.removed:
            lines.append("  removed findings:")
            lines.extend(f"    - {_finding_label(finding)}" for finding in delta.removed)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _finding_label(finding: Finding) -> str:
    if isinstance(finding, SASTFinding):
        location = finding.module_path
        if finding.source_span is not None:
            location = f"{location}:{finding.source_span.start_line}"
        return f"[{finding.severity}] {finding.rule_id} at {location} - {finding.message}"
    if isinstance(finding, SCAFinding):
        return (
            f"[{finding.severity}] {finding.package_name} "
            f"{finding.installed_version} {finding.advisory_id} - {finding.message}"
        )
    return f"[{finding.severity}] {finding}"
