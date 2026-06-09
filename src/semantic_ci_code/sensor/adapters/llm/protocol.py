"""Protocol for advisory-only LLM security scout adapters.

H-1 intentionally defines only the projection boundary. Implementations may
produce raw findings later, but this module keeps the canonical projection pure
and deterministic so LLM output cannot become a verdict-bearing judge.
"""

from __future__ import annotations

from typing import Protocol, TypeAlias

from pydantic import Field, model_validator

from semantic_ci_code.domain.state_schema import CodeState, FrozenModel
from semantic_ci_code.sensor.models import (
    LLMAnchorKind,
    LLMSecurityFinding,
    SecuritySeverity,
    SensorProvenance,
    SourceSpan,
    canonical_id_for_identity,
)

CodeView: TypeAlias = CodeState


class RawLLMFinding(FrozenModel):
    """Structured finding before deterministic canonical-id projection."""

    finding_class: str = Field(min_length=1)
    module_path: str = Field(min_length=1)
    qualified_name: str = Field(min_length=1)
    anchor_kind: LLMAnchorKind
    expected_property: str = ""
    ordinal: int = Field(ge=0)
    severity: SecuritySeverity
    message: str = ""
    source_span: SourceSpan | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_module_path(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        module_path = normalized.get("module_path")
        if isinstance(module_path, str):
            normalized["module_path"] = module_path.replace("\\", "/")
        return normalized

    @model_validator(mode="after")
    def _anchor_kind_matches_expected_property(self) -> RawLLMFinding:
        if self.anchor_kind == "absence" and self.expected_property == "":
            raise ValueError("absence LLM findings require expected_property")
        if self.anchor_kind == "presence" and self.expected_property != "":
            raise ValueError("presence LLM findings must not include expected_property")
        return self


def project_to_canonical(
    finding: RawLLMFinding,
    *,
    sensor_id: str,
) -> LLMSecurityFinding:
    """Project a raw scout finding into a canonical advisory finding."""

    identity_components = (
        "v1",
        "llm",
        sensor_id,
        finding.finding_class,
        finding.module_path,
        finding.qualified_name,
        finding.anchor_kind,
        finding.expected_property,
        str(finding.ordinal),
    )
    return LLMSecurityFinding(
        category="llm",
        sensor_id=sensor_id,
        canonical_id=canonical_id_for_identity(identity_components),
        identity_components=identity_components,
        severity=finding.severity,
        finding_class=finding.finding_class,
        module_path=finding.module_path,
        qualified_name=finding.qualified_name,
        anchor_kind=finding.anchor_kind,
        expected_property=finding.expected_property,
        ordinal=finding.ordinal,
        source_span=finding.source_span,
        message=finding.message,
    )


class LLMSensorAdapter(Protocol):
    """Protocol for advisory-only LLM scout adapters."""

    sensor_id: str

    def scan_candidate(self, candidate_code: CodeView) -> tuple[RawLLMFinding, ...]:
        """Return raw scout findings for candidate code."""

    def project_to_canonical(self, finding: RawLLMFinding) -> LLMSecurityFinding:
        """Project one raw finding to canonical advisory form."""

    def provenance(self) -> SensorProvenance:
        """Return provenance for the advisory sensor run."""
