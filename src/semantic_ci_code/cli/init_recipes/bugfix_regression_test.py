"""Recipe `bugfix:regression-test` (Brief 8 / CSCI-42).

Inviolate output predicate: `change.primary_kind: bugfix`, with a
`test_surface_delta.new_cases` constraint that either lists the
supplied canonical test IDs (when `--test-case` was given or PR body /
issue body `## Test cases` was parsed) or requires `not_equals []` so
the recipe forces at least one new regression test.

The BUGFIX template (`compiler/templates.py:64-76`) auto-expands
`api_surface_public equals_baseline` and `effect_changes.added equals ()`
— public API addition and removal are both locked. PRs that introduce
or remove public API must use `feature:add-api`, not `bugfix`.
"""

from __future__ import annotations

from typing import Any

from semantic_ci_code.authoring.sources.merge import MergedSources
from semantic_ci_code.cli.init_recipes._shared import (
    append_new_cases_constraint,
    empty_recipe_payload,
)


def build(merged: MergedSources) -> dict[str, Any]:
    payload = empty_recipe_payload(merged)
    append_new_cases_constraint(
        payload,
        constraint_id="recipe:bugfix:regression-test:test_surface_new_cases",
        test_ids=merged.test_ids,
    )
    return payload
