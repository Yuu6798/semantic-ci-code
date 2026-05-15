"""Recipe `feature:add-api` (Brief 8 / CSCI-42).

Inviolate output predicate: the generated YAML carries an
`api_surface_delta.added includes_all [{fqn, visibility: "public"}, …]`
constraint built from the merged FQN list. Record match form is used
(not the flat-projection alias) so `framework/match_schema.py:47`
`_API_SCHEMA.optional_keys={"kind", "visibility"}` is exercised and
visibility information is not dropped at compile time.

`change.primary_kind: feature` triggers the FEATURE template, which
auto-expands `api_surface_delta.removed_public equals ()` and
`effect_changes.added equals ()` (`compiler/templates.py:77-89`); the
recipe does not repeat them.
"""

from __future__ import annotations

from typing import Any

from semantic_ci_code.authoring.sources.merge import MergedSources
from semantic_ci_code.cli.init_recipes._shared import (
    append_new_cases_constraint,
    empty_recipe_payload,
)


class FeatureRecipeError(ValueError):
    """Raised when the recipe cannot produce a valid constraint set."""


def build(merged: MergedSources) -> dict[str, Any]:
    if not merged.api_fqns:
        msg = (
            "empty FQN list after merge for recipe 'feature:add-api'; "
            "supply --add-api FQN, a PR body '## Expected public API' "
            "section, or (as medium fallback) an issue body "
            "'## Expected public API' section"
        )
        raise FeatureRecipeError(msg)

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
