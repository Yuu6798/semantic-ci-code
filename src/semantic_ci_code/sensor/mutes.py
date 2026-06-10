"""Advisory-only mute ledger for LLM scout findings.

This ledger is intentionally separate from Phase G security suppressions. Mutes
hide already-accepted advisory candidates from the advisory surface only; they
never participate in verdict or exit-code decisions.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import Field, ValidationError, model_validator

from semantic_ci_code.domain.state_schema import FrozenModel
from semantic_ci_code.sensor.models import canonical_id_for_identity


class AdvisoryMute(FrozenModel):
    canonical_id: Annotated[str, Field(pattern=r"^v1:[0-9a-f]{16}$")]
    identity_components: tuple[str, ...]
    reason: Annotated[str, Field(min_length=1)]
    expires: dt.date
    owner: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def _valid_llm_identity(self) -> AdvisoryMute:
        _validate_llm_identity_components(self.identity_components)
        if self.canonical_id != canonical_id_for_identity(self.identity_components):
            raise ValueError("advisory mute canonical_id does not match identity_components")
        return self

    def is_active(self, *, as_of: dt.date) -> bool:
        """Return whether this mute is active on the supplied date."""

        return self.expires >= as_of


def load_advisory_mutes(path: Path | str) -> tuple[AdvisoryMute, ...]:
    """Load advisory mutes from a YAML file with top-level `mutes: [...]`."""

    mute_path = Path(path)
    try:
        raw = yaml.safe_load(mute_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"advisory mutes file could not be read: {mute_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"advisory mutes file is not valid YAML: {mute_path}") from exc

    if not isinstance(raw, dict):
        raise ValueError("advisory mutes YAML must be a mapping with top-level 'mutes'")
    entries = raw.get("mutes")
    if not isinstance(entries, list):
        raise ValueError("advisory mutes YAML must include top-level list 'mutes'")

    mutes: list[AdvisoryMute] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        try:
            mute = AdvisoryMute.model_validate(entry)
        except ValidationError as exc:
            message = exc.errors()[0]["msg"]
            raise ValueError(f"invalid advisory mute at index {index}: {message}") from exc
        if mute.canonical_id in seen_ids:
            raise ValueError(f"duplicate advisory mute canonical_id: {mute.canonical_id}")
        seen_ids.add(mute.canonical_id)
        mutes.append(mute)
    return tuple(mutes)


def _validate_llm_identity_components(components: tuple[str, ...]) -> None:
    # (v1, llm, sensor_id, finding_class, module_path, qualified_name,
    #  anchor_kind, expected_property, ordinal)
    if len(components) < 2:
        raise ValueError("LLM advisory mute identity_components must include version and category")
    version, category = components[0], components[1]
    if version != "v1":
        raise ValueError("LLM advisory mute identity_components must use identity version v1")
    if category != "llm":
        raise ValueError("advisory mutes only support llm identity_components")
    if len(components) != 9:
        raise ValueError("LLM advisory mute identity_components must have 9 elements")
    if any(not item for item in components[2:7]):
        raise ValueError("LLM advisory mute identity_components has empty required fields")
    anchor_kind = components[6]
    expected_property = components[7]
    if anchor_kind not in {"presence", "absence"}:
        raise ValueError("LLM advisory mute anchor_kind must be presence or absence")
    if anchor_kind == "absence" and expected_property == "":
        raise ValueError("absence advisory mute identity_components requires expected_property")
    if anchor_kind == "presence" and expected_property != "":
        raise ValueError(
            "presence advisory mute identity_components must not include expected_property"
        )
    ordinal = components[8]
    if not ordinal.isdecimal() or str(int(ordinal)) != ordinal:
        raise ValueError(
            "LLM advisory mute identity_components ordinal must be a non-negative integer string"
        )
