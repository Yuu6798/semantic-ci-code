from __future__ import annotations

from typing import Any

from semantic_ci_code.compiler import ConstraintSource
from semantic_ci_code.domain.state_schema import JsonValue
from semantic_ci_code.evaluator import ResultStatus, UnknownCause, VerdictResult
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.repair.emitter import RepairCategory, RepairInstruction, RepairPlan


def deserialize_repair_plan(payload: dict[str, Any]) -> RepairPlan:
    """Restore a RepairPlan from the CLI JSON representation.

    This is the inverse of `_serialize_repair_plan` in
    `semantic_ci_code.cli.output.json_formatter`. Keep both in sync; the
    serialization round-trip tests guard that contract.
    """

    if not isinstance(payload, dict):
        raise ValueError("RepairPlan payload must be a JSON object")
    result = VerdictResult(_required(payload, "result"))
    instructions_raw = _required(payload, "instructions")
    if not isinstance(instructions_raw, list):
        raise ValueError("RepairPlan.instructions must be a list")
    return RepairPlan(
        result=result,
        instructions=tuple(_deserialize_instruction(item) for item in instructions_raw),
    )


def _deserialize_instruction(payload: object) -> RepairInstruction:
    if not isinstance(payload, dict):
        raise ValueError("RepairInstruction payload must be a JSON object")
    return RepairInstruction(
        constraint_id=str(_required(payload, "constraint_id")),
        source=ConstraintSource(_required(payload, "source")),
        kind=ConstraintKind(_required(payload, "kind")),
        target=str(_required(payload, "target")),
        operator=Operator(_required(payload, "operator")),
        severity=Severity(_required(payload, "severity")),
        unknown_policy=UnknownPolicy(_required(payload, "unknown_policy")),
        status=ResultStatus(_required(payload, "status")),
        error_code=_optional_str(payload.get("error_code")),
        repair_code=str(_required(payload, "repair_code")),
        category=RepairCategory(_required(payload, "category")),
        message=str(_required(payload, "message")),
        observed=_restore_json(payload.get("observed")),
        expected=_restore_json(payload.get("expected")),
        added=_tuple_field(payload, "added"),
        removed=_tuple_field(payload, "removed"),
        missing=_tuple_field(payload, "missing"),
        extra=_tuple_field(payload, "extra"),
        extra_evidence=_extra_evidence(payload),
        unknown_cause=_optional_unknown_cause(payload.get("unknown_cause")),
    )


def _optional_unknown_cause(value: object) -> UnknownCause | None:
    if value is None:
        return None
    return UnknownCause(value)


def _required(payload: dict[str, Any], key: str) -> Any:
    if key not in payload:
        raise ValueError(f"missing required key: {key}")
    return payload[key]


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _tuple_field(payload: dict[str, Any], key: str) -> tuple[JsonValue, ...]:
    value = _required(payload, key)
    if not isinstance(value, list | tuple):
        raise ValueError(f"{key} must be a list")
    return tuple(_restore_json(item) for item in value)


def _extra_evidence(payload: dict[str, Any]) -> tuple[tuple[str, JsonValue], ...]:
    value = _required(payload, "extra_evidence")
    if not isinstance(value, dict):
        raise ValueError("extra_evidence must be an object")
    return tuple((str(key), _restore_json(value[key])) for key in sorted(value))


def _restore_json(value: Any) -> JsonValue:
    if isinstance(value, list | tuple):
        return tuple(_restore_json(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _restore_json(item) for key, item in sorted(value.items())}
    return value
