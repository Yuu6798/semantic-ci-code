"""Static enumeration of valid constraint target paths.

The runtime path resolver in ``evaluator/path_resolver.py`` returns
``UNRESOLVED`` when a target path does not match the CodeState /
CodeStateDelta schema. That late failure conflates two distinct
concerns: extractor failures (which ``unknown_policy`` should govern)
and authoring errors (which should be rejected at compile time so a
typo never reaches the evaluator).

This module reflects on the Pydantic schema once at import time and
exposes the set of dotted paths that the evaluator can resolve, so the
compiler can reject authoring errors with a structured ``CompileError``.
"""

from __future__ import annotations

import inspect
import re
from difflib import get_close_matches
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from semantic_ci_code.domain.state_schema import CodeState, CodeStateDelta

# Mirrors ``evaluator._TARGET_PATTERN``. Open-dimension paths still have
# to satisfy this dotted-identifier syntax at runtime; we enforce it at
# compile time too so authoring errors do not slip through the open-prefix
# exception and resurface as ``E_PATH_UNRESOLVED``.
_TARGET_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")

# Top-level aliases recognized by the evaluator that do not appear in
# the Pydantic schema. Keep this list in sync with the special cases in
# ``path_resolver.resolve_path``.
_CODE_STATE_ALIASES: frozenset[str] = frozenset({"api_surface_public"})

# Subfield aliases recognized when the parent has a ``removed`` field
# (SymbolDelta and lookalikes). Mirrors ``resolve_path`` line 31-33.
_REMOVED_PUBLIC_ALIAS: str = "removed_public"

# Dimensions whose values are open ``JsonMapping``s; any subpath under
# these prefixes is a syntactically valid authoring target.
_OPEN_PREFIXES: frozenset[str] = frozenset({"python_specific", "typescript_specific"})


def valid_target_paths() -> frozenset[str]:
    """Return every dotted path the evaluator can resolve as a target."""

    paths: set[str] = set()
    for field_name, field_info in CodeState.model_fields.items():
        _walk(field_name, field_info.annotation, paths)
    for field_name, field_info in CodeStateDelta.model_fields.items():
        _walk(field_name, field_info.annotation, paths)
    paths.update(_CODE_STATE_ALIASES)
    return frozenset(paths)


def is_open_path(target: str) -> bool:
    """Return True when a target lives under an open dict dimension.

    The whole target must satisfy the evaluator's dotted-identifier
    syntax: a malformed open-prefix path such as ``python_specific..foo``
    or ``python_specific.bad-key`` would otherwise pass the compile-time
    schema check and resurface as ``E_PATH_UNRESOLVED`` at evaluate time.
    """

    if _TARGET_PATTERN.fullmatch(target) is None:
        return False
    head, _, _ = target.partition(".")
    return head in _OPEN_PREFIXES


def suggest_targets(target: str, *, max_suggestions: int = 3) -> tuple[str, ...]:
    """Return up to ``max_suggestions`` close matches for ``target``."""

    return tuple(get_close_matches(target, valid_target_paths(), n=max_suggestions, cutoff=0.6))


def _walk(prefix: str, annotation: Any, paths: set[str]) -> None:
    paths.add(prefix)
    if prefix in _OPEN_PREFIXES:
        return
    model = _model_class(annotation)
    if model is None:
        return
    for sub_name, sub_info in model.model_fields.items():
        sub_path = f"{prefix}.{sub_name}"
        _walk(sub_path, sub_info.annotation, paths)
    if "removed" in model.model_fields:
        paths.add(f"{prefix}.{_REMOVED_PUBLIC_ALIAS}")


def _model_class(annotation: Any) -> type[BaseModel] | None:
    """Unwrap ``Optional`` / ``Union`` and return a BaseModel class if any."""

    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        for arg in get_args(annotation):
            model = _model_class(arg)
            if model is not None:
                return model
    return None
