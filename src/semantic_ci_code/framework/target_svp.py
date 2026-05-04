from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from semantic_ci_code.domain.state_schema import ChangeKind, EffectClass
from semantic_ci_code.framework.constraint_types import Constraint


class APISurfaceAllowRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fqn: str | None = None
    fqn_prefix: str | None = None


class APISurfacePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allow_changes: tuple[APISurfaceAllowRule, ...] = Field(default_factory=tuple)


class ChangeBlock(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_kind: ChangeKind
    allowed_secondary_kinds: tuple[ChangeKind, ...] = Field(default_factory=tuple)
    scope: dict[str, tuple[str, ...]] = Field(default_factory=dict)


class EffectAllowRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fqn: str | None = None
    effect_class: EffectClass | None = None


class EffectsPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allow_new: tuple[EffectAllowRule, ...] = Field(default_factory=tuple)


class TargetSVP(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    intent: str
    change: ChangeBlock
    api_surface: APISurfacePolicy | None = None
    effects: EffectsPolicy | None = None
    constraints: tuple[Constraint, ...] = Field(default_factory=tuple)


def parse_target_svp_yaml(source: str | Path) -> TargetSVP:
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8")
    else:
        text = source

    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        msg = "Target SVP YAML root must be a mapping."
        raise ValueError(msg)

    return TargetSVP.model_validate(data)


def target_svp_to_yaml(target_svp: TargetSVP) -> str:
    payload = target_svp.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
