from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from semantic_ci_code.domain.state_schema import CodeState, JsonValue
from semantic_ci_code.framework.target_svp import TargetSVP
from semantic_ci_code.repair import RepairPlan
from semantic_ci_code.repair_compiler.types import (
    REPAIR_COMPILER_SCHEMA_VERSION,
    Adapter,
    CompiledPreGen,
    CompiledRepair,
    empty_risk_summary,
)

PACKAGE_NAME = "semantic-ci-code"
UNKNOWN_VERSION = "0.0.0"


class RepairCompiler:
    def __init__(self, adapter: Adapter) -> None:
        self.adapter = adapter

    def render_repair(
        self,
        plan: RepairPlan,
        target: TargetSVP | None = None,
    ) -> CompiledRepair:
        metadata = _repair_metadata(self.adapter, plan=plan, target=target)
        rendered = _ensure_trailing_newline(self.adapter.render_repair(plan, target))
        return CompiledRepair(
            adapter_name=self.adapter.name,
            output_format=self.adapter.output_format,
            rendered=rendered,
            metadata=metadata,
        )

    def render_pre_gen(
        self,
        target: TargetSVP,
        baseline_state: CodeState,
    ) -> CompiledPreGen:
        risk_summary = empty_risk_summary()
        metadata = _pre_gen_metadata(self.adapter, target=target)
        rendered = _ensure_trailing_newline(self.adapter.render_pre_gen(target, baseline_state))
        return CompiledPreGen(
            adapter_name=self.adapter.name,
            output_format=self.adapter.output_format,
            rendered=rendered,
            metadata=metadata,
            risk_summary=risk_summary,
        )


def _repair_metadata(
    adapter: Adapter,
    *,
    plan: RepairPlan,
    target: TargetSVP | None,
) -> dict[str, JsonValue]:
    return {
        "schema_version": REPAIR_COMPILER_SCHEMA_VERSION,
        "engine_package_version": _engine_package_version(),
        "adapter_name": adapter.name,
        "adapter_version": adapter.schema_version,
        "intent": target.intent if target is not None else "",
        "primary_kind": target.change.primary_kind.value if target is not None else "",
        "constraint_count": len(plan.instructions),
        "render_timestamp": None,
        "input_kind": "raw_repair_plan",
    }


def _pre_gen_metadata(adapter: Adapter, *, target: TargetSVP) -> dict[str, JsonValue]:
    return {
        "schema_version": REPAIR_COMPILER_SCHEMA_VERSION,
        "engine_package_version": _engine_package_version(),
        "adapter_name": adapter.name,
        "adapter_version": adapter.schema_version,
        "intent": target.intent,
        "primary_kind": target.change.primary_kind.value,
        "constraint_count": len(target.constraints),
        "render_timestamp": None,
        "input_kind": "target_svp",
    }


def _engine_package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def _ensure_trailing_newline(rendered: str) -> str:
    return rendered if rendered.endswith("\n") else f"{rendered}\n"
