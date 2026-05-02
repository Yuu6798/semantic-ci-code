from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

JsonValue: TypeAlias = Any


class ConstraintKind(StrEnum):
    STATE = "state"
    DELTA = "delta"
    REPAIR = "repair"


class Operator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    EQUALS_BASELINE = "equals_baseline"
    NOT_EQUALS_BASELINE = "not_equals_baseline"
    INCLUDES_ALL = "includes_all"
    INCLUDES_ANY = "includes_any"
    EXCLUDES_ALL = "excludes_all"
    SUBSET_OF = "subset_of"
    SUPERSET_OF = "superset_of"
    SUPERSET_OF_BASELINE = "superset_of_baseline"
    NO_NEW_ITEMS = "no_new_items"
    NO_REMOVED_ITEMS = "no_removed_items"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    WITHIN_RANGE = "within_range"
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    CHANGED_ONLY_IN = "changed_only_in"


class Severity(StrEnum):
    HARD = "hard"
    SOFT = "soft"
    INFO = "info"


class UnknownPolicy(StrEnum):
    FAIL = "fail"
    REPAIR = "repair"
    WARN = "warn"
    IGNORE = "ignore"


class _BaseConstraint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    target: str
    operator: Operator
    expected: JsonValue = None
    severity: Severity = Severity.HARD
    unknown_policy: UnknownPolicy = UnknownPolicy.FAIL
    tolerance: float | None = None
    evidence_required: bool = False
    scope: JsonValue = None


class StateConstraint(_BaseConstraint):
    kind: Literal["state"] = ConstraintKind.STATE.value


class DeltaConstraint(_BaseConstraint):
    kind: Literal["delta"] = ConstraintKind.DELTA.value


class RepairConstraint(_BaseConstraint):
    kind: Literal["repair"] = ConstraintKind.REPAIR.value


Constraint: TypeAlias = Annotated[
    StateConstraint | DeltaConstraint | RepairConstraint,
    Field(discriminator="kind"),
]

CONSTRAINT_ADAPTER = TypeAdapter(Constraint)


def validate_constraint(data: object) -> Constraint:
    return CONSTRAINT_ADAPTER.validate_python(data)
