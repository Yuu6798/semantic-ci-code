from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from semantic_ci_code.domain.state_schema import EffectClass, EffectEntry
from semantic_ci_code.effects.effect_db import (
    EffectSignature,
    ResolutionLevel,
    load_effect_db,
)

# ``global_mutation`` is detected via a dedicated AST pass rather than
# the effect signature DB: it is statement-level (``global`` /
# ``nonlocal`` declarations, module-level rebindings, attribute /
# subscript writes) rather than a call signature.

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
        elif isinstance(stmt, ast.Try | ast.TryStar):
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
    module_fqn: str | None = None,
    db: tuple[EffectSignature, ...] | None = None,
) -> tuple[EffectEntry, ...]:
    """Extract direct-call, import-alias, and global-mutation effects.

    Call resolution covers two P1 levels (see design §7.3):

    * ``direct_call``: ``ast.Name`` and ``ast.Attribute`` chains rooted
      in a name that already matches a DB entry as written.
    * ``imported_alias``: top-level ``import``/``from`` rebinds whose
      bound name resolves to a canonical DB call after substitution.

    A separate statement-level pass detects ``global_mutation`` effects:
    function-body ``global`` / ``nonlocal`` declarations, module-scope
    name rebindings beyond the first, and module-scope attribute /
    subscript writes against a named base.

    Method calls on instances, dynamic imports, star imports, and
    instance-method mutations (``items.append(...)`` etc.) are out of
    scope for P1.

    A :class:`SyntaxError` from :func:`ast.parse` propagates unchanged
    so callers can distinguish parse failures from extraction misses.
    """
    tree = ast.parse(source, filename=filename)
    signatures = db if db is not None else default_python_effect_db()
    index = _build_call_index(signatures)
    alias_map = _collect_alias_map(tree)

    entries: list[EffectEntry] = []
    entries.extend(_extract_call_effects(tree, index, alias_map, filename, module_fqn))
    entries.extend(_extract_global_mutations(tree, filename))
    return tuple(entries)


def _extract_call_effects(
    tree: ast.Module,
    index: dict[str, EffectSignature],
    alias_map: dict[str, str],
    filename: str,
    module_fqn: str | None,
) -> list[EffectEntry]:
    """Detect direct_call / imported_alias effects from call sites."""
    visitor = _CallEffectVisitor(
        index=index,
        alias_map=alias_map,
        filename=filename,
        module_fqn=module_fqn,
    )
    visitor.visit(tree)
    return visitor.entries


