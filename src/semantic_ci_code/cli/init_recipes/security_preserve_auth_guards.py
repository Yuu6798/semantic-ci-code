"""Recipe `security:preserve-auth-guards`."""

from __future__ import annotations

from typing import Any

from semantic_ci_code.authoring.sources.merge import MergedSources
from semantic_ci_code.cli.init_recipes._shared import empty_recipe_payload

AUTH_GUARD_DECORATORS: tuple[str, ...] = (
    "login_required",
    "requires_auth",
    "permission_required",
)


def build(merged: MergedSources) -> dict[str, Any]:
    payload = empty_recipe_payload(merged)
    payload["constraints"].append(
        {
            "id": "security:preserve-auth-guards",
            "kind": "delta",
            "target": "decorators_delta.removed",
            "operator": "excludes_all",
            "expected": [{"decorator": decorator} for decorator in AUTH_GUARD_DECORATORS],
            "severity": "hard",
            "unknown_policy": "fail",
        }
    )
    return payload
