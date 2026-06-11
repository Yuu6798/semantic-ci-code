"""Dependency source discovery for pip-audit SSP scans."""

from __future__ import annotations

import re
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
