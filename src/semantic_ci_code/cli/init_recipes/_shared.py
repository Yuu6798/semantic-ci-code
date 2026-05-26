"""Recipe payload builders shared across the four recipe modules."""

from __future__ import annotations

from typing import Any

from semantic_ci_code.authoring.provenance import build_generation_metadata
from semantic_ci_code.authoring.sources.merge import MergedSources


def empty_recipe_payload(merged: MergedSources) -> dict[str, Any]:
    generation_metadata = build_generation_metadata(
        recipe_id=merged.recipe_id,
        source_surfaces=merged.source_surfaces,
    )
    authorship: dict[str, Any] = {}
    if merged.declared_at is not None:
        authorship["declared_at"] = merged.declared_at
    authorship["generation_metadata"] = generation_metadata

    return {
        "intent": merged.intent,
        "change": {"primary_kind": merged.primary_kind.value},
        "authorship": authorship,
        "constraints": [],
    }


def append_new_cases_constraint(
    payload: dict[str, Any],
    *,
    constraint_id: str,
    test_ids: tuple[str, ...],
) -> None:
    if test_ids:
        payload["constraints"].append(
            {
                "id": constraint_id,
                "kind": "delta",
                "target": "test_surface_delta.new_cases",
                "operator": "includes_all",
                "expected": list(test_ids),
            }
        )
    else:
        payload["constraints"].append(
            {
                "id": constraint_id,
                "kind": "delta",
                "target": "test_surface_delta.new_cases",
                "operator": "not_equals",
                "expected": [],
            }
        )
