"""Qualified-name extraction for Python SAST findings."""

from __future__ import annotations

import ast
from pathlib import Path

_SCOPE_NODES = (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef)


def qualified_name_for_line(source_path: Path, *, repo_root: Path, line: int) -> str:
    """Return the nearest Python scope qualified name for a 1-based source line."""

    module_name = module_name_for_path(source_path, repo_root=repo_root)
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return module_name

    scope = _scope_for_line(tree, line)
    if not scope:
        return module_name
    return ".".join((module_name, *scope))


def module_name_for_path(source_path: Path, *, repo_root: Path) -> str:
    """Return a dotted module name for a source path."""

    try:
        relative = source_path.resolve().relative_to(repo_root.resolve())
    except (OSError, ValueError):
        relative = source_path

    without_suffix = relative.with_suffix("")
    parts = tuple(part for part in without_suffix.parts if part not in {"", "."})
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return source_path.stem or "<module>"
    return ".".join(parts)


def _scope_for_line(tree: ast.AST, line: int) -> tuple[str, ...]:
    best: tuple[str, ...] = ()

    def visit(node: ast.AST, stack: tuple[str, ...]) -> None:
        nonlocal best
        next_stack = stack
        if isinstance(node, _SCOPE_NODES) and _contains_line(node, line):
            next_stack = (*stack, node.name)
            if len(next_stack) > len(best):
                best = next_stack

        for child in ast.iter_child_nodes(node):
            if _may_contain_line(child, line):
                visit(child, next_stack)

    visit(tree, ())
    return best


def _may_contain_line(node: ast.AST, line: int) -> bool:
    if hasattr(node, "lineno"):
        return _contains_line(node, line)
    return True


def _contains_line(node: ast.AST, line: int) -> bool:
    start = _start_line(node)
    if start is None or line < start:
        return False
    end = getattr(node, "end_lineno", start)
    return line <= end


def _start_line(node: ast.AST) -> int | None:
    start = getattr(node, "lineno", None)
    decorators = getattr(node, "decorator_list", ())
    decorator_lines = [
        decorator.lineno
        for decorator in decorators
        if hasattr(decorator, "lineno") and decorator.lineno is not None
    ]
    if decorator_lines:
        decorator_start = min(decorator_lines)
        return min(start, decorator_start) if start is not None else decorator_start
    return start
