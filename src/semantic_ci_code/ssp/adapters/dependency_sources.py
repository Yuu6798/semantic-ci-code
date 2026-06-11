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
_LOCAL_SOURCE_KEYS = frozenset(
    {
        "directory",
        "editable",
        "file",
        "git",
        "path",
        "url",
        "virtual",
        "workspace",
    }
)
_LOCAL_SOURCE_TYPES = frozenset({"directory", "file", "git", "path", "url"})


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


@dataclass(frozen=True)
class _DependencyEdge:
    name: str
    extras: frozenset[str] = frozenset()


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
        if self_name is not None and _normalize_name(name) == _normalize_name(self_name):
            continue
        if _is_local_lock_package(package):
            continue
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

    packages_by_name = _lock_packages_by_name(packages, source_name=source_name)
    default_roots: set[_DependencyEdge] = set()
    non_default_roots: set[_DependencyEdge] = set()
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
            _dependency_edges_from_object(
                package.get("dependencies"),
                source_name=source_name,
                context="dependencies",
            )
        )
        non_default_roots.update(
            _dependency_edges_from_object(
                package.get("dev-dependencies"),
                source_name=source_name,
                context="dev-dependencies",
            )
        )
        non_default_roots.update(
            _dependency_edges_from_object(
                package.get("dependency-groups"),
                source_name=source_name,
                context="dependency-groups",
            )
        )
        non_default_roots.update(
            _dependency_edges_from_object(
                package.get("optional-dependencies"),
                source_name=source_name,
                context="optional-dependencies",
            )
        )

    default_closure = _dependency_closure(default_roots, packages_by_name, source_name=source_name)
    if project_name is not None:
        return frozenset(
            packages_by_name.keys() - default_closure - {_normalize_name(project_name)}
        )
    non_default_closure = _dependency_closure(
        non_default_roots,
        packages_by_name,
        source_name=source_name,
    )
    return frozenset(non_default_closure - default_closure)


def _lock_packages_by_name(
    packages: Sequence[object],
    *,
    source_name: str,
) -> Mapping[str, tuple[Mapping[str, Any], ...]]:
    packages_by_name: dict[str, list[Mapping[str, Any]]] = {}
    for index, package in enumerate(packages):
        if not isinstance(package, Mapping):
            raise DependencySourceError(f"{source_name}: package entry {index} must be a table")
        raw_name = package.get("name")
        if isinstance(raw_name, str) and raw_name:
            packages_by_name.setdefault(_normalize_name(raw_name), []).append(package)
    return {name: tuple(variants) for name, variants in packages_by_name.items()}


def _dependency_closure(
    roots: set[_DependencyEdge],
    packages: Mapping[str, tuple[Mapping[str, Any], ...]],
    *,
    source_name: str,
) -> set[str]:
    included: set[str] = set()
    processed: set[_DependencyEdge] = set()
    stack = list(roots)
    while stack:
        edge = stack.pop()
        name = edge.name
        if edge in processed:
            continue
        processed.add(edge)
        active_variants = _active_lock_package_variants(
            packages,
            name,
            source_name=source_name,
        )
        if not active_variants:
            continue
        included.add(name)
        for package in active_variants:
            for dependency in _dependency_edges_from_object(
                package.get("dependencies"),
                source_name=source_name,
                context=f"package {name} dependencies",
            ):
                if dependency not in processed:
                    stack.append(dependency)
            for dependency in _optional_dependency_edges(
                package,
                extras=edge.extras,
                source_name=source_name,
                package_name=name,
            ):
                if dependency not in processed:
                    stack.append(dependency)
    return included


def _active_lock_package_variants(
    packages: Mapping[str, tuple[Mapping[str, Any], ...]],
    name: str,
    *,
    source_name: str,
) -> tuple[Mapping[str, Any], ...]:
    active: list[Mapping[str, Any]] = []
    for package in packages.get(name, ()):
        if _marker_allows_current_environment(
            package,
            source_name=source_name,
            package_name=name,
        ):
            active.append(package)
    return tuple(active)


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


