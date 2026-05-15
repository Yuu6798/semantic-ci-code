"""Provenance metadata builder for `init --recipe` paths.

Section F of `docs/target_authoring_surface.md`: `generation_metadata` is
populated only on generator paths. The block is **absent** on plain
`semantic-ci init` and hand-written target.yaml files. In Brief 8 the
recorded `candidate_code_used` and `llm_used` fields are always `false`
(no candidate-derived expectations, no LLM path — Brief 8b would
revisit `llm_used`).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

PACKAGE_NAME = "semantic-ci-code"
TOOL_NAME = "semantic-ci-init"
UNKNOWN_VERSION = "0.0.0+unknown"


def _resolved_tool_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def build_generation_metadata(
    *,
    recipe_id: str,
    source_surfaces: tuple[str, ...],
) -> dict[str, Any]:
    """Build the `authorship.generation_metadata` dict for a recipe run.

    `tool_version` is resolved statically from package metadata so output
    is wall-clock and git-ref independent.

    `source_surfaces` is a tuple of surface identifiers consulted during
    generation, ordered: `user_input` first if any explicit-input flag
    was given, then `pr_body` / `issue` / `labels` / `commits` in the
    order their `--from-*` flags appeared in the canonical list.

    `candidate_code_used` and `llm_used` are fixed `False` sentinels in
    Brief 8 — they make the provenance invariant visible to operators and
    must remain `False` until a future brief negotiates the boundary
    against `docs/code_semantic_ci_design.md §23.3`.
    """
    return {
        "tool": TOOL_NAME,
        "tool_version": _resolved_tool_version(),
        "recipe": recipe_id,
        "source_surfaces": list(source_surfaces),
        "candidate_code_used": False,
        "llm_used": False,
    }
