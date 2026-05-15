from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from semantic_ci_code.domain.state_schema import CodeState, JsonValue
from semantic_ci_code.framework.target_svp import TargetSVP
from semantic_ci_code.repair import RepairPlan

REPAIR_COMPILER_SCHEMA_VERSION = "1"
# Risk summary key order. ``authoring_errors`` comes first so adapters
# render the "fix the spec before implementing" hint above the
# implementation-side hints (Brief D3, ``docs/brief_resultstatus_planning.md``
# §3 D3 two-step instruction).
RISK_SUMMARY_KEYS = (
    "authoring_errors",
    "would_violate",
    "forbidden_zones",
    "required_additions",
    "template_implications",
)
RiskSummary = dict[str, list[JsonValue]]


@dataclass(frozen=True)
class CompiledRepair:
    """Adapter-rendered repair guidance, ready for hand-off to a generator."""

    adapter_name: str
    output_format: str
    rendered: str
    metadata: dict[str, JsonValue]

    def __hash__(self) -> int:
        return hash(
            (
                self.adapter_name,
                self.output_format,
                self.rendered,
                _hashable_json(self.metadata),
            )
        )


@dataclass(frozen=True)
class CompiledPreGen:
    """Adapter-rendered pre-generation guidance."""

    adapter_name: str
    output_format: str
    rendered: str
    metadata: dict[str, JsonValue]
    risk_summary: RiskSummary

    def __hash__(self) -> int:
        return hash(
            (
                self.adapter_name,
                self.output_format,
                self.rendered,
                _hashable_json(self.metadata),
                _hashable_json(self.risk_summary),
            )
        )


class Adapter(Protocol):
    name: str
    output_format: str
    schema_version: str

    def render_repair(self, plan: RepairPlan, target: TargetSVP | None) -> str: ...

    def render_pre_gen(
        self,
        target: TargetSVP,
        baseline_state: CodeState,
        *,
        risk_summary: RiskSummary | None = None,
    ) -> str: ...


def empty_risk_summary() -> RiskSummary:
    return {key: [] for key in RISK_SUMMARY_KEYS}


def _hashable_json(value: JsonValue) -> object:
    if isinstance(value, dict):
        return tuple((key, _hashable_json(item)) for key, item in sorted(value.items()))
    if isinstance(value, list | tuple):
        return tuple(_hashable_json(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_hashable_json(item) for item in value)
    return value
