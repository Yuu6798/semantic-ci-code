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

    pylock = resolved_root / "pylock.toml"
    if pylock.exists():
        return DependencySource(kind="pylock", root=resolved_root, path=pylock)

    for filename, kind in _LOCK_SOURCE_FILES:
        path = resolved_root / filename
        if path.exists():
            return DependencySource(kind=kind, root=resolved_root, path=path)

    pyproject = resolved_root / "pyproject.toml"
    if pyproject.exists():
        return _discover_pyproject(resolved_root, pyproject)

    return DependencySource(kind="fallback", root=resolved_root, path=None)


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
        if _is_optional_package(package):
            continue
        if not _marker_allows_current_environment(
            package, source_name=path.name, package_name=name
        ):
            continue
        if self_name is not None and _normalize_name(name) == _normalize_name(self_name):
            continue
        pinned.add((name, version))
    return tuple(f"{name}=={version}" for name, version in sorted(pinned))


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
        return left == right
    if isinstance(op, ast.NotEq):
        return left != right
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


def _versionish(value: str) -> tuple[int | str, ...]:
    parts: list[int | str] = []
    for part in re.split(r"[.\-+_]", value):
        if not part:
            continue
        parts.append(int(part) if part.isdigit() else part)
    return tuple(parts) or (value,)
