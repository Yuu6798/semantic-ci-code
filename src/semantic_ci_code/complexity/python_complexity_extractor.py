"""Deterministic Python complexity extraction.

CSCI-8 intentionally uses stdlib ``ast`` instead of ``radon`` or
``lizard``. The P1 contract is a conservative approximation, owned by us:
zero dependencies, deterministic output, full control over the formula and
FQN model, and trivially auditable code. A later brief may add optional
cross-checking against third-party tools after a baseline corpus exists.

Emission parity contract: this extractor emits entries for the same
function/method subset as the P1 ``api_surface`` extractor: module-level
``FunctionDef`` / ``AsyncFunctionDef`` and direct ``FunctionDef`` /
``AsyncFunctionDef`` children of module-level ``ClassDef``. Definitions
inside module-scope compound statements are emitted. Nested functions,
nested classes, lambdas, module-level code, and class bodies themselves are
not emitted as ``ComplexityEntry`` records.

Cyclomatic formula:

Start at 1. Walk the function body. STOP descent when entering a nested
``FunctionDef`` / ``AsyncFunctionDef`` / ``ClassDef``; nested definitions
contribute 0 to the enclosing function's number.

Add to the count:

| Node | Contribution |
|---|---|
| ``ast.If`` | +1 (each ``elif`` is a nested ``If``, also +1 each) |
| ``ast.For``, ``ast.AsyncFor`` | +1 |
| ``ast.While`` | +1 |
| ``ast.ExceptHandler`` (inside ``Try`` or ``TryStar``) | +1 per handler |
| ``ast.IfExp`` (ternary ``a if c else b``) | +1 |
| ``ast.match_case`` | +1 per case |
| ``ast.BoolOp`` (``and`` / ``or``) | +(N-1) where N is the number of operands in ``values`` |
| ``ast.comprehension.ifs`` | +1 per ``if`` clause |
| ``ast.Assert`` | +1 |

DO NOT count: ``else`` / ``orelse`` blocks (handled by nested ``If`` for
``elif`` chains), ``with`` / ``AsyncWith``, ``return`` / ``break`` /
``continue`` / ``raise``, ``try``-``finally`` body, the ``match`` subject
itself, function/class definitions, walrus / named expressions.

The ``Assert`` rule is included for parity with ``radon``'s default
``--no-assert`` behavior being false. If a downstream consumer wants to
exclude asserts, that's a constraints-layer concern.

Cognitive formula:

Start at 0 with ``nesting = 0``. Walk the function body. STOP descent at
nested ``FunctionDef`` / ``AsyncFunctionDef`` / ``ClassDef``; nested
definitions contribute 0 to the enclosing function's number.

When entering one of ``ast.If`` (including elif), ``ast.For``,
``ast.AsyncFor``, ``ast.While``, ``ast.ExceptHandler``, ``ast.match_case``,
``ast.IfExp``, or a ``comprehension`` (the generator itself):

- cognitive += ``(1 + nesting)``
- Recurse into the body with ``nesting + 1``.

When encountering ``ast.BoolOp``: cognitive += 1 (regardless of operand
count; nesting bonus does NOT apply).

When a ``comprehension`` has multiple ``if`` clauses in ``ifs``: each
``if`` after the first contributes +1 (no nesting bonus).

DO NOT count: ``Assert``, ``with``, plain ``return`` / ``break`` /
``continue`` / ``raise``, function/class definitions.

This is a conservative approximation of SonarSource cognitive complexity,
NOT a faithful reimplementation. The numbers are stable and owned by us,
but should not be compared against SonarQube reports.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from semantic_ci_code.api_surface.python_api_extractor import _module_fqn_from_path
from semantic_ci_code.domain.state_schema import ComplexityEntry


def extract_python_complexity(
    source: str,
    *,
    module_fqn: str,
    filename: str = "<string>",
) -> tuple[ComplexityEntry, ...]:
    """Extract deterministic complexity entries from Python ``source``.

    ``SyntaxError`` from :func:`ast.parse` propagates unchanged so callers
    can distinguish parse failures from empty complexity surfaces.
    """
    tree = ast.parse(source, filename=filename)
    entries: list[ComplexityEntry] = []

    for stmt in _iter_module_scope_definitions(tree.body):
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            entries.append(_entry_for_function(stmt, _join_fqn(module_fqn, stmt.name)))
        elif isinstance(stmt, ast.ClassDef):
            entries.extend(_entries_for_class_methods(stmt, _join_fqn(module_fqn, stmt.name)))

    return _stable_entries(entries)


def extract_python_complexity_from_paths(
    paths: Iterable[Path],
    *,
    package_root: Path,
) -> tuple[ComplexityEntry, ...]:
    """Extract complexity entries from Python files under ``package_root``.

    Directory paths are expanded recursively to ``*.py`` files. File paths
    outside ``package_root`` raise :class:`ValueError` via
    :meth:`Path.relative_to`.
    """
    root = package_root.resolve()
    entries: list[ComplexityEntry] = []

    for path in _expand_python_paths(paths):
        resolved = path.resolve()
        module_fqn = _module_fqn_from_path(resolved, package_root=root)
        source = resolved.read_text(encoding="utf-8")
        entries.extend(
            extract_python_complexity(
                source,
                module_fqn=module_fqn,
                filename=str(resolved),
            )
        )

    return _stable_entries(entries)


def _iter_module_scope_definitions(stmts: list[ast.stmt]) -> Iterable[ast.stmt]:
    """Yield definitions that bind in module scope, walking compound bodies."""
    for stmt in stmts:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            yield stmt
            continue
        if isinstance(stmt, ast.If):
            yield from _iter_module_scope_definitions(stmt.body)
            yield from _iter_module_scope_definitions(stmt.orelse)
        elif isinstance(stmt, ast.Try | ast.TryStar):
            yield from _iter_module_scope_definitions(stmt.body)
            for handler in stmt.handlers:
                yield from _iter_module_scope_definitions(handler.body)
            yield from _iter_module_scope_definitions(stmt.orelse)
            yield from _iter_module_scope_definitions(stmt.finalbody)
        elif isinstance(stmt, ast.For | ast.AsyncFor):
            yield from _iter_module_scope_definitions(stmt.body)
            yield from _iter_module_scope_definitions(stmt.orelse)
        elif isinstance(stmt, ast.While):
            yield from _iter_module_scope_definitions(stmt.body)
            yield from _iter_module_scope_definitions(stmt.orelse)
        elif isinstance(stmt, ast.With | ast.AsyncWith):
            yield from _iter_module_scope_definitions(stmt.body)
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                yield from _iter_module_scope_definitions(case.body)


def _entries_for_class_methods(node: ast.ClassDef, class_fqn: str) -> list[ComplexityEntry]:
    entries: list[ComplexityEntry] = []
    for stmt in node.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            entries.append(_entry_for_function(stmt, _join_fqn(class_fqn, stmt.name)))
    return entries


def _entry_for_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    fqn: str,
) -> ComplexityEntry:
    return ComplexityEntry(
        fqn=fqn,
        cyclomatic=_cyclomatic_complexity(node),
        cognitive=_cognitive_complexity(node),
    )


def _cyclomatic_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    counter = _CyclomaticCounter()
    return counter.count_body(node.body)


def _cognitive_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    counter = _CognitiveCounter()
    return counter.count_body(node.body)


class _CyclomaticCounter(ast.NodeVisitor):
    def __init__(self) -> None:
        self.value = 1

    def count_body(self, body: list[ast.stmt]) -> int:
        for stmt in body:
            self.visit(stmt)
        return self.value

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        return None

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        self.value += 1
        self.visit(node.test)
        self._visit_statements(node.body)
        self._visit_statements(node.orelse)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        self.value += 1
        self.visit(node.target)
        self.visit(node.iter)
        self._visit_statements(node.body)
        self._visit_statements(node.orelse)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802
        self.visit_For(node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self.value += 1
        self.visit(node.test)
        self._visit_statements(node.body)
        self._visit_statements(node.orelse)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:  # noqa: N802
        self.value += 1
        if node.type is not None:
            self.visit(node.type)
        self._visit_statements(node.body)

    def visit_IfExp(self, node: ast.IfExp) -> None:  # noqa: N802
        self.value += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:  # noqa: N802
        for case in node.cases:
            self.visit(case)

    def visit_match_case(self, node: ast.match_case) -> None:
        self.value += 1
        if node.guard is not None:
            self.visit(node.guard)
        self._visit_statements(node.body)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802
        self.value += max(len(node.values) - 1, 0)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.value += len(node.ifs)
        self.visit(node.target)
        self.visit(node.iter)
        for condition in node.ifs:
            self.visit(condition)

    def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
        self.value += 1
        self.visit(node.test)
        if node.msg is not None:
            self.visit(node.msg)

    def _visit_statements(self, stmts: list[ast.stmt]) -> None:
        for stmt in stmts:
            self.visit(stmt)


class _CognitiveCounter:
    def __init__(self) -> None:
        self.value = 0

    def count_body(self, body: list[ast.stmt]) -> int:
        self._visit_statements(body, nesting=0)
        return self.value

    def _visit(self, node: ast.AST, nesting: int) -> None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            return

        method = getattr(self, f"_visit_{node.__class__.__name__}", None)
        if method is not None:
            method(node, nesting)
            return

        for child in ast.iter_child_nodes(node):
            self._visit(child, nesting)

    def _visit_statements(self, stmts: list[ast.stmt], *, nesting: int) -> None:
        for stmt in stmts:
            self._visit(stmt, nesting)

    def _visit_If(self, node: ast.If, nesting: int) -> None:  # noqa: N802
        self.value += 1 + nesting
        self._visit(node.test, nesting)
        self._visit_statements(node.body, nesting=nesting + 1)
        self._visit_if_orelse(node.orelse, parent_col_offset=node.col_offset, nesting=nesting)

    def _visit_if_orelse(
        self,
        orelse: list[ast.stmt],
        *,
        parent_col_offset: int,
        nesting: int,
    ) -> None:
        if (
            len(orelse) == 1
            and isinstance(orelse[0], ast.If)
            and orelse[0].col_offset == parent_col_offset
        ):
            self._visit(orelse[0], nesting)
            return
        self._visit_statements(orelse, nesting=nesting + 1)

    def _visit_For(self, node: ast.For, nesting: int) -> None:  # noqa: N802
        self.value += 1 + nesting
        self._visit(node.target, nesting)
        self._visit(node.iter, nesting)
        self._visit_statements(node.body, nesting=nesting + 1)
        self._visit_statements(node.orelse, nesting=nesting + 1)

    def _visit_AsyncFor(self, node: ast.AsyncFor, nesting: int) -> None:  # noqa: N802
        self._visit_For(node, nesting)

    def _visit_While(self, node: ast.While, nesting: int) -> None:  # noqa: N802
        self.value += 1 + nesting
        self._visit(node.test, nesting)
        self._visit_statements(node.body, nesting=nesting + 1)
        self._visit_statements(node.orelse, nesting=nesting + 1)

    def _visit_ExceptHandler(self, node: ast.ExceptHandler, nesting: int) -> None:  # noqa: N802
        self.value += 1 + nesting
        if node.type is not None:
            self._visit(node.type, nesting)
        self._visit_statements(node.body, nesting=nesting + 1)

    def _visit_IfExp(self, node: ast.IfExp, nesting: int) -> None:  # noqa: N802
        self.value += 1 + nesting
        self._visit(node.test, nesting)
        self._visit(node.body, nesting + 1)
        self._visit(node.orelse, nesting + 1)

    def _visit_Match(self, node: ast.Match, nesting: int) -> None:  # noqa: N802
        for case in node.cases:
            self._visit(case, nesting)

    def _visit_match_case(self, node: ast.match_case, nesting: int) -> None:
        self.value += 1 + nesting
        if node.guard is not None:
            self._visit(node.guard, nesting)
        self._visit_statements(node.body, nesting=nesting + 1)

    def _visit_BoolOp(self, node: ast.BoolOp, nesting: int) -> None:  # noqa: N802
        self.value += 1
        for value in node.values:
            self._visit(value, nesting)

    def _visit_Assert(self, node: ast.Assert, nesting: int) -> None:  # noqa: N802
        self._visit(node.test, nesting)
        if node.msg is not None:
            self._visit(node.msg, nesting)

    def _visit_ListComp(self, node: ast.ListComp, nesting: int) -> None:  # noqa: N802
        self._visit_comprehension_expr([node.elt], node.generators, nesting)

    def _visit_SetComp(self, node: ast.SetComp, nesting: int) -> None:  # noqa: N802
        self._visit_comprehension_expr([node.elt], node.generators, nesting)

    def _visit_GeneratorExp(self, node: ast.GeneratorExp, nesting: int) -> None:  # noqa: N802
        self._visit_comprehension_expr([node.elt], node.generators, nesting)

    def _visit_DictComp(self, node: ast.DictComp, nesting: int) -> None:  # noqa: N802
        self._visit_comprehension_expr([node.key, node.value], node.generators, nesting)

    def _visit_comprehension_expr(
        self,
        elt_nodes: list[ast.AST],
        generators: list[ast.comprehension],
        nesting: int,
    ) -> None:
        current_nesting = nesting
        for generator in generators:
            self.value += 1 + current_nesting
            self._visit(generator.target, current_nesting)
            self._visit(generator.iter, current_nesting)
            for index, condition in enumerate(generator.ifs):
                if index > 0:
                    self.value += 1
                self._visit(condition, current_nesting + 1)
            current_nesting += 1
        for elt in elt_nodes:
            self._visit(elt, current_nesting)


def _stable_entries(entries: Iterable[ComplexityEntry]) -> tuple[ComplexityEntry, ...]:
    seen: set[str] = set()
    unique: list[ComplexityEntry] = []
    for entry in entries:
        if entry.fqn in seen:
            continue
        seen.add(entry.fqn)
        unique.append(entry)
    return tuple(sorted(unique, key=lambda entry: entry.fqn))


def _join_fqn(*parts: str) -> str:
    return ".".join(part for part in parts if part)


def _expand_python_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    expanded: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            expanded.extend(path.rglob("*.py"))
        elif path.suffix == ".py":
            expanded.append(path)
    return tuple(sorted(expanded, key=lambda path: str(path.resolve())))
