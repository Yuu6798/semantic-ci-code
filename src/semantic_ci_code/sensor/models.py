"""Pydantic models for core security sensor state."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from semantic_ci_code.domain.state_schema import FrozenModel

IdentityAlgorithmVersion = Literal["v1"]
SensorRunStatus = Literal["complete", "error", "timeout", "skipped"]
SecuritySeverity = Literal["critical", "high", "medium", "low", "info"]
SecurityDeltaStatus = Literal["pass", "fail", "unknown"]
SecurityFindingKind = Literal["sast", "sca"]

FAIL_SEVERITIES = frozenset({"critical", "high", "medium", "low"})
_FAIL_SEVERITIES = FAIL_SEVERITIES
# When identity v2 lands, widen both IdentityAlgorithmVersion and canonical_id regexes.


def canonical_id_for_identity(identity_components: Iterable[str]) -> str:
    """Return the canonical `vN:<digest>` id for identity components."""

    components = tuple(identity_components)
    if not components:
        raise ValueError("identity_components must not be empty")
    return f"{components[0]}:{_digest_array(list(components))}"


def _digest_array(values: list[object]) -> str:
    payload = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class SensorProvenance(FrozenModel):
    sensor_id: str = Field(min_length=1)
    sensor_version: str = ""
    adapter_version: str = ""
    identity_algorithm_version: IdentityAlgorithmVersion = "v1"
    ruleset_hash: str | None = None
    advisory_db_hash: str | None = None
    status: SensorRunStatus = "complete"
    error_message: str | None = None

    @model_validator(mode="after")
    def _complete_status_matches_error_message(self) -> SensorProvenance:
        if self.status == "complete" and self.error_message is not None:
            raise ValueError("complete sensor provenance must not include error_message")
        if self.status != "complete" and self.error_message is None:
            raise ValueError("non-complete sensor provenance requires error_message")
        return self


class _SecurityFindingBase(FrozenModel):
    sensor_id: str = Field(min_length=1)
    canonical_id: str = Field(pattern=r"^v1:[0-9a-f]{16}$")
    identity_components: tuple[str, ...]
    severity: SecuritySeverity
    message: str = ""

    @model_validator(mode="after")
    def _canonical_id_matches_identity(self) -> _SecurityFindingBase:
        if self.canonical_id != canonical_id_for_identity(self.identity_components):
            raise ValueError("canonical_id does not match identity_components")
        return self


class SourceSpan(FrozenModel):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    start_col: int = Field(ge=0)
    end_col: int = Field(ge=0)


def _posix_path(value: str) -> str:
    return value.replace("\\", "/")


class SASTSecurityFinding(_SecurityFindingBase):
    category: Literal["sast"] = "sast"
    rule_id: str = Field(min_length=1)
    module_path: str = Field(min_length=1)
    qualified_name: str = Field(min_length=1)
    normalized_text: str
    ordinal: int = Field(ge=0)
    source_span: SourceSpan | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_module_path(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        module_path = normalized.get("module_path")
        if isinstance(module_path, str):
            normalized["module_path"] = _posix_path(module_path)
        identity_components = normalized.get("identity_components")
        if isinstance(identity_components, (list, tuple)) and len(identity_components) == 8:
            components = list(identity_components)
            if isinstance(components[4], str):
                components[4] = _posix_path(components[4])
            normalized["identity_components"] = tuple(components)
        return normalized

    @model_validator(mode="after")
    def _identity_components_match_sast_fields(self) -> SASTSecurityFinding:
        expected = (
            self.identity_components[0] if self.identity_components else "",
            "sast",
            self.sensor_id,
            self.rule_id,
            self.module_path,
            self.qualified_name,
            self.normalized_text,
            str(self.ordinal),
        )
        if self.identity_components != expected:
            raise ValueError("SAST identity_components must match finding fields")
        return self


class SCASecurityFinding(_SecurityFindingBase):
    category: Literal["sca"] = "sca"
    package_name: str = Field(min_length=1)
    installed_version: str = Field(min_length=1)
    advisory_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _identity_components_match_sca_fields(self) -> SCASecurityFinding:
        expected = (
            self.identity_components[0] if self.identity_components else "",
            "sca",
            self.sensor_id,
            self.package_name,
            self.installed_version,
            self.advisory_id,
        )
        if self.identity_components != expected:
            raise ValueError("SCA identity_components must match finding fields")
        return self


SecurityFinding = Annotated[
    SASTSecurityFinding | SCASecurityFinding,
    Field(discriminator="category"),
]


class PerSensorDelta(FrozenModel):
    sensor_id: str = Field(min_length=1)
    status: SecurityDeltaStatus
    added: tuple[SecurityFinding, ...] = ()
    removed: tuple[SecurityFinding, ...] = ()
    unchanged_count: int = Field(ge=0)
    provenance_changed: bool = False
    error_message: str | None = None

    @model_validator(mode="after")
    def _validate_delta_invariants(self) -> PerSensorDelta:
        if self.provenance_changed and self.status != "unknown":
            raise ValueError("provenance_changed requires status='unknown'")
        if any(finding.sensor_id != self.sensor_id for finding in (*self.added, *self.removed)):
            raise ValueError("PerSensorDelta findings must match sensor_id")
        if self.status == "unknown" and self.error_message is None:
            raise ValueError("unknown PerSensorDelta requires error_message")
        if self.status != "unknown" and self.error_message is not None:
            raise ValueError("non-unknown PerSensorDelta must not include error_message")
        if self.status == "pass" and any(
            finding.severity in _FAIL_SEVERITIES for finding in self.added
        ):
            raise ValueError("pass PerSensorDelta cannot include fail-severity added findings")
        if self.status == "fail" and not any(
            finding.severity in _FAIL_SEVERITIES for finding in self.added
        ):
            raise ValueError("fail PerSensorDelta requires a fail-severity added finding")
        return self


class SecurityDelta(FrozenModel):
    deltas_by_sensor: dict[str, PerSensorDelta]
    aggregate_status: SecurityDeltaStatus

    @model_validator(mode="after")
    def _validate_delta_map(self) -> SecurityDelta:
        mismatches = [
            (key, delta.sensor_id)
            for key, delta in self.deltas_by_sensor.items()
            if key != delta.sensor_id
        ]
        if mismatches:
            raise ValueError(f"deltas_by_sensor keys must match sensor_id: {mismatches}")
        expected = aggregate_status(delta.status for delta in self.deltas_by_sensor.values())
        if self.aggregate_status != expected:
            raise ValueError(
                f"aggregate_status must be {expected!r}, got {self.aggregate_status!r}"
            )
        return self


class SensorState(FrozenModel):
    identity_algorithm_version: IdentityAlgorithmVersion = "v1"
    provenance_by_sensor: dict[str, SensorProvenance] = Field(default_factory=dict)
    findings: tuple[SecurityFinding, ...] = ()

    @model_validator(mode="after")
    def _validate_state_invariants(self) -> SensorState:
        provenance_mismatches = [
            (key, provenance.sensor_id)
            for key, provenance in self.provenance_by_sensor.items()
            if key != provenance.sensor_id
        ]
        if provenance_mismatches:
            raise ValueError(
                f"provenance_by_sensor keys must match sensor_id: {provenance_mismatches}"
            )

        all_versions = [
            *(
                provenance.identity_algorithm_version
                for provenance in self.provenance_by_sensor.values()
            ),
            *(finding.identity_components[0] for finding in self.findings),
        ]
        if any(version != self.identity_algorithm_version for version in all_versions):
            raise ValueError("identity_algorithm_version must match all nested identities")

        if tuple(finding.canonical_id for finding in self.findings) != tuple(
            sorted(finding.canonical_id for finding in self.findings)
        ):
            raise ValueError("findings must be sorted by canonical_id")

        finding_ids = [finding.canonical_id for finding in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("finding canonical_id values must be unique")

        for finding in self.findings:
            provenance = self.provenance_by_sensor.get(finding.sensor_id)
            if provenance is None:
                raise ValueError(f"finding references unknown sensor_id: {finding.sensor_id}")
            if provenance.status != "complete":
                raise ValueError("non-complete sensors must not include findings")
        return self


def aggregate_status(statuses: Iterable[SecurityDeltaStatus]) -> SecurityDeltaStatus:
    values = tuple(statuses)
    if "unknown" in values:
        return "unknown"
    if "fail" in values:
        return "fail"
    return "pass"
