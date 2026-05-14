from __future__ import annotations

import json

from semantic_ci_code.domain.state_schema import JsonValue
from semantic_ci_code.framework.target_svp import TargetSVP
from semantic_ci_code.repair import RepairInstruction

RISK_SECTION_TITLES = {
    "authoring_errors": "Authoring Errors",
    "would_violate": "Risk Areas",
    "forbidden_zones": "Forbidden Zones",
    "required_additions": "Required Additions",
    "template_implications": "Template Implications",
}

# Two-step instruction surfaced when authoring_errors and the
# implementation-side hints coexist (planning §3 D3).
IMPLEMENTATION_ORDER_NOTE = (
    "**Implementation order**: fix every item under *Authoring Errors* in "
    "`target.yaml` first; only then implement against *Risk Areas* / "
    "*Forbidden Zones* / *Required Additions*."
)
RISK_FIELD_ORDER = (
    ("source", "Source"),
    ("target", "Target"),
    ("operator", "Operator"),
)
_RISK_RENDERED_KEYS = frozenset(
    {"constraint_id", "source", "target", "operator", "expected", "expected_any_of"}
)


def render_instruction_section(
    title: str,
    instructions: tuple[RepairInstruction, ...],
) -> list[str]:
    lines = [f"## {title}"]
    if not instructions:
        return [*lines, "(none)", ""]

    for index, instruction in enumerate(instructions, start=1):
        lines.extend(
            [
                f"{index}. **{instruction.repair_code}** - {instruction.message}",
                f"   - Constraint: `{instruction.constraint_id}`",
                f"   - Kind: `{instruction.kind.value}`",
                f"   - Severity: `{instruction.severity.value}`",
                f"   - Target: `{instruction.target}`",
                f"   - Operator: `{instruction.operator.value}`",
                f"   - Status: `{instruction.status.value}`",
                f"   - Error code: `{instruction.error_code}`",
            ]
        )
        lines.extend(render_optional_evidence(instruction))
        lines.append("   - Hint: address the constraint or update target.yaml if intent changed.")
    lines.append("")
    return lines


def render_optional_evidence(instruction: RepairInstruction) -> list[str]:
    lines: list[str] = []
    if instruction.observed is not None:
        lines.append(f"   - Observed: {format_value(instruction.observed)}")
    if instruction.expected is not None:
        lines.append(f"   - Expected: {format_value(instruction.expected)}")
    for label, values in (
        ("Added", instruction.added),
        ("Removed", instruction.removed),
        ("Missing", instruction.missing),
        ("Extra", instruction.extra),
    ):
        if values:
            lines.append(f"   - {label}: {format_value(values)}")
    if instruction.extra_evidence:
        lines.append(f"   - Extra evidence: {format_value(instruction.extra_evidence)}")
    return lines


def render_target_constraints(target: TargetSVP) -> list[str]:
    lines = ["## Target Constraints"]
    if not target.constraints:
        return [*lines, "(none)", ""]

    for index, constraint in enumerate(target.constraints, start=1):
        lines.extend(
            [
                f"{index}. `{constraint.id}`",
                f"   - Kind: `{enum_value(constraint.kind)}`",
                f"   - Target: `{constraint.target}`",
                f"   - Operator: `{enum_value(constraint.operator)}`",
                f"   - Expected: {format_value(constraint.expected)}",
                f"   - Severity: `{enum_value(constraint.severity)}`",
                f"   - Unknown policy: `{enum_value(constraint.unknown_policy)}`",
            ]
        )
        if constraint.tolerance is not None:
            lines.append(f"   - Tolerance: {format_value(constraint.tolerance)}")
        if constraint.evidence_required:
            lines.append("   - Evidence required: true")
        if constraint.scope is not None:
            lines.append(f"   - Scope: {format_value(constraint.scope)}")
    lines.append("")
    return lines


def render_risk_section(title: str, values: list[JsonValue]) -> list[str]:
    lines = [f"## {title}"]
    if not values:
        return [*lines, "(none)", ""]
    return [*lines, *(f"- {format_value(value)}" for value in values), ""]


def render_risk_section_structured(title: str, values: list[JsonValue]) -> list[str]:
    lines = [f"## {title}"]
    if not values:
        return [*lines, "(none)", ""]
    for index, value in enumerate(values, start=1):
        lines.extend(_render_risk_item_block(index, value))
    lines.append("")
    return lines


def _render_risk_item_block(index: int, value: JsonValue) -> list[str]:
    if not isinstance(value, dict):
        return [f"- {_format_risk_scalar(value)}"]

    constraint_id = value.get("constraint_id")
    if not isinstance(constraint_id, str) or not constraint_id:
        return [f"- {format_value(value)}"]

    lines = [f"{index}. `{constraint_id}`"]
    for key, label in RISK_FIELD_ORDER:
        if key in value:
            lines.append(f"   - {label}: `{value[key]}`")

    if "expected" in value:
        lines.append(f"   - Expected: {format_value(value['expected'])}")

    if "expected_any_of" in value:
        lines.append("   - Any of:")
        for item in _as_list(value["expected_any_of"]):
            lines.append(f"     - {format_value(item)}")

    for key in sorted(set(value) - _RISK_RENDERED_KEYS):
        lines.append(f"   - {key}: {format_value(value[key])}")

    return lines


def _format_risk_scalar(value: JsonValue) -> str:
    return value if isinstance(value, str) else format_value(value)


def _as_list(value: JsonValue) -> list[JsonValue]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def format_generation_metadata(target: TargetSVP) -> str:
    if target.authorship is None or target.authorship.generation_metadata is None:
        return "(none)"
    return format_value(target.authorship.generation_metadata)


def enum_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value


def format_value(value: JsonValue) -> str:
    try:
        return json.dumps(jsonable(value), ensure_ascii=False, sort_keys=True)
    except TypeError:
        return repr(value)


def jsonable(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value


def finish(lines: list[str]) -> str:
    return "\n".join(lines).rstrip() + "\n"
