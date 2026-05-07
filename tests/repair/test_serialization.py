from __future__ import annotations

import pytest

from semantic_ci_code.cli.output.json_formatter import build_payload
from semantic_ci_code.compiler import ConstraintSource
from semantic_ci_code.evaluator import ConstraintResult, ResultStatus, Verdict, VerdictResult
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.repair import deserialize_repair_plan, emit_repair_plan


def sample_repair_plan():
    result = ConstraintResult(
        constraint_id="hard_api",
        source=ConstraintSource.USER,
        kind=ConstraintKind.DELTA,
        target="api_surface_public",
        operator=Operator.EQUALS,
        severity=Severity.HARD,
        unknown_policy=UnknownPolicy.FAIL,
        tolerance=None,
        evidence_required=False,
        status=ResultStatus.VIOLATED,
        error_code="E_VIOLATION",
        evidence=(("expected", ()), ("observed", ("removed",))),
    )
    return emit_repair_plan(Verdict(result=VerdictResult.FAIL, results=(result,)))


def serialized_plan():
    return build_payload("compare", repair_plan=sample_repair_plan())["repair_plan"]


def test_deserialize_repair_plan_round_trips_cli_json_shape():
    plan = sample_repair_plan()
    payload = build_payload("compare", repair_plan=plan)["repair_plan"]

    assert deserialize_repair_plan(payload) == plan


def test_deserialize_repair_plan_rejects_invalid_result_enum():
    payload = serialized_plan()
    payload["result"] = "maybe"

    with pytest.raises(ValueError):
        deserialize_repair_plan(payload)


def test_deserialize_repair_plan_rejects_invalid_instruction_enum():
    payload = serialized_plan()
    payload["instructions"][0]["severity"] = "urgent"

    with pytest.raises(ValueError):
        deserialize_repair_plan(payload)


def test_deserialize_repair_plan_rejects_missing_required_key():
    payload = serialized_plan()
    del payload["instructions"][0]["repair_code"]

    with pytest.raises(ValueError, match="missing required key: repair_code"):
        deserialize_repair_plan(payload)
