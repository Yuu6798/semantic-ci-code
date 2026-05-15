"""Recipe `refactor:preserve-api-with-allowlist` (Brief 8 / CSCI-42).

Inviolate output predicate: `change.primary_kind: refactor`. With no
allowlist flags the REFACTOR template alone applies
(`compiler/templates.py:41-63`) — `api_surface_public equals_baseline`
plus `type_relations` / `effect_changes` / `test_surface` lockdown.

When `--allow-fqn` / `--allow-fqn-prefix` is given, the recipe emits an
`api_surface.allow_changes` block (the existing policy escape hatch at
`compiler/target_compiler.py:301-314`). No new operator or new policy
hatch is introduced; direction-specific allowlists (add-only /
remove-only) are not expressible in the current DSL and the recipe
does not silently guess one.
"""

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
