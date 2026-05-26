"""Pure SSP delta engine."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from semantic_ci_code.ssp.fingerprint import sast_fingerprint, sca_fingerprint
from semantic_ci_code.ssp.models import Finding, SASTFinding, SCAFinding, SensorOutput, SSPDelta
from semantic_ci_code.ssp.verdict import verdict_for_delta


def compute_delta(baseline: SensorOutput, candidate: SensorOutput) -> SSPDelta:
    """Compute an SSPDelta from two SensorOutput values."""

    if baseline.sensor_id != candidate.sensor_id:
        raise ValueError(
            f"sensor_id mismatch: baseline={baseline.sensor_id!r}, "
            f"candidate={candidate.sensor_id!r}"
        )
    if baseline.status == "error" or candidate.status == "error":
        return SSPDelta(
            sensor_id=candidate.sensor_id,
            status="unknown",
            added=(),
            removed=(),
            unchanged_count=0,
            error_message=candidate.error_message or baseline.error_message,
        )

    baseline_by_fp = _findings_by_fingerprint(_fingerprinted_findings(baseline.findings))
    candidate_by_fp = _findings_by_fingerprint(_fingerprinted_findings(candidate.findings))

    baseline_fps = set(baseline_by_fp)
    candidate_fps = set(candidate_by_fp)
    added = tuple(candidate_by_fp[fp] for fp in sorted(candidate_fps - baseline_fps))
    removed = tuple(baseline_by_fp[fp] for fp in sorted(baseline_fps - candidate_fps))
    delta = SSPDelta(
        sensor_id=candidate.sensor_id,
        status="pass",
        added=added,
        removed=removed,
        unchanged_count=len(baseline_fps & candidate_fps),
    )
    return delta.model_copy(update={"status": verdict_for_delta(delta)})


def assign_sast_ordinals(findings: Iterable[SASTFinding]) -> tuple[SASTFinding, ...]:
    """Assign section 5.1.2 SAST ordinals deterministically."""

    unique: dict[tuple[object, ...], tuple[int, SASTFinding]] = {}
    for index, finding in enumerate(findings):
        unique.setdefault(_sast_dedup_key(finding, index), (index, finding))

    grouped: dict[tuple[str, str, str, str], list[tuple[int, SASTFinding]]] = defaultdict(list)
    for index, finding in unique.values():
        grouped[_sast_group_key(finding)].append((index, finding))

    assigned: list[tuple[int, SASTFinding]] = []
    for group in grouped.values():
        sorted_group = sorted(group, key=lambda item: _span_sort_key(item[1], item[0]))
        for ordinal, (original_index, finding) in enumerate(sorted_group):
            fingerprint = sast_fingerprint(
                finding.rule_id,
                finding.module_path,
                finding.qualified_name,
                finding.normalized_text,
                ordinal,
            )
            assigned.append(
                (
                    original_index,
                    finding.model_copy(update={"ordinal": ordinal, "fingerprint": fingerprint}),
                )
            )
    return tuple(finding for _, finding in sorted(assigned, key=lambda item: item[0]))


def _fingerprinted_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    sast_findings: list[SASTFinding] = []
    sca_findings: list[SCAFinding] = []
    for finding in findings:
        if isinstance(finding, SASTFinding):
            sast_findings.append(finding)
        elif isinstance(finding, SCAFinding):
            sca_findings.append(finding)

    result: list[Finding] = [*assign_sast_ordinals(sast_findings)]
    result.extend(_with_fingerprint(finding) for finding in sca_findings)
    return tuple(_dedup_fingerprinted(result))


def _with_fingerprint(finding: Finding) -> Finding:
    if isinstance(finding, SASTFinding):
        if finding.fingerprint is not None and finding.ordinal is not None:
            return finding
        ordinal = finding.ordinal or 0
        return finding.model_copy(
            update={
                "ordinal": ordinal,
                "fingerprint": sast_fingerprint(
                    finding.rule_id,
                    finding.module_path,
                    finding.qualified_name,
                    finding.normalized_text,
                    ordinal,
                ),
            }
        )
    if isinstance(finding, SCAFinding):
        if finding.fingerprint is not None:
            return finding
        return finding.model_copy(
            update={
                "fingerprint": sca_fingerprint(
                    finding.package_name,
                    finding.installed_version,
                    finding.advisory_id,
                )
            }
        )
    return finding


def _dedup_fingerprinted(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    by_fp: dict[str, Finding] = {}
    for finding in findings:
        if finding.fingerprint is None:
            raise ValueError(f"finding has no fingerprint after normalization: {finding!r}")
        by_fp.setdefault(finding.fingerprint, finding)
    return tuple(by_fp[fp] for fp in sorted(by_fp))


def _findings_by_fingerprint(findings: Iterable[Finding]) -> dict[str, Finding]:
    result: dict[str, Finding] = {}
    for finding in findings:
        if finding.fingerprint is None:
            raise ValueError(f"finding has no fingerprint: {finding!r}")
        result.setdefault(finding.fingerprint, finding)
    return result


def _sast_group_key(finding: SASTFinding) -> tuple[str, str, str, str]:
    return (
        finding.rule_id,
        finding.module_path,
        finding.qualified_name,
        finding.normalized_text,
    )


def _sast_dedup_key(finding: SASTFinding, original_index: int) -> tuple[object, ...]:
    span = (
        ("span", *finding.source_span.sort_key())
        if finding.source_span is not None
        else ("spanless", original_index)
    )
    return (*_sast_group_key(finding), span)


def _span_sort_key(finding: SASTFinding, original_index: int) -> tuple[int, int, int, int, int]:
    if finding.source_span is None:
        return (0, 0, 0, 0, original_index)
    return (*finding.source_span.sort_key(), original_index)
