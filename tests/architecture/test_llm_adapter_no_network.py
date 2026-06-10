from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

PROJECT_PREFIX = "semantic_ci_code"
LLM_ADAPTER_PACKAGE = "semantic_ci_code.sensor.adapters.llm"
FORBIDDEN_NETWORK_IMPORTS = (
    "aiohttp",
    "http",
    "httpx",
    "openai",
    "requests",
    "socket",
    "subprocess",
    "urllib",
)


def _module_to_path(module_name: str) -> Path | None:
    try:
        spec = importlib.util.find_spec(module_name)
    except (ModuleNotFoundError, AttributeError, ValueError):
        return None
    if spec is None or spec.origin is None or spec.origin == "built-in":
        return None
    path = Path(spec.origin)
    if not path.exists():
        return None
    return path


def _discover_package_modules(package_name: str) -> tuple[str, ...]:
    package_path = _module_to_path(package_name)
    if package_path is None:
        raise AssertionError(f"package not importable: {package_name}")
    package_root = package_path.parent
    modules: set[str] = set()
    for path in package_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(package_root)
        if path.name == "__init__.py":
            suffix_parts = relative.parent.parts
        else:
            suffix_parts = relative.with_suffix("").parts
        modules.add(".".join((package_name, *suffix_parts)))
    return tuple(sorted(modules))


def _direct_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or node.module is None:
                continue
            base = node.module
            imports.add(base)
            for alias in node.names:
                candidate = f"{base}.{alias.name}"
                if _module_to_path(candidate) is not None:
                    imports.add(candidate)
    return imports


def _transitive_imports(root_module: str) -> set[str]:
    visited_project_modules: set[str] = set()
    imports: set[str] = set()
    queue: list[str] = [root_module]
    while queue:
        module_name = queue.pop()
        if module_name in visited_project_modules:
            continue
        visited_project_modules.add(module_name)
        path = _module_to_path(module_name)
        if path is None:
            continue
        for imported in _direct_imports(path):
            imports.add(imported)
            if imported.startswith(PROJECT_PREFIX) and imported not in visited_project_modules:
                queue.append(imported)
    return imports


def _forbidden_root(module_name: str) -> str | None:
    root = module_name.split(".", 1)[0]
    for forbidden in FORBIDDEN_NETWORK_IMPORTS:
        if root == forbidden:
            return forbidden
    return None


def test_llm_adapter_package_has_no_network_or_subprocess_imports():
    failures: dict[str, list[str]] = {}
    for module in _discover_package_modules(LLM_ADAPTER_PACKAGE):
        leaks = sorted(
            imported
            for imported in _transitive_imports(module)
            if _forbidden_root(imported) is not None
        )
        if leaks:
            failures[module] = leaks

    assert not failures, f"LLM adapter package imported network/subprocess modules: {failures}"
