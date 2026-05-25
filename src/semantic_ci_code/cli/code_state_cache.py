from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from pydantic import ValidationError

from semantic_ci_code.cli.modes import ExecutionMode
from semantic_ci_code.cli.output.json_formatter import UNKNOWN_VERSION, package_version
from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.framework.extract_config import ExtractConfig

CACHE_FORMAT_VERSION = 3
CODE_STATE_SCHEMA_VERSION = "1"
DEFAULT_CACHE_MAX_BYTES = 100 * 1024 * 1024
DEFAULT_EVICTION_LOW_WATER = 0.8
STALE_TMP_SECONDS = 60 * 60
_EXTRACTOR_SOURCE_MAP: Final[dict[str, tuple[str, ...]]] = {
    "api_surface": ("api_surface/",),
    "effects": ("effects/",),
    "imports": ("imports/",),
    "complexity": ("complexity/",),
    "test_surface": ("test_surface/",),
    "module_graph": ("module_graph/",),
}
_COMMON_EXTRACTOR_DEPS: Final = ("pipeline/python_code_state.py", "domain/state_schema.py")

LogFn = Callable[[str], None]


@dataclass
class CacheStats:
    hit: int = 0
    miss: int = 0
    invalid: int = 0
    write_failed: int = 0
    disabled: bool = False


def cache_disabled(*, no_cache_flag: bool) -> bool:
    if no_cache_flag:
        return True
    return os.environ.get("SEMANTIC_CI_NO_CACHE") == "1"


def resolve_cache_root(raw_cache_dir: str | None, *, repo_root: Path, cwd: Path) -> Path:
    if raw_cache_dir is None:
        return repo_root / ".semantic-ci" / "cache"
    path = Path(raw_cache_dir)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def resolve_cache_max_bytes(raw_max_bytes: str | None) -> int:
    raw_value = (
        raw_max_bytes
        if raw_max_bytes is not None
        else os.environ.get("SEMANTIC_CI_CACHE_MAX_BYTES")
    )
    if raw_value is None:
        return DEFAULT_CACHE_MAX_BYTES
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"cache max bytes must be an integer: {raw_value}") from exc
    if value < 0:
        raise ValueError("cache max bytes must be non-negative")
    return value


def package_root_cache_path(package_root: Path) -> PurePosixPath:
    value = package_root.as_posix()
    return PurePosixPath(value or ".")


def dimensions_for_cache(dimensions: frozenset[str] | None) -> tuple[str, ...] | None:
    if dimensions is None:
        return None
    return tuple(sorted(dimensions))


def effective_exclude_key(
    extract_config: ExtractConfig | None,
    *,
    tree_root: Path,
) -> tuple[str, tuple[str, ...]]:
    if extract_config is None or not extract_config.patterns:
        return ("", ())
    try:
        config_root = extract_config.config_root.resolve().relative_to(tree_root.resolve())
        config_root_posix = PurePosixPath(config_root.as_posix()).as_posix() or "."
    except ValueError:
        config_root_posix = extract_config.config_root.resolve().as_posix()
    return (config_root_posix, tuple(sorted(extract_config.patterns)))


def current_python_xy() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def cache_package_version() -> str:
    """Return the package version component used in CodeState cache keys.

    Installed packages use package metadata directly. Source-tree execution can
    legitimately lack metadata, in which case `package_version()` returns the
    constant unknown fallback. A constant would let extractor code changes reuse
    stale cache entries, so cache keys include a deterministic source fingerprint
    only for that fallback case.
    """

    value = package_version()
    if value != UNKNOWN_VERSION:
        return value
    return f"{UNKNOWN_VERSION}.source.{_source_fingerprint()}"


def extractor_versions() -> dict[str, str]:
    """Return deterministic source fingerprints for each extractor dimension."""

    package_root = Path(__file__).resolve().parents[1]
    return {
        dimension: _fingerprint_paths(
            package_root,
            _extractor_source_paths(package_root, source_paths),
        )
        for dimension, source_paths in sorted(_EXTRACTOR_SOURCE_MAP.items())
    }


