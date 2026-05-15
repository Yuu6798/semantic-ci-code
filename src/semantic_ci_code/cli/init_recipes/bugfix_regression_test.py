"""Recipe `bugfix:regression-test`."""

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
