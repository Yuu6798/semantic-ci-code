"""Def counting for the complexity authoring advisories (D6 / D7).

`python_complexity_extractor` only emits entries for the ``api_surface``
parity subset (module-level defs + direct methods of module-level
classes) and stops descent at nested ``def`` boundaries. Both complexity
hazards are shapes of that emission rule
(`docs/dogfooding_findings_tracker.md`):

- **D6**: complexity displaced into function-nested helpers vanishes from
  ``complexity_delta`` numbers (vacuous PASS). Signal: per-file
  function-nested def count growth (`count_nested_defs` /
  `NestedDefGrowth`).
- **D7**: extract-method refactors add extractor-visible functions, each
  starting at cyclomatic base 1, so a summed ``cyclomatic <= 0`` lock is
  mathematically guaranteed to false-FAIL on a faithful extraction.
  Signal: per-file extractor-visible def count growth
  (`count_visible_defs` / `VisibleDefGrowth`).

The CLI layer computes the per-file growth records from the candidate
diff and feeds them to `detect_d6` / `detect_d7`.

Scope note for `count_nested_defs`: only defs nested (at any depth)
inside another function are counted. Lambdas are not counted — they
cannot contain statements, so they cannot absorb branch complexity the
way a nested def can. Methods of module-level classes are
extractor-visible and not counted.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from semantic_ci_code.complexity.python_complexity_extractor import extract_python_complexity


@dataclass(frozen=True)
class NestedDefGrowth:
    """Per-file nested-def counts on both sides of the candidate diff.

    `path` is the candidate-side repo-relative posix path. A file absent
    on one side contributes a count of 0 for that side.
    """

    path: str
    baseline_count: int
    candidate_count: int


@dataclass(frozen=True)
class VisibleDefGrowth:
    """Per-file extractor-visible def counts on both diff sides.

    Same path / absent-side conventions as `NestedDefGrowth`.
    """

    path: str
    baseline_count: int
    candidate_count: int


def count_nested_defs(source: str) -> int | None:
    """Count function defs nested inside another function.

    Returns `None` when `source` does not parse — the caller must skip
    the file rather than treat it as zero, so a syntax error cannot
    fabricate or suppress a growth signal.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    count = 0
    # Iterative walk: (node, inside_function). A def found while inside a
    # function counts, including defs inside a class that is itself inside
    # a function (the extractor emits neither).
    stack: list[tuple[ast.AST, bool]] = [(tree, False)]
    while stack:
        node, inside_function = stack.pop()
        for child in ast.iter_child_nodes(node):
            is_def = isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
            if is_def and inside_function:
                count += 1
            stack.append((child, inside_function or is_def))
    return count


def count_visible_defs(source: str) -> int | None:
    """Count extractor-visible function defs (``api_surface`` parity).

    Delegates to `extract_python_complexity` so the count can never
    drift from the real emission rule (module-level defs incl.
    module-scope compound statements + direct methods of module-level
    classes). Returns `None` when `source` does not parse, mirroring
    `count_nested_defs`.
    """
    try:
        return len(extract_python_complexity(source, module_fqn="_advisory_probe"))
    except (SyntaxError, ValueError):
        return None
