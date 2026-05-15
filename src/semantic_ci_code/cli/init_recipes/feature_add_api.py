"""Recipe `feature:add-api`."""

from __future__ import annotations

from typing import Any

from semantic_ci_code.authoring.sources.merge import MergedSources
from semantic_ci_code.cli.init_recipes._shared import (
    append_new_cases_constraint,
    empty_recipe_payload,
)


class FeatureRecipeError(ValueError):
    pass


def build(merged: MergedSources) -> dict[str, Any]:
    if not merged.api_fqns:
        raise FeatureRecipeError(
            "empty FQN list after merge for recipe 'feature:add-api'; supply "
            "--add-api FQN, a PR body '## Expected public API' section, or "
            "(as medium fallback) an issue body '## Expected public API' section"
        )

    payload = empty_recipe_payload(merged)
    payload["constraints"].append(
        {
            "id": "recipe:feature:add-api:api_surface_delta_added",
            "kind": "delta",
            "target": "api_surface_delta.added",
            "operator": "includes_all",
            "expected": [{"fqn": fqn, "visibility": "public"} for fqn in merged.api_fqns],
        }
    )
    if merged.test_ids:
        append_new_cases_constraint(
            payload,
            constraint_id="recipe:feature:add-api:test_surface_new_cases",
            test_ids=merged.test_ids,
        )
    return payload
