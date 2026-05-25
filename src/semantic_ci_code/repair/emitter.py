"""Emit deterministic structured repair plans from evaluator verdicts.

``emit_repair_plan(verdict)`` is a pure, total, deterministic translation from
CSCI-13 ``Verdict`` data into JSON-shaped repair data. It performs no rendering,
file I/O, network access, LLM calls, git operations, time reads, or environment
reads. Brief 4 owns Markdown/SARIF/GitHub annotation rendering and exit-code
routing.

Filtering and categories are fixed for P1:

* ``SATISFIED`` constraints are not emitted.
* ``UNKNOWN`` constraints with ``unknown_policy=ignore`` are not emitted.
* hard violations and ``unknown_policy=fail`` unknowns are ``fix_required``.
* soft violations and ``unknown_policy=repair`` unknowns are ``suggested``.
* info violations are ``info``.
* ``unknown_policy=warn`` unknowns and evaluator ``SKIPPED`` constraints are
  ``unresolved``, except post-hard-failure short-circuit skips which are not
  actionable repair instructions.

Instruction order preserves ``verdict.results`` order after filtering. The
repair plan mirrors ``verdict.result`` exactly and does not re-aggregate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from semantic_ci_code.compiler import ConstraintSource
from semantic_ci_code.domain.state_schema import JsonValue
from semantic_ci_code.evaluator import (
    ConstraintResult,
    ResultStatus,
    UnknownCause,
    Verdict,
    VerdictResult,
)
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.repair.codes import resolve_repair_code

__all__ = [
    "RepairCategory",
    "RepairInstruction",
    "RepairPlan",
    "emit_repair_plan",
]

_TEMPLATE_ID_PATTERN: Final = re.compile(r"^template:(?P<primary_kind>[A-Za-z_][A-Za-z0-9_]*):")
_NAMED_EVIDENCE_KEYS: Final = frozenset(
    {"observed", "expected", "added", "removed", "missing", "extra"}
)
_TUPLE_EVIDENCE_KEYS: Final = ("added", "removed", "missing", "extra")
_SHORT_CIRCUIT_SKIP_ERROR_CODE: Final = "E_HARD_LOCK_SHORT_CIRCUIT"
_TEMPLATE_REPAIR_CODES: Final = frozenset(
    {
        "R_API_REMOVED",
        "R_API_CHANGED",
        "R_TYPE_RELATIONS_CHANGED",
        "R_EFFECTS_CHANGED",
        "R_NEW_EFFECT",
        "R_TEST_SURFACE_CHANGED",
        "R_IMPORTS_CHANGED",
    }
)
_EXPECTED_STATE_BY_REPAIR_CODE: Final = {
    "R_API_REMOVED": "without removed API",
    "R_API_CHANGED": "unchanged",
    "R_TYPE_RELATIONS_CHANGED": "unchanged",
    "R_EFFECTS_CHANGED": "unchanged",
    "R_NEW_EFFECT": "without new effects",
    "R_TEST_SURFACE_CHANGED": "unchanged",
    "R_IMPORTS_CHANGED": "unchanged",
}


class RepairCategory(StrEnum):
    FIX_REQUIRED = "fix_required"
    SUGGESTED = "suggested"
    INFO = "info"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class RepairInstruction:
    constraint_id: str
    source: ConstraintSource
    kind: ConstraintKind
    target: str
    operator: Operator
    severity: Severity
    unknown_policy: UnknownPolicy
    status: ResultStatus
    error_code: str | None
    repair_code: str
    category: RepairCategory
    message: str
    observed: JsonValue
    expected: JsonValue
    added: tuple[JsonValue, ...]
    removed: tuple[JsonValue, ...]
    missing: tuple[JsonValue, ...]
    extra: tuple[JsonValue, ...]
    extra_evidence: tuple[tuple[str, JsonValue], ...]
    unknown_cause: UnknownCause | None = None

    def __hash__(self) -> int:
        return hash(
            (
                self.constraint_id,
                self.source,
                self.kind,
                self.target,
                self.operator,
                self.severity,
                self.unknown_policy,
                self.status,
                self.error_code,
                self.repair_code,
                self.category,
                self.message,
                _hashable_json(self.observed),
                _hashable_json(self.expected),
                _hashable_json(self.added),
                _hashable_json(self.removed),
                _hashable_json(self.missing),
                _hashable_json(self.extra),
                _hashable_json(self.extra_evidence),
                self.unknown_cause,
            )
        )


@dataclass(frozen=True)
class RepairPlan:
    result: VerdictResult
    instructions: tuple[RepairInstruction, ...]

    @property
    def fix_required(self) -> tuple[RepairInstruction, ...]:
        return tuple(
            instruction
            for instruction in self.instructions
            if instruction.category is RepairCategory.FIX_REQUIRED
        )

    @property
    def suggested(self) -> tuple[RepairInstruction, ...]:
        return tuple(
            instruction
            for instruction in self.instructions
            if instruction.category is RepairCategory.SUGGESTED
        )

    @property
    def info(self) -> tuple[RepairInstruction, ...]:
        return tuple(
            instruction
            for instruction in self.instructions
            if instruction.category is RepairCategory.INFO
        )

    @property
    def unresolved(self) -> tuple[RepairInstruction, ...]:
        return tuple(
            instruction
            for instruction in self.instructions
            if instruction.category is RepairCategory.UNRESOLVED
        )


def emit_repair_plan(verdict: Verdict) -> RepairPlan:
    """Translate a Verdict into a deterministic structured RepairPlan."""

    instructions = tuple(
        instruction
        for instruction in (_instruction_or_none(result) for result in verdict.results)
        if instruction is not None
    )
    return RepairPlan(result=verdict.result, instructions=instructions)


def _instruction_or_none(result: ConstraintResult) -> RepairInstruction | None:
    category = _category_or_none(result)
    if category is None:
        return None

    repair_code = resolve_repair_code(result)
    evidence = _surface_evidence(result.evidence)
    return RepairInstruction(
        constraint_id=result.constraint_id,
        source=result.source,
        kind=result.kind,
        target=result.target,
        operator=result.operator,
        severity=result.severity,
        unknown_policy=result.unknown_policy,
        status=result.status,
        error_code=result.error_code,
        repair_code=repair_code,
        category=category,
        message=_message(result, repair_code),
        observed=evidence.observed,
        expected=evidence.expected,
        added=evidence.added,
        removed=evidence.removed,
        missing=evidence.missing,
        extra=evidence.extra,
        extra_evidence=evidence.extra_evidence,
        unknown_cause=result.unknown_cause,
    )


def _category_or_none(result: ConstraintResult) -> RepairCategory | None:
    if result.status is ResultStatus.SATISFIED:
        return None

    if result.status is ResultStatus.VIOLATED:
        if result.severity is Severity.HARD:
            return RepairCategory.FIX_REQUIRED
        if result.severity is Severity.SOFT:
            return RepairCategory.SUGGESTED
        if result.severity is Severity.INFO:
            return RepairCategory.INFO

    if result.status is ResultStatus.UNKNOWN:
        # Authoring-cause UNKNOWN forces fix_required regardless of
        # unknown_policy: a malformed spec is invalid input that must be
        # corrected before the generator can iterate on the implementation
        # (planning §3 D2, §3 D3 two-step instruction).
        if result.unknown_cause is UnknownCause.AUTHORING:
            return RepairCategory.FIX_REQUIRED
        if result.unknown_policy is UnknownPolicy.FAIL:
            return RepairCategory.FIX_REQUIRED
        if result.unknown_policy is UnknownPolicy.REPAIR:
            return RepairCategory.SUGGESTED
        if result.unknown_policy is UnknownPolicy.WARN:
            return RepairCategory.UNRESOLVED
        if result.unknown_policy is UnknownPolicy.IGNORE:
            return None

    if result.status is ResultStatus.SKIPPED:
        if result.error_code == _SHORT_CIRCUIT_SKIP_ERROR_CODE:
            return None
        return RepairCategory.UNRESOLVED

    raise AssertionError(f"Unhandled result status: {result.status}")


@dataclass(frozen=True)
class _SurfacedEvidence:
    observed: JsonValue
    expected: JsonValue
    added: tuple[JsonValue, ...]
    removed: tuple[JsonValue, ...]
    missing: tuple[JsonValue, ...]
    extra: tuple[JsonValue, ...]
    extra_evidence: tuple[tuple[str, JsonValue], ...]


def _surface_evidence(evidence: tuple[tuple[str, JsonValue], ...]) -> _SurfacedEvidence:
    # CSCI-13 emits unique keys; dict conversion is deterministic for that contract.
    by_key = dict(evidence)
    extra_evidence = tuple(
        sorted(
            ((key, value) for key, value in evidence if key not in _NAMED_EVIDENCE_KEYS),
            key=lambda item: item[0],
        )
    )
    tuple_values = {key: _as_tuple(by_key.get(key)) for key in _TUPLE_EVIDENCE_KEYS}
    return _SurfacedEvidence(
        observed=by_key.get("observed"),
        expected=by_key.get("expected"),
        added=tuple_values["added"],
        removed=tuple_values["removed"],
        missing=tuple_values["missing"],
        extra=tuple_values["extra"],
        extra_evidence=extra_evidence,
    )


def _as_tuple(value: JsonValue) -> tuple[JsonValue, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _message(result: ConstraintResult, repair_code: str) -> str:
    if repair_code in _TEMPLATE_REPAIR_CODES:
        primary_kind = _primary_kind(result.constraint_id)
        expected_state = _EXPECTED_STATE_BY_REPAIR_CODE[repair_code]
        return (
            f"{primary_kind} change requires {result.target} to remain {expected_state}; "
            f"constraint {result.constraint_id} violated."
        )

    if repair_code == "R_USER_VIOLATION":
        return (
            f"User constraint {result.constraint_id} violated: "
            f"operator={result.operator.value}, target={result.target}."
        )

    if repair_code in {
        "R_PATH_UNRESOLVED",
        "R_TYPE_MISMATCH",
        "R_OPERATOR_TARGET_MISMATCH",
    }:
        cause_suffix = f", cause={result.unknown_cause.value}" if result.unknown_cause else ""
        return (
            f"{result.constraint_id}: cannot evaluate ({result.error_code}); "
            f"target={result.target}, operator={result.operator.value}{cause_suffix}."
        )

    if repair_code in {"R_UNSUPPORTED_OPERATOR", "R_UNSUPPORTED_REPAIR_KIND"}:
        return (
            f"{result.constraint_id}: skipped in P1 ({result.error_code}); "
            f"operator={result.operator.value}, kind={result.kind.value}."
        )

    if result.error_code == "E_DIMENSION_SKIPPED":
        return (
            f"{result.constraint_id}: skipped because execution mode did not "
            f"extract this target dimension; target={result.target}."
        )

    return f"{result.constraint_id}: unrecognized error_code={result.error_code}."


def _primary_kind(constraint_id: str) -> str:
    match = _TEMPLATE_ID_PATTERN.match(constraint_id)
    if match is None:
        return "template"
    return match.group("primary_kind")


def _hashable_json(value: JsonValue) -> object:
    if isinstance(value, dict):
        return tuple((key, _hashable_json(item)) for key, item in sorted(value.items()))
    if isinstance(value, list | tuple):
        return tuple(_hashable_json(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_hashable_json(item) for item in value)
    return value
