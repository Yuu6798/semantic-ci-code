"""Extractor-side operational configuration.

This module intentionally lives in ``framework`` instead of ``cli`` or
``pipeline`` so compile-time and runtime surfaces can share the same config
contract without making extraction policy part of target intent.
"""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


@dataclass(frozen=True)
class ExtractConfig:
    patterns: tuple[str, ...]
    config_root: Path
    source_path: Path | None


@dataclass(frozen=True)
class ExcludedPath:
    path: Path
    relative_path: PurePosixPath
    pattern: str


class ExtractConfigError(Exception):
    """Raised when ``[tool.semantic_ci_code.extract]`` cannot be loaded."""


def load_extract_config(package_root: Path) -> ExtractConfig:
    root = package_root.resolve()
    search_dir = root if root.is_dir() else root.parent
    pyproject = _find_nearest_pyproject(search_dir)
    if pyproject is None:
        return ExtractConfig(patterns=(), config_root=search_dir, source_path=None)

    data = _load_toml(pyproject)
    extract = _extract_section(data, pyproject)
    if extract is None or "exclude" not in extract:
        return ExtractConfig(patterns=(), config_root=pyproject.parent, source_path=pyproject)

    raw_patterns = extract["exclude"]
    patterns = _validate_patterns(raw_patterns, source_path=pyproject)
    return ExtractConfig(
        patterns=patterns,
        config_root=pyproject.parent.resolve(),
        source_path=pyproject,
    )


def matches_exclude(candidate: Path, config: ExtractConfig) -> str | None:
    if not config.patterns:
        return None
    relative = _relative_candidate(candidate, config)
    if relative is None:
        return None
    for pattern in config.patterns:
        if _matches_pattern(relative, pattern):
            return pattern
    return None


def filter_excluded_paths(
    paths: tuple[Path, ...],
    config: ExtractConfig | None,
) -> tuple[tuple[Path, ...], tuple[ExcludedPath, ...]]:
    if config is None or not config.patterns:
        return paths, ()

    kept: list[Path] = []
    excluded: list[ExcludedPath] = []
    for path in paths:
        relative = _relative_candidate(path, config)
        if relative is None:
            kept.append(path)
            continue
        pattern = matches_exclude(path, config)
        if pattern is None:
            kept.append(path)
        else:
            excluded.append(ExcludedPath(path=path, relative_path=relative, pattern=pattern))
    return tuple(kept), tuple(excluded)


def _find_nearest_pyproject(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        candidate = current / "pyproject.toml"
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ExtractConfigError(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise ExtractConfigError(f"{path}: cannot read pyproject.toml: {exc}") from exc
    if not isinstance(data, dict):
        raise ExtractConfigError(f"{path}: pyproject.toml must contain a TOML table")
    return data


def _extract_section(data: dict[str, Any], source_path: Path) -> dict[str, Any] | None:
    tool = data.get("tool")
    if tool is None:
        return None
    if not isinstance(tool, dict):
        raise ExtractConfigError(f"{source_path}: [tool] must be a table")

    semantic = tool.get("semantic_ci_code")
    if semantic is None:
        return None
    if not isinstance(semantic, dict):
        raise ExtractConfigError(f"{source_path}: [tool.semantic_ci_code] must be a table")

    extract = semantic.get("extract")
    if extract is None:
        return None
    if not isinstance(extract, dict):
        raise ExtractConfigError(f"{source_path}: [tool.semantic_ci_code.extract] must be a table")

    unknown = sorted(set(extract) - {"exclude"})
    if unknown:
        key_list = ", ".join(unknown)
        raise ExtractConfigError(
            f"{source_path}: unknown [tool.semantic_ci_code.extract] key(s): {key_list}"
        )
    return extract


def _validate_patterns(raw_patterns: Any, *, source_path: Path) -> tuple[str, ...]:
    if not isinstance(raw_patterns, list):
        raise ExtractConfigError(f"{source_path}: extract.exclude must be a list of strings")

    patterns: list[str] = []
    for index, raw_pattern in enumerate(raw_patterns):
        prefix = f"{source_path}: invalid extract.exclude[{index}]"
        if not isinstance(raw_pattern, str):
            raise ExtractConfigError(f"{prefix}: expected string, got {type(raw_pattern).__name__}")
        pattern = raw_pattern.strip()
        if pattern == "":
            raise ExtractConfigError(f"{prefix}: empty pattern is not allowed")
        if "\\" in pattern:
            raise ExtractConfigError(f"{prefix}: use POSIX '/' separators, not backslashes")
        if pattern.startswith("/") or PureWindowsPath(pattern).is_absolute():
            raise ExtractConfigError(f"{prefix}: absolute paths are not allowed")
        if ".." in PurePosixPath(pattern).parts:
            raise ExtractConfigError(f"{prefix}: parent traversal '..' is not allowed")
        patterns.append(pattern)
    return tuple(patterns)


def _relative_candidate(candidate: Path, config: ExtractConfig) -> PurePosixPath | None:
    try:
        relative = candidate.resolve().relative_to(config.config_root.resolve())
    except ValueError:
        return None
    return PurePosixPath(relative.as_posix())


def _matches_pattern(relative: PurePosixPath, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return _matches_literal(relative, pattern[:-3])
    if not _has_glob(pattern):
        return _matches_literal(relative, pattern)
    if pattern.startswith("**/"):
        basename_pattern = pattern[3:]
        if basename_pattern and "/" not in basename_pattern:
            return fnmatch.fnmatchcase(relative.name, basename_pattern)
    return _matches_path_glob(relative, pattern)


def _matches_literal(relative: PurePosixPath, pattern: str) -> bool:
    literal = PurePosixPath(pattern)
    return relative == literal or literal in relative.parents


def _has_glob(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def _matches_path_glob(relative: PurePosixPath, pattern: str) -> bool:
    pattern_parts = PurePosixPath(pattern).parts
    if len(pattern_parts) != len(relative.parts):
        return False
    return all(
        fnmatch.fnmatchcase(path_part, pattern_part)
        for path_part, pattern_part in zip(relative.parts, pattern_parts, strict=True)
    )
