from __future__ import annotations

from semantic_ci_code.compiler.target_compiler import (
    CompiledConstraint,
    ConstraintSource,
)
from semantic_ci_code.domain.state_schema import ChangeKind
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)

__all__ = ["TEMPLATE_CONSTRAINTS"]


def _template(
    *,
    id: str,
    target: str,
    operator: Operator,
    expected: object = None,
) -> CompiledConstraint:
    return CompiledConstraint(
        id=id,
        kind=ConstraintKind.DELTA,
        target=target,
        operator=operator,
        expected=expected,
        severity=Severity.HARD,
        unknown_policy=UnknownPolicy.FAIL,
        tolerance=None,
        evidence_required=False,
        scope=None,
        source=ConstraintSource.TEMPLATE,
    )


TEMPLATE_CONSTRAINTS: dict[ChangeKind, tuple[CompiledConstraint, ...]] = {
    ChangeKind.REFACTOR: (
        _template(
            id="template:refactor:api_surface_unchanged",
            target="api_surface_public",
            operator=Operator.EQUALS_BASELINE,
        ),
        _template(
            id="template:refactor:type_relations_unchanged",
            target="type_relations",
            operator=Operator.EQUALS_BASELINE,
        ),
        _template(
            id="template:refactor:effects_unchanged",
            target="effect_changes",
            operator=Operator.EQUALS,
            expected={"added": (), "removed": ()},
        ),
        _template(
            id="template:refactor:test_surface_unchanged",
            target="test_surface",
            operator=Operator.EQUALS_BASELINE,
        ),
    ),
    ChangeKind.BUGFIX: (
        _template(
            id="template:bugfix:api_surface_unchanged",
            target="api_surface_public",
            operator=Operator.EQUALS_BASELINE,
        ),
        _template(
            id="template:bugfix:no_new_effects",
            target="effect_changes.added",
            operator=Operator.EQUALS,
            expected=(),
        ),
    ),
    ChangeKind.FEATURE: (
        _template(
            id="template:feature:no_removed_api",
            target="api_surface_delta.removed_public",
            operator=Operator.EQUALS,
            expected=(),
        ),
        _template(
            id="template:feature:no_new_effects",
            target="effect_changes.added",
            operator=Operator.EQUALS,
            expected=(),
        ),
    ),
    ChangeKind.TEST_UPDATE: (
        _template(
            id="template:test_update:api_surface_unchanged",
            target="api_surface_public",
            operator=Operator.EQUALS_BASELINE,
        ),
        _template(
            id="template:test_update:effects_unchanged",
            target="effect_changes",
            operator=Operator.EQUALS,
            expected={"added": (), "removed": ()},
        ),
        _template(
            id="template:test_update:imports_unchanged",
            target="imports",
            operator=Operator.EQUALS_BASELINE,
        ),
    ),
    ChangeKind.GENERIC: (),
}
