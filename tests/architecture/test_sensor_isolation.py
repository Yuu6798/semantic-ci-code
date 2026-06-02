from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

PROJECT_PREFIX = "semantic_ci_code"
SENSOR_PACKAGE = "semantic_ci_code.sensor"

SENSOR_FORBIDDEN_IMPORTS = (
    "semantic_ci_code.cli",
    "semantic_ci_code.evaluator",
    "semantic_ci_code.compiler",
    "semantic_ci_code.repair_compiler",
)
SENSOR_CORE_MODULES = (
    "semantic_ci_code.sensor.models",
    "semantic_ci_code.sensor.delta",
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


def _transitive_closure(root_module: str) -> set[str]:
    visited: set[str] = set()
    queue: list[str] = [root_module]
    while queue:
        module_name = queue.pop()
        if module_name in visited:
            continue
        visited.add(module_name)
        if not module_name.startswith(PROJECT_PREFIX):
            continue
        path = _module_to_path(module_name)
        if path is None:
            continue
        for imported in _direct_imports(path):
            if imported not in visited:
                queue.append(imported)
    return visited


def _is_forbidden_match(module: str) -> str | None:
    for forbidden in SENSOR_FORBIDDEN_IMPORTS:
        if module == forbidden or module.startswith(forbidden + "."):
            return forbidden
    return None


def _is_prefix_match(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def test_sensor_package_does_not_import_core_engine_or_cli_layers():
    failures: dict[str, list[str]] = {}
    for module in _discover_package_modules(SENSOR_PACKAGE):
        closure = _transitive_closure(module)
        leaks = sorted(item for item in closure if _is_forbidden_match(item))
        if leaks:
            failures[module] = leaks

    assert not failures, f"Sensor package isolation violation: {failures}"


def test_sensor_core_models_and_delta_do_not_import_ssp_protocol():
    failures: dict[str, list[str]] = {}
    for module in SENSOR_CORE_MODULES:
        closure = _transitive_closure(module)
        leaks = sorted(item for item in closure if _is_prefix_match(item, "semantic_ci_code.ssp"))
        if leaks:
            failures[module] = leaks

    assert not failures, f"Sensor core module imported SSP protocol: {failures}"
