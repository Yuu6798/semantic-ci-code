"""Python ``CodeState`` assembly from the P1 extractor set.

This module is the first Brief 3 pipeline slice: it assembles observed or
baseline RPE material by calling the six Python P1 extractors and storing
their outputs in the matching ``CodeState`` fields. It intentionally does
not compute deltas, evaluate constraints, repair specs, read intent YAML,
run dynamic coverage, or expose CLI wiring.

Failure policy is fail-fast unless a per-dimension timeout is explicitly
provided. Any extractor exception is wrapped in ``ExtractorError`` with the
extractor name and the best-known file path, then re-raised with the original
exception as ``__cause__``. A timed-out dimension falls back to the CodeState
schema default and is reported through ``CodeStateExtraction`` so the evaluator
can route affected constraints as extraction-cause UNKNOWN.

The paths variant is intentionally asymmetric: ``api_surface``,
``effects``, ``imports``, ``complexity``, and ``test_surface`` are limited
to the supplied paths, while ``module_graph`` is always extracted from the
whole ``package_root``. The module graph represents repository structure,
so cutting it to a file subset would create a misleading ``CodeState``.
"""

from __future__ import annotations

import math
import queue
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from semantic_ci_code.api_surface import extract_python_api_surface_from_paths
from semantic_ci_code.api_surface.python_api_extractor import _module_fqn_from_path
from semantic_ci_code.complexity import extract_python_complexity_from_paths
from semantic_ci_code.domain.state_schema import (
    APISurfaceEntry,
    CodeState,
    ComplexityEntry,
    EffectEntry,
    ImportEntry,
    ModuleGraphEntry,
    TestSurfaceEntry,
)
from semantic_ci_code.effects import extract_python_effects
from semantic_ci_code.framework.extract_config import (
    ExcludedPath,
    ExtractConfig,
    filter_excluded_paths,
)
from semantic_ci_code.imports import extract_python_imports_from_paths
from semantic_ci_code.module_graph import extract_python_module_graph
from semantic_ci_code.test_surface import extract_python_test_surface_from_paths

T = TypeVar("T")
ExcludeReporter = Callable[[tuple[ExcludedPath, ...]], None]

DIMENSION_API_SURFACE = "api_surface"
DIMENSION_EFFECTS = "effects"
DIMENSION_IMPORTS = "imports"
DIMENSION_COMPLEXITY = "complexity"
DIMENSION_TEST_SURFACE = "test_surface"
DIMENSION_MODULE_GRAPH = "module_graph"

SMOKE_DIMENSIONS = frozenset(
    {
        DIMENSION_API_SURFACE,
        DIMENSION_EFFECTS,
        DIMENSION_IMPORTS,
    }
)


class ExtractorError(Exception):
    """Fail-fast wrapper for extractor failures."""

    extractor_name: str
    path: Path | None

    def __init__(self, extractor_name: str, path: Path | None) -> None:
        self.extractor_name = extractor_name
        self.path = path
        super().__init__(extractor_name, path)

    def __str__(self) -> str:
        location = str(self.path) if self.path is not None else "<package_root>"
        cause = self.__cause__
        if cause is None:
            return f"{self.extractor_name} extractor failed at {location}"
        detail = str(cause).splitlines()[0] if str(cause) else cause.__class__.__name__
        return (
            f"{self.extractor_name} extractor failed at {location}: "
            f"{cause.__class__.__name__}: {detail}"
        )


@dataclass(frozen=True)
class CodeStateExtraction:
    """CodeState plus extraction diagnostics that do not change the schema."""

    state: CodeState
    timed_out_dimensions: frozenset[str]


def extract_python_code_state(
    package_root: Path,
    *,
    dimensions: frozenset[str] | None = None,
    extract_config: ExtractConfig | None = None,
    exclude_reporter: ExcludeReporter | None = None,
    timeout_seconds: float | None = None,
) -> CodeState:
    """Assemble a whole-package Python ``CodeState`` from ``package_root``.

    By default all six extracted fields are populated from the package root.
    Passing ``dimensions`` limits extraction to that subset and leaves omitted
    dimensions at schema defaults; this is used by CLI smoke mode. P1-unextracted
    fields such as ``type_relations``, ``control_flow``, ``data_flow``, and
    ``coverage`` are always left at the schema defaults.
    """
    return extract_python_code_state_result(
        package_root,
        dimensions=dimensions,
        extract_config=extract_config,
        exclude_reporter=exclude_reporter,
        timeout_seconds=timeout_seconds,
    ).state


