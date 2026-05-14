from __future__ import annotations

from semantic_ci_code.compiler import ConstraintSource
from semantic_ci_code.evaluator import ConstraintResult, ResultStatus, Verdict, VerdictResult
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair import RepairPlan, emit_repair_plan


def constraint_result(
    *,
    constraint_id: str,
    target: str,
    operator: Operator = Operator.EQUALS,
    severity: Severity = Severity.HARD,
    status: ResultStatus = ResultStatus.VIOLATED,
    error_code: str | None = "E_VIOLATION",
    evidence: tuple[tuple[str, object], ...] = (),
) -> ConstraintResult:
    return ConstraintResult(
        constraint_id=constraint_id,
        source=ConstraintSource.USER,
        kind=ConstraintKind.DELTA,
        target=target,
        operator=operator,
        severity=severity,
        unknown_policy=UnknownPolicy.FAIL,
        tolerance=None,
        evidence_required=False,
        status=status,
        error_code=error_code,
        evidence=evidence,
    )


def sample_repair_plan() -> RepairPlan:
    hard = constraint_result(
        constraint_id="hard_api",
        target="api_surface_public",
        severity=Severity.HARD,
        evidence=(("expected", ()), ("observed", ("removed",))),
    )
    soft = constraint_result(
        constraint_id="soft_effect",
        target="effect_changes.added",
        severity=Severity.SOFT,
    )
    info = constraint_result(
        constraint_id="info_imports",
        target="imports_delta.added",
        severity=Severity.INFO,
    )
    skipped = constraint_result(
        constraint_id="changed_only_in",
        target="api_surface",
        operator=Operator.CHANGED_ONLY_IN,
        status=ResultStatus.SKIPPED,
        error_code="E_OPERATOR_UNSUPPORTED_P1",
    )
    verdict = Verdict(result=VerdictResult.FAIL, results=(hard, soft, info, skipped))
    return emit_repair_plan(verdict)


def pre_gen_risk_target():
    return parse_target_svp_yaml(
        """
intent: validate profile endpoint plan
change:
  primary_kind: refactor
  scope:
    files:
      - src/**/*.py
constraints:
  - id: lock_api_surface
    kind: delta
    target: api_surface
    operator: equals_baseline
  - id: require_missing_api
    kind: state
    target: api_surface
    operator: includes_all
    expected:
      - pkg.profile
"""
    )


def pre_gen_risk_summary():
    return {
        "authoring_errors": [],
        "would_violate": ["require_missing_api"],
        "forbidden_zones": [
            {
                "constraint_id": "lock_api_surface",
                "source": "user",
                "target": "api_surface",
                "operator": "equals_baseline",
            }
        ],
        "required_additions": [
            {
                "constraint_id": "require_missing_api",
                "source": "user",
                "target": "api_surface",
                "operator": "includes_all",
                "expected": "pkg.profile",
            }
        ],
        "template_implications": ["template:refactor:api_surface_unchanged"],
    }
