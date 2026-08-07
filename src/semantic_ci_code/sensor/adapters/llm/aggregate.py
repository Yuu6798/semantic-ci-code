"""Deterministic ensemble aggregation for advisory-only LLM scout states."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from semantic_ci_code.sensor.adapters.llm.protocol import (
    LLMSensorProvenance,
    RawLLMFinding,
    project_to_canonical,
)
from semantic_ci_code.sensor.models import (
    LLMAnchorKind,
    LLMSecurityFinding,
    SecuritySeverity,
    SensorState,
    SourceSpan,
)

LLM_ENSEMBLE_SENSOR_ID = "llm-ensemble"
LLM_ENSEMBLE_ADAPTER_VERSION = "llm-ensemble-aggregator-1"

_SEVERITY_RANK: dict[SecuritySeverity, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


@dataclass(frozen=True)
class LLMEnsembleAggregation:
    """Aggregated advisory SensorState plus member provenance audit trail."""

    state: SensorState
    members: tuple[LLMSensorProvenance, ...]


@dataclass(frozen=True)
class _Member:
    provenance: LLMSensorProvenance
    findings: tuple[LLMSecurityFinding, ...]


@dataclass(frozen=True)
class _AnchorGroup:
    finding_class: str
    module_path: str
    qualified_name: str
    anchor_kind: LLMAnchorKind
    expected_property: str
    ordinal: int
    findings: tuple[LLMSecurityFinding, ...]


def aggregate_advisory_states(states: Sequence[SensorState]) -> LLMEnsembleAggregation:
    """Aggregate advisory LLM SensorStates into one ensemble SensorState."""

    if not states:
        raise ValueError("aggregate_advisory_states requires at least one SensorState")

    members = tuple(sorted(_members(states), key=_member_sort_key))
    complete_members = tuple(member for member in members if member.provenance.status == "complete")
    provenance = _ensemble_provenance(members=members, has_complete=bool(complete_members))
    findings = _aggregate_findings(complete_members) if provenance.status == "complete" else ()
    return LLMEnsembleAggregation(
        state=SensorState(
            provenance_by_sensor={LLM_ENSEMBLE_SENSOR_ID: provenance},
            findings=findings,
        ),
        members=tuple(member.provenance for member in members),
    )


def _members(states: Sequence[SensorState]) -> tuple[_Member, ...]:
    members: list[_Member] = []
    for state in states:
        for provenance in state.provenance_by_sensor.values():
            if not provenance.non_reproducible:
                raise ValueError("aggregate_advisory_states only accepts LLM advisory provenance")
            member = LLMSensorProvenance.model_validate(provenance.model_dump())
            non_llm_findings = tuple(
                finding
                for finding in state.findings
                if finding.sensor_id == member.sensor_id
                and not isinstance(finding, LLMSecurityFinding)
            )
            if non_llm_findings:
                raise ValueError("aggregate_advisory_states only accepts LLM advisory findings")
            findings = tuple(
                finding
                for finding in state.findings
                if isinstance(finding, LLMSecurityFinding) and finding.sensor_id == member.sensor_id
            )
            members.append(_Member(provenance=member, findings=findings))
    if not members:
        raise ValueError("aggregate_advisory_states requires LLM advisory provenance")
    return tuple(members)


def _member_sort_key(member: _Member) -> tuple[str, str, str, str, str, str]:
    provenance = member.provenance
    return (
        provenance.sensor_id,
        provenance.model_id,
        provenance.prompt_hash,
        provenance.adapter_version,
        provenance.sensor_version,
        _findings_digest(member.findings),
    )


def _findings_digest(findings: tuple[LLMSecurityFinding, ...]) -> str:
    payload = [finding.model_dump(mode="json") for finding in findings]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _ensemble_provenance(
    *,
    members: tuple[_Member, ...],
    has_complete: bool,
) -> LLMSensorProvenance:
    status = "complete" if has_complete else "error"
    return LLMSensorProvenance(
        sensor_id=LLM_ENSEMBLE_SENSOR_ID,
        sensor_version="llm-ensemble",
        adapter_version=LLM_ENSEMBLE_ADAPTER_VERSION,
        identity_algorithm_version="v1",
        model_id="ensemble:" + ",".join(_member_model_ids(members)),
        prompt_hash=_ensemble_prompt_hash(members),
        non_reproducible=True,
        status=status,
        error_message=None if status == "complete" else _all_failed_error_message(members),
    )


def _member_model_ids(members: tuple[_Member, ...]) -> tuple[str, ...]:
    return tuple(sorted(member.provenance.model_id for member in members))


def _ensemble_prompt_hash(members: tuple[_Member, ...]) -> str:
    pairs = sorted(
        (member.provenance.model_id, member.provenance.prompt_hash) for member in members
    )
    payload = json.dumps(pairs, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _all_failed_error_message(members: tuple[_Member, ...]) -> str:
    details = []
    for member in members:
        provenance = member.provenance
        details.append(
            f"{provenance.sensor_id}/{provenance.model_id} "
            f"{provenance.status}: {provenance.error_message}"
        )
    return "all LLM ensemble members non-complete: " + "; ".join(details)


def _aggregate_findings(members: tuple[_Member, ...]) -> tuple[LLMSecurityFinding, ...]:
    groups: dict[tuple[str, str, str, str, str, int], list[LLMSecurityFinding]] = {}
    for member in members:
        for finding in sorted(member.findings, key=lambda item: item.canonical_id):
            groups.setdefault(_anchor_key(finding), []).append(finding)

    aggregated = [
        _project_group(_group_from_findings(findings))
        for _, findings in sorted(groups.items(), key=lambda item: item[0])
    ]
    return tuple(sorted(aggregated, key=lambda finding: finding.canonical_id))


def _anchor_key(finding: LLMSecurityFinding) -> tuple[str, str, str, str, str, int]:
    return (
        finding.finding_class,
        finding.module_path,
        finding.qualified_name,
        finding.anchor_kind,
        finding.expected_property,
        finding.ordinal,
    )


def _group_from_findings(findings: Iterable[LLMSecurityFinding]) -> _AnchorGroup:
    values = tuple(findings)
    first = values[0]
    return _AnchorGroup(
        finding_class=first.finding_class,
        module_path=first.module_path,
        qualified_name=first.qualified_name,
        anchor_kind=first.anchor_kind,
        expected_property=first.expected_property,
        ordinal=first.ordinal,
        findings=values,
    )


def _project_group(group: _AnchorGroup) -> LLMSecurityFinding:
    representative = _max_severity_finding(group.findings)
    return project_to_canonical(
        RawLLMFinding(
            finding_class=group.finding_class,
            module_path=group.module_path,
            qualified_name=group.qualified_name,
            anchor_kind=group.anchor_kind,
            expected_property=group.expected_property,
            ordinal=group.ordinal,
            severity=representative.severity,
            message=representative.message,
            source_span=_first_source_span(group.findings),
        ),
        sensor_id=LLM_ENSEMBLE_SENSOR_ID,
    )


def _max_severity_finding(
    findings: tuple[LLMSecurityFinding, ...],
) -> LLMSecurityFinding:
    return max(findings, key=lambda finding: _SEVERITY_RANK[finding.severity])


def _first_source_span(findings: tuple[LLMSecurityFinding, ...]) -> SourceSpan | None:
    for finding in findings:
        if finding.source_span is not None:
            return finding.source_span
    return None
