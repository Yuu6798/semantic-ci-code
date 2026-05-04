from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from semantic_ci_code.compiler import CompiledConstraint, CompiledTarget
from semantic_ci_code.domain.state_schema import CodeState, LocDelta
from semantic_ci_code.evaluator import ConstraintResult, ResultStatus, Verdict
from semantic_ci_code.repair import RepairCategory, RepairInstruction, RepairPlan

SCHEMA_VERSION = "1"
PACKAGE_NAME = "semantic-ci-code"
UNKNOWN_VERSION = "0.0.0+unknown"


def package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def build_payload(
    subcommand: str,
    *,
    state: CodeState | None = None,
    compiled: CompiledTarget | None = None,
    verdict: Verdict | None = None,
    repair_plan: RepairPlan | None = None,
    files_touched: int = 0,
    loc_delta: LocDelta | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "subcommand": subcommand,
        "verdict": verdict.result.value if verdict is not None else None,
        "intent": compiled.intent if compiled is not None else None,
        "primary_kind": compiled.primary_kind.value if compiled is not None else None,
        "allowed_secondary_kinds": (
            [kind.value for kind in compiled.allowed_secondary_kinds]
            if compiled is not None
            else []
        ),
        "summary": _summary(verdict, repair_plan) if verdict is not None else None,
        "results": (
            [_serialize_constraint_result(result) for result in verdict.results]
            if verdict is not None
            else []
        ),
        "repair_plan": _serialize_repair_plan(repair_plan) if repair_plan is not None else None,
        "code_state": state.model_dump(mode="json") if state is not None else None,
        "files_touched": files_touched,
        "loc_delta": _serialize_loc_delta(loc_delta or LocDelta()),
        "engine": {
            "extractor_pyver": f"{sys.version_info.major}.{sys.version_info.minor}",
            "package_version": package_version(),
        },
    }


def build_observe_payload(state: CodeState) -> dict[str, Any]:
    return build_payload("observe", state=state)


def build_compile_payload(compiled: CompiledTarget) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "subcommand": "compile",
        "compiled_target": {
            "intent": compiled.intent,
            "primary_kind": compiled.primary_kind.value,
            "allowed_secondary_kinds": [kind.value for kind in compiled.allowed_secondary_kinds],
            "scope": [[key, list(values)] for key, values in compiled.scope],
            "constraints": [
                _serialize_compiled_constraint(constraint) for constraint in compiled.constraints
            ],
        },
        "engine": {
            "extractor_pyver": f"{sys.version_info.major}.{sys.version_info.minor}",
            "package_version": package_version(),
        },
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _summary(verdict: Verdict, repair_plan: RepairPlan | None) -> dict[str, int]:
    instructions = repair_plan.instructions if repair_plan is not None else ()
    return {
        "fix_required": sum(
            1 for item in instructions if item.category is RepairCategory.FIX_REQUIRED
        ),
        "suggested": sum(1 for item in instructions if item.category is RepairCategory.SUGGESTED),
        "info": sum(1 for item in instructions if item.category is RepairCategory.INFO),
        "unresolved": sum(1 for item in instructions if item.category is RepairCategory.UNRESOLVED),
        "satisfied": sum(1 for item in verdict.results if item.status is ResultStatus.SATISFIED),
    }


def _serialize_constraint_result(result: ConstraintResult) -> dict[str, Any]:
    return {
        "constraint_id": result.constraint_id,
        "source": result.source.value,
        "kind": result.kind.value,
        "target": result.target,
        "operator": result.operator.value,
        "severity": result.severity.value,
        "unknown_policy": result.unknown_policy.value,
        "tolerance": result.tolerance,
        "evidence_required": result.evidence_required,
        "status": result.status.value,
        "error_code": result.error_code,
        "evidence": _pairs_to_dict(result.evidence),
    }


def _serialize_compiled_constraint(constraint: CompiledConstraint) -> dict[str, Any]:
    return {
        "id": constraint.id,
        "source": constraint.source.value,
        "kind": constraint.kind.value,
        "target": constraint.target,
        "operator": constraint.operator.value,
        "expected": _json_value(constraint.expected),
        "severity": constraint.severity.value,
        "unknown_policy": constraint.unknown_policy.value,
        "tolerance": constraint.tolerance,
        "evidence_required": constraint.evidence_required,
        "scope": _json_value(constraint.scope),
    }


def _serialize_repair_plan(plan: RepairPlan) -> dict[str, Any]:
    return {
        "result": plan.result.value,
        "instructions": [
            _serialize_repair_instruction(instruction) for instruction in plan.instructions
        ],
    }


def _serialize_repair_instruction(instruction: RepairInstruction) -> dict[str, Any]:
    return {
        "constraint_id": instruction.constraint_id,
        "source": instruction.source.value,
        "kind": instruction.kind.value,
        "target": instruction.target,
        "operator": instruction.operator.value,
        "severity": instruction.severity.value,
        "unknown_policy": instruction.unknown_policy.value,
        "status": instruction.status.value,
        "error_code": instruction.error_code,
        "repair_code": instruction.repair_code,
        "category": instruction.category.value,
        "message": instruction.message,
        "observed": _json_value(instruction.observed),
        "expected": _json_value(instruction.expected),
        "added": [_json_value(item) for item in instruction.added],
        "removed": [_json_value(item) for item in instruction.removed],
        "missing": [_json_value(item) for item in instruction.missing],
        "extra": [_json_value(item) for item in instruction.extra],
        "extra_evidence": _pairs_to_dict(instruction.extra_evidence),
    }


def _serialize_loc_delta(loc_delta: LocDelta) -> dict[str, int]:
    return {"added": loc_delta.added, "removed": loc_delta.removed}


def _pairs_to_dict(pairs: tuple[tuple[str, Any], ...]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in pairs}


def _json_value(value: Any) -> Any:
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value
