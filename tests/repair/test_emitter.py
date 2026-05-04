from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.compiler import ConstraintSource, compile_target_svp
from semantic_ci_code.compiler.templates import TEMPLATE_CONSTRAINTS
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.evaluator import (
    ConstraintResult,
    ResultStatus,
    Verdict,
    VerdictResult,
    evaluate_constraints,
)
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.pipeline import extract_python_code_state
from semantic_ci_code.repair import (
    REPAIR_CODES,
    RepairCategory,
    RepairPlan,
    emit_repair_plan,
)
from semantic_ci_code.repair.codes import resolve_repair_code

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def constraint_result(
    *,
    constraint_id: str = "constraint",
    source: ConstraintSource = ConstraintSource.USER,
    kind: ConstraintKind = ConstraintKind.DELTA,
    target: str = "api_surface",
    operator: Operator = Operator.EQUALS,
    severity: Severity = Severity.HARD,
    unknown_policy: UnknownPolicy = UnknownPolicy.FAIL,
    status: ResultStatus = ResultStatus.VIOLATED,
    error_code: str | None = "E_VIOLATION",
    evidence: tuple[tuple[str, object], ...] = (),
) -> ConstraintResult:
    return ConstraintResult(
        constraint_id=constraint_id,
        source=source,
        kind=kind,
        target=target,
        operator=operator,
        severity=severity,
        unknown_policy=unknown_policy,
        tolerance=None,
        evidence_required=False,
        status=status,
        error_code=error_code,
        evidence=evidence,
    )


def verdict(
    *results: ConstraintResult,
    result: VerdictResult = VerdictResult.FAIL,
) -> Verdict:
    return Verdict(result=result, results=results)


def emit_one(item: ConstraintResult, *, verdict_result: VerdictResult = VerdictResult.FAIL):
    plan = emit_repair_plan(verdict(item, result=verdict_result))
    assert len(plan.instructions) == 1
    return plan.instructions[0]


def test_all_satisfied_verdict_returns_empty_pass_plan():
    item = constraint_result(status=ResultStatus.SATISFIED, error_code=None)

    plan = emit_repair_plan(verdict(item, result=VerdictResult.PASS))

    assert plan == RepairPlan(result=VerdictResult.PASS, instructions=())


def test_hard_violation_emits_fix_required():
    instruction = emit_one(
        constraint_result(severity=Severity.HARD),
        verdict_result=VerdictResult.FAIL,
    )

    assert instruction.category is RepairCategory.FIX_REQUIRED


def test_soft_violation_emits_suggested():
    instruction = emit_one(
        constraint_result(severity=Severity.SOFT),
        verdict_result=VerdictResult.REPAIR,
    )

    assert instruction.category is RepairCategory.SUGGESTED


def test_info_violation_emits_info_while_plan_mirrors_pass():
    plan = emit_repair_plan(
        verdict(
            constraint_result(severity=Severity.INFO),
            result=VerdictResult.PASS,
        )
    )

    assert plan.result is VerdictResult.PASS
    assert plan.instructions[0].category is RepairCategory.INFO
    assert plan.info == plan.instructions


def test_unknown_fail_emits_fix_required():
    instruction = emit_one(
        constraint_result(
            status=ResultStatus.UNKNOWN,
            error_code="E_PATH_UNRESOLVED",
            unknown_policy=UnknownPolicy.FAIL,
        ),
        verdict_result=VerdictResult.FAIL,
    )

    assert instruction.category is RepairCategory.FIX_REQUIRED


def test_unknown_repair_emits_suggested():
    instruction = emit_one(
        constraint_result(
            status=ResultStatus.UNKNOWN,
            error_code="E_PATH_UNRESOLVED",
            unknown_policy=UnknownPolicy.REPAIR,
        ),
        verdict_result=VerdictResult.REPAIR,
    )

    assert instruction.category is RepairCategory.SUGGESTED


def test_unknown_warn_emits_unresolved_while_plan_mirrors_pass():
    plan = emit_repair_plan(
        verdict(
            constraint_result(
                status=ResultStatus.UNKNOWN,
                error_code="E_PATH_UNRESOLVED",
                unknown_policy=UnknownPolicy.WARN,
            ),
            result=VerdictResult.PASS,
        )
    )

    assert plan.result is VerdictResult.PASS
    assert plan.instructions[0].category is RepairCategory.UNRESOLVED
    assert plan.unresolved == plan.instructions


def test_unknown_ignore_is_not_emitted():
    plan = emit_repair_plan(
        verdict(
            constraint_result(
                status=ResultStatus.UNKNOWN,
                error_code="E_PATH_UNRESOLVED",
                unknown_policy=UnknownPolicy.IGNORE,
            ),
            result=VerdictResult.PASS,
        )
    )

    assert plan.instructions == ()


