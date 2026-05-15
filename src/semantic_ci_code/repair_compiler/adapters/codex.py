from __future__ import annotations

import json

from semantic_ci_code.domain.state_schema import CodeState, JsonValue
from semantic_ci_code.framework.target_svp import TargetSVP
from semantic_ci_code.repair import RepairCategory, RepairInstruction, RepairPlan
from semantic_ci_code.repair_compiler.risk_summary import normalize_risk_summary
from semantic_ci_code.repair_compiler.types import RISK_SUMMARY_KEYS, RiskSummary

_CATEGORY_SECTIONS = (
    (RepairCategory.FIX_REQUIRED, "FIX REQUIRED"),
    (RepairCategory.SUGGESTED, "SUGGESTED"),
    (RepairCategory.INFO, "INFO"),
    (RepairCategory.UNRESOLVED, "UNRESOLVED"),
)

_RISK_SECTION_LABELS = {
    "authoring_errors": "AUTHORING ERRORS",
    "would_violate": "RISK AREAS",
    "forbidden_zones": "FORBIDDEN ZONES",
    "required_additions": "REQUIRED ADDITIONS",
    "template_implications": "TEMPLATE IMPLICATIONS",
}

# Two-step instruction rendered above the risk sections (planning §3 D3).
_IMPLEMENTATION_ORDER_LINES = (
    "[IMPLEMENTATION ORDER]",
    "1. Fix every item under AUTHORING ERRORS in target.yaml first.",
    "2. Then implement against RISK AREAS / FORBIDDEN ZONES / REQUIRED ADDITIONS.",
    "",
)


class CodexAdapter:
    name = "codex"
    output_format = "text"
    schema_version = "1"

    def render_repair(self, plan: RepairPlan, target: TargetSVP | None) -> str:
        intent = target.intent if target is not None else ""
        lines = [
            "[INTENT]",
            intent or "(none)",
            "",
            "[CURRENT VERDICT]",
            f"result: {plan.result.value}",
            f"fix_required: {len(plan.fix_required)}",
            f"suggested: {len(plan.suggested)}",
            f"info: {len(plan.info)}",
            f"unresolved: {len(plan.unresolved)}",
            "",
        ]
        for category, label in _CATEGORY_SECTIONS:
            instructions = tuple(
                instruction for instruction in plan.instructions if instruction.category is category
            )
            lines.extend(_render_instruction_section(label, instructions))
        lines.extend(
            [
                "[HINTS]",
                (
                    "Use instruction-specific hints first; revise target.yaml only when the "
                    "declared intent changed."
                ),
                "",
            ]
        )
        return _finish(lines)

    def render_pre_gen(
        self,
        target: TargetSVP,
        baseline_state: CodeState,
        *,
        risk_summary: RiskSummary | None = None,
    ) -> str:
        del baseline_state
        allowed_secondary = (
            ", ".join(kind.value for kind in target.change.allowed_secondary_kinds) or "(none)"
        )
        lines = [
            "[INTENT]",
            target.intent or "(none)",
            "",
            "[PRIMARY KIND]",
            target.change.primary_kind.value,
            "",
            "[ALLOWED SECONDARY KINDS]",
            allowed_secondary,
            "",
            "[GENERATION METADATA]",
            _format_generation_metadata(target),
            "",
        ]
        lines.extend(_render_target_constraints(target))
        risk_summary = normalize_risk_summary(risk_summary)
        lines.extend(_IMPLEMENTATION_ORDER_LINES)
        for key in RISK_SUMMARY_KEYS:
            lines.extend(_render_value_section(_RISK_SECTION_LABELS[key], risk_summary[key]))
        return _finish(lines)


def _render_instruction_section(
    label: str,
    instructions: tuple[RepairInstruction, ...],
) -> list[str]:
    lines = [f"[{label}]"]
    if not instructions:
        return [*lines, "(none)", ""]

    for index, instruction in enumerate(instructions, start=1):
        lines.extend(
            [
                f"{index}. {instruction.repair_code} - {instruction.message}",
                f"  constraint: {instruction.constraint_id}",
                f"  kind: {instruction.kind.value}",
                f"  severity: {instruction.severity.value}",
                f"  target: {instruction.target}",
                f"  operator: {instruction.operator.value}",
                f"  status: {instruction.status.value}",
                f"  error_code: {instruction.error_code}",
            ]
        )
        lines.extend(_render_optional_evidence(instruction))
        lines.append("  hint: address the constraint or update target.yaml if intent changed.")
    lines.append("")
    return lines


def _render_optional_evidence(instruction: RepairInstruction) -> list[str]:
    lines: list[str] = []
    if instruction.observed is not None:
        lines.append(f"  observed: {_format_value(instruction.observed)}")
    if instruction.expected is not None:
        lines.append(f"  expected: {_format_value(instruction.expected)}")
    for key, values in (
        ("added", instruction.added),
        ("removed", instruction.removed),
        ("missing", instruction.missing),
        ("extra", instruction.extra),
    ):
        if values:
            lines.append(f"  {key}: {_format_value(values)}")
    if instruction.extra_evidence:
        lines.append(f"  extra_evidence: {_format_value(instruction.extra_evidence)}")
    return lines


def _render_target_constraints(target: TargetSVP) -> list[str]:
    lines = ["[TARGET CONSTRAINTS]"]
    if not target.constraints:
        return [*lines, "(none)", ""]

    for index, constraint in enumerate(target.constraints, start=1):
        lines.extend(
            [
                f"{index}. {constraint.id}",
                f"  kind: {_enum_value(constraint.kind)}",
                f"  target: {constraint.target}",
                f"  operator: {_enum_value(constraint.operator)}",
                f"  expected: {_format_value(constraint.expected)}",
                f"  severity: {_enum_value(constraint.severity)}",
                f"  unknown_policy: {_enum_value(constraint.unknown_policy)}",
            ]
        )
        if constraint.tolerance is not None:
            lines.append(f"  tolerance: {_format_value(constraint.tolerance)}")
        if constraint.evidence_required:
            lines.append("  evidence_required: true")
        if constraint.scope is not None:
            lines.append(f"  scope: {_format_value(constraint.scope)}")
    lines.append("")
    return lines


def _render_value_section(label: str, values: list[JsonValue]) -> list[str]:
    lines = [f"[{label}]"]
    if not values:
        return [*lines, "(none)", ""]
    return [*lines, *(f"- {_format_value(value)}" for value in values), ""]


def _format_generation_metadata(target: TargetSVP) -> str:
    if target.authorship is None or target.authorship.generation_metadata is None:
        return "(none)"
    return _format_value(target.authorship.generation_metadata)


def _enum_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value


def _format_value(value: JsonValue) -> str:
    try:
        return json.dumps(_jsonable(value), ensure_ascii=True, sort_keys=True)
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