def extract_python_code_state_result(
    package_root: Path,
    *,
    dimensions: frozenset[str] | None = None,
    extract_config: ExtractConfig | None = None,
    exclude_reporter: ExcludeReporter | None = None,
    timeout_seconds: float | None = None,
) -> CodeStateExtraction:
    """Assemble a CodeState and report dimensions that timed out."""

    _validate_timeout(timeout_seconds)
    root = _resolve_package_root(package_root)
    paths = _python_paths_from_inputs((root,), package_root=root)
    paths = _filter_excluded(
        paths,
        extract_config=extract_config,
        exclude_reporter=exclude_reporter,
    )
    return _assemble_code_state(
        paths=paths,
        package_root=root,
        dimensions=dimensions,
        extract_config=extract_config,
        timeout_seconds=timeout_seconds,
    )


def extract_python_code_state_from_paths(
    paths: Iterable[Path],
    *,
    package_root: Path,
    dimensions: frozenset[str] | None = None,
    extract_config: ExtractConfig | None = None,
    exclude_reporter: ExcludeReporter | None = None,
    timeout_seconds: float | None = None,
) -> CodeState:
    """Assemble a Python ``CodeState`` with per-file fields limited to ``paths``.

    ``paths`` is consumed exactly once, then expanded deterministically. Empty
    iterables are valid and yield empty per-file fields. ``module_graph`` is
    extracted from the whole ``package_root`` when selected because it is a
    structural repository invariant, not a per-file signal. Passing
    ``dimensions`` limits extraction to that subset and leaves omitted
    dimensions at schema defaults.
    """
    return extract_python_code_state_from_paths_result(
        paths,
        package_root=package_root,
        dimensions=dimensions,
        extract_config=extract_config,
        exclude_reporter=exclude_reporter,
        timeout_seconds=timeout_seconds,
    ).state


def extract_python_code_state_from_paths_result(
    paths: Iterable[Path],
    *,
    package_root: Path,
    dimensions: frozenset[str] | None = None,
    extract_config: ExtractConfig | None = None,
    exclude_reporter: ExcludeReporter | None = None,
    timeout_seconds: float | None = None,
) -> CodeStateExtraction:
    """Assemble a CodeState from selected paths and report timed-out dimensions."""

    _validate_timeout(timeout_seconds)
    root = _resolve_package_root(package_root)
    selected_paths = tuple(paths)
    expanded_paths = _python_paths_from_inputs(selected_paths, package_root=root)
    expanded_paths = _filter_excluded(
        expanded_paths,
        extract_config=extract_config,
        exclude_reporter=exclude_reporter,
    )
    return _assemble_code_state(
        paths=expanded_paths,
        package_root=root,
        dimensions=dimensions,
        extract_config=extract_config,
        timeout_seconds=timeout_seconds,
    )


def _assemble_code_state(
    *,
    paths: tuple[Path, ...],
    package_root: Path,
    dimensions: frozenset[str] | None,
    extract_config: ExtractConfig | None,
    timeout_seconds: float | None,
) -> CodeStateExtraction:
    timed_out: set[str] = set()

    def extract_dimension(dimension: str, action: Callable[[], T]) -> T | tuple[object, ...]:
        if not _should_extract(dimension, dimensions):
            return ()
        value, timed_out_dimension = _extract_with_timeout(
            action,
            timeout_seconds=timeout_seconds,
            dimension=dimension,
        )
        if timed_out_dimension is not None:
            timed_out.add(timed_out_dimension)
            return ()
        return value

    state = CodeState(
        api_surface=extract_dimension(
            DIMENSION_API_SURFACE,
            lambda: _extract_api_surface(paths, package_root=package_root),
        ),
        effects=extract_dimension(
            DIMENSION_EFFECTS,
            lambda: _extract_effects(paths, package_root=package_root),
        ),
        imports=extract_dimension(
            DIMENSION_IMPORTS,
            lambda: _extract_imports(paths, package_root=package_root),
        ),
        complexity=extract_dimension(
            DIMENSION_COMPLEXITY,
            lambda: _extract_complexity(paths, package_root=package_root),
        ),
        test_surface=extract_dimension(
            DIMENSION_TEST_SURFACE,
            lambda: _extract_test_surface(paths, package_root=package_root),
        ),
        module_graph=extract_dimension(
            DIMENSION_MODULE_GRAPH,
            lambda: _extract_module_graph(package_root, extract_config=extract_config),
        ),
    )
    return CodeStateExtraction(state=state, timed_out_dimensions=frozenset(timed_out))


def _extract_with_timeout(
    action: Callable[[], T],
    *,
    timeout_seconds: float | None,
    dimension: str,
) -> tuple[T, None] | tuple[None, str]:
    if timeout_seconds is None:
        return action(), None

    result_queue: queue.Queue[tuple[bool, T | BaseException]] = queue.Queue(maxsize=1)

    def run_action() -> None:
        try:
            result_queue.put((True, action()))
        except BaseException as exc:  # noqa: BLE001 - re-raised on caller thread.
            result_queue.put((False, exc))

    worker = threading.Thread(target=run_action, daemon=True)
    worker.start()
    worker.join(timeout=timeout_seconds)
    if worker.is_alive():
        return None, dimension

    ok, payload = result_queue.get_nowait()
    if ok:
        return payload, None
    raise payload


