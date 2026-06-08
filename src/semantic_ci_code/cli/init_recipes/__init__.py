"""Recipe registry for `semantic-ci init --recipe`."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from semantic_ci_code.authoring.sources.merge import (
    RECIPE_BUGFIX_REGRESSION_TEST,
    RECIPE_FEATURE_ADD_API,
    RECIPE_REFACTOR_PRESERVE_API,
    RECIPE_SECURITY_DENY_DANGEROUS_EFFECTS,
    RECIPE_SECURITY_DENY_DANGEROUS_IMPORTS,
    RECIPE_SECURITY_PRESERVE_AUTH_GUARDS,
    RECIPE_TEST_UPDATE_ADD_TEST_CASE,
    MergedSources,
)
from semantic_ci_code.cli.init_recipes import (
    bugfix_regression_test,
    feature_add_api,
    refactor_preserve_api,
    security_deny_dangerous_effects,
    security_deny_dangerous_imports,
    security_preserve_auth_guards,
    test_update_add_test_case,
)

RecipeBuilder = Callable[[MergedSources], dict[str, Any]]

RECIPES: dict[str, RecipeBuilder] = {
    RECIPE_FEATURE_ADD_API: feature_add_api.build,
    RECIPE_BUGFIX_REGRESSION_TEST: bugfix_regression_test.build,
    RECIPE_REFACTOR_PRESERVE_API: refactor_preserve_api.build,
    RECIPE_TEST_UPDATE_ADD_TEST_CASE: test_update_add_test_case.build,
    RECIPE_SECURITY_DENY_DANGEROUS_IMPORTS: security_deny_dangerous_imports.build,
    RECIPE_SECURITY_DENY_DANGEROUS_EFFECTS: security_deny_dangerous_effects.build,
    RECIPE_SECURITY_PRESERVE_AUTH_GUARDS: security_preserve_auth_guards.build,
}


def apply_recipe(merged: MergedSources) -> dict[str, Any]:
    return RECIPES[merged.recipe_id](merged)


__all__ = ["RECIPES", "RecipeBuilder", "apply_recipe"]