def _is_local_lock_package(package: Mapping[str, Any]) -> bool:
    source = package.get("source")
    if isinstance(source, Mapping):
        if any(key in source for key in _LOCAL_SOURCE_KEYS):
            return True
        source_type = source.get("type")
        return isinstance(source_type, str) and source_type.strip().lower() in _LOCAL_SOURCE_TYPES
    return any(package.get(key) for key in ("editable", "develop"))


def _dependency_edges_from_object(
    value: object,
    *,
    source_name: str,
    context: str,
) -> frozenset[_DependencyEdge]:
    if value is None:
        return frozenset()
    if isinstance(value, Mapping):
        edges: set[_DependencyEdge] = set()
        for group_name, dependencies in value.items():
            if not isinstance(group_name, str) or not group_name:
                raise DependencySourceError(f"{source_name}: invalid {context} group")
            edges.update(
                _dependency_edges_from_object(
                    dependencies,
                    source_name=source_name,
                    context=f"{context}.{group_name}",
                )
            )
        return frozenset(edges)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        edges = set()
        for item in value:
            edge = _dependency_edge_from_item(
                item,
                source_name=source_name,
                context=context,
            )
            if edge is not None:
                edges.add(edge)
        return frozenset(edges)
    raise DependencySourceError(f"{source_name}: invalid {context}")


def _dependency_edge_from_item(
    item: object,
    *,
    source_name: str,
    context: str,
) -> _DependencyEdge | None:
    if isinstance(item, str):
        name = _requirement_name(item)
        extras = frozenset()
    elif isinstance(item, Mapping):
        raw = item.get("name")
        if not isinstance(raw, str):
            raise DependencySourceError(f"{source_name}: invalid {context} dependency")
        if not _marker_allows_current_environment(
            item,
            source_name=source_name,
            package_name=raw,
        ):
            return None
        name = raw
        extras = _requested_extras(item, source_name=source_name, context=context)
    else:
        raise DependencySourceError(f"{source_name}: invalid {context} dependency")
    if not name:
        raise DependencySourceError(f"{source_name}: invalid {context} dependency")
    return _DependencyEdge(name=_normalize_name(name), extras=extras)


def _requested_extras(
    item: Mapping[str, Any],
    *,
    source_name: str,
    context: str,
) -> frozenset[str]:
    extras: set[str] = set()
    for key in ("extra", "extras"):
        raw = item.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            if not raw:
                raise DependencySourceError(f"{source_name}: invalid {context} extra")
            extras.add(_normalize_name(raw))
            continue
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            for value in raw:
                if not isinstance(value, str) or not value:
                    raise DependencySourceError(f"{source_name}: invalid {context} extra")
                extras.add(_normalize_name(value))
            continue
        raise DependencySourceError(f"{source_name}: invalid {context} extra")
    return frozenset(extras)


def _optional_dependency_edges(
    package: Mapping[str, Any],
    *,
    extras: frozenset[str],
    source_name: str,
    package_name: str,
) -> frozenset[_DependencyEdge]:
    if not extras:
        return frozenset()
    optional = package.get("optional-dependencies")
    if optional is None:
        return frozenset()
    if not isinstance(optional, Mapping):
        raise DependencySourceError(
            f"{source_name}: package {package_name} has invalid optional-dependencies"
        )

    edges: set[_DependencyEdge] = set()
    optional_by_extra: dict[str, object] = {}
    for raw_extra, dependencies in optional.items():
        if not isinstance(raw_extra, str) or not raw_extra:
            raise DependencySourceError(
                f"{source_name}: package {package_name} has invalid optional-dependencies"
            )
        optional_by_extra[_normalize_name(raw_extra)] = dependencies
    for extra in extras:
        dependencies = optional_by_extra.get(extra)
        if dependencies is None:
            continue
        edges.update(
            _dependency_edges_from_object(
                dependencies,
                source_name=source_name,
                context=f"package {package_name} optional-dependencies.{extra}",
            )
        )
    return frozenset(edges)


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
    resolution_markers = _marker_values_for_keys(package, ("resolution-markers",))
    if resolution_markers:
        for marker in resolution_markers:
            try:
                if _evaluate_marker(marker):
                    return True
            except (SyntaxError, ValueError) as exc:
                raise DependencySourceError(
                    f"{source_name}: package {package_name} has unsupported marker: {marker}"
                ) from exc
        return False
    return True


