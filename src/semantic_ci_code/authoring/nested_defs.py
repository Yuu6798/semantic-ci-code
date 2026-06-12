"""Nested-function counting for ADVISORY-D6 (nested-function blind spot).

`python_complexity_extractor` stops descent at nested ``FunctionDef`` /
``AsyncFunctionDef`` / ``ClassDef`` boundaries and only emits entries for
the ``api_surface`` parity subset (module-level defs + direct methods of
module-level classes). Complexity moved into function-nested helpers
therefore disappears from ``complexity_delta`` numbers (D6,
`docs/dogfooding_findings_tracker.md`). This module provides the
deterministic per-file signal — the count of function-nested defs — that
the CLI layer feeds to `detect_d6` as `NestedDefGrowth` records.

Scope note: only defs nested (at any depth) inside another function are
counted. Lambdas are not counted — they cannot contain statements, so they
cannot absorb branch complexity the way a nested def can. Methods of
module-level classes are extractor-visible and not counted.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class NestedDefGrowth:
    """Per-file nested-def counts on both sides of the candidate diff.

    `path` is the candidate-side repo-relative posix path. A file absent
    on one side contributes a count of 0 for that side.
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
