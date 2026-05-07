from __future__ import annotations

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.framework.target_svp import TargetSVP
from semantic_ci_code.repair import RepairCategory, RepairPlan
from semantic_ci_code.repair_compiler.adapters.markdown import (
    RISK_SECTION_TITLES,
    finish,
    format_generation_metadata,
    format_value,
    render_instruction_section,
    render_risk_section,
    render_target_constraints,
)
from semantic_ci_code.repair_compiler.types import RISK_SUMMARY_KEYS, empty_risk_summary

_DEFAULT_PYTHON_GLOBS = ("**/*.py",)

_CATEGORY_SECTIONS = (
    (RepairCategory.FIX_REQUIRED, "Fix Required"),
    (RepairCategory.SUGGESTED, "Suggested"),
    (RepairCategory.INFO, "Info"),
    (RepairCategory.UNRESOLVED, "Unresolved"),
)


class CursorAdapter:
    """Render Cursor rules.

    Repair guidance is scoped to the current change, so `alwaysApply` is false.
    Pre-generation guidance should be active throughout generation, so `alwaysApply` is true.
    """

    name = "cursor"
    output_format = "mdc"
    schema_version = "1"

    def render_repair(self, plan: RepairPlan, target: TargetSVP | None) -> str:
        intent = target.intent if target is not None else ""
        lines = [
            *_render_frontmatter(
                "Semantic CI repair guidance for current change",
                _globs_for_target(target),
                always_apply=False,
            ),
            "",
            "# Semantic CI Repair Guidance",
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

    def render_pre_gen(self, target: TargetSVP, baseline_state: CodeState) -> str:
        del baseline_state
        allowed_secondary = (
            ", ".join(kind.value for kind in target.change.allowed_secondary_kinds) or "(none)"
        )
        lines = [
            *_render_frontmatter(
                "Semantic CI plan validation guidance",
                _globs_for_target(target),
                always_apply=True,
            ),
            "",
            "# Semantic CI Plan Validation",
            "",
            f"**Intent**: {target.intent}",
            f"**Primary kind**: {target.change.primary_kind.value}",
            f"**Allowed secondary kinds**: {allowed_secondary}",
            f"**Generation metadata**: {format_generation_metadata(target)}",
            "",
        ]
        lines.extend(render_target_constraints(target))
        risk_summary = empty_risk_summary()
        for key in RISK_SUMMARY_KEYS:
            lines.extend(render_risk_section(RISK_SECTION_TITLES[key], risk_summary[key]))
        return finish(lines)


def _render_frontmatter(
    description: str,
    globs: tuple[str, ...],
    *,
    always_apply: bool,
) -> list[str]:
    lines = ["---", f"description: {format_value(description)}", "globs:"]
    for glob in globs:
        lines.append(f"  - {format_value(glob)}")
    lines.append(f"alwaysApply: {'true' if always_apply else 'false'}")
    lines.append("---")
    return lines


def _globs_for_target(target: TargetSVP | None) -> tuple[str, ...]:
    if target is None:
        return _DEFAULT_PYTHON_GLOBS
    scope_files = tuple(target.change.scope.get("files", ()))
    # Brief 5 remains Python-only; revisit this default when TypeScript support resumes.
    return scope_files or _DEFAULT_PYTHON_GLOBS
