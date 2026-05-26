"""Pydantic models for the Semantic Security Protocol v0.1 envelope."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Severity = Literal["critical", "high", "medium", "low", "info"]
SensorStatus = Literal["complete", "error"]
SSPResult = Literal["pass", "fail", "unknown"]
ScanMode = Literal["real", "staged", "virtual", "hybrid"]
EndpointKind = Literal["git-rev", "git-tree", "virtual", "prebuilt"]
Normalization = Literal["ast", "raw"]
FindingsOrderInvariant = Literal["source-span", "schema-order"]


class _SSPModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceSpan(_SSPModel):
    start_line: int = Field(ge=1)
    start_col: int = Field(ge=0)
    end_line: int = Field(ge=1)
    end_col: int = Field(ge=0)

    def sort_key(self) -> tuple[int, int, int, int]:
        return (self.start_line, self.start_col, self.end_line, self.end_col)


class SASTFinding(_SSPModel):
    category: Literal["sast"] = "sast"
    rule_id: str = Field(min_length=1)
    module_path: str = Field(min_length=1)
    qualified_name: str = Field(min_length=1)
    normalized_text: str
    ordinal: int | None = Field(default=None, ge=0)
    fingerprint: str | None = Field(default=None, min_length=16, max_length=16)
    severity: Severity
    message: str = ""
    source_span: SourceSpan | None = None
    normalization: Normalization = "ast"

    @field_validator("module_path")
    @classmethod
    def _posix_module_path(cls, value: str) -> str:
        return value.replace("\\", "/")


class SCAFinding(_SSPModel):
    category: Literal["sca"] = "sca"
    package_name: str = Field(min_length=1)
    installed_version: str = Field(min_length=1)
    advisory_id: str = Field(min_length=1)
    fingerprint: str | None = Field(default=None, min_length=16, max_length=16)
    severity: Severity
    message: str = ""


Finding = Annotated[SASTFinding | SCAFinding, Field(discriminator="category")]


class SensorOutput(_SSPModel):
    sensor_id: str = Field(min_length=1)
    sensor_version: str = ""
    status: SensorStatus = "complete"
    findings: tuple[Finding, ...] = ()
    error_message: str | None = None

    @model_validator(mode="after")
    def _error_outputs_have_no_findings(self) -> SensorOutput:
        if self.status == "error" and self.findings:
            raise ValueError("SensorOutput with status='error' must not include findings")
        return self


class SSPDelta(_SSPModel):
    sensor_id: str = Field(min_length=1)
    status: SSPResult
    added: tuple[Finding, ...] = ()
    removed: tuple[Finding, ...] = ()
    unchanged_count: int = Field(ge=0)
    error_message: str | None = None


class SSPVerdict(_SSPModel):
    sensor_verdicts: dict[str, SSPResult]
    aggregate_verdict: SSPResult


class ScanEndpoint(_SSPModel):
    kind: EndpointKind
    ref: str | None = None


class SensorSpec(_SSPModel):
    id: str = Field(min_length=1)
    version: str = ""
    ruleset_hash: str | None = None
    advisory_db_hash: str | None = None


class SSPEngine(_SSPModel):
    ssp_version: str = "0.1"
    scan_mode: ScanMode
    baseline: ScanEndpoint
    candidate: ScanEndpoint
    sensors: tuple[SensorSpec, ...] = ()


class SSPMetadata(_SSPModel):
    timestamp: str = ""
    findings_order_invariant: FindingsOrderInvariant = "source-span"


class SSPEnvelope(_SSPModel):
    schema_version: Literal["ssp-1"] = "ssp-1"
    engine: SSPEngine
    deltas_by_sensor: dict[str, SSPDelta]
    aggregate_verdict: SSPResult
    metadata: SSPMetadata = Field(default_factory=SSPMetadata)

    @model_validator(mode="after")
    def _delta_keys_match_sensor_ids(self) -> SSPEnvelope:
        mismatches = [
            (key, delta.sensor_id)
            for key, delta in self.deltas_by_sensor.items()
            if key != delta.sensor_id
        ]
        if mismatches:
            details = ", ".join(
                f"{key!r} maps to delta.sensor_id {sensor_id!r}"
                for key, sensor_id in sorted(mismatches)
            )
            raise ValueError(f"deltas_by_sensor keys must match SSPDelta.sensor_id: {details}")
        return self
