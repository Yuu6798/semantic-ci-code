"""Recipe `security:deny-dangerous-effects`."""

from __future__ import annotations

from typing import Any

from semantic_ci_code.authoring.sources.merge import MergedSources
from semantic_ci_code.cli.init_recipes._shared import empty_recipe_payload

DANGEROUS_EFFECT_CLASSES: tuple[str, ...] = (
    "process",
    "dynamic_code",
    "unsafe_deserialize",
)


def build(merged: MergedSources) -> dict[str, Any]:
    payload = empty_recipe_payload(merged)
    payload["constraints"].append(
        {
            "id": "security:deny-dangerous-effects",
            "kind": "delta",
            "target": "effect_changes.added",
            "operator": "excludes_all",
            "expected": [
                {"effect_class": effect_class} for effect_class in DANGEROUS_EFFECT_CLASSES
            ],
        }
    )
    return payload
