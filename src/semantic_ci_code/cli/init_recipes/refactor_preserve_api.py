"""Recipe `refactor:preserve-api-with-allowlist`."""

from __future__ import annotations

from typing import Any

from semantic_ci_code.authoring.sources.merge import MergedSources
from semantic_ci_code.cli.init_recipes._shared import empty_recipe_payload


def build(merged: MergedSources) -> dict[str, Any]:
    payload = empty_recipe_payload(merged)
    if merged.allow_fqns or merged.allow_fqn_prefixes:
        rules: list[dict[str, str]] = []
        for fqn in merged.allow_fqns:
            rules.append({"fqn": fqn})
        for prefix in merged.allow_fqn_prefixes:
            rules.append({"fqn_prefix": prefix})
        payload["api_surface"] = {"allow_changes": rules}
    return payload
