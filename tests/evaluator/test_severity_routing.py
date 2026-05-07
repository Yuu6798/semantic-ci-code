from __future__ import annotations

from dataclasses import replace

import pytest

from semantic_ci_code.compiler import compile_target_svp
from semantic_ci_code.domain.state_schema import CodeState, CodeStateDelta
from semantic_ci_code.evaluator import ResultStatus, VerdictResult, evaluate_constraints
from semantic_ci_code.evaluator.evaluator import _aggregate
from semantic_ci_code.repair import RepairCategory, emit_repair_plan


@pytest.mark.parametrize(
    ("severity", "expected_verdict", "expected_category"),
    [
        ("hard", VerdictResult.FAIL, RepairCategory.FIX_REQUIRED),
        ("soft", VerdictResult.REPAIR, RepairCategory.SUGGESTED),
        ("info", VerdictResult.PASS, RepairCategory.INFO),
    ],
)
def test_violation_severity_routes_to_expected_verdict_and_repair_category(
    severity: str,
    expected_verdict: VerdictResult,
    expected_category: RepairCategory,
):
    compiled = compile_target_svp(
        f"""
intent: severity routing
change:
  primary_kind: feature
constraints:
  - id: user_{severity}
    kind: delta
    target: files_touched
    operator: equals
    expected: 99
    severity: {severity}
    unknown_policy: fail
"""
    )

    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(files_touched=0),
        baseline=CodeState(),
        candidate=CodeState(),
    )
    plan = emit_repair_plan(verdict)
    result = next(item for item in verdict.results if item.constraint_id == f"user_{severity}")

    assert result.status is ResultStatus.VIOLATED
    assert verdict.result is expected_verdict
    assert plan.instructions[-1].category is expected_category


def test_unknown_severity_is_exhaustive_guard_failure():
    compiled = compile_target_svp(
        """
intent: severity routing
change:
  primary_kind: feature
constraints:
  - id: user_hard
    kind: delta
    target: files_touched
    operator: equals
    expected: 99
    severity: hard
    unknown_policy: fail
"""
    )
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(files_touched=0),
        baseline=CodeState(),
        candidate=CodeState(),
    )
    result = next(item for item in verdict.results if item.constraint_id == "user_hard")

    with pytest.raises(NotImplementedError, match="unhandled severity"):
        _aggregate((replace(result, severity="future"),))
