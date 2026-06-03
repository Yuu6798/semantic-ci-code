"""Declared-intent schema for the target.yaml ``security:`` namespace."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Keep this Literal value-identical to sensor.models.SecuritySeverity without
# importing sensor into framework; framework models perform structure checks only.
Severity = Literal["critical", "high", "medium", "low", "info"]


class SeverityFilter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    not_in: tuple[Severity, ...] = Field(default_factory=tuple)


class AddedFindingsPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: SeverityFilter | None = None
    max_count: int | None = Field(default=None, ge=0)


class FindingsPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    added: AddedFindingsPolicy | None = None


class RulesPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    deny_added: tuple[str, ...] = Field(default_factory=tuple)


class ScannerPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    require_same_ruleset: bool = True
    require_same_sensor_version: bool = False
    require_same_advisory_db: bool = True


class Suppression(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_id: Annotated[str, Field(pattern=r"^v1:[0-9a-f]{16}$")]
    identity_components: tuple[str, ...]
    reason: Annotated[str, Field(min_length=1)]
    expires: dt.date
    owner: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def _identity_components_match_supported_shape(self) -> Suppression:
        _validate_suppression_identity_components(self.identity_components)
        return self


def _validate_suppression_identity_components(components: tuple[str, ...]) -> None:
    """Validate suppression identity tuple shape without importing sensor models."""

    if len(components) < 2:
        raise ValueError("suppression identity_components must include version and category")
    version, category = components[0], components[1]
    if version != "v1":
        raise ValueError("suppression identity_components must use identity version v1")
    if category == "sast":
        _validate_sast_identity_components(components)
        return
    if category == "sca":
        _validate_sca_identity_components(components)
        return
    raise ValueError("suppression identity_components category must be 'sast' or 'sca'")


def _validate_sast_identity_components(components: tuple[str, ...]) -> None:
    # (v1, sast, sensor_id, rule_id, module_path, qualified_name, normalized_text, ordinal)
    if len(components) != 8:
        raise ValueError("SAST suppression identity_components must have 8 elements")
    if any(not item for item in components[2:6]):
        raise ValueError("SAST suppression identity_components has empty required fields")
    ordinal = components[7]
    if not ordinal.isdecimal() or str(int(ordinal)) != ordinal:
        raise ValueError(
            "SAST suppression identity_components ordinal must be a non-negative integer string"
        )


def _validate_sca_identity_components(components: tuple[str, ...]) -> None:
    # (v1, sca, sensor_id, package_name, installed_version, advisory_id)
    if len(components) != 6:
        raise ValueError("SCA suppression identity_components must have 6 elements")
    if any(not item for item in components[2:]):
        raise ValueError("SCA suppression identity_components has empty required fields")


class SecurityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: FindingsPolicy | None = None
    rules: RulesPolicy | None = None
    scanner: ScannerPolicy | None = None
    suppressions: tuple[Suppression, ...] = Field(default_factory=tuple)
