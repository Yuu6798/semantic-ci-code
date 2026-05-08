"""Deterministic Python module-graph extraction.

The graph for P1 is repo-internal only. External dependencies (``os``,
``urllib``, third-party packages) are intentionally not represented as
nodes. This is for three reasons:

1. Stability: the ``module_graph`` dimension feeds change-impact
   reasoning in the diff layer. If external modules were nodes, their
   ``imported_by`` sets would be enormous and noisy. The ``imports``
   dimension already records every external import for constraint checks.
2. Finiteness: external resolution would require ``sys.path``,
   virtualenv layout, vendor directories, and namespace packages; none of
   that is deterministic across CI environments.
3. Scope discipline: this extractor reuses the imports extractor. It does
   not build a Python module resolver.

So a module exists in the graph iff a ``*.py`` file backing it exists under
``package_root``. Imports of anything outside that set produce no edge.

Resolution rules (``ImportEntry`` -> set of internal modules):

Step A: compute the candidate base module(s).

- If ``from_ is None`` (absolute): base = ``module``.
- If ``from_ is not None`` (relative): the relative-prefix length is
  ``len(from_)``. Walk up ``len(from_) - 1`` package levels from the
  importer's containing package, then append ``module`` if ``module`` is
  non-empty.
- If the importer has no containing package, or walking up exhausts the
  importer's package path, the import is unresolvable in our universe and
  emits no edge.

Step B: expand candidates per symbol.

- For absolute imports, ``import a, b`` is already represented by one
  ``ImportEntry`` per imported module. Each is its own base candidate and
  has ``symbols=()``.
- For ``from x import y, z`` (absolute or relative), each symbol can be a
  submodule. Generate ``{base}`` plus ``{base + "." + symbol}`` for every
  non-star symbol.
- For ``from x import *``, the candidate set is ``{base}`` only. The star
  is opaque; we record only the source-module dependency.

Step C: filter by universe.

- Keep only candidates that are members of the discovered module universe.
  Drop the rest silently.

Step D: collect.

- Add all kept candidates to the importer's forward edge set. Self-edges
  are dropped. Backward edges are materialized as the exact transpose.

Extraction is a full scan of ``package_root``. Incremental extraction,
unresolved-import evidence, namespace-package semantics, and cycle
warnings are deferred to later briefs. Files are read as UTF-8.
"""

from __future__ import annotations

from pathlib import Path

from semantic_ci_code.api_surface.python_api_extractor import _module_fqn_from_path
from semantic_ci_code.domain.state_schema import ImportEntry, ModuleGraphEntry
from semantic_ci_code.framework.extract_config import ExtractConfig, filter_excluded_paths
from semantic_ci_code.imports import extract_python_imports


def extract_python_module_graph(
    package_root: Path,
    *,
    extract_config: ExtractConfig | None = None,
) -> tuple[ModuleGraphEntry, ...]:
    """Extract a deterministic repo-internal Python module graph."""
    root = package_root.resolve()
    module_paths = _discover_module_paths(root, extract_config=extract_config)
    modules_by_path = {
        path: _module_fqn_from_path(path, package_root=root) for path in module_paths
    }
    package_modules = {
        module for path, module in modules_by_path.items() if path.name == "__init__.py"
    }
    universe = frozenset(modules_by_path.values())

    forward: dict[str, set[str]] = {module: set() for module in universe}
    for path in module_paths:
        importer = modules_by_path[path]
        source = path.read_text(encoding="utf-8")
        entries = extract_python_imports(source, filename=str(path))
        for entry in entries:
            for candidate in _resolve_internal_modules(
                importer=importer,
                entry=entry,
                universe=universe,
                package_modules=package_modules,
            ):
                if candidate != importer:
                    forward[importer].add(candidate)

    backward: dict[str, set[str]] = {module: set() for module in universe}
    for importer, imports in forward.items():
        for imported in imports:
            backward[imported].add(importer)

    return tuple(
        ModuleGraphEntry(
            module=module,
            imports=tuple(sorted(forward[module])),
            imported_by=tuple(sorted(backward[module])),
        )
        for module in sorted(universe)
    )


def _discover_module_paths(
    package_root: Path,
    *,
    extract_config: ExtractConfig | None,
) -> tuple[Path, ...]:
    paths = tuple(sorted(package_root.rglob("*.py"), key=lambda path: str(path.resolve())))
    # ``python_code_state`` filters once before per-dimension extractors, but
    # module graph is also public as a direct extractor. Keep this second filter
    # here so direct callers get the same node/edge surface.
    kept, _excluded = filter_excluded_paths(paths, extract_config)
    return kept


def _resolve_internal_modules(
    *,
    importer: str,
    entry: ImportEntry,
    universe: frozenset[str],
    package_modules: set[str],
) -> tuple[str, ...]:
    base = _candidate_base(
        importer=importer,
        entry=entry,
        package_modules=package_modules,
    )
    if base is None:
        return ()

    candidates = {base}
    for symbol in entry.symbols:
        if symbol != "*":
            candidates.add(_join_module(base, symbol))

    return tuple(sorted(candidate for candidate in candidates if candidate in universe))


def _candidate_base(
    *,
    importer: str,
    entry: ImportEntry,
    package_modules: set[str],
) -> str | None:
    if entry.from_ is None:
        return entry.module

    containing_package = _containing_package(importer, package_modules=package_modules)
    if not containing_package:
        return None
    parts = containing_package.split(".") if containing_package else []
    ascents = len(entry.from_) - 1
    if ascents >= len(parts) and ascents > 0:
        return None
    if ascents:
        parts = parts[:-ascents]
    if entry.module:
        parts.extend(entry.module.split("."))
    return ".".join(parts)


def _containing_package(importer: str, *, package_modules: set[str]) -> str:
    if importer in package_modules:
        return importer
    head, _, _tail = importer.rpartition(".")
    return head


def _join_module(base: str, symbol: str) -> str:
    return f"{base}.{symbol}" if base else symbol
