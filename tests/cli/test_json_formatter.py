from __future__ import annotations

from semantic_ci_code.cli.output.json_formatter import build_compile_payload, build_payload
from semantic_ci_code.compiler import CompiledConstraint, CompiledTarget, ConstraintSource
from semantic_ci_code.domain.state_schema import ChangeKind
from semantic_ci_code.evaluator import ConstraintResult, ResultStatus, Verdict, VerdictResult
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.repair import RepairPlan


def test_compile_payload_preserves_non_evidence_pair_arrays():
    compiled = CompiledTarget(
        intent="pair arrays are data",
        primary_kind=ChangeKind.FEATURE,
        allowed_secondary_kinds=(),
        scope=(),
        constraints=(
            CompiledConstraint(
                id="pair_array",
                kind=ConstraintKind.DELTA,
                target="python_specific.pairs",
                operator=Operator.EQUALS,
                expected=(("left", "right"), ("answer", 42)),
                severity=Severity.HARD,
                unknown_policy=UnknownPolicy.FAIL,
                tolerance=None,
                evidence_required=False,
                scope=None,
                source=ConstraintSource.USER,
            ),
        ),
    )

    constraint = build_compile_payload(compiled)["compiled_target"]["constraints"][0]

    assert constraint["expected"] == [["left", "right"], ["answer", 42]]


def test_verdict_payload_preserves_string_pair_arrays_in_evidence():
    compiled = _compiled_with_constraint()
    verdict = Verdict(
        result=VerdictResult.FAIL,
        results=(
            ConstraintResult(
                constraint_id="open_pairs",
                source=ConstraintSource.USER,
                kind=ConstraintKind.DELTA,
                target="python_specific.module_graph_delta.added_edges",
                operator=Operator.EXCLUDES_ALL,
                severity=Severity.HARD,
                unknown_policy=UnknownPolicy.FAIL,
                tolerance=None,
                evidence_required=False,
                status=ResultStatus.VIOLATED,
                error_code="E_VIOLATION",
                evidence=(
                    ("observed", (("pkg.a", "pkg.b"), ("pkg.a", "pkg.c"))),
                    ("expected", (("pkg.a", "pkg.b"),)),
                ),
            ),
        ),
    )

    payload = build_payload(
        "compare",
        compiled=compiled,
        verdict=verdict,
        repair_plan=RepairPlan(result=VerdictResult.FAIL, instructions=()),
    )
    evidence = payload["results"][0]["evidence"]

    assert evidence["observed"] == [["pkg.a", "pkg.b"], ["pkg.a", "pkg.c"]]
    assert evidence["expected"] == [["pkg.a", "pkg.b"]]


def _compiled_with_constraint() -> CompiledTarget:
    return CompiledTarget(
        intent="pair arrays are data",
        primary_kind=ChangeKind.FEATURE,
        allowed_secondary_kinds=(),
        scope=(),
        constraints=(
            CompiledConstraint(
                id="open_pairs",
                kind=ConstraintKind.DELTA,
                target="python_specific.module_graph_delta.added_edges",
                operator=Operator.EXCLUDES_ALL,
                expected=(("pkg.a", "pkg.b"),),
                severity=Severity.HARD,
                unknown_policy=UnknownPolicy.FAIL,
                tolerance=None,
                evidence_required=False,
                scope=None,
                source=ConstraintSource.USER,
            ),
        ),
    )
