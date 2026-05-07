from __future__ import annotations

import json

from semantic_ci_code.domain.state_schema import CodeState, JsonValue
from semantic_ci_code.framework.target_svp import TargetSVP
from semantic_ci_code.repair import RepairCategory, RepairInstruction, RepairPlan
from semantic_ci_code.repair_compiler.types import RISK_SUMMARY_KEYS, empty_risk_summary

_CATEGORY_SECTIONS = (
    (RepairCategory.FIX_REQUIRED, "Fix Required"),
    (RepairCategory.SUGGESTED, "Suggested"),
    (RepairCategory.INFO, "Info"),
    (RepairCategory.UNRESOLVED, "Unresolved"),
)

_RISK_SECTION_TITLES = {
    "would_violate": "Risk Areas",
    "forbidden_zones": "Forbidden Zones",
    "required_additions": "Required Additions",
    "template_implications": "Template Implications",
}


class ClaudeCodeAdapter:
    name = "claude-code"
    output_format = "markdown"
    schema_version = "1"

    def render_repair(self, plan: RepairPlan, target: TargetSVP | None) -> str:
        intent = target.intent if target is not None else ""
        lines = [
            "# Repair Instructions",
            "",
            f"**Intent**: {intent}",
            (
                f"**Verdict**: {plan.result.value} "
                f"(fix_required: {len(plan.fix_required)}, "
                f"suggested: {len(plan.suggested)}, "
                f"info: {len(plan.info)}, "
                f"unresolved: {len(plan.unresolved)})"
            ),
            "",
        ]
        for category, title in _CATEGORY_SECTIONS:
            instructions = tuple(
                instruction for instruction in plan.instructions if instruction.category is category
            )
            lines.extend(_render_instruction_section(title, instructions))
        return _finish(lines)

    def render_pre_gen(self, target: TargetSVP, baseline_state: CodeState) -> str:
        del baseline_state
        allowed_secondary = (
            ", ".join(kind.value for kind in target.change.allowed_secondary_kinds) or "(none)"
        )
        lines = [
            "# Plan Validation - Pre-Generation Guidance",
            "",
            f"**Intent**: {target.intent}",
            f"**Primary kind**: {target.change.primary_kind.value}",
            f"**Allowed secondary kinds**: {allowed_secondary}",
            "",
        ]
        risk_summary = empty_risk_summary()
        for key in RISK_SUMMARY_KEYS:
            lines.extend(_render_risk_section(_RISK_SECTION_TITLES[key], risk_summary[key]))
        return _finish(lines)


def _render_instruction_section(
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
        lines.extend(_render_optional_evidence(instruction))
        lines.append("   - Hint: address the constraint or update target.yaml if intent changed.")
    lines.append("")
    return lines


def _render_optional_evidence(instruction: RepairInstruction) -> list[str]:
    lines: list[str] = []
    if instruction.observed is not None:
        lines.append(f"   - Observed: {_format_value(instruction.observed)}")
    if instruction.expected is not None:
        lines.append(f"   - Expected: {_format_value(instruction.expected)}")
    for label, values in (
        ("Added", instruction.added),
        ("Removed", instruction.removed),
        ("Missing", instruction.missing),
        ("Extra", instruction.extra),
    ):
        if values:
            lines.append(f"   - {label}: {_format_value(values)}")
    if instruction.extra_evidence:
        lines.append(f"   - Extra evidence: {_format_value(instruction.extra_evidence)}")
    return lines


def _render_risk_section(title: str, values: list[JsonValue]) -> list[str]:
    lines = [f"## {title}"]
    if not values:
        return [*lines, "(none)", ""]
    return [*lines, *(f"- {_format_value(value)}" for value in values), ""]


def _format_value(value: JsonValue) -> str:
    try:
        return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True)
    except TypeError:
        return repr(value)


def _jsonable(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value


def _finish(lines: list[str]) -> str:
    return "\n".join(lines).rstrip() + "\n"
