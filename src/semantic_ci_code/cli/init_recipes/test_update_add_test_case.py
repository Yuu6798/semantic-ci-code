"""Recipe `test-update:add-test-case` (Brief 8 / CSCI-42).

Inviolate output predicate: `change.primary_kind: test_update` and a
`test_surface_delta.new_cases` constraint (canonical IDs when
`--test-case` or PR body `## Test cases` populated the list, `not_equals
[]` otherwise).

The TEST_UPDATE template (`compiler/templates.py:91-108`) auto-expands
`api_surface_public equals_baseline`, `effect_changes equals
{added: (), removed: ()}`, and `imports equals_baseline` — every
non-test surface is locked so the change is constrained to test
additions only.
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
        constraint_id="recipe:test-update:add-test-case:test_surface_new_cases",
        test_ids=merged.test_ids,
    )
    return payload