def _marker_values(package: Mapping[str, Any]) -> tuple[str, ...]:
    return _marker_values_for_keys(package, ("marker", "markers"))


def _marker_values_for_keys(
    package: Mapping[str, Any],
    keys: tuple[str, ...],
) -> tuple[str, ...]:
    values: list[str] = []
    for key in keys:
        raw = package.get(key)
        if isinstance(raw, str) and raw.strip():
            values.append(raw.strip())
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    values.append(item.strip())
    return tuple(values)


def _evaluate_marker(marker: str) -> bool:
    marker = _normalize_pep508_marker_syntax(marker)
    tree = ast.parse(marker, mode="eval")
    return _eval_marker_node(tree.body)


def _normalize_pep508_marker_syntax(marker: str) -> str:
    marker = re.sub(r"\s+===\s+", " == ", marker)
    return re.sub(
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*~=\s*(?P<quote>['\"])(?P<version>[^'\"]+)(?P=quote)",
        _compatible_release_replacement,
        marker,
    )


def _compatible_release_replacement(match: re.Match[str]) -> str:
    name = match.group("name")
    quote = match.group("quote")
    version = match.group("version")
    wildcard = _compatible_release_wildcard(version)
    return f"({name} >= {quote}{version}{quote} and {name} == {quote}{wildcard}{quote})"


def _compatible_release_wildcard(version: str) -> str:
    parts = version.split(".")
    if len(parts) <= 2:
        return f"{parts[0]}.*"
    return f"{'.'.join(parts[:-1])}.*"


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
        return _compare_marker_versions(left, right) < 0
    if isinstance(op, ast.LtE):
        return _compare_marker_versions(left, right) <= 0
    if isinstance(op, ast.Gt):
        return _compare_marker_versions(left, right) > 0
    if isinstance(op, ast.GtE):
        return _compare_marker_versions(left, right) >= 0
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


def _compare_marker_versions(left: str, right: str) -> int:
    left_version = _pep440ish_version(left)
    right_version = _pep440ish_version(right)
    if left_version is None or right_version is None:
        return (left > right) - (left < right)

    left_release, left_phase = left_version
    right_release, right_phase = right_version
    width = max(len(left_release), len(right_release))
    padded_left = left_release + (0,) * (width - len(left_release))
    padded_right = right_release + (0,) * (width - len(right_release))
    if padded_left != padded_right:
        return (padded_left > padded_right) - (padded_left < padded_right)
    return (left_phase > right_phase) - (left_phase < right_phase)


def _pep440ish_version(value: str) -> tuple[tuple[int, ...], tuple[int, int, int]] | None:
    match = re.match(
        r"^\s*v?(?P<release>\d+(?:\.\d+)*)"
        r"(?:(?P<pre>a|alpha|b|beta|rc|c|pre|preview)(?P<pre_n>\d*))?"
        r"(?:(?:\.?post)(?P<post_n>\d+))?"
        r"(?:(?:\.?dev)(?P<dev_n>\d+))?",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None

    release = tuple(int(part) for part in match.group("release").split("."))
    if match.group("dev_n") is not None and match.group("pre") is None:
        return release, (-1, 0, int(match.group("dev_n") or 0))
    if match.group("pre") is not None:
        pre = match.group("pre").lower()
        pre_rank = {
            "a": 0,
            "alpha": 0,
            "b": 1,
            "beta": 1,
            "rc": 2,
            "c": 2,
            "pre": 2,
            "preview": 2,
        }[pre]
        return release, (0, pre_rank, int(match.group("pre_n") or 0))
    if match.group("post_n") is not None:
        return release, (2, 0, int(match.group("post_n") or 0))
    return release, (1, 0, 0)


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
