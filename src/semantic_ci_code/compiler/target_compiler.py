"""Compile Target SVP YAML into evaluator-ready dataclasses.

CSCI-12 is a normalization layer only. It parses Target SVP YAML, reuses the
existing Pydantic ``TargetSVP`` validation path, expands fixed change-kind
templates, and returns frozen dataclasses that CSCI-13 can evaluate. Operator
semantics, target path resolution, unknown-policy behavior, verdict production,
repair generation, file loading, and git integration are out of scope.

Constraint order is deterministic and fixed as:
``template constraints`` in table order, followed by ``user constraints`` in
YAML declaration order. P1 does not support template override or merge; duplicate
constraint ids across the combined sequence are compile errors.

Target strings are validated against the static CodeState / CodeStateDelta
schema (see ``compiler.path_schema``) so authoring errors fail at compile
time rather than mixing with extractor failures via ``unknown_policy``.
Open ``JsonMapping`` dimensions (``python_specific`` / ``typescript_specific``)
accept any subpath. Operator semantics, runtime resolution, and unknown-policy
behavior remain the evaluator's responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import yaml
from pydantic import ValidationError

from semantic_ci_code.compiler.path_schema import (
    is_open_path,
    suggest_targets,
    valid_target_paths,
)
from semantic_ci_code.domain.state_schema import ChangeKind, EffectClass
from semantic_ci_code.framework.constraint_types import (
    Constraint,
    ConstraintKind,
    JsonValue,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.framework.target_svp import TargetSVP, parse_target_svp_yaml

__all__ = [
    "CompileError",
    "CompiledAPISurfaceAllowRule",
    "CompiledAuthor",
    "CompiledAuthorship",
    "CompiledConstraint",
    "CompiledEffectAllowRule",
    "CompiledTarget",
    "ConstraintSource",
    "compile_target_svp",
]


class ConstraintSource(StrEnum):
    TEMPLATE = "template"
    USER = "user"


@dataclass(frozen=True)
class CompiledAPISurfaceAllowRule:
    fqn: str | None = None
    fqn_prefix: str | None = None


@dataclass(frozen=True)
class CompiledConstraint:
    id: str
    kind: ConstraintKind
    target: str
    operator: Operator
    expected: JsonValue
    severity: Severity
    unknown_policy: UnknownPolicy
    tolerance: float | None
    evidence_required: bool
    scope: JsonValue
    source: ConstraintSource

    def __hash__(self) -> int:
        return hash(
            (
                self.id,
                self.kind,
                self.target,
                self.operator,
                _hashable_json(self.expected),
                self.severity,
                self.unknown_policy,
                self.tolerance,
                self.evidence_required,
                _hashable_json(self.scope),
                self.source,
            )
        )


@dataclass(frozen=True)
class CompiledEffectAllowRule:
    fqn: str | None = None
    effect_class: EffectClass | None = None


@dataclass(frozen=True)
class CompiledAuthor:
    identity: str
    signature: str | None = None


@dataclass(frozen=True)
class CompiledAuthorship:
    authors: tuple[CompiledAuthor, ...]
    declared_at: str | None = None
    generation_metadata: JsonValue = None

    def __hash__(self) -> int:
        return hash(
            (
                self.authors,
                self.declared_at,
                _hashable_json(self.generation_metadata),
            )
        )


@dataclass(frozen=True)
class CompiledTarget:
    intent: str
    primary_kind: ChangeKind
    allowed_secondary_kinds: tuple[ChangeKind, ...]
    scope: tuple[tuple[str, tuple[str, ...]], ...]
    constraints: tuple[CompiledConstraint, ...]
    api_surface_allow_changes: tuple[CompiledAPISurfaceAllowRule, ...] = ()
    effect_allow_new: tuple[CompiledEffectAllowRule, ...] = ()
    authorship: CompiledAuthorship | None = None


@dataclass(init=False)
class CompileError(Exception):
    message: str
    filename: str
    path: str | None
    line: int | None
    column: int | None

    def __init__(
        self,
        message: str,
        filename: str = "<string>",
        path: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        self.message = message
        self.filename = filename
        self.path = path
        self.line = line
        self.column = column
        super().__init__(message, filename, path, line, column)

    def __str__(self) -> str:
        location = self.filename
        if self.line is not None:
            location = f"{location}:{self.line}"
            if self.column is not None:
                location = f"{location}:{self.column}"

        suffix = f" at {self.path}" if self.path else ""
        return f"{location}: {self.message}{suffix}"

    @classmethod
    def from_validation_error(
        cls,
        exc: ValidationError,
        *,
        filename: str = "<string>",
    ) -> CompileError:
        first = exc.errors()[0]
        message = str(first.get("msg", "Target SVP validation failed."))
        path = _format_validation_path(tuple(first.get("loc", ()))) or None
        return cls(message=message, filename=filename, path=path)


def compile_target_svp(
    yaml_source: str,
    *,
    filename: str = "<string>",
) -> CompiledTarget:
    """Parse and compile a Target SVP YAML into a frozen CompiledTarget.

    The input is a YAML string only; CLI/file-path loading belongs to Brief 4.
    All expected parse, validation, normalization, and duplicate-id errors are
    wrapped as ``CompileError``. Operator truth evaluation and target path
    resolution are CSCI-13 responsibilities.
    """

    if not isinstance(yaml_source, str):
        raise CompileError(
            message="compile_target_svp expects YAML source as a string.",
            filename=filename,
        )

    target_svp = _parse_target_svp(yaml_source, filename=filename)
    _validate_target_svp_values(target_svp, filename=filename)

    compiled_user = tuple(_compile_user_constraint(item) for item in target_svp.constraints)
    templates = _template_constraints_for(target_svp.change.primary_kind)
    constraints = templates + compiled_user
    _validate_unique_ids(constraints, filename=filename)

    return CompiledTarget(
        intent=target_svp.intent,
        primary_kind=target_svp.change.primary_kind,
        allowed_secondary_kinds=target_svp.change.allowed_secondary_kinds,
        scope=_freeze_change_scope(target_svp.change.scope),
        constraints=constraints,
        api_surface_allow_changes=_compile_api_surface_allow_changes(target_svp),
        effect_allow_new=_compile_effect_allow_new(target_svp),
        authorship=_compile_authorship(target_svp),
    )


def _parse_target_svp(yaml_source: str, *, filename: str) -> TargetSVP:
    try:
        return parse_target_svp_yaml(yaml_source)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        raise CompileError(
            message=str(exc),
            filename=filename,
            line=mark.line + 1 if mark else None,
            column=mark.column + 1 if mark else None,
        ) from exc
    except ValidationError as exc:
        raise CompileError.from_validation_error(exc, filename=filename) from exc
    except ValueError as exc:
        raise CompileError(message=str(exc), filename=filename) from exc


def _validate_target_svp_values(target_svp: TargetSVP, *, filename: str) -> None:
    valid_paths = valid_target_paths()
    for index, constraint in enumerate(target_svp.constraints):
        if constraint.target == "":
            raise CompileError(
                message="constraint target must not be empty.",
                filename=filename,
                path=f"constraints[{index}].target",
            )
        if constraint.target in valid_paths or is_open_path(constraint.target):
            continue
        suggestions = suggest_targets(constraint.target)
        message = (
            f"constraint target {constraint.target!r} does not exist on CodeState/CodeStateDelta."
        )
        if suggestions:
            message += f" Did you mean: {', '.join(suggestions)}?"
        raise CompileError(
            message=message,
            filename=filename,
            path=f"constraints[{index}].target",
        )

    if target_svp.api_surface is not None:
        for index, rule in enumerate(target_svp.api_surface.allow_changes):
            if rule.fqn is None and rule.fqn_prefix is None:
                raise CompileError(
                    message="api_surface.allow_changes entries require fqn or fqn_prefix.",
                    filename=filename,
                    path=f"api_surface.allow_changes[{index}]",
                )
            if rule.fqn == "" or rule.fqn_prefix == "":
                raise CompileError(
                    message="api_surface.allow_changes values must not be empty.",
                    filename=filename,
                    path=f"api_surface.allow_changes[{index}]",
                )

    if target_svp.effects is None:
        return
    for index, rule in enumerate(target_svp.effects.allow_new):
        if rule.fqn is None and rule.effect_class is None:
            raise CompileError(
                message="effects.allow_new entries require fqn or effect_class.",
                filename=filename,
                path=f"effects.allow_new[{index}]",
            )


def _compile_user_constraint(constraint: Constraint) -> CompiledConstraint:
    return CompiledConstraint(
        id=constraint.id,
        kind=ConstraintKind(constraint.kind),
        target=constraint.target,
        operator=constraint.operator,
        expected=_freeze_expected(constraint.expected),
        severity=constraint.severity,
        unknown_policy=constraint.unknown_policy,
        tolerance=constraint.tolerance,
        evidence_required=constraint.evidence_required,
        scope=constraint.scope,
        source=ConstraintSource.USER,
    )


def _compile_api_surface_allow_changes(
    target_svp: TargetSVP,
) -> tuple[CompiledAPISurfaceAllowRule, ...]:
    if target_svp.api_surface is None:
        return ()
    return tuple(
        CompiledAPISurfaceAllowRule(fqn=rule.fqn, fqn_prefix=rule.fqn_prefix)
        for rule in target_svp.api_surface.allow_changes
    )


def _compile_effect_allow_new(target_svp: TargetSVP) -> tuple[CompiledEffectAllowRule, ...]:
    if target_svp.effects is None:
        return ()
    return tuple(
        CompiledEffectAllowRule(fqn=rule.fqn, effect_class=rule.effect_class)
        for rule in target_svp.effects.allow_new
    )


def _compile_authorship(target_svp: TargetSVP) -> CompiledAuthorship | None:
    if target_svp.authorship is None:
        return None
    return CompiledAuthorship(
        authors=tuple(
            CompiledAuthor(identity=author.identity, signature=author.signature)
            for author in target_svp.authorship.authors
        ),
        declared_at=target_svp.authorship.declared_at,
        generation_metadata=target_svp.authorship.generation_metadata,
    )


def _template_constraints_for(primary_kind: ChangeKind) -> tuple[CompiledConstraint, ...]:
    from semantic_ci_code.compiler.templates import TEMPLATE_CONSTRAINTS

    return TEMPLATE_CONSTRAINTS[primary_kind]


def _validate_unique_ids(
    constraints: tuple[CompiledConstraint, ...],
    *,
    filename: str,
) -> None:
    seen: dict[str, str] = {}
    source_counts: dict[ConstraintSource, int] = {}
    for constraint in constraints:
        source_index = source_counts.get(constraint.source, 0)
        location = f"{constraint.source.value}[{source_index}]"
        previous = seen.get(constraint.id)
        if previous is not None:
            raise CompileError(
                message=(
                    f"duplicate constraint id {constraint.id!r}; first occurrence at "
                    f"{previous}, second occurrence at {location}"
                ),
                filename=filename,
                path="constraints",
            )
        seen[constraint.id] = location
        source_counts[constraint.source] = source_index + 1


def _freeze_change_scope(
    scope: dict[str, tuple[str, ...]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple((key, tuple(value)) for key, value in sorted(scope.items()))


def _freeze_expected(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_freeze_expected(item) for item in value)
    return value


def _hashable_json(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple((key, _hashable_json(item)) for key, item in sorted(value.items()))
    if isinstance(value, list | tuple):
        return tuple(_hashable_json(item) for item in value)
    return value


def _format_validation_path(loc: tuple[object, ...]) -> str:
    normalized: list[object] = []
    for index, item in enumerate(loc):
        if (
            item
            in {ConstraintKind.STATE.value, ConstraintKind.DELTA.value, ConstraintKind.REPAIR.value}
            and index > 0
            and isinstance(loc[index - 1], int)
        ):
            continue
        normalized.append(item)

    path = ""
    for item in normalized:
        if isinstance(item, int):
            path += f"[{item}]"
            continue
        if path:
            path += "."
        path += str(item)
    return path
