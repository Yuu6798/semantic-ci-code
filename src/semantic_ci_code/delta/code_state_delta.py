"""Deterministic ``CodeStateDelta`` computation.

This module exposes one pure, total function:
``compute_code_state_delta(baseline, candidate)``. It performs no file I/O,
network access, time reads, random reads, or environment reads. Given two
schema-valid ``CodeState`` values, it returns a deterministic ``CodeStateDelta``.

Delta rules:

- ``api_surface_delta`` uses identity key ``(fqn, kind)``. Entries present
  only in candidate are ``added``; entries present only in baseline are
  ``removed``; entries present in both with different ``signature`` or
  ``visibility`` are ``changed`` as ``{"fqn", "kind", "before", "after"}``.
  Lists are sorted by ``(fqn, kind)``.
- ``type_changes`` is always ``()`` in P1 until a ``type_relations`` extractor
  exists.
- ``effect_changes`` uses identity key ``(fqn, effect_class)`` and has no
  ``changed`` slot. A same-fqn effect class change is represented as removed
  old class plus added new class. ``confidence`` and ``evidence`` differences
  are ignored in P1.
- ``imports_delta`` uses identity key ``(module, from_ or "", sorted symbols)``.
  A same-module symbols-only change is represented as removed old row plus
  added new row. Import JSON uses ``by_alias=True`` to preserve the ``from``
  field alias.
- ``cfg_delta`` is always ``CFGDelta()`` in P1. It is independent of
  ``complexity_delta`` and becomes active only when a control-flow extractor
  exists.
- ``complexity_delta`` is a net total: sum candidate cyclomatic/cognitive minus
  sum baseline cyclomatic/cognitive. Added, removed, and changed functions all
  contribute to the total; ``None`` is treated as ``0``.
- ``test_surface_delta`` records candidate-only files as ``new_files``,
  candidate-only test cases as ``new_cases``, and baseline-only test cases as
  ``removed_cases``. ``asserts`` and ``parametrize_count`` changes are stored in
  ``python_specific.test_surface_changes`` because the first-class schema has
  no changed slot.
- ``coverage_delta`` is always ``None`` in P1.
- ``files_touched`` and ``loc_delta`` always stay at defaults in CSCI-11. They
  are git-diff-derived and belong to CLI overlay via ``model_copy(update=...)``.
- ``typescript_specific`` is always ``None`` in this Python P1 slice.

``python_specific`` stores schema extension details in a deterministic dict.
Subkeys are inserted in this fixed order and omitted when empty:
``module_graph_delta``, ``complexity_changes``, ``test_surface_changes``.
Pydantic JSON emission preserves Python dict insertion order, which is part of
the byte-stability contract here. If all subkeys are empty,
``python_specific`` is ``None``, not an empty dict.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

from pydantic import BaseModel

from semantic_ci_code.domain.state_schema import (
    APISurfaceEntry,
    CFGDelta,
    CodeState,
    CodeStateDelta,
    ComplexityDelta,
    ComplexityEntry,
    EffectChanges,
    EffectEntry,
    ImportDelta,
    ImportEntry,
    JsonMapping,
    JsonValue,
    ModuleGraphEntry,
    SymbolDelta,
    TestSurfaceDelta,
    TestSurfaceEntry,
)

T = TypeVar("T")
K = TypeVar("K")

__all__ = ["compute_code_state_delta"]


def compute_code_state_delta(
    baseline: CodeState,
    candidate: CodeState,
) -> CodeStateDelta:
    """Compute a deterministic ``CodeStateDelta`` from two ``CodeState`` values.

    Pure function: no I/O, no time, no random. Total: schema-valid inputs never
    raise. ``files_touched`` and ``loc_delta`` are always defaults; the CLI
    layer overlays them in Brief 4 via ``model_copy(update=...)``.
    """
    return CodeStateDelta(
        api_surface_delta=_api_surface_delta(baseline.api_surface, candidate.api_surface),
        type_changes=(),
        effect_changes=_effect_changes(baseline.effects, candidate.effects),
        cfg_delta=CFGDelta(),
        imports_delta=_imports_delta(baseline.imports, candidate.imports),
        complexity_delta=_complexity_delta(baseline.complexity, candidate.complexity),
        test_surface_delta=_test_surface_delta(baseline.test_surface, candidate.test_surface),
        coverage_delta=None,
        files_touched=0,
        python_specific=_build_python_specific(baseline=baseline, candidate=candidate),
        typescript_specific=None,
    )


def _api_surface_delta(
    baseline: tuple[APISurfaceEntry, ...],
    candidate: tuple[APISurfaceEntry, ...],
) -> SymbolDelta:
    base = _index_by(baseline, _api_key)
    cand = _index_by(candidate, _api_key)

    added = tuple(_dump(cand[key]) for key in _sorted_added_keys(base, cand))
    removed = tuple(_dump(base[key]) for key in _sorted_removed_keys(base, cand))
    changed = tuple(
        {
            "fqn": key[0],
            "kind": key[1],
            "before": _dump(base[key]),
            "after": _dump(cand[key]),
        }
        for key in sorted(base.keys() & cand.keys())
        if (
            base[key].signature != cand[key].signature
            or base[key].visibility != cand[key].visibility
        )
    )
    return SymbolDelta(added=added, removed=removed, changed=changed)


def _effect_changes(
    baseline: tuple[EffectEntry, ...],
    candidate: tuple[EffectEntry, ...],
) -> EffectChanges:
    base = _index_by(baseline, _effect_key)
    cand = _index_by(candidate, _effect_key)

    return EffectChanges(
        added=tuple(_dump(cand[key]) for key in _sorted_added_keys(base, cand)),
        removed=tuple(_dump(base[key]) for key in _sorted_removed_keys(base, cand)),
    )


def _imports_delta(
    baseline: tuple[ImportEntry, ...],
    candidate: tuple[ImportEntry, ...],
) -> ImportDelta:
    base = _index_by(baseline, _import_key)
    cand = _index_by(candidate, _import_key)

    return ImportDelta(
        added=tuple(_dump_import(cand[key]) for key in _sorted_added_keys(base, cand)),
        removed=tuple(_dump_import(base[key]) for key in _sorted_removed_keys(base, cand)),
    )


def _complexity_delta(
    baseline: tuple[ComplexityEntry, ...],
    candidate: tuple[ComplexityEntry, ...],
) -> ComplexityDelta:
    return ComplexityDelta(
        cyclomatic=_sum_complexity(candidate, "cyclomatic")
        - _sum_complexity(baseline, "cyclomatic"),
        cognitive=_sum_complexity(candidate, "cognitive") - _sum_complexity(baseline, "cognitive"),
    )


def _test_surface_delta(
    baseline: tuple[TestSurfaceEntry, ...],
    candidate: tuple[TestSurfaceEntry, ...],
) -> TestSurfaceDelta:
    base_files = {entry.test_file for entry in baseline}
    cand_files = {entry.test_file for entry in candidate}
    base_cases = {_test_case_id(entry) for entry in baseline}
    cand_cases = {_test_case_id(entry) for entry in candidate}

    return TestSurfaceDelta(
        new_files=tuple(sorted(cand_files - base_files)),
        new_cases=tuple(sorted(cand_cases - base_cases)),
        removed_cases=tuple(sorted(base_cases - cand_cases)),
    )


def _build_python_specific(*, baseline: CodeState, candidate: CodeState) -> JsonMapping | None:
    details: JsonMapping = {}

    module_graph_delta = _module_graph_delta(baseline.module_graph, candidate.module_graph)
    if module_graph_delta is not None:
        details["module_graph_delta"] = module_graph_delta

    complexity_changes = _complexity_changes(baseline.complexity, candidate.complexity)
    if complexity_changes is not None:
        details["complexity_changes"] = complexity_changes

    test_surface_changes = _test_surface_changes(baseline.test_surface, candidate.test_surface)
    if test_surface_changes is not None:
        details["test_surface_changes"] = test_surface_changes

    return details or None


def _module_graph_delta(
    baseline: tuple[ModuleGraphEntry, ...],
    candidate: tuple[ModuleGraphEntry, ...],
) -> JsonMapping | None:
    base_edges = _module_edges(baseline)
    cand_edges = _module_edges(candidate)
    added_edges = tuple(sorted(cand_edges - base_edges))
    removed_edges = tuple(sorted(base_edges - cand_edges))
    if not added_edges and not removed_edges:
        return None
    return {
        "added_edges": [list(edge) for edge in added_edges],
        "removed_edges": [list(edge) for edge in removed_edges],
    }


def _complexity_changes(
    baseline: tuple[ComplexityEntry, ...],
    candidate: tuple[ComplexityEntry, ...],
) -> JsonMapping | None:
    base = _index_by(baseline, _complexity_key)
    cand = _index_by(candidate, _complexity_key)

    added = [_dump(cand[key]) for key in _sorted_added_keys(base, cand)]
    removed = [_dump(base[key]) for key in _sorted_removed_keys(base, cand)]
    changed = [
        {"fqn": key, "before": _dump(base[key]), "after": _dump(cand[key])}
        for key in sorted(base.keys() & cand.keys())
        if (
            base[key].cyclomatic != cand[key].cyclomatic
            or base[key].cognitive != cand[key].cognitive
        )
    ]
    if not added and not removed and not changed:
        return None
    return {"added": added, "removed": removed, "changed": changed}


def _test_surface_changes(
    baseline: tuple[TestSurfaceEntry, ...],
    candidate: tuple[TestSurfaceEntry, ...],
) -> JsonMapping | None:
    base = _index_by(baseline, _test_surface_key)
    cand = _index_by(candidate, _test_surface_key)
    changed = [
        {
            "test_file": key[0],
            "test_function": key[1],
            "before": _dump(base[key]),
            "after": _dump(cand[key]),
        }
        for key in sorted(base.keys() & cand.keys())
        if (
            base[key].asserts != cand[key].asserts
            or base[key].parametrize_count != cand[key].parametrize_count
        )
    ]
    if not changed:
        return None
    return {"changed": changed}


def _index_by(entries: Iterable[T], key: Callable[[T], K]) -> dict[K, T]:
    indexed: dict[K, T] = {}
    for entry in entries:
        indexed.setdefault(key(entry), entry)
    return indexed


def _sorted_added_keys(base: dict[K, T], cand: dict[K, T]) -> list[K]:
    return sorted(cand.keys() - base.keys())


def _sorted_removed_keys(base: dict[K, T], cand: dict[K, T]) -> list[K]:
    return sorted(base.keys() - cand.keys())


def _api_key(entry: APISurfaceEntry) -> tuple[str, str]:
    return entry.fqn, entry.kind


def _effect_key(entry: EffectEntry) -> tuple[str, str]:
    return entry.fqn, entry.effect_class.value


def _import_key(entry: ImportEntry) -> tuple[str, str, tuple[str, ...]]:
    return entry.module, entry.from_ or "", tuple(sorted(entry.symbols))


def _complexity_key(entry: ComplexityEntry) -> str:
    return entry.fqn


def _test_surface_key(entry: TestSurfaceEntry) -> tuple[str, str]:
    return entry.test_file, entry.test_function


def _test_case_id(entry: TestSurfaceEntry) -> str:
    return f"{entry.test_file}::{entry.test_function}"


def _module_edges(entries: tuple[ModuleGraphEntry, ...]) -> frozenset[tuple[str, str]]:
    return frozenset((entry.module, imported) for entry in entries for imported in entry.imports)


def _sum_complexity(entries: tuple[ComplexityEntry, ...], field: str) -> int:
    return sum(getattr(entry, field) or 0 for entry in entries)


def _dump(entry: BaseModel) -> JsonValue:
    return entry.model_dump(mode="json")


def _dump_import(entry: ImportEntry) -> JsonValue:
    return entry.model_dump(mode="json", by_alias=True)
