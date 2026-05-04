"""Python ``CodeState`` assembly from the P1 extractor set.

This module is the first Brief 3 pipeline slice: it assembles observed or
baseline RPE material by calling the six Python P1 extractors and storing
their outputs in the matching ``CodeState`` fields. It intentionally does
not compute deltas, evaluate constraints, repair specs, read intent YAML,
run dynamic coverage, or expose CLI wiring.

Failure policy is fail-fast. Any extractor exception is wrapped in
``ExtractorError`` with the extractor name and the best-known file path,
then re-raised with the original exception as ``__cause__``. Partial
results, ``unknown_policy`` integration, and extraction tolerance are
deferred to a later brief (see ``docs/code_semantic_ci_design.md`` section 6.2).

The paths variant is intentionally asymmetric: ``api_surface``,
``effects``, ``imports``, ``complexity``, and ``test_surface`` are limited
to the supplied paths, while ``module_graph`` is always extracted from the
whole ``package_root``. The module graph represents repository structure,
so cutting it to a file subset would create a misleading ``CodeState``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeVar

from semantic_ci_code.api_surface import extract_python_api_surface_from_paths
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
from semantic_ci_code.imports import extract_python_imports_from_paths
from semantic_ci_code.module_graph import extract_python_module_graph
from semantic_ci_code.test_surface import extract_python_test_surface_from_paths

T = TypeVar("T")


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


def extract_python_code_state(package_root: Path) -> CodeState:
    """Assemble a whole-package Python ``CodeState`` from ``package_root``.

    All six extracted fields are populated from the package root. P1-unextracted
    fields such as ``type_relations``, ``control_flow``, ``data_flow``, and
    ``coverage`` are left at the schema defaults.
    """
    root = _resolve_package_root(package_root)
    paths = _python_paths_from_inputs((root,), package_root=root)
    return _assemble_code_state(paths=paths, package_root=root)


def extract_python_code_state_from_paths(
    paths: Iterable[Path],
    *,
    package_root: Path,
) -> CodeState:
    """Assemble a Python ``CodeState`` with per-file fields limited to ``paths``.

    ``paths`` is consumed exactly once, then expanded deterministically. Empty
    iterables are valid and yield empty per-file fields. ``module_graph`` is
    still extracted from the whole ``package_root`` because it is a structural
    repository invariant, not a per-file signal.
    """
    root = _resolve_package_root(package_root)
    selected_paths = tuple(paths)
    expanded_paths = _python_paths_from_inputs(selected_paths, package_root=root)
    return _assemble_code_state(paths=expanded_paths, package_root=root)


def _assemble_code_state(
    *,
    paths: tuple[Path, ...],
    package_root: Path,
) -> CodeState:
    return CodeState(
        api_surface=_extract_api_surface(paths, package_root=package_root),
        effects=_extract_effects(paths),
        imports=_extract_imports(paths, package_root=package_root),
        complexity=_extract_complexity(paths, package_root=package_root),
        test_surface=_extract_test_surface(paths, package_root=package_root),
        module_graph=_extract_module_graph(package_root),
    )


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


def _extract_effects(paths: tuple[Path, ...]) -> tuple[EffectEntry, ...]:
    entries: list[EffectEntry] = []
    for path in paths:
        entries.extend(
            _run_extractor(
                "effects",
                path,
                lambda path=path: extract_python_effects(
                    _read_source(path),
                    filename=str(path),
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


def _extract_module_graph(package_root: Path) -> tuple[ModuleGraphEntry, ...]:
    return _run_extractor(
        "module_graph",
        package_root,
        lambda: extract_python_module_graph(package_root),
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
