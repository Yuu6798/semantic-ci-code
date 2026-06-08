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
from dataclasses import dataclass
from pathlib import Path

from semantic_ci_code.domain.state_schema import APISurfaceEntry

FUNCTION_KIND = "function"
ASYNC_FUNCTION_KIND = "async_function"
CLASS_KIND = "class"
METHOD_KIND = "method"
ASYNC_METHOD_KIND = "async_method"
CONSTANT_KIND = "constant"


@dataclass(frozen=True)
class _SurfaceCandidate:
    entry: APISurfaceEntry
    preserve_signature_duplicates: bool = False


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
    candidates: list[_SurfaceCandidate] = []

    for stmt in _iter_module_scope_statements(tree.body):
        if isinstance(stmt, ast.AsyncFunctionDef):
            candidates.append(
                _candidate(
                    fqn=_join_fqn(module_fqn, stmt.name),
                    kind=ASYNC_FUNCTION_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                    decorators=_decorator_names(stmt.decorator_list),
                    preserve_signature_duplicates=_is_overload_definition(stmt),
                )
            )
        elif isinstance(stmt, ast.FunctionDef):
            candidates.append(
                _candidate(
                    fqn=_join_fqn(module_fqn, stmt.name),
                    kind=FUNCTION_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                    decorators=_decorator_names(stmt.decorator_list),
                    preserve_signature_duplicates=_is_overload_definition(stmt),
                )
            )
        elif isinstance(stmt, ast.ClassDef):
            class_fqn = _join_fqn(module_fqn, stmt.name)
            candidates.append(
                _candidate(
                    fqn=class_fqn,
                    kind=CLASS_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                    decorators=_decorator_names(stmt.decorator_list),
                )
            )
            candidates.extend(_extract_class_methods(stmt, class_fqn))
        elif isinstance(stmt, ast.Assign | ast.AnnAssign):
            candidates.extend(_extract_constants(stmt, module_fqn))

    return _stable_entries(candidates)


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

    return _sort_entries(entries)


def _iter_module_scope_statements(stmts: list[ast.stmt]) -> Iterable[ast.stmt]:
    """Yield statements that bind in module scope, walking compound bodies."""
    for stmt in stmts:
        if isinstance(
            stmt,
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Assign | ast.AnnAssign,
        ):
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


def _extract_class_methods(node: ast.ClassDef, class_fqn: str) -> list[_SurfaceCandidate]:
    candidates: list[_SurfaceCandidate] = []
    for stmt in node.body:
        if isinstance(stmt, ast.AsyncFunctionDef):
            candidates.append(
                _candidate(
                    fqn=_join_fqn(class_fqn, stmt.name),
                    kind=ASYNC_METHOD_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                    decorators=_decorator_names(stmt.decorator_list),
                    preserve_signature_duplicates=_is_overload_definition(stmt),
                )
            )
        elif isinstance(stmt, ast.FunctionDef):
            candidates.append(
                _candidate(
                    fqn=_join_fqn(class_fqn, stmt.name),
                    kind=METHOD_KIND,
                    signature=_render_signature(stmt),
                    leaf_name=stmt.name,
                    decorators=_decorator_names(stmt.decorator_list),
                    preserve_signature_duplicates=_is_overload_definition(stmt),
                )
            )
    return candidates


def _extract_constants(
    stmt: ast.Assign | ast.AnnAssign, module_fqn: str
) -> list[_SurfaceCandidate]:
    candidates: list[_SurfaceCandidate] = []
    for target in _constant_targets(stmt):
        if _is_all_caps_name(target.id):
            candidates.append(
                _candidate(
                    fqn=_join_fqn(module_fqn, target.id),
                    kind=CONSTANT_KIND,
                    signature=None,
                    leaf_name=target.id,
                )
            )
    return candidates


def _constant_targets(stmt: ast.Assign | ast.AnnAssign) -> tuple[ast.Name, ...]:
    if isinstance(stmt, ast.Assign):
        return tuple(target for target in stmt.targets if isinstance(target, ast.Name))
    if stmt.value is not None and isinstance(stmt.target, ast.Name):
        return (stmt.target,)
    return ()


def _render_signature(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str:
    stripped = copy.deepcopy(node)
    stripped.decorator_list = []
    stripped.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
    ast.fix_missing_locations(stripped)
    return ast.unparse(stripped)


def _entry(
    *,
    fqn: str,
    kind: str,
    signature: str | None,
    leaf_name: str,
    decorators: tuple[str, ...] = (),
) -> APISurfaceEntry:
    return APISurfaceEntry(
        fqn=fqn,
        kind=kind,
        signature=signature,
        visibility=_visibility_for_leaf_name(leaf_name),
        decorators=decorators,
    )


def _candidate(
    *,
    fqn: str,
    kind: str,
    signature: str | None,
    leaf_name: str,
    decorators: tuple[str, ...] = (),
    preserve_signature_duplicates: bool = False,
) -> _SurfaceCandidate:
    return _SurfaceCandidate(
        entry=_entry(
            fqn=fqn,
            kind=kind,
            signature=signature,
            leaf_name=leaf_name,
            decorators=decorators,
        ),
        preserve_signature_duplicates=preserve_signature_duplicates,
    )


def _stable_entries(candidates: Iterable[_SurfaceCandidate]) -> tuple[APISurfaceEntry, ...]:
    seen: set[tuple[str, ...]] = set()
    unique: list[APISurfaceEntry] = []
    for candidate in candidates:
        entry = candidate.entry
        key = _dedupe_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return _sort_entries(unique)


def _dedupe_key(candidate: _SurfaceCandidate) -> tuple[str, ...]:
    entry = candidate.entry
    if candidate.preserve_signature_duplicates:
        return (entry.fqn, entry.kind, entry.signature or "", entry.visibility or "")
    return (entry.fqn, entry.kind)


def _sort_entries(entries: Iterable[APISurfaceEntry]) -> tuple[APISurfaceEntry, ...]:
    return tuple(sorted(entries, key=lambda entry: (entry.fqn, entry.kind, entry.signature or "")))


def _is_overload_definition(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_is_overload_decorator(decorator) for decorator in node.decorator_list)


def _is_overload_decorator(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "overload"
    if isinstance(node, ast.Attribute):
        return node.attr == "overload"
    if isinstance(node, ast.Call):
        return _is_overload_decorator(node.func)
    return False


def _decorator_names(decorators: list[ast.expr]) -> tuple[str, ...]:
    return tuple(name for decorator in decorators if (name := _decorator_name(decorator)))


def _decorator_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _decorator_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return None


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