def _validate_timeout(timeout_seconds: float | None) -> None:
    if timeout_seconds is not None and (not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise ValueError("extractor timeout must be a finite value greater than 0 seconds")


def _should_extract(dimension: str, dimensions: frozenset[str] | None) -> bool:
    return dimensions is None or dimension in dimensions


def _extract_api_surface(
    paths: tuple[Path, ...],
    *,
    package_root: Path,
) -> tuple[APISurfaceEntry, ...]:
    return _run_extractor(
        "api_surface",
        None,
        lambda: extract_python_api_surface_from_paths(paths, package_root=package_root),
    )


def _extract_effects(
    paths: tuple[Path, ...],
    *,
    package_root: Path,
) -> tuple[EffectEntry, ...]:
    entries: list[EffectEntry] = []
    for path in paths:
        resolved = path.resolve()
        module_fqn = _module_fqn_from_path(resolved, package_root=package_root)
        entries.extend(
            _run_extractor(
                "effects",
                path,
                lambda path=path, module_fqn=module_fqn: extract_python_effects(
                    _read_source(path),
                    filename=str(path),
                    module_fqn=module_fqn,
                ),
            )
        )
    return tuple(entries)


def _extract_imports(
    paths: tuple[Path, ...],
    *,
    package_root: Path,
) -> tuple[ImportEntry, ...]:
    return _run_extractor(
        "imports",
        None,
        lambda: extract_python_imports_from_paths(paths, package_root=package_root),
    )


def _extract_complexity(
    paths: tuple[Path, ...],
    *,
    package_root: Path,
) -> tuple[ComplexityEntry, ...]:
    return _run_extractor(
        "complexity",
        None,
        lambda: extract_python_complexity_from_paths(paths, package_root=package_root),
    )


def _extract_test_surface(
    paths: tuple[Path, ...],
    *,
    package_root: Path,
) -> tuple[TestSurfaceEntry, ...]:
    return _run_extractor(
        "test_surface",
        None,
        lambda: extract_python_test_surface_from_paths(paths, package_root=package_root),
    )


def _extract_module_graph(
    package_root: Path,
    *,
    extract_config: ExtractConfig | None,
) -> tuple[ModuleGraphEntry, ...]:
    return _run_extractor(
        "module_graph",
        package_root,
        lambda: extract_python_module_graph(package_root, extract_config=extract_config),
    )


def _run_extractor(
    extractor_name: str,
    path: Path | None,
    action: Callable[[], T],
) -> T:
    try:
        return action()
    except Exception as exc:
        error_path = path if path is not None else _path_from_exception(exc)
        raise ExtractorError(extractor_name=extractor_name, path=error_path) from exc


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _path_from_exception(exc: Exception) -> Path | None:
    filename = getattr(exc, "filename", None)
    if isinstance(filename, str) and filename:
        return Path(filename)
    return None


def _filter_excluded(
    paths: tuple[Path, ...],
    *,
    extract_config: ExtractConfig | None,
    exclude_reporter: ExcludeReporter | None,
) -> tuple[Path, ...]:
    kept, excluded = filter_excluded_paths(paths, extract_config)
    if exclude_reporter is not None and extract_config is not None and extract_config.patterns:
        exclude_reporter(excluded)
    return kept


def _python_paths_from_inputs(
    paths: Iterable[Path],
    *,
    package_root: Path,
) -> tuple[Path, ...]:
    expanded: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = Path(raw_path).resolve()
        if not path.exists():
            raise ValueError(f"path does not exist under package_root: {path}")
        _ensure_under_package_root(path, package_root=package_root)
        if path.is_dir():
            for candidate in sorted(path.rglob("*.py"), key=lambda item: str(item.resolve())):
                resolved = candidate.resolve()
                _ensure_under_package_root(resolved, package_root=package_root)
                _append_once(resolved, expanded=expanded, seen=seen)
        elif path.suffix == ".py":
            _append_once(path, expanded=expanded, seen=seen)
    return tuple(sorted(expanded, key=lambda path: str(path.resolve())))


def _resolve_package_root(package_root: Path) -> Path:
    root = Path(package_root).resolve()
    if not root.exists():
        raise ValueError(f"package_root does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"package_root is not a directory: {root}")
    return root


def _ensure_under_package_root(path: Path, *, package_root: Path) -> None:
    if path == package_root or package_root in path.parents:
        return
    raise ValueError(f"path is outside package_root: {path}")


def _append_once(path: Path, *, expanded: list[Path], seen: set[Path]) -> None:
    if path in seen:
        return
    seen.add(path)
    expanded.append(path)
