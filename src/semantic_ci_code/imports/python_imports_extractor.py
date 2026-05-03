"""Deterministic Python imports extraction.

This P1 extractor is purely syntactic and stdlib-``ast`` based. It emits
``ImportEntry`` records for module-scope import statements only.

Field-population contract:

| Source statement | `module` | `from_` | `symbols` |
|---|---|---|---|
| `import x` | `"x"` | `None` | `()` |
| `import x as y` | `"x"` | `None` | `()` (alias info intentionally lost — see below) |
| `import a.b` | `"a.b"` | `None` | `()` |
| `import a.b as c` | `"a.b"` | `None` | `()` |
| `import a, b` | two entries: `("a", None, ())`, `("b", None, ())` | | |
| `from x import y` | `"x"` | `None` | `("y",)` |
| `from x import y, z` | `"x"` | `None` | `("y", "z")` (one entry, multiple symbols) |
| `from x import y as z` | `"x"` | `None` | `("y",)` (original imported name, alias lost) |
| `from x.y import z` | `"x.y"` | `None` | `("z",)` |
| `from . import y` | `""` | `"."` | `("y",)` |
| `from . import y as z` | `""` | `"."` | `("y",)` |
| `from .pkg import y` | `"pkg"` | `"."` | `("y",)` |
| `from ..pkg.sub import y, z` | `"pkg.sub"` | `".."` | `("y", "z")` |
| `from x import *` | `"x"` | `None` | `("*",)` |
| `from . import *` | `""` | `"."` | `("*",)` |

Core encoding decisions:

1. ``module`` is the dotted source-module path as written. For relative
   imports, leading dots are stripped from ``module`` and recorded in
   ``from_``.
2. ``from_`` records only the relative-import dot prefix, or ``None``
   for absolute imports. It is not the source module name.
3. Empty ``module`` is reserved for ``from . import name``.
4. ``symbols`` records original imported names, not local aliases.
   Alias information is intentionally lost in this dimension.
5. Star imports use the literal symbol ``"*"``.
6. ``import a, b`` emits one entry per imported module; ``from x import
   a, b`` emits one entry with multiple symbols.
7. ``symbols`` is sorted ascending within each entry.

Module-scope compound bodies are traversed, so imports inside
``if TYPE_CHECKING:`` and ``try`` / ``except ImportError`` blocks are
emitted. Function-local and class-body imports are skipped in this P1
slice. Files are read as UTF-8 in path-based extraction.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from semantic_ci_code.domain.state_schema import ImportEntry


def extract_python_imports(
    source: str,
    *,
    filename: str = "<string>",
) -> tuple[ImportEntry, ...]:
    """Extract deterministic module-scope import entries from Python ``source``.

    ``SyntaxError`` from :func:`ast.parse` propagates unchanged so
    callers can distinguish parse failures from empty import surfaces.
    """
    tree = ast.parse(source, filename=filename)
    entries: list[ImportEntry] = []

    for stmt in _iter_module_scope_imports(tree.body):
        if isinstance(stmt, ast.Import):
            entries.extend(_entries_for_import(stmt))
        elif isinstance(stmt, ast.ImportFrom):
            entries.append(_entry_for_import_from(stmt))

    return _stable_entries(entries)


def extract_python_imports_from_paths(
    paths: Iterable[Path],
    *,
    package_root: Path,
) -> tuple[ImportEntry, ...]:
    """Extract imports from Python files under ``package_root``.

    Directory paths are expanded recursively to ``*.py`` files. File
    paths outside ``package_root`` raise :class:`ValueError` via
    :meth:`Path.relative_to`.
    """
    root = package_root.resolve()
    entries: list[ImportEntry] = []

    for path in _expand_python_paths(paths):
        resolved = path.resolve()
        resolved.relative_to(root)
        source = resolved.read_text(encoding="utf-8")
        entries.extend(extract_python_imports(source, filename=str(resolved)))

    return _stable_entries(entries)


def _iter_module_scope_imports(stmts: list[ast.stmt]) -> Iterable[ast.Import | ast.ImportFrom]:
    """Yield import statements that execute in module scope."""
    for stmt in stmts:
        if isinstance(stmt, ast.Import | ast.ImportFrom):
            yield stmt
        elif isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        elif isinstance(stmt, ast.If):
            yield from _iter_module_scope_imports(stmt.body)
            yield from _iter_module_scope_imports(stmt.orelse)
        elif isinstance(stmt, ast.Try | ast.TryStar):
            yield from _iter_module_scope_imports(stmt.body)
            for handler in stmt.handlers:
                yield from _iter_module_scope_imports(handler.body)
            yield from _iter_module_scope_imports(stmt.orelse)
            yield from _iter_module_scope_imports(stmt.finalbody)
        elif isinstance(stmt, ast.For | ast.AsyncFor):
            yield from _iter_module_scope_imports(stmt.body)
            yield from _iter_module_scope_imports(stmt.orelse)
        elif isinstance(stmt, ast.While):
            yield from _iter_module_scope_imports(stmt.body)
            yield from _iter_module_scope_imports(stmt.orelse)
        elif isinstance(stmt, ast.With | ast.AsyncWith):
            yield from _iter_module_scope_imports(stmt.body)
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                yield from _iter_module_scope_imports(case.body)


def _entries_for_import(stmt: ast.Import) -> list[ImportEntry]:
    return [ImportEntry(module=alias.name) for alias in stmt.names]


def _entry_for_import_from(stmt: ast.ImportFrom) -> ImportEntry:
    return ImportEntry(
        module=stmt.module or "",
        from_="." * stmt.level if stmt.level else None,
        symbols=tuple(sorted(alias.name for alias in stmt.names)),
    )


def _stable_entries(entries: Iterable[ImportEntry]) -> tuple[ImportEntry, ...]:
    seen: set[tuple[str, str | None, tuple[str, ...]]] = set()
    unique: list[ImportEntry] = []
    for entry in entries:
        key = (entry.module, entry.from_, entry.symbols)
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return tuple(sorted(unique, key=lambda entry: (entry.from_ or "", entry.module, entry.symbols)))


def _expand_python_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    expanded: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            expanded.extend(path.rglob("*.py"))
        elif path.suffix == ".py":
            expanded.append(path)
    return tuple(sorted(expanded, key=lambda path: str(path.resolve())))
