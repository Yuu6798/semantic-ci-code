"""Recipe `security:deny-dangerous-imports`."""

from __future__ import annotations

from typing import Any

from semantic_ci_code.authoring.sources.merge import MergedSources
from semantic_ci_code.cli.init_recipes._shared import empty_recipe_payload

DANGEROUS_IMPORT_MODULES: tuple[str, ...] = (
    "pickle",
    "subprocess",
    "marshal",
    "shelve",
    "dill",
)


def build(merged: MergedSources) -> dict[str, Any]:
    payload = empty_recipe_payload(merged)
    payload["constraints"].append(
        {
            "id": "security:deny-dangerous-imports",
            "kind": "delta",
            "target": "imports_delta.added",
            "operator": "excludes_all",
            "expected": [{"module": module} for module in DANGEROUS_IMPORT_MODULES],
        }
    )
    return payload
