"""Deterministic Python test-surface extraction.

CSCI-9 intentionally uses stdlib ``ast`` instead of ``pytest --collect-only``.
The P1 contract is pytest-name-convention static recognition, owned by us:
zero dependencies, deterministic output, no import side effects, trivially
auditable code, and no subprocess. A later brief may add an optional
collect-only cross-check after a baseline corpus exists.

Collection rules:

Pytest-name-convention static recognition. Emit ONE ``TestSurfaceEntry``
per:

| Source | Emitted | ``test_function`` value |
|---|---|---|
| Module-level ``def test_<name>(...)`` | yes | ``"test_<name>"`` |
| Module-level ``async def test_<name>(...)`` | yes | ``"test_<name>"`` |
| ``def test_<name>(self, ...)`` in ``class Test<X>:`` | yes | ``"Test<X>::test_<name>"`` |
| ``async def test_<name>(self, ...)`` in ``class Test<X>:`` | yes | ``"Test<X>::test_<name>"`` |
| ``def test_<name>(...)`` inside a class NOT starting with ``Test`` | no (pytest-faithful) |
| ``def <other>(...)`` inside ``class Test<X>:`` (no ``test_`` prefix) | no |
| ``def test_<name>`` nested inside another function or method | no |
| ``def test_<name>`` inside a nested class | no |
| ``class Test<X>`` with an ``__init__`` method | emit anyway in P1 |
| Lambdas, module-level code, ``class TestX(unittest.TestCase)`` non-``test_`` methods | no |

The ``__init__``-presence check is the one place we explicitly diverge
from runtime collection in P1, to keep the rule purely lexical. Definitions
inside module-scope compound statements are considered module-level bindings,
matching the P1 ``api_surface`` extractor.

Asserts rule:

Count ``ast.Assert`` nodes inside the test function body. STOP descent at
nested ``FunctionDef`` / ``AsyncFunctionDef`` / ``ClassDef``. Do NOT count:

- ``unittest.TestCase.assertEqual`` and friends (these are ``ast.Call``,
  not ``ast.Assert``).
- ``pytest.raises`` context managers (these are ``ast.With``, not
  asserts).
- Asserts inside lambdas (lambdas have no ``ast.Assert`` since they are
  expressions; this is a no-op rule but documented).
- Asserts inside nested helper functions defined within the test (parity
  with the nested-def rule for complexity in CSCI-8).

If the test body contains zero ``ast.Assert`` nodes, set ``asserts = 0``
(NOT ``None``). ``None`` is reserved for cases where the count is genuinely
undefined; for pytest tests this never happens.

Parametrize count rule:

Inspect the test function's ``decorator_list``. A decorator counts as a
parametrize decorator iff:

1. It is an ``ast.Call``.
2. Its ``func`` is an ``ast.Attribute`` chain whose final ``attr`` is
   ``"parametrize"``, OR an ``ast.Name`` whose ``id`` is ``"parametrize"``.
   This catches ``pytest.mark.parametrize``, ``mark.parametrize``, and bare
   ``parametrize``. The chain prefix is NOT verified; we trust the lexical
   signal.

For each parametrize decorator, extract the ``argvalues`` argument:

- Positional: ``args[1]`` if ``len(args) >= 2``.
- Keyword: ``keywords`` entry with ``arg == "argvalues"`` if not found
  positionally.

Determine the case count statically:

- If ``argvalues`` is ``ast.List`` or ``ast.Tuple``: case count =
  ``len(node.elts)``.
- Otherwise (a ``Name``, ``Call``, comprehension, generator, etc.): the
  count is NOT statically determinable.

Combine across stacked decorators by multiplication (cartesian product,
matches pytest behavior):

- All decorators statically determinable -> ``parametrize_count = product
  of case counts``.
- Any decorator non-determinable -> ``parametrize_count = None``.
- No parametrize decorator on the function -> ``parametrize_count = None``.

This is a deliberate P1 conflation: ``parametrize_count = None`` means
EITHER "no parametrize decorator" OR "parametrize present but
non-determinable". A future brief may split these into separate fields.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from semantic_ci_code.domain.state_schema import TestSurfaceEntry


def extract_python_test_surface(
    source: str,
    *,
    test_file: str,
    filename: str = "<string>",
) -> tuple[TestSurfaceEntry, ...]:
    """Extract deterministic pytest-style test surface entries from ``source``.

    ``SyntaxError`` from :func:`ast.parse` propagates unchanged so callers
    can distinguish parse failures from empty test surfaces.
    """
    tree = ast.parse(source, filename=filename)
    entries: list[TestSurfaceEntry] = []

    for stmt in _iter_module_scope_definitions(tree.body):
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            if _is_test_function_name(stmt.name):
                entries.append(
                    _entry_for_test(test_file=test_file, test_function=stmt.name, node=stmt)
                )
        elif isinstance(stmt, ast.ClassDef) and _is_test_class_name(stmt.name):
            entries.extend(_entries_for_test_class(test_file=test_file, node=stmt))

    return _stable_entries(entries)


def extract_python_test_surface_from_paths(
    paths: Iterable[Path],
    *,
    package_root: Path,
) -> tuple[TestSurfaceEntry, ...]:
    """Extract test-surface entries from Python files under ``package_root``.

    Directory paths are expanded recursively to ``*.py`` files. File paths
    outside ``package_root`` raise :class:`ValueError` via
    :meth:`Path.relative_to`.
    """
    root = package_root.resolve()
    entries: list[TestSurfaceEntry] = []

    for path in _expand_python_paths(paths):
        resolved = path.resolve()
        relative = resolved.relative_to(root)
        test_file = relative.as_posix()
        source = resolved.read_text(encoding="utf-8")
        entries.extend(
            extract_python_test_surface(
                source,
                test_file=test_file,
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


def _entries_for_test_class(test_file: str, node: ast.ClassDef) -> list[TestSurfaceEntry]:
    entries: list[TestSurfaceEntry] = []
    for stmt in node.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef) and _is_test_function_name(
            stmt.name
        ):
            entries.append(
                _entry_for_test(
                    test_file=test_file,
                    test_function=f"{node.name}::{stmt.name}",
                    node=stmt,
                )
            )
    return entries


def _entry_for_test(
    *,
    test_file: str,
    test_function: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> TestSurfaceEntry:
    return TestSurfaceEntry(
        test_file=test_file,
        test_function=test_function,
        asserts=_count_asserts(node),
        parametrize_count=_parametrize_count(node),
    )


def _count_asserts(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    counter = _AssertCounter()
    return counter.count_body(node.body)


class _AssertCounter(ast.NodeVisitor):
    def __init__(self) -> None:
        self.value = 0

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

    def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
        self.value += 1


def _parametrize_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    counts: list[int] = []
    for decorator in node.decorator_list:
        if not _is_parametrize_decorator(decorator):
            continue
        argvalues = _argvalues_argument(decorator)
        if argvalues is None:
            return None
        case_count = _static_case_count(argvalues)
        if case_count is None:
            return None
        counts.append(case_count)

    if not counts:
        return None

    product = 1
    for count in counts:
        product *= count
    return product


def _is_parametrize_decorator(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and _is_parametrize_func(node.func)


def _is_parametrize_func(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "parametrize"
    if isinstance(node, ast.Attribute):
        return node.attr == "parametrize"
    return False


def _argvalues_argument(node: ast.Call) -> ast.expr | None:
    if len(node.args) >= 2:
        return node.args[1]
    for keyword in node.keywords:
        if keyword.arg == "argvalues":
            return keyword.value
    return None


def _static_case_count(node: ast.expr) -> int | None:
    if isinstance(node, ast.List | ast.Tuple):
        return len(node.elts)
    return None


def _is_test_function_name(name: str) -> bool:
    return name.startswith("test_")


def _is_test_class_name(name: str) -> bool:
    return name.startswith("Test")


def _stable_entries(entries: Iterable[TestSurfaceEntry]) -> tuple[TestSurfaceEntry, ...]:
    seen: set[tuple[str, str]] = set()
    unique: list[TestSurfaceEntry] = []
    for entry in entries:
        key = (entry.test_file, entry.test_function)
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return tuple(sorted(unique, key=lambda entry: (entry.test_file, entry.test_function)))


def _expand_python_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    expanded: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            expanded.extend(path.rglob("*.py"))
        elif path.suffix == ".py":
            expanded.append(path)
    return tuple(sorted(expanded, key=lambda path: str(path.resolve())))
