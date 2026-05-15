"""Recipe registry for `semantic-ci init --recipe` (Brief 8 / CSCI-42).

Each recipe module exposes a single `build(merged: MergedSources)`
function that returns the target.yaml payload as an ordered mapping.
The mapping is then serialised with `yaml.safe_dump(..., sort_keys=False)`
so that same input yields byte-identical output across runs (INV-1 /
determinism acceptance).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from semantic_ci_code.authoring.sources.merge import (
    RECIPE_BUGFIX_REGRESSION_TEST,
    RECIPE_FEATURE_ADD_API,
    RECIPE_REFACTOR_PRESERVE_API,
    RECIPE_TEST_UPDATE_ADD_TEST_CASE,
    MergedSources,
)
from semantic_ci_code.cli.init_recipes import (
    bugfix_regression_test,
    feature_add_api,
    refactor_preserve_api,
    test_update_add_test_case,
)

RecipeBuilder = Callable[[MergedSources], dict[str, Any]]

RECIPES: dict[str, RecipeBuilder] = {
    RECIPE_FEATURE_ADD_API: feature_add_api.build,
    RECIPE_BUGFIX_REGRESSION_TEST: bugfix_regression_test.build,
    RECIPE_REFACTOR_PRESERVE_API: refactor_preserve_api.build,
    RECIPE_TEST_UPDATE_ADD_TEST_CASE: test_update_add_test_case.build,
}


def apply_recipe(merged: MergedSources) -> dict[str, Any]:
    """Apply the recipe selected by `merged.recipe_id`.

    The caller is expected to have already validated the recipe ID via
    the merger and to pass the corresponding `MergedSources` payload.
    """
    builder = RECIPES[merged.recipe_id]
    return builder(merged)


__all__ = ["RECIPES", "RecipeBuilder", "apply_recipe"]