def cache_key(
    *,
    tree_object_id: str,
    package_root_relpath_posix: PurePosixPath,
    mode: ExecutionMode,
    dimensions_sorted_tuple: tuple[str, ...] | None,
    python_xy: str,
    package_version_value: str,
    extractor_versions_value: dict[str, str] | None = None,
    effective_exclude_key_value: tuple[str, tuple[str, ...]] = ("", ()),
    code_state_schema_version: str = CODE_STATE_SCHEMA_VERSION,
    cache_format_version: int = CACHE_FORMAT_VERSION,
) -> str:
    extractor_versions_payload = _extractor_versions_for_key(
        extractor_versions_value if extractor_versions_value is not None else extractor_versions(),
        dimensions_sorted_tuple,
    )
    payload = {
        "cache_format_version": cache_format_version,
        "code_state_schema_version": code_state_schema_version,
        "dimensions": (
            list(dimensions_sorted_tuple) if dimensions_sorted_tuple is not None else None
        ),
        "effective_exclude": {
            "config_root": effective_exclude_key_value[0],
            "patterns": list(effective_exclude_key_value[1]),
        },
        "extractor_versions": extractor_versions_payload,
        "mode": mode.value,
        "package_root": package_root_relpath_posix.as_posix(),
        "package_version": package_version_value,
        "python_xy": python_xy,
        "tree_object_id": tree_object_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def key_meta(
    *,
    tree_object_id: str,
    package_root_relpath_posix: PurePosixPath,
    mode: ExecutionMode,
    dimensions_sorted_tuple: tuple[str, ...] | None,
    effective_exclude_key_value: tuple[str, tuple[str, ...]] = ("", ()),
    python_xy: str | None = None,
    package_version_value: str | None = None,
    extractor_versions_value: dict[str, str] | None = None,
) -> dict[str, Any]:
    extractor_versions_payload = _extractor_versions_for_key(
        extractor_versions_value if extractor_versions_value is not None else extractor_versions(),
        dimensions_sorted_tuple,
    )
    return {
        "tree_object_id": tree_object_id,
        "package_root": package_root_relpath_posix.as_posix(),
        "mode": mode.value,
        "dimensions": (
            list(dimensions_sorted_tuple) if dimensions_sorted_tuple is not None else None
        ),
        "effective_exclude": {
            "config_root": effective_exclude_key_value[0],
            "patterns": list(effective_exclude_key_value[1]),
        },
        "python_xy": python_xy or current_python_xy(),
        "package_version": package_version_value or cache_package_version(),
        "extractor_versions": extractor_versions_payload,
    }


def key_for_state(
    *,
    tree_object_id: str,
    package_root_relpath_posix: PurePosixPath,
    mode: ExecutionMode,
    dimensions_sorted_tuple: tuple[str, ...] | None,
    effective_exclude_key_value: tuple[str, tuple[str, ...]] = ("", ()),
    python_xy: str | None = None,
    package_version_value: str | None = None,
    extractor_versions_value: dict[str, str] | None = None,
    code_state_schema_version: str = CODE_STATE_SCHEMA_VERSION,
    cache_format_version: int = CACHE_FORMAT_VERSION,
) -> str:
    return cache_key(
        tree_object_id=tree_object_id,
        package_root_relpath_posix=package_root_relpath_posix,
        mode=mode,
        dimensions_sorted_tuple=dimensions_sorted_tuple,
        python_xy=python_xy or current_python_xy(),
        package_version_value=package_version_value or cache_package_version(),
        extractor_versions_value=extractor_versions_value,
        effective_exclude_key_value=effective_exclude_key_value,
        code_state_schema_version=code_state_schema_version,
        cache_format_version=cache_format_version,
    )


def read_cached_code_state(
    cache_root: Path,
    key: str,
    *,
    stats: CacheStats | None = None,
    log: LogFn | None = None,
) -> CodeState | None:
    path = _cache_path(cache_root, key)
    if not path.exists():
        if stats is not None:
            stats.miss += 1
        _log(log, f"cache miss: code_state {key}")
        return None

    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            raise ValueError("empty cache file")
        payload = json.loads(raw)
        if payload["cache_format_version"] != CACHE_FORMAT_VERSION:
            raise ValueError("cache_format_version mismatch")
        if payload["code_state_schema_version"] != CODE_STATE_SCHEMA_VERSION:
            raise ValueError("code_state_schema_version mismatch")
        state = CodeState.model_validate(payload["code_state"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, ValidationError) as exc:
        if stats is not None:
            stats.invalid += 1
            stats.miss += 1
        _log(log, f"cache invalid: {_one_line(str(exc))}; recomputing")
        return None

    if stats is not None:
        stats.hit += 1
    _log(log, f"cache hit: code_state {key}")
    return state


def write_cached_code_state(
    cache_root: Path,
    key: str,
    *,
    state: CodeState,
    meta: dict[str, Any],
    stats: CacheStats | None = None,
    max_bytes: int | None = None,
    log: LogFn | None = None,
) -> None:
    path = _cache_path(cache_root, key)
    tmp_path = path.with_name(f"{path.name}.tmp")
    payload = {
        "cache_format_version": CACHE_FORMAT_VERSION,
        "code_state_schema_version": CODE_STATE_SCHEMA_VERSION,
        "key_meta": meta,
        "code_state": state.model_dump(mode="json"),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
        if max_bytes is not None:
            evict_to_budget(cache_root, max_bytes, log=log)
    except OSError as exc:
        if stats is not None:
            stats.write_failed += 1
        _log(log, f"cache write failed: {_one_line(str(exc))}")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def evict_to_budget(
    cache_root: Path,
    budget_bytes: int,
    *,
    low_water: float = DEFAULT_EVICTION_LOW_WATER,
    log: LogFn | None = None,
) -> tuple[Path, ...]:
    if budget_bytes <= 0:
        return ()

    records = sorted(_cache_file_records(cache_root), key=lambda record: record[1])
    total = sum(size for _, _, size in records)
    if total <= budget_bytes:
        return ()

    target = int(budget_bytes * low_water)
    removed: list[Path] = []
    for path, mtime, size in records:
        if total <= target:
            break
        try:
            path.unlink()
        except FileNotFoundError:
            total -= size
            continue
        except OSError as exc:
            _log(log, f"cache eviction failed: {_one_line(str(exc))}")
            continue
        total -= size
        removed.append(path)
        _log(log, f"cache evicted: {path} (mtime={mtime})")
    return tuple(removed)


def _cache_path(cache_root: Path, key: str) -> Path:
    return cache_root / "code_state" / f"{key}.json"


def _extractor_versions_for_key(
    versions: dict[str, str],
    dimensions_sorted_tuple: tuple[str, ...] | None,
) -> dict[str, str]:
    if dimensions_sorted_tuple is None:
        return dict(sorted(versions.items()))
    selected = set(dimensions_sorted_tuple)
    return {dimension: versions[dimension] for dimension in sorted(selected & versions.keys())}


def _log(log: LogFn | None, message: str) -> None:
    if log is not None:
        log(message)


def _one_line(message: str) -> str:
    return message.splitlines()[0] if message else ""


def _cache_file_records(cache_root: Path) -> tuple[tuple[Path, float, int], ...]:
    if not cache_root.exists():
        return ()
    now = time.time()
    records: list[tuple[Path, float, int]] = []
    for path in cache_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".json":
            record = _file_record(path)
        elif path.suffix == ".tmp":
            record = _file_record(path)
            if record is not None and now - record[1] < STALE_TMP_SECONDS:
                record = None
        else:
            record = None
        if record is not None:
            records.append(record)
    return tuple(records)


def _file_record(path: Path) -> tuple[Path, float, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (path, stat.st_mtime, stat.st_size)


def _source_fingerprint() -> str:
    package_root = Path(__file__).resolve().parents[1]
    return _fingerprint_paths(
        package_root,
        tuple(
            sorted(
                package_root.rglob("*.py"),
                key=lambda candidate: candidate.relative_to(package_root).as_posix(),
            )
        ),
    )


def _extractor_source_paths(
    package_root: Path,
    source_paths: tuple[str, ...],
) -> tuple[Path, ...]:
    paths: set[Path] = set()
    for raw_path in source_paths:
        path = package_root / raw_path
        if path.is_dir():
            paths.update(path.rglob("*.py"))
        else:
            paths.add(path)
    for raw_path in _COMMON_EXTRACTOR_DEPS:
        paths.add(package_root / raw_path)
    return tuple(
        sorted(paths, key=lambda candidate: candidate.relative_to(package_root).as_posix())
    )


def _fingerprint_paths(package_root: Path, paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(package_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError as exc:
            digest.update(f"<unreadable:{type(exc).__name__}>".encode())
        digest.update(b"\0")
    return digest.hexdigest()[:16]
