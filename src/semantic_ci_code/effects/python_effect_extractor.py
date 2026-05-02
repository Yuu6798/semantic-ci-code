from __future__ import annotations

import ast
from functools import lru_cache
from importlib import resources

from semantic_ci_code.domain.state_schema import EffectEntry
from semantic_ci_code.effects.effect_db import (
    EffectSignature,
    ResolutionLevel,
    load_effect_db,
)

# TODO(P1+): ``global_mutation`` is intentionally not represented as an
# effect_db entry. It requires statement-level detection (``global`` /
# ``nonlocal`` declarations and module-level rebindings) rather than a
# call signature, and will be implemented as a dedicated extractor pass.

DEFAULT_DB_PACKAGE = "semantic_ci_code.effects"
DEFAULT_DB_RESOURCE_NAME = "effect_db_python.yaml"
PYTHON_LANGUAGE = "python"


@lru_cache(maxsize=1)
def default_python_effect_db() -> tuple[EffectSignature, ...]:
    """Return the project-default Python effect signature database.

    The YAML is shipped as package data so resolution works identically
    in editable installs, plain wheels, and zipped distributions.
    """
    resource = resources.files(DEFAULT_DB_PACKAGE).joinpath(DEFAULT_DB_RESOURCE_NAME)
    with resources.as_file(resource) as path:
        return load_effect_db(path)


