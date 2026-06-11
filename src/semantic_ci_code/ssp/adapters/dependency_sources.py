"""Dependency source discovery for pip-audit SSP scans."""

from __future__ import annotations

import ast
import os
import platform
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

DependencySourceKind = Literal[
    "requirements",
    "pylock",
    "uv-lock",
    "pdm-lock",
    "poetry-lock",
    "pyproject",
    "fallback",
    "error",
]

_LOCK_SOURCE_FILES: tuple[tuple[str, DependencySourceKind], ...] = (
    ("uv.lock", "uv-lock"),
    ("pdm.lock", "pdm-lock"),
    ("poetry.lock", "poetry-lock"),
)


class DependencySourceError(ValueError):
    """Dependency source was recognized but could not be converted safely."""


@dataclass(frozen=True)
class DependencySource:
    """A single dependency source selected by deterministic precedence."""

    kind: DependencySourceKind
    root: Path
    path: Path | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class GeneratedRequirements:
    """Requirements file content generated from a structured dependency source."""

    lines: tuple[str, ...]
    no_deps: bool


def discover_dependency_source(root: Path) -> DependencySource:
    """Discover the highest-precedence dependency source for a scan directory."""

    resolved_root = root.resolve()
    requirements = resolved_root / "requirements.txt"
    if requirements.exists():
        return DependencySource(kind="requirements", root=resolved_root, path=requirements)

    pylock = _pylock_source(resolved_root)
    if pylock is not None:
        return DependencySource(kind="pylock", root=resolved_root, path=pylock)

    for filename, kind in _LOCK_SOURCE_FILES:
        path = resolved_root / filename
        if path.exists():
            return DependencySource(kind=kind, root=resolved_root, path=path)

    pyproject = resolved_root / "pyproject.toml"
    if pyproject.exists():
        return _discover_pyproject(resolved_root, pyproject)

    return DependencySource(kind="fallback", root=resolved_root, path=None)


def _pylock_source(root: Path) -> Path | None:
    pylock = root / "pylock.toml"
    if pylock.exists():
        return pylock
    named = sorted(path for path in root.glob("pylock.*.toml") if path.is_file())
    return named[0] if named else None


def generated_requirements_for_source(source: DependencySource) -> GeneratedRequirements:
    """Convert a recognized structured source into deterministic requirements lines."""

    if source.kind == "error":
        raise DependencySourceError(source.error_message or "dependency source parse failed")
    if source.path is None:
        raise DependencySourceError(f"{source.kind} does not have a dependency file")
    if source.kind in {"uv-lock", "pdm-lock", "poetry-lock"}:
        return GeneratedRequirements(
            lines=_pinned_lines_from_lock(source.path, root=source.root),
            no_deps=True,
        )
    if source.kind == "pyproject":
        return GeneratedRequirements(
            lines=_dependency_lines_from_pyproject(source.path),
            no_deps=False,
        )
    raise DependencySourceError(f"{source.kind} cannot be converted to requirements")


def _discover_pyproject(root: Path, path: Path) -> DependencySource:
    try:
        payload = _load_toml(path)
    except DependencySourceError as exc:
        return DependencySource(kind="error", root=root, path=path, error_message=str(exc))

    project = payload.get("project")
    if not isinstance(project, Mapping):
        return DependencySource(kind="fallback", root=root, path=None)

    dynamic = project.get("dynamic")
    if _contains_dynamic_dependencies(dynamic):
        return DependencySource(kind="fallback", root=root, path=None)

    if "dependencies" not in project:
        return DependencySource(kind="fallback", root=root, path=None)

    dependencies = project.get("dependencies")
    if not _is_string_sequence(dependencies):
        return DependencySource(
            kind="error",
            root=root,
            path=path,
            error_message=f"{path.name}: [project].dependencies must be a list of strings",
        )
    return DependencySource(kind="pyproject", root=root, path=path)


def _dependency_lines_from_pyproject(path: Path) -> tuple[str, ...]:
    payload = _load_toml(path)
    project = payload.get("project")
    if not isinstance(project, Mapping):
        raise DependencySourceError(f"{path.name}: missing [project] table")
    dependencies = project.get("dependencies")
    if not _is_string_sequence(dependencies):
        raise DependencySourceError(
            f"{path.name}: [project].dependencies must be a list of strings"
        )
    return tuple(str(item) for item in dependencies)