class _CallEffectVisitor(ast.NodeVisitor):
    """Collect call effects while tracking enclosing Python scopes."""

    def __init__(
        self,
        *,
        index: dict[str, EffectSignature],
        alias_map: dict[str, str],
        filename: str,
        module_fqn: str | None,
    ) -> None:
        self._index = index
        self._alias_map = alias_map
        self._filename = filename
        self._module_fqn = module_fqn
        self._scope_stack: list[str] = []
        self.entries: list[EffectEntry] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_named_scope(node.name, node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_named_scope(node.name, node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_named_scope(node.name, node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._scope_stack.append("<lambda>")
        try:
            self.generic_visit(node)
        finally:
            self._scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        raw = _resolve_dotted_name(node.func)
        if raw is not None:
            resolved, level = _resolve_call(raw, self._alias_map)
            signature = self._index.get(resolved)
            if signature is not None:
                self.entries.append(
                    EffectEntry(
                        fqn=self._enclosing_fqn(),
                        effect_class=signature.effect_class,
                        confidence=1.0,
                        evidence={
                            "raw_call": raw,
                            "resolved_call": resolved,
                            "file": self._filename,
                            "line": node.lineno,
                            "resolution_level": level.value,
                        },
                    )
                )
        self.generic_visit(node)

    def _visit_named_scope(self, name: str, node: ast.AST) -> None:
        self._scope_stack.append(name)
        try:
            self.generic_visit(node)
        finally:
            self._scope_stack.pop()

    def _enclosing_fqn(self) -> str:
        if not self._scope_stack:
            return self._module_fqn or "<module>"
        if self._scope_stack[-1] == "<lambda>":
            local_fqn = "<lambda>"
        else:
            local_fqn = ".".join(self._scope_stack)
        return f"{self._module_fqn}.{local_fqn}" if self._module_fqn else local_fqn


# --------------------------------------------------------------------- #
# global_mutation extraction
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class _NameBindingEvent:
    name: str
    line: int


_ModuleBindingEvent = ast.stmt | _NameBindingEvent


def _iter_module_scope_binding_events(
    stmts: list[ast.stmt],
) -> list[_ModuleBindingEvent]:
    """Return module-scope binding-event statements in source order.

    Yields ``Import`` / ``ImportFrom`` / ``Assign`` / ``AnnAssign`` /
    ``AugAssign`` / ``Delete`` statements, plus ``except ... as name``
    bindings, that execute in module scope. Recurses into ``if`` /
    ``try`` / ``for`` / ``while`` / ``with`` / ``match`` bodies.
    ``FunctionDef`` / ``AsyncFunctionDef`` / ``ClassDef`` introduce
    new scopes and are not traversed.
    """
    events: list[_ModuleBindingEvent] = []
    for stmt in stmts:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if isinstance(
            stmt,
            ast.Import | ast.ImportFrom | ast.Assign | ast.AnnAssign | ast.AugAssign | ast.Delete,
        ):
            events.append(stmt)
            continue
        if isinstance(stmt, ast.If):
            events.extend(_iter_module_scope_binding_events(stmt.body))
            events.extend(_iter_module_scope_binding_events(stmt.orelse))
        elif isinstance(stmt, ast.Try | ast.TryStar):
            events.extend(_iter_module_scope_binding_events(stmt.body))
            for handler in stmt.handlers:
                if handler.name is not None:
                    events.append(_NameBindingEvent(name=handler.name, line=handler.lineno))
                events.extend(_iter_module_scope_binding_events(handler.body))
            events.extend(_iter_module_scope_binding_events(stmt.orelse))
            events.extend(_iter_module_scope_binding_events(stmt.finalbody))
        elif isinstance(stmt, ast.For | ast.AsyncFor):
            events.extend(_iter_module_scope_binding_events(stmt.body))
            events.extend(_iter_module_scope_binding_events(stmt.orelse))
        elif isinstance(stmt, ast.While):
            events.extend(_iter_module_scope_binding_events(stmt.body))
            events.extend(_iter_module_scope_binding_events(stmt.orelse))
        elif isinstance(stmt, ast.With | ast.AsyncWith):
            events.extend(_iter_module_scope_binding_events(stmt.body))
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                events.extend(_iter_module_scope_binding_events(case.body))
    return events


def _import_bound_names(stmt: ast.Import | ast.ImportFrom) -> list[str]:
    """Return the local names bound by an import statement.

    Star imports are skipped because they do not contribute deterministic
    local binding names. Relative ``ImportFrom`` statements still bind
    their imported local names, so they are included here even though
    alias resolution intentionally ignores them.
    """
    bound: list[str] = []
    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            if alias.asname is not None:
                bound.append(alias.asname)
            else:
                bound.append(alias.name.split(".", 1)[0])
        return bound
    for alias in stmt.names:
        if alias.name == "*":
            continue
        bound.append(alias.asname if alias.asname is not None else alias.name)
    return bound


def _classify_assignment_target(target: ast.AST) -> list[tuple[str, str]]:
    """Classify an assignment target into ``(kind, base_name)`` tuples.

    ``kind`` is one of ``"name"``, ``"subscript"``, ``"attribute"``.
    Tuple / list / starred destructurings are flattened. Targets whose
    Subscript / Attribute chain bottoms out on a non-Name (e.g. a call
    result) are skipped — there is no stable base name to report.
    """
    if isinstance(target, ast.Name):
        return [("name", target.id)]
    if isinstance(target, ast.Subscript):
        root = _attr_subscript_root_name(target.value)
        return [("subscript", root)] if root is not None else []
    if isinstance(target, ast.Attribute):
        root = _attr_subscript_root_name(target.value)
        return [("attribute", root)] if root is not None else []
    if isinstance(target, ast.Tuple | ast.List):
        results: list[tuple[str, str]] = []
        for elt in target.elts:
            results.extend(_classify_assignment_target(elt))
        return results
    if isinstance(target, ast.Starred):
        return _classify_assignment_target(target.value)
    return []


def _attr_subscript_root_name(node: ast.AST) -> str | None:
    """Walk Subscript / Attribute chains to the base ``Name`` id, if any."""
    while isinstance(node, ast.Subscript | ast.Attribute):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    return None


def _statement_target_classifications(
    stmt: ast.stmt,
) -> list[tuple[str, str]]:
    """Return ``(kind, base_name)`` tuples for an assignment statement.

    ``AnnAssign`` without a value is intentionally returned empty: it is
    a pure annotation and does not rebind the target.
    """
    if isinstance(stmt, ast.Assign):
        results: list[tuple[str, str]] = []
        for target in stmt.targets:
            results.extend(_classify_assignment_target(target))
        return results
    if isinstance(stmt, ast.AnnAssign):
        if stmt.value is None:
            return []
        return _classify_assignment_target(stmt.target)
    if isinstance(stmt, ast.AugAssign):
        return _classify_assignment_target(stmt.target)
    if isinstance(stmt, ast.Delete):
        results = []
        for target in stmt.targets:
            results.extend(_classify_assignment_target(target))
        return results
    return []


def _mutation_kind_for(stmt: ast.stmt, kind: str) -> str:
    """Map a (statement type, target kind) pair to a stable kind label."""
    if isinstance(stmt, ast.Delete):
        if kind == "name":
            return "module_delete"
        if kind == "subscript":
            return "module_subscript_delete"
        if kind == "attribute":
            return "module_attribute_delete"
    if kind == "name":
        return "module_reassignment"
    if kind == "subscript":
        return "module_subscript_assign"
    if kind == "attribute":
        return "module_attribute_assign"
    return "module_mutation"


def _build_mutation_entry(
    *,
    fqn: str,
    target: str,
    mutation_kind: str,
    filename: str,
    line: int,
) -> EffectEntry:
    return EffectEntry(
        fqn=fqn,
        effect_class=EffectClass.GLOBAL_MUTATION,
        confidence=1.0,
        evidence={
            "mutation_kind": mutation_kind,
            "target": target,
            "file": filename,
            "line": line,
            "resolution_level": ResolutionLevel.STATEMENT_LEVEL.value,
        },
    )


def _extract_global_mutations(tree: ast.Module, filename: str) -> list[EffectEntry]:
    """Detect statement-level global_mutation effects.

    Three sub-passes:

    1. Module-scope binding events in source order: imports register
       their bound names but never emit; ``Assign`` / ``AnnAssign`` with
       value / ``AugAssign`` / ``Delete`` against a Name target emit on
       the second and subsequent occurrence per name; against a
       Subscript or Attribute target rooted on a Name they emit
       unconditionally.
    2. ``ast.Global`` and ``ast.Nonlocal`` statements anywhere in the
       tree emit one entry per declared name.
    """
    entries: list[EffectEntry] = []

    seen_module_bindings: set[str] = set()
    for event in _iter_module_scope_binding_events(tree.body):
        if isinstance(event, _NameBindingEvent):
            if event.name in seen_module_bindings:
                entries.append(
                    _build_mutation_entry(
                        fqn=f"module:{event.name}",
                        target=event.name,
                        mutation_kind="module_reassignment",
                        filename=filename,
                        line=event.line,
                    )
                )
            else:
                seen_module_bindings.add(event.name)
            continue

        stmt = event
        if isinstance(stmt, ast.Import | ast.ImportFrom):
            seen_module_bindings.update(_import_bound_names(stmt))
            continue
        for kind, base_name in _statement_target_classifications(stmt):
            mutation_kind = _mutation_kind_for(stmt, kind)
            if kind == "name":
                if base_name in seen_module_bindings:
                    entries.append(
                        _build_mutation_entry(
                            fqn=f"module:{base_name}",
                            target=base_name,
                            mutation_kind=mutation_kind,
                            filename=filename,
                            line=stmt.lineno,
                        )
                    )
                else:
                    seen_module_bindings.add(base_name)
            else:
                # Subscript / Attribute writes are mutations on every
                # occurrence; there is no first-binding exemption.
                entries.append(
                    _build_mutation_entry(
                        fqn=f"module:{base_name}",
                        target=base_name,
                        mutation_kind=mutation_kind,
                        filename=filename,
                        line=stmt.lineno,
                    )
                )

    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            for name in node.names:
                entries.append(
                    _build_mutation_entry(
                        fqn=f"global:{name}",
                        target=name,
                        mutation_kind="global_declaration",
                        filename=filename,
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.Nonlocal):
            for name in node.names:
                entries.append(
                    _build_mutation_entry(
                        fqn=f"nonlocal:{name}",
                        target=name,
                        mutation_kind="nonlocal_declaration",
                        filename=filename,
                        line=node.lineno,
                    )
                )

    return entries