def _resolve_dotted_name(node: ast.AST) -> str | None:
    """Recover a dotted name from ``ast.Name`` / ``ast.Attribute`` chains.

    Returns ``None`` when the chain bottoms out on a non-name node (e.g.
    a call result or subscript), which signals an unresolved direct call
    in the P1 sense.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _resolve_dotted_name(node.value)
        if prefix is None:
            return None
        return f"{prefix}.{node.attr}"
    return None


def _build_call_index(
    signatures: tuple[EffectSignature, ...],
) -> dict[str, EffectSignature]:
    """Build a call-name → signature lookup, restricted to Python entries.

    A shared multi-language DB may declare a non-Python signature for
    a call name that also exists in Python (e.g. ``print``). Filtering
    by ``language`` here keeps the Python extractor from picking up
    foreign entries just because they were declared first.
    """
    index: dict[str, EffectSignature] = {}
    for signature in signatures:
        if signature.language != PYTHON_LANGUAGE:
            continue
        index.setdefault(signature.match.call, signature)
    return index


def _assign_target_names(node: ast.AST) -> set[str]:
    """Collect names that an assignment target binds, conservatively.

    Only plain ``Name`` targets and tuple/list/starred destructurings of
    ``Name`` targets contribute. Attribute and subscript writes (``a.x``,
    ``a[0]``) do not rebind the local name and are ignored.
    """
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Tuple | ast.List):
        names: set[str] = set()
        for elt in node.elts:
            names |= _assign_target_names(elt)
        return names
    if isinstance(node, ast.Starred):
        return _assign_target_names(node.value)
    return set()


def _collect_module_scope_shadows(stmts: list[ast.stmt]) -> set[str]:
    """Collect names rebound by statements executed in module scope.

    Recurses into compound statements (``if`` / ``try`` / ``for`` /
    ``while`` / ``with`` / ``match``) because their bodies still bind
    in module scope. Stops at function and class definitions, which
    introduce their own scopes — full per-scope analysis is out of P1.
    """
    shadowed: set[str] = set()
    for stmt in stmts:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                shadowed |= _assign_target_names(target)
        elif isinstance(stmt, ast.AnnAssign):
            if stmt.value is not None:
                shadowed |= _assign_target_names(stmt.target)
        elif isinstance(stmt, ast.AugAssign):
            shadowed |= _assign_target_names(stmt.target)
        elif isinstance(stmt, ast.If):
            shadowed |= _collect_module_scope_shadows(stmt.body)
            shadowed |= _collect_module_scope_shadows(stmt.orelse)
        elif isinstance(stmt, ast.Try):
            shadowed |= _collect_module_scope_shadows(stmt.body)
            for handler in stmt.handlers:
                if handler.name is not None:
                    shadowed.add(handler.name)
                shadowed |= _collect_module_scope_shadows(handler.body)
            shadowed |= _collect_module_scope_shadows(stmt.orelse)
            shadowed |= _collect_module_scope_shadows(stmt.finalbody)
        elif isinstance(stmt, ast.For | ast.AsyncFor):
            shadowed |= _assign_target_names(stmt.target)
            shadowed |= _collect_module_scope_shadows(stmt.body)
            shadowed |= _collect_module_scope_shadows(stmt.orelse)
        elif isinstance(stmt, ast.While):
            shadowed |= _collect_module_scope_shadows(stmt.body)
            shadowed |= _collect_module_scope_shadows(stmt.orelse)
        elif isinstance(stmt, ast.With | ast.AsyncWith):
            for item in stmt.items:
                if item.optional_vars is not None:
                    shadowed |= _assign_target_names(item.optional_vars)
            shadowed |= _collect_module_scope_shadows(stmt.body)
        elif isinstance(stmt, ast.Match):
            # Pattern bindings (``case [x]:``) are not analyzed here;
            # only case bodies are recursed into. This is a conservative
            # P1 simplification — patterns rarely shadow effect aliases.
            for case in stmt.cases:
                shadowed |= _collect_module_scope_shadows(case.body)
    return shadowed


def _collect_alias_map(tree: ast.Module) -> dict[str, str]:
    """Build a module-level alias map: ``bound_name → canonical_dotted``.

    Only top-level ``import`` and ``from ... import ...`` statements are
    considered. Star imports and relative imports are skipped (P1 limit).

    A bound name that is rebound anywhere in module scope — including
    inside top-level ``if`` / ``try`` / ``for`` / ``while`` / ``with``
    bodies — is treated as shadowed and dropped from the map for the
    entire module. Function and class bodies are not traversed because
    they introduce their own scopes; full per-scope analysis is out of
    P1. The rule is intentionally order-insensitive per the brief.
    """
    alias_map: dict[str, str] = {}

    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if alias.asname is not None:
                    # ``import os as op`` → op resolves to "os".
                    alias_map[alias.asname] = alias.name
                else:
                    # ``import urllib.request`` binds the top-level
                    # ``urllib`` name; the canonical head is itself, so
                    # downstream calls resolve as direct_call.
                    bound = alias.name.split(".", 1)[0]
                    alias_map.setdefault(bound, bound)
        elif isinstance(stmt, ast.ImportFrom):
            if stmt.module is None or stmt.level > 0:
                # Relative imports (``from . import x``) are out of scope
                # for P1 alias resolution.
                continue
            module = stmt.module
            for alias in stmt.names:
                if alias.name == "*":
                    # Star imports cannot be resolved without runtime
                    # introspection of the source module.
                    continue
                bound = alias.asname if alias.asname is not None else alias.name
                alias_map[bound] = f"{module}.{alias.name}"

    shadowed = _collect_module_scope_shadows(tree.body)
    for name in shadowed:
        alias_map.pop(name, None)

    return alias_map


def _resolve_call(raw: str, alias_map: dict[str, str]) -> tuple[str, ResolutionLevel]:
    """Resolve a raw dotted call name through the alias map.

    Returns ``(resolved_name, level)``. When the head segment is not in
    the alias map, or maps to itself, the raw name is returned as-is
    with ``direct_call``. Otherwise the head is rewritten to its
    canonical dotted form and ``imported_alias`` is reported.
    """
    head, _, tail = raw.partition(".")
    canonical_head = alias_map.get(head)
    if canonical_head is None or canonical_head == head:
        return raw, ResolutionLevel.DIRECT_CALL
    resolved = f"{canonical_head}.{tail}" if tail else canonical_head
    return resolved, ResolutionLevel.IMPORTED_ALIAS


def extract_python_effects(
    source: str,
    *,
    filename: str = "<string>",
    db: tuple[EffectSignature, ...] | None = None,
) -> tuple[EffectEntry, ...]:
    """Extract direct-call and import-alias effects from Python ``source``.

    Resolution covers two P1 levels (see design §7.3):

    * ``direct_call``: ``ast.Name`` and ``ast.Attribute`` chains rooted
      in a name that already matches a DB entry as written.
    * ``imported_alias``: top-level ``import``/``from`` rebinds whose
      bound name resolves to a canonical DB call after substitution.

    Method calls on instances, dynamic imports, and star imports are
    left for later phases.

    A :class:`SyntaxError` from :func:`ast.parse` propagates unchanged
    so callers can distinguish parse failures from extraction misses.
    """
    tree = ast.parse(source, filename=filename)
    signatures = db if db is not None else default_python_effect_db()
    index = _build_call_index(signatures)
    alias_map = _collect_alias_map(tree)

    entries: list[EffectEntry] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        raw = _resolve_dotted_name(node.func)
        if raw is None:
            continue
        resolved, level = _resolve_call(raw, alias_map)
        signature = index.get(resolved)
        if signature is None:
            continue
        entries.append(
            EffectEntry(
                fqn=resolved,
                effect_class=signature.effect_class,
                confidence=1.0,
                evidence={
                    "raw_call": raw,
                    "resolved_call": resolved,
                    "file": filename,
                    "line": node.lineno,
                    "resolution_level": level.value,
                },
            )
        )
    return tuple(entries)
