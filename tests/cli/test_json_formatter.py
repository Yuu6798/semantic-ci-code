from __future__ import annotations

from semantic_ci_code.cli.output.json_formatter import build_compile_payload
from semantic_ci_code.compiler import CompiledConstraint, CompiledTarget, ConstraintSource
from semantic_ci_code.domain.state_schema import ChangeKind
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)


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