def _pinned_lines_from_lock(path: Path, *, root: Path) -> tuple[str, ...]:
    payload = _load_toml(path)
    packages = payload.get("package")
    if packages is None:
        return ()
    if not isinstance(packages, Sequence) or isinstance(packages, (str, bytes)):
        raise DependencySourceError(f"{path.name}: package entries must be a list")

    self_name = _project_name(root)
    excluded_names = _excluded_lock_package_names(
        payload,
        source_name=path.name,
        project_name=self_name,
    )
    pinned: set[tuple[str, str]] = set()
    for index, package in enumerate(packages):
        if not isinstance(package, Mapping):
            raise DependencySourceError(f"{path.name}: package entry {index} must be a table")
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str) or not name:
            raise DependencySourceError(f"{path.name}: package entry {index} is missing name")
        if not isinstance(version, str) or not version:
            raise DependencySourceError(f"{path.name}: package {name} is missing version")
        if _normalize_name(name) in excluded_names:
            continue
        if _is_optional_package(package):
            continue
        if not _is_selected_dependency_group(
            package,
            source_name=path.name,
            package_name=name,
        ):
            continue
        if not _marker_allows_current_environment(
            package, source_name=path.name, package_name=name
        ):
            continue
        if self_name is not None and _normalize_name(name) == _normalize_name(self_name):
            continue
        pinned.add((name, version))
    return tuple(f"{name}=={version}" for name, version in sorted(pinned))


def _excluded_lock_package_names(
    payload: Mapping[str, Any],
    *,
    source_name: str,
    project_name: str | None,
) -> frozenset[str]:
    if source_name != "uv.lock":
        return frozenset()

    packages = payload.get("package")
    if not isinstance(packages, Sequence) or isinstance(packages, (str, bytes)):
        return frozenset()

    package_by_name = _lock_package_by_name(packages, source_name=source_name)
    default_roots: set[str] = set()
    dev_roots: set[str] = set()
    for package in packages:
        if not isinstance(package, Mapping):
            continue
        package_name = package.get("name")
        if (
            project_name is not None
            and isinstance(package_name, str)
            and _normalize_name(package_name) != _normalize_name(project_name)
        ):
            continue
        default_roots.update(
            _dependency_names_from_object(
                package.get("dependencies"),
                source_name=source_name,
                context="dependencies",
            )
        )
        dev_roots.update(
            _dependency_names_from_object(
                package.get("dev-dependencies"),
                source_name=source_name,
                context="dev-dependencies",
            )
        )
        dev_roots.update(
            _dependency_names_from_object(
                package.get("dependency-groups"),
                source_name=source_name,
                context="dependency-groups",
            )
        )

    default_closure = _dependency_closure(default_roots, package_by_name, source_name=source_name)
    dev_closure = _dependency_closure(dev_roots, package_by_name, source_name=source_name)
    return frozenset(dev_closure - default_closure)


def _lock_package_by_name(
    packages: Sequence[object],
    *,
    source_name: str,
) -> Mapping[str, Mapping[str, Any]]:
    package_by_name: dict[str, Mapping[str, Any]] = {}
    for index, package in enumerate(packages):
        if not isinstance(package, Mapping):
            raise DependencySourceError(f"{source_name}: package entry {index} must be a table")
        raw_name = package.get("name")
        if isinstance(raw_name, str) and raw_name:
            package_by_name[_normalize_name(raw_name)] = package
    return package_by_name


def _dependency_closure(
    roots: set[str],
    packages: Mapping[str, Mapping[str, Any]],
    *,
    source_name: str,
) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        package = packages.get(name)
        if package is None:
            continue
        for dependency in _dependency_names_from_object(
            package.get("dependencies"),
            source_name=source_name,
            context=f"package {name} dependencies",
        ):
            if dependency not in seen:
                stack.append(dependency)
    return seen


def _project_name(root: Path) -> str | None:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        payload = _load_toml(pyproject)
    except DependencySourceError:
        return None
    project = payload.get("project")
    if not isinstance(project, Mapping):
        return None
    name = project.get("name")
    return name if isinstance(name, str) and name else None


def _load_toml(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise DependencySourceError(f"{path.name}: malformed TOML: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise DependencySourceError(f"{path.name}: TOML root must be a table")
    return payload


def _contains_dynamic_dependencies(value: object) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return False
    return any(item == "dependencies" for item in value)


def _is_string_sequence(value: object) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and all(isinstance(item, str) for item in value)
    )


def _normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _is_optional_package(package: Mapping[str, Any]) -> bool:
    return package.get("optional") is True


def _dependency_names_from_object(
    value: object,
    *,
    source_name: str,
    context: str,
) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, Mapping):
        names: set[str] = set()
        for group_name, dependencies in value.items():
            if not isinstance(group_name, str) or not group_name:
                raise DependencySourceError(f"{source_name}: invalid {context} group")
            names.update(
                _dependency_names_from_object(
                    dependencies,
                    source_name=source_name,
                    context=f"{context}.{group_name}",
                )
            )
        return frozenset(names)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        names = set()
        for item in value:
            names.add(_dependency_name_from_item(item, source_name=source_name, context=context))
        return frozenset(names)
    raise DependencySourceError(f"{source_name}: invalid {context}")


def _dependency_name_from_item(
    item: object,
    *,
    source_name: str,
    context: str,
) -> str:
    if isinstance(item, str):
        name = _requirement_name(item)
    elif isinstance(item, Mapping):
        raw = item.get("name")
        if not isinstance(raw, str):
            raise DependencySourceError(f"{source_name}: invalid {context} dependency")
        name = raw
    else:
        raise DependencySourceError(f"{source_name}: invalid {context} dependency")
    if not name:
        raise DependencySourceError(f"{source_name}: invalid {context} dependency")
    return _normalize_name(name)


