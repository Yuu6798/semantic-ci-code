from __future__ import annotations

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.framework.target_svp import TargetSVP
from semantic_ci_code.repair import RepairCategory, RepairPlan
from semantic_ci_code.repair_compiler.adapters.markdown import (
    RISK_SECTION_TITLES,
    finish,
    format_generation_metadata,
    render_instruction_section,
    render_risk_section,
    render_target_constraints,
)
from semantic_ci_code.repair_compiler.risk_summary import normalize_risk_summary
from semantic_ci_code.repair_compiler.types import RISK_SUMMARY_KEYS, RiskSummary

_CATEGORY_SECTIONS = (
    (RepairCategory.FIX_REQUIRED, "Fix Required"),
    (RepairCategory.SUGGESTED, "Suggested"),
    (RepairCategory.INFO, "Info"),
    (RepairCategory.UNRESOLVED, "Unresolved"),
)


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
            lines.extend(render_instruction_section(title, instructions))
        return finish(lines)

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
            "# Plan Validation - Pre-Generation Guidance",
            "",
            f"**Intent**: {target.intent}",
            f"**Primary kind**: {target.change.primary_kind.value}",
            f"**Allowed secondary kinds**: {allowed_secondary}",
            f"**Generation metadata**: {format_generation_metadata(target)}",
            "",
        ]
        lines.extend(render_target_constraints(target))
        risk_summary = normalize_risk_summary(risk_summary)
        for key in RISK_SUMMARY_KEYS:
            lines.extend(render_risk_section(RISK_SECTION_TITLES[key], risk_summary[key]))
        return finish(lines)
