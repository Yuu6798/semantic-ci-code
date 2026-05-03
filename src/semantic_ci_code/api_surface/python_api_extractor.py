"""Deterministic Python api_surface extraction.

This P1 extractor is purely syntactic and stdlib-``ast`` based. It emits
``APISurfaceEntry`` records for the closed kind set:

``function``, ``async_function``, ``class``, ``method``,
``async_method``, and ``constant``.

Definitions inside module-scope compound statements, including
``if TYPE_CHECKING:`` blocks and version-conditional branches, are
emitted because they are present in the source AST. Nested functions,
nested classes, re-exports, ``__all__`` semantics, dynamic definitions,
and property/dataclass sub-kinds are deferred to later briefs.
"""

from __future__ import annotations

import ast
import copy
from collections.abc import Iterable
from pathlib import Path

from semantic_ci_code.domain.state_schema import APISurfaceEntry

FUNCTION_KIND = "function"
ASYNC_FUNCTION_KIND = "async_function"
CLASS_KIND = "class"
METHOD_KIND = "method"
ASYNC_METHOD_KIND = "async_method"
CONSTANT_KIND = "constant"


def extract_python_api_surface(
    source: str,
    *,
    module_fqn: str,
    filename: str = "<string>",
) -> tuple[APISurfaceEntry, ...]:
    """Extract syntactic Python API surface entries from ``source``.

    ``SyntaxError`` from :func:`ast.parse` propagates unchanged so
    callers can distinguish parse failures from empty surfaces.
    """
    tree = ast.parse(source, filename=filename)
    entries: list[APISurfaceEntry] = []

    for stmt in _iter_module_scope_statements(tree.body):
        if isinstance(stmt, ast.AsyncFunctionDef):
            entries.append(
                _entry(
                    fqn=_join_fqn(module_fqn, stmt.name),
                    kind=ASYNC_FUNCTION_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                )
            )
        elif isinstance(stmt, ast.FunctionDef):
            entries.append(
                _entry(
                    fqn=_join_fqn(module_fqn, stmt.name),
                    kind=FUNCTION_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                )
            )
        elif isinstance(stmt, ast.ClassDef):
            class_fqn = _join_fqn(module_fqn, stmt.name)
            entries.append(
                _entry(
                    fqn=class_fqn,
                    kind=CLASS_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                )
            )
            entries.extend(_extract_class_methods(stmt, class_fqn))
        elif isinstance(stmt, ast.Assign):
            entries.extend(_extract_constants(stmt, module_fqn))

    return _stable_entries(entries)


def extract_python_api_surface_from_paths(
    paths: Iterable[Path],
    *,
    package_root: Path,
) -> tuple[APISurfaceEntry, ...]:
    """Extract API surface entries from Python files under ``package_root``.

    Directory paths are expanded recursively to ``*.py`` files. File
    paths outside ``package_root`` raise :class:`ValueError` via
    :meth:`Path.relative_to`.
    """
    root = package_root.resolve()
    entries: list[APISurfaceEntry] = []

    for path in _expand_python_paths(paths):
        resolved = path.resolve()
        module_fqn = _module_fqn_from_path(resolved, package_root=root)
        source = resolved.read_text(encoding="utf-8")
        entries.extend(
            extract_python_api_surface(
                source,
                module_fqn=module_fqn,
                filename=str(resolved),
            )
        )

    return _stable_entries(entries)


def _iter_module_scope_statements(stmts: list[ast.stmt]) -> Iterable[ast.stmt]:
    """Yield statements that bind in module scope, walking compound bodies."""
    for stmt in stmts:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Assign):
            yield stmt
            continue
        if isinstance(stmt, ast.If):
            yield from _iter_module_scope_statements(stmt.body)
            yield from _iter_module_scope_statements(stmt.orelse)
        elif isinstance(stmt, ast.Try | ast.TryStar):
            yield from _iter_module_scope_statements(stmt.body)
            for handler in stmt.handlers:
                yield from _iter_module_scope_statements(handler.body)
            yield from _iter_module_scope_statements(stmt.orelse)
            yield from _iter_module_scope_statements(stmt.finalbody)
        elif isinstance(stmt, ast.For | ast.AsyncFor):
            yield from _iter_module_scope_statements(stmt.body)
            yield from _iter_module_scope_statements(stmt.orelse)
        elif isinstance(stmt, ast.While):
            yield from _iter_module_scope_statements(stmt.body)
            yield from _iter_module_scope_statements(stmt.orelse)
        elif isinstance(stmt, ast.With | ast.AsyncWith):
            yield from _iter_module_scope_statements(stmt.body)
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                yield from _iter_module_scope_statements(case.body)


def _extract_class_methods(node: ast.ClassDef, class_fqn: str) -> list[APISurfaceEntry]:
    entries: list[APISurfaceEntry] = []
    for stmt in node.body:
        if isinstance(stmt, ast.AsyncFunctionDef):
            entries.append(
                _entry(
                    fqn=_join_fqn(class_fqn, stmt.name),
                    kind=ASYNC_METHOD_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                )
            )
        elif isinstance(stmt, ast.FunctionDef):
            entries.append(
                _entry(
                    fqn=_join_fqn(class_fqn, stmt.name),
                    kind=METHOD_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                )
            )
    return entries


def _extract_constants(stmt: ast.Assign, module_fqn: str) -> list[APISurfaceEntry]:
    entries: list[APISurfaceEntry] = []
    for target in stmt.targets:
        if isinstance(target, ast.Name) and _is_all_caps_name(target.id):
            entries.append(
                _entry(
                    fqn=_join_fqn(module_fqn, target.id),
                    kind=CONSTANT_KIND,
                    signature=None,
                    leaf_name=target.id,
                )
            )
    return entries


def _render_signature(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str:
    stripped = copy.deepcopy(node)
    stripped.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
    ast.fix_missing_locations(stripped)
    return ast.unparse(stripped)


def _entry(
    *,
    fqn: str,
    kind: str,
    signature: str | None,
    leaf_name: str,
) -> APISurfaceEntry:
    return APISurfaceEntry(
        fqn=fqn,
        kind=kind,
        signature=signature,
        visibility=_visibility_for_leaf_name(leaf_name),
    )


def _stable_entries(entries: Iterable[APISurfaceEntry]) -> tuple[APISurfaceEntry, ...]:
    seen: set[tuple[str, str, str | None, str | None]] = set()
    unique: list[APISurfaceEntry] = []
    for entry in entries:
        key = (entry.fqn, entry.kind, entry.signature, entry.visibility)
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return tuple(sorted(unique, key=lambda entry: (entry.fqn, entry.kind)))


def _visibility_for_leaf_name(name: str) -> str:
    if len(name) > 4 and name.startswith("__") and name.endswith("__"):
        return "dunder"
    if name.startswith("_"):
        return "private"
    return "public"


def _is_all_caps_name(name: str) -> bool:
    return name.isupper()


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


def _module_fqn_from_path(path: Path, *, package_root: Path) -> str:
    relative = path.relative_to(package_root)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        parts = [path.parent.name]
    return ".".join(parts)