def _requirement_name(value: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", value)
    return match.group(1) if match else ""


def _is_selected_dependency_group(
    package: Mapping[str, Any],
    *,
    source_name: str,
    package_name: str,
) -> bool:
    selected = {"default", "main"}

    groups = package.get("groups")
    if groups is not None:
        if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes)):
            raise DependencySourceError(f"{source_name}: package {package_name} has invalid groups")
        normalized = {_normalize_group(group) for group in groups}
        if not all(normalized):
            raise DependencySourceError(f"{source_name}: package {package_name} has invalid groups")
        return bool(normalized & selected)

    for key in ("group", "category"):
        raw = package.get(key)
        if raw is None:
            continue
        if not isinstance(raw, str) or not raw:
            raise DependencySourceError(f"{source_name}: package {package_name} has invalid {key}")
        return _normalize_group(raw) in selected

    return True


def _normalize_group(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _marker_allows_current_environment(
    package: Mapping[str, Any],
    *,
    source_name: str,
    package_name: str,
) -> bool:
    markers = _marker_values(package)
    for marker in markers:
        try:
            if not _evaluate_marker(marker):
                return False
        except (SyntaxError, ValueError) as exc:
            raise DependencySourceError(
                f"{source_name}: package {package_name} has unsupported marker: {marker}"
            ) from exc
    return True


def _marker_values(package: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("marker", "markers"):
        raw = package.get(key)
        if isinstance(raw, str) and raw.strip():
            values.append(raw.strip())
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    values.append(item.strip())
    return tuple(values)


def _evaluate_marker(marker: str) -> bool:
    tree = ast.parse(marker, mode="eval")
    return _eval_marker_node(tree.body)


def _eval_marker_node(node: ast.AST) -> bool:
    if isinstance(node, ast.BoolOp):
        values = [_eval_marker_node(value) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
    if isinstance(node, ast.Compare):
        left = _eval_marker_value(node.left)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _eval_marker_value(comparator)
            if not _compare_marker_values(left, op, right):
                return False
            left = right
        return True
    raise ValueError(f"unsupported marker expression: {ast.dump(node)}")


def _eval_marker_value(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        env = _marker_environment()
        if node.id not in env:
            raise ValueError(f"unsupported marker variable: {node.id}")
        return env[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise ValueError(f"unsupported marker value: {ast.dump(node)}")


def _compare_marker_values(left: str, op: ast.cmpop, right: str) -> bool:
    if isinstance(op, ast.Eq):
        return _marker_values_equal(left, right)
    if isinstance(op, ast.NotEq):
        return not _marker_values_equal(left, right)
    if isinstance(op, ast.In):
        return left in right
    if isinstance(op, ast.NotIn):
        return left not in right
    if isinstance(op, ast.Lt):
        return _versionish(left) < _versionish(right)
    if isinstance(op, ast.LtE):
        return _versionish(left) <= _versionish(right)
    if isinstance(op, ast.Gt):
        return _versionish(left) > _versionish(right)
    if isinstance(op, ast.GtE):
        return _versionish(left) >= _versionish(right)
    raise ValueError(f"unsupported marker operator: {op.__class__.__name__}")


def _marker_environment() -> dict[str, str]:
    version = sys.version_info
    implementation_version = getattr(sys.implementation, "version", version)
    return {
        "os_name": os.name,
        "sys_platform": sys.platform,
        "platform_machine": platform.machine(),
        "platform_python_implementation": platform.python_implementation(),
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "platform_version": platform.version(),
        "python_version": f"{version.major}.{version.minor}",
        "python_full_version": platform.python_version(),
        "implementation_name": sys.implementation.name,
        "implementation_version": ".".join(
            str(part)
            for part in (
                implementation_version.major,
                implementation_version.minor,
                implementation_version.micro,
            )
        ),
        "extra": "",
    }


def _versionish(value: str) -> tuple[tuple[int, int | str], ...]:
    tokens: list[tuple[int, int | str]] = []
    for part in re.findall(r"\d+|[A-Za-z]+", value):
        if part.isdigit():
            tokens.append((0, int(part)))
        else:
            tokens.append((1, part.lower()))
    return tuple(tokens) or ((1, value),)


def _marker_values_equal(left: str, right: str) -> bool:
    return (
        left == right
        or _version_wildcard_matches(pattern=left, value=right)
        or _version_wildcard_matches(pattern=right, value=left)
    )


def _version_wildcard_matches(*, pattern: str, value: str) -> bool:
    if not re.fullmatch(r"\d+(?:\.\d+)*\.\*", pattern):
        return False
    prefix = pattern.removesuffix(".*")
    return value == prefix or value.startswith(f"{prefix}.")