def test_skipped_emits_unresolved():
    instruction = emit_one(
        constraint_result(
            status=ResultStatus.SKIPPED,
            error_code="E_OPERATOR_UNSUPPORTED_P1",
            operator=Operator.CHANGED_ONLY_IN,
        ),
        verdict_result=VerdictResult.PASS,
    )

    assert instruction.category is RepairCategory.UNRESOLVED


@pytest.mark.parametrize(
    ("expected_code", "item"),
    [
        (
            "R_API_REMOVED",
            constraint_result(
                constraint_id="template:feature:no_removed_api",
                source=ConstraintSource.TEMPLATE,
            ),
        ),
        (
            "R_API_CHANGED",
            constraint_result(
                constraint_id="template:refactor:api_surface_unchanged",
                source=ConstraintSource.TEMPLATE,
            ),
        ),
        (
            "R_TYPE_RELATIONS_CHANGED",
            constraint_result(
                constraint_id="template:refactor:type_relations_unchanged",
                source=ConstraintSource.TEMPLATE,
            ),
        ),
        (
            "R_EFFECTS_CHANGED",
            constraint_result(
                constraint_id="template:test_update:effects_unchanged",
                source=ConstraintSource.TEMPLATE,
            ),
        ),
        (
            "R_NEW_EFFECT",
            constraint_result(
                constraint_id="template:bugfix:no_new_effects",
                source=ConstraintSource.TEMPLATE,
            ),
        ),
        (
            "R_TEST_SURFACE_CHANGED",
            constraint_result(
                constraint_id="template:refactor:test_surface_unchanged",
                source=ConstraintSource.TEMPLATE,
            ),
        ),
        (
            "R_IMPORTS_CHANGED",
            constraint_result(
                constraint_id="template:test_update:imports_unchanged",
                source=ConstraintSource.TEMPLATE,
            ),
        ),
        ("R_USER_VIOLATION", constraint_result(constraint_id="user_rule")),
        (
            "R_PATH_UNRESOLVED",
            constraint_result(status=ResultStatus.UNKNOWN, error_code="E_PATH_UNRESOLVED"),
        ),
        (
            "R_TYPE_MISMATCH",
            constraint_result(status=ResultStatus.UNKNOWN, error_code="E_TYPE_MISMATCH"),
        ),
        (
            "R_OPERATOR_TARGET_MISMATCH",
            constraint_result(
                status=ResultStatus.UNKNOWN,
                error_code="E_OPERATOR_TARGET_MISMATCH",
            ),
        ),
        (
            "R_UNSUPPORTED_OPERATOR",
            constraint_result(
                status=ResultStatus.SKIPPED,
                error_code="E_OPERATOR_UNSUPPORTED_P1",
                operator=Operator.CHANGED_ONLY_IN,
            ),
        ),
        (
            "R_UNSUPPORTED_REPAIR_KIND",
            constraint_result(
                kind=ConstraintKind.REPAIR,
                status=ResultStatus.SKIPPED,
                error_code="E_REPAIR_KIND_UNSUPPORTED_P1",
            ),
        ),
        (
            "R_UNKNOWN",
            constraint_result(status=ResultStatus.UNKNOWN, error_code="E_FUTURE"),
        ),
    ],
)
def test_repair_code_lookup_covers_p1_set(expected_code: str, item: ConstraintResult):
    assert expected_code in REPAIR_CODES
    assert emit_one(item).repair_code == expected_code


def test_template_repair_map_covers_all_template_constraint_ids():
    for constraints in TEMPLATE_CONSTRAINTS.values():
        for template in constraints:
            item = constraint_result(
                constraint_id=template.id,
                source=ConstraintSource.TEMPLATE,
            )

            assert resolve_repair_code(item) != "R_USER_VIOLATION"


def test_template_violation_uses_specific_repair_code():
    instruction = emit_one(
        constraint_result(
            constraint_id="template:refactor:api_surface_unchanged",
            source=ConstraintSource.TEMPLATE,
        )
    )

    assert instruction.repair_code == "R_API_CHANGED"


def test_user_violation_uses_user_repair_code():
    instruction = emit_one(constraint_result(constraint_id="user:api_rule"))

    assert instruction.repair_code == "R_USER_VIOLATION"


def test_instruction_source_is_carried_through():
    instruction = emit_one(constraint_result(source=ConstraintSource.TEMPLATE))

    assert instruction.source is ConstraintSource.TEMPLATE


def test_observed_and_expected_evidence_are_surfaced():
    instruction = emit_one(constraint_result(evidence=(("expected", ("b",)), ("observed", ("a",)))))

    assert instruction.observed == ("a",)
    assert instruction.expected == ("b",)


def test_collection_evidence_keys_are_tupled_and_surfaced():
    instruction = emit_one(
        constraint_result(
            evidence=(
                ("added", ["new"]),
                ("extra", ("extra",)),
                ("missing", ["missing"]),
                ("removed", ("old",)),
            )
        )
    )

    assert instruction.added == ("new",)
    assert instruction.removed == ("old",)
    assert instruction.missing == ("missing",)
    assert instruction.extra == ("extra",)


