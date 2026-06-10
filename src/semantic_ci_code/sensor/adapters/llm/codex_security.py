"""Fixture-mode Codex Security LLM scout adapter.

The recorded-output envelope accepted by this module is a JSON object with:

```
{
  "sensor_version": "...",
  "model_id": "...",
  "prompt_hash": "...",
  "status": "complete" | "error" | "timeout" | "skipped",
  "error_message": null | "...",
  "findings": [
    {
      "finding_class": "...",
      "module_path": "...",
      "qualified_name": "...",
      "anchor_kind": "presence" | "absence",
      "expected_property": "...",
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "message": "...",
      "source_span": {"start_line": 1, "end_line": 1, "start_col": 0, "end_col": 1},
      "ordinal": 0
    }
  ]
}
```

This adapter intentionally has no live LLM execution path. It normalizes a
recorded Codex Security artifact into advisory-only SensorState values by
parsing every complete finding through RawLLMFinding and then reusing the shared
LLM projection helper.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.sensor.adapters.llm.protocol import (
    CodeView,
    LLMSensorAdapter,
    LLMSensorProvenance,
    RawLLMFinding,
    project_to_canonical,
)
from semantic_ci_code.sensor.models import (
    LLMSecurityFinding,
    SensorRunStatus,
    SensorState,
)

CODEX_SECURITY_SENSOR_ID = "codex-security"
CODEX_SECURITY_SENSOR_ADAPTER_VERSION = "sensor-codex-security-adapter-1"

_RUN_STATUSES = frozenset({"complete", "error", "timeout", "skipped"})
_GROUP_KEYS = (
    "finding_class",
    "module_path",
    "qualified_name",
    "anchor_kind",
    "expected_property",
)


@dataclass(frozen=True)
class _ParsedCodexSecurityPayload:
    raw_findings: tuple[RawLLMFinding, ...]
    provenance: LLMSensorProvenance


class CodexSecurityAdapter:
    """Reference Codex Security adapter for recorded fixture payloads."""

    sensor_id = CODEX_SECURITY_SENSOR_ID

    def __init__(self, payload: Mapping[str, Any]) -> None:
        parsed = _parse_payload(payload, sensor_id=self.sensor_id)
        self._raw_findings = parsed.raw_findings
        self._provenance = parsed.provenance

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> CodexSecurityAdapter:
        """Build an adapter from a recorded Codex Security JSON payload."""

        return cls(payload)

    def scan_candidate(self, candidate_code: CodeView) -> tuple[RawLLMFinding, ...]:
        """Return recorded raw findings; no live scan is performed."""

        del candidate_code
        return self._raw_findings

    def project_to_canonical(self, finding: RawLLMFinding) -> LLMSecurityFinding:
        """Project one raw finding through the shared LLM canonicalizer."""

        return project_to_canonical(finding, sensor_id=self.sensor_id)

    def provenance(self) -> LLMSensorProvenance:
        """Return non-reproducible provenance for the recorded scout run."""

        return self._provenance

    def sensor_state(self) -> SensorState:
        """Return an advisory-only SensorState for this recorded payload."""

        return _sensor_state_from_adapter(self)


def sensor_state_from_codex_security_json(payload: Mapping[str, Any]) -> SensorState:
    """Build advisory-only SensorState from a recorded Codex Security payload."""

    return CodexSecurityAdapter.from_json(payload).sensor_state()


def _sensor_state_from_adapter(adapter: LLMSensorAdapter) -> SensorState:
    provenance = adapter.provenance()
    if provenance.status != "complete":
        findings: tuple[LLMSecurityFinding, ...] = ()
    else:
        findings = tuple(
            sorted(
                (
                    adapter.project_to_canonical(finding)
                    for finding in adapter.scan_candidate(CodeState())
                ),
                key=lambda finding: finding.canonical_id,
            )
        )
    return SensorState(
        provenance_by_sensor={provenance.sensor_id: provenance},
        findings=findings,
    )


def _parse_payload(
    payload: Mapping[str, Any],
    *,
    sensor_id: str,
) -> _ParsedCodexSecurityPayload:
    if not isinstance(payload, Mapping):
        raise ValueError("Codex Security payload must be a JSON object")

    sensor_version = _required_string(payload, "sensor_version")
    model_id = _required_string(payload, "model_id", non_empty=True)
    prompt_hash = _required_string(payload, "prompt_hash", non_empty=True)
    status = _status(payload)
    error_message = _error_message(payload)
    findings_payload = _findings_payload(payload)

    if status != "complete" and not error_message:
        raise ValueError("non-complete Codex Security payload requires error_message")

    provenance = LLMSensorProvenance(
        sensor_id=sensor_id,
        sensor_version=sensor_version,
        adapter_version=CODEX_SECURITY_SENSOR_ADAPTER_VERSION,
        identity_algorithm_version="v1",
        model_id=model_id,
        prompt_hash=prompt_hash,
        non_reproducible=True,
        status=status,
        error_message=error_message,
    )
    if status != "complete":
        return _ParsedCodexSecurityPayload(raw_findings=(), provenance=provenance)

    return _ParsedCodexSecurityPayload(
        raw_findings=_raw_findings(findings_payload),
        provenance=provenance,
    )


def _raw_findings(findings_payload: list[Any]) -> tuple[RawLLMFinding, ...]:
    next_ordinal_by_group: dict[tuple[str, str, str, str, str], int] = {}
    seen_ordinals_by_group: dict[tuple[str, str, str, str, str], set[int]] = {}
    raw_findings: list[RawLLMFinding] = []
    for index, item in enumerate(findings_payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"Codex Security finding #{index} must be a JSON object")
        finding_payload = dict(item)
        if "ordinal" not in finding_payload:
            group = _group_from_mapping(finding_payload, index=index)
            ordinal = next_ordinal_by_group.get(group, 0)
            next_ordinal_by_group[group] = ordinal + 1
            finding_payload["ordinal"] = ordinal

        raw = RawLLMFinding.model_validate(finding_payload)
        group = _group_from_raw(raw)
        seen_ordinals = seen_ordinals_by_group.setdefault(group, set())
        if raw.ordinal in seen_ordinals:
            raise ValueError(
                f"duplicate Codex Security ordinal {raw.ordinal} in finding group {group!r}"
            )
        seen_ordinals.add(raw.ordinal)
        raw_findings.append(raw)
    return tuple(raw_findings)


def _group_from_mapping(
    payload: Mapping[str, Any],
    *,
    index: int,
) -> tuple[str, str, str, str, str]:
    values: list[str] = []
    for key in _GROUP_KEYS:
        if key == "expected_property" and key not in payload:
            values.append("")
            continue
        value = payload.get(key)
        if not isinstance(value, str):
            raise ValueError(f"Codex Security finding #{index} requires string {key!r}")
        values.append(value.replace("\\", "/") if key == "module_path" else value)
    return (values[0], values[1], values[2], values[3], values[4])


def _group_from_raw(raw: RawLLMFinding) -> tuple[str, str, str, str, str]:
    return (
        raw.finding_class,
        raw.module_path,
        raw.qualified_name,
        raw.anchor_kind,
        raw.expected_property,
    )


def _required_string(
    payload: Mapping[str, Any],
    key: str,
    *,
    non_empty: bool = False,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Codex Security payload requires string {key!r}")
    if non_empty and value == "":
        raise ValueError(f"Codex Security payload requires non-empty {key!r}")
    return value


def _status(payload: Mapping[str, Any]) -> SensorRunStatus:
    value = _required_string(payload, "status")
    if value not in _RUN_STATUSES:
        raise ValueError(f"unsupported Codex Security status: {value!r}")
    return value  # type: ignore[return-value]


def _error_message(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("error_message")
    if value is None or isinstance(value, str):
        return value
    raise ValueError("Codex Security payload error_message must be a string or null")


def _findings_payload(payload: Mapping[str, Any]) -> list[Any]:
    value = payload.get("findings")
    if not isinstance(value, list):
        raise ValueError("Codex Security payload requires list 'findings'")
    return value
