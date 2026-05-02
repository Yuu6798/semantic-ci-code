from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from semantic_ci_code.domain.state_schema import EffectClass


class EffectAccess(StrEnum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    UNKNOWN = "unknown"


class ResolutionLevel(StrEnum):
    DIRECT_CALL = "direct_call"
    IMPORTED_ALIAS = "imported_alias"
    METHOD_NAME_ONLY = "method_name_only"
    STATEMENT_LEVEL = "statement_level"


Severity = Literal["low", "medium", "high"]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")


class EffectMatch(_FrozenModel):
    call: str


class EffectSignature(_FrozenModel):
    id: str
    language: str
    match: EffectMatch
    effect_class: EffectClass = Field(alias="effect")
    access: EffectAccess
    severity: Severity


_ALLOWED_ROOT_KEYS = frozenset({"effects"})


def load_effect_db(path: str | Path) -> tuple[EffectSignature, ...]:
    """Load and validate a known-effect signature database from YAML.

    Validation errors:
    - root must be a mapping containing only ``effects``
    - ``effects`` must be a list of mappings
    - each entry must validate against :class:`EffectSignature` (unknown
      fields and unknown enum values are rejected)
    - ids must be unique across the database
    Duplicate ``match.call`` values are allowed; the loader preserves
    declaration order so consumers can deterministically pick the first.
    """
    with Path(path).open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        msg = "Effect DB root must be a mapping."
        raise ValueError(msg)

    unknown_keys = sorted(set(data) - _ALLOWED_ROOT_KEYS)
    if unknown_keys:
        msg = f"Unknown root key(s) in effect DB: {unknown_keys}."
        raise ValueError(msg)

    if "effects" not in data:
        msg = "Effect DB requires an 'effects' list at the root."
        raise ValueError(msg)

    raw_entries = data["effects"]
    if not isinstance(raw_entries, list):
        msg = "Effect DB 'effects' must be a list."
        raise ValueError(msg)

    seen_ids: set[str] = set()
    signatures: list[EffectSignature] = []
    for raw in raw_entries:
        signature = EffectSignature.model_validate(raw)
        if signature.id in seen_ids:
            msg = f"Duplicate effect id in DB: {signature.id!r}."
            raise ValueError(msg)
        seen_ids.add(signature.id)
        signatures.append(signature)

    return tuple(signatures)
