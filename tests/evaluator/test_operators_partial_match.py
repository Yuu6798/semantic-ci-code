from __future__ import annotations

from semantic_ci_code.compiler import CompiledConstraint, CompiledTarget, ConstraintSource
from semantic_ci_code.domain.state_schema import (
    APISurfaceEntry,
    ChangeKind,
    CodeState,
    CodeStateDelta,
    SymbolDelta,
)
from semantic_ci_code.evaluator import ResultStatus, evaluate_constraints
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)


def _api(fqn: str, *, signature: str = "def f(): ...") -> APISurfaceEntry:
    return APISurfaceEntry(
        fqn=fqn,
        kind="function",
        signature=signature,
        visibility="public",
    )


def _constraint(operator: Operator, expected: object) -> CompiledConstraint:
    return CompiledConstraint(
        id="partial",
        kind=ConstraintKind.DELTA,
        target="api_surface_delta.added",
        operator=operator,
        expected=expected,
        severity=Severity.HARD,
        unknown_policy=UnknownPolicy.FAIL,
        tolerance=None,
        evidence_required=False,
        scope=None,
        source=ConstraintSource.USER,
    )


def _result(operator: Operator, expected: object, observed: tuple[object, ...]):
    verdict = evaluate_constraints(
        CompiledTarget(
            intent="partial match",
            primary_kind=ChangeKind.FEATURE,
            allowed_secondary_kinds=(),
            scope=(),
            constraints=(_constraint(operator, expected),),
        ),
        CodeStateDelta(api_surface_delta=SymbolDelta(added=observed)),
        baseline=CodeState(),
        candidate=CodeState(),
    )
    return verdict.results[0]


def test_includes_any_partial_record_matches_observed_extra_fields():
    result = _result(
        Operator.INCLUDES_ANY,
        ({"fqn": "myapi.endpoints.password_reset"},),
        (_api("myapi.endpoints.password_reset", signature="def password_reset(email): ..."),),
    )

    assert result.status is ResultStatus.SATISFIED


def test_includes_any_null_optional_key_requires_observed_key_presence():
    result = _result(
        Operator.INCLUDES_ANY,
        ({"fqn": "pkg.maybe_public", "visibility": None},),
        ({"fqn": "pkg.maybe_public"},),
    )

    assert result.status is ResultStatus.VIOLATED


def test_excludes_all_partial_record_violation_reports_matched_pair():
    result = _result(
        Operator.EXCLUDES_ALL,
        ({"fqn": "dangerous.api"},),
        (_api("dangerous.api", signature="def dangerous_api(token): ..."),),
    )

    assert result.status is ResultStatus.VIOLATED
    evidence = dict(result.evidence)
    assert "matched" in evidence
    matched = evidence["matched"][0]
    assert dict(matched)["expected_item"] == (("fqn", "dangerous.api"),)
    assert ("signature", "def dangerous_api(token): ...") in dict(matched)["observed_record"]


def test_excludes_all_null_optional_key_requires_observed_key_presence():
    result = _result(
        Operator.EXCLUDES_ALL,
        ({"fqn": "pkg.maybe_public", "visibility": None},),
        ({"fqn": "pkg.maybe_public"},),
    )

    assert result.status is ResultStatus.SATISFIED


def test_subset_of_treats_expected_records_as_partial_allow_list():
    result = _result(
        Operator.SUBSET_OF,
        ({"fqn": "pkg.allowed_a"}, {"fqn": "pkg.allowed_b"}),
        (_api("pkg.allowed_a"), _api("pkg.allowed_b")),
    )

    assert result.status is ResultStatus.SATISFIED


def test_subset_of_violates_when_observed_record_matches_no_expected_partial():
    result = _result(
        Operator.SUBSET_OF,
        ({"fqn": "pkg.allowed_a"},),
        (_api("pkg.allowed_a"), _api("pkg.unlisted")),
    )

    assert result.status is ResultStatus.VIOLATED


def test_superset_of_is_includes_all_for_partial_records():
    result = _result(
        Operator.SUPERSET_OF,
        ({"fqn": "pkg.required"},),
        (_api("pkg.required"), _api("pkg.other")),
    )

    assert result.status is ResultStatus.SATISFIED


def test_flat_projection_alias_resolves_string_set_without_record_matching():
    verdict = evaluate_constraints(
        CompiledTarget(
            intent="flat projection",
            primary_kind=ChangeKind.FEATURE,
            allowed_secondary_kinds=(),
            scope=(),
            constraints=(
                CompiledConstraint(
                    id="flat",
                    kind=ConstraintKind.DELTA,
                    target="api_surface_delta.added.fqns",
                    operator=Operator.INCLUDES_ALL,
                    expected=("pkg.required",),
                    severity=Severity.HARD,
                    unknown_policy=UnknownPolicy.FAIL,
                    tolerance=None,
                    evidence_required=False,
                    scope=None,
                    source=ConstraintSource.USER,
                ),
            ),
        ),
        CodeStateDelta(api_surface_delta=SymbolDelta(added=(_api("pkg.required"),))),
        baseline=CodeState(),
        candidate=CodeState(),
    )

    assert verdict.results[0].status is ResultStatus.SATISFIED
