"""Declared-intent schema for the target.yaml ``security:`` namespace."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class SecurityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: FindingsPolicy | None = None
    rules: RulesPolicy | None = None
    scanner: ScannerPolicy | None = None
    suppressions: tuple[Suppression, ...] = Field(default_factory=tuple)