def test_unknown_evidence_keys_are_preserved_as_extra_evidence():
    instruction = emit_one(constraint_result(evidence=(("zeta", 2), ("baseline", ("a",)))))

    assert instruction.extra_evidence == (("baseline", ("a",)), ("zeta", 2))


def test_empty_evidence_uses_default_instruction_fields():
    instruction = emit_one(constraint_result(evidence=()))

    assert instruction.observed is None
    assert instruction.expected is None
    assert instruction.added == ()
    assert instruction.removed == ()
    assert instruction.missing == ()
    assert instruction.extra == ()
    assert instruction.extra_evidence == ()


def test_instruction_order_preserves_filtered_verdict_result_order():
    first = constraint_result(constraint_id="template:first", source=ConstraintSource.TEMPLATE)
    dropped = constraint_result(
        constraint_id="ignore",
        status=ResultStatus.UNKNOWN,
        error_code="E_PATH_UNRESOLVED",
        unknown_policy=UnknownPolicy.IGNORE,
    )
    second = constraint_result(constraint_id="user:second")
    third = constraint_result(constraint_id="template:third", source=ConstraintSource.TEMPLATE)
    plan = emit_repair_plan(verdict(first, dropped, second, third))

    assert tuple(instruction.constraint_id for instruction in plan.instructions) == (
        "template:first",
        "user:second",
        "template:third",
    )


def test_template_message_includes_primary_kind_and_constraint_id():
    instruction = emit_one(
        constraint_result(
            constraint_id="template:refactor:api_surface_unchanged",
            source=ConstraintSource.TEMPLATE,
        )
    )

    assert "refactor" in instruction.message
    assert "template:refactor:api_surface_unchanged" in instruction.message


def test_user_message_includes_constraint_id_operator_and_target():
    instruction = emit_one(
        constraint_result(
            constraint_id="user_rule",
            target="complexity_delta.cyclomatic",
            operator=Operator.LESS_THAN_OR_EQUAL,
        )
    )

    assert "user_rule" in instruction.message
    assert "less_than_or_equal" in instruction.message
    assert "complexity_delta.cyclomatic" in instruction.message


def test_message_is_deterministic_for_same_instruction():
    item = constraint_result(
        constraint_id="template:feature:no_removed_api",
        source=ConstraintSource.TEMPLATE,
    )

    first = emit_one(item)
    second = emit_one(item)

    assert first.message == second.message


def test_hand_built_verdict_engine_contract():
    item = constraint_result(
        constraint_id="hand_built",
        evidence=(("observed", {"names": ("a", "b")}),),
    )

    plan = emit_repair_plan(verdict(item))

    assert plan.result is VerdictResult.FAIL
    assert plan.instructions[0].constraint_id == "hand_built"
    assert hash(plan.instructions[0])
    assert hash(plan)


def test_same_process_determinism():
    item = constraint_result(
        constraint_id="deterministic",
        evidence=(("extra", ["b", "a"]), ("observed", {"value": ("x",)})),
    )

    first = emit_repair_plan(verdict(item))
    second = emit_repair_plan(verdict(item))

    assert first == second
    assert repr(first) == repr(second)


def test_subprocess_determinism_across_hash_seeds():
    script = """
from semantic_ci_code.compiler import ConstraintSource
from semantic_ci_code.evaluator import ConstraintResult, ResultStatus, Verdict, VerdictResult
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.repair import emit_repair_plan

result = ConstraintResult(
    constraint_id="deterministic",
    source=ConstraintSource.USER,
    kind=ConstraintKind.DELTA,
    target="api_surface",
    operator=Operator.EQUALS,
    severity=Severity.HARD,
    unknown_policy=UnknownPolicy.FAIL,
    tolerance=None,
    evidence_required=False,
    status=ResultStatus.VIOLATED,
    error_code="E_VIOLATION",
    evidence=(("observed", {"names": ("a", "b")}),),
)
plan = emit_repair_plan(Verdict(result=VerdictResult.FAIL, results=(result,)))
print(repr(plan))
"""

    first = _run_subprocess(script, hash_seed="1")
    second = _run_subprocess(script, hash_seed="2")

    assert first == second


def _run_subprocess(script: str, *, hash_seed: str) -> str:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return result.stdout


def test_pipeline_delta_compiler_evaluator_repair_integration():
    evaluator_fixtures = FIXTURES / "evaluator"
    baseline = extract_python_code_state(evaluator_fixtures / "baseline_pkg")
    candidate = extract_python_code_state(evaluator_fixtures / "candidate_pkg")
    delta = compute_code_state_delta(baseline, candidate)
    compiled = compile_target_svp(
        (FIXTURES / "repair" / "integration.yaml").read_text(encoding="utf-8")
    )
    verdict_result = evaluate_constraints(compiled, delta, baseline=baseline, candidate=candidate)

    plan = emit_repair_plan(verdict_result)

    assert plan.result is VerdictResult.FAIL
    assert "R_API_CHANGED" in {instruction.repair_code for instruction in plan.instructions}
