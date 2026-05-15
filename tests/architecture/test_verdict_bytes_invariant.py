"""Brief 8 / CSCI-42 — INV-1 and INV-3 architecture tests.

INV-1 (Verdict bytes invariant, narrow scope): for `check` / `compare` /
`compile-repair`, the evaluator-derived fields (`verdict`, `repair_plan`,
`summary`, and the per-constraint `results`) are byte-identical across
the Brief 8 changes for the same `(target, baseline, candidate)` triple.

INV-3 (Provenance non-participation invariant, narrow scope): changing
`authorship.generation_metadata` in target.yaml (the values, the
presence of optional keys) does NOT alter the evaluator-derived fields.
`target_authorship` itself is excluded because it intentionally
reflects authorship.

This test materialises a virtual baseline / candidate pair, runs
`compare` twice with two different `generation_metadata` blocks, and
asserts the evaluator-derived projection is byte-identical between the
two runs. It does not assert hashes against a committed fixture (which
would be brittle across Python versions), only that the two
recipe-generated runs agree with each other and with a hand-written
target that omits `generation_metadata` entirely.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.cli.helpers import run_semantic_ci

# Fields that the evaluator decides. These are what INV-1 / INV-3
# protect: their bytes must be stable across (a) Brief 8 module
# additions and (b) any variation in `target_authorship`.
VERDICT_FIELDS: tuple[str, ...] = ("verdict", "summary", "results", "repair_plan")


def _evaluator_derived_bytes(payload: dict) -> bytes:
    projection = {key: payload.get(key) for key in VERDICT_FIELDS}
    return json.dumps(projection, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _evaluator_derived_hash(payload: dict) -> str:
    return hashlib.sha256(_evaluator_derived_bytes(payload)).hexdigest()


def _materialise_virtual_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Materialise a tiny `mod.py` pair where candidate adds `added()`."""
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()

    (baseline / "__init__.py").write_text("", encoding="utf-8")
    (candidate / "__init__.py").write_text("", encoding="utf-8")
    (baseline / "mod.py").write_text(
        "VALUE = 1\n\n\ndef existing() -> int:\n    return VALUE\n",
        encoding="utf-8",
    )
    (candidate / "mod.py").write_text(
        "VALUE = 1\n\n\ndef existing() -> int:\n    return VALUE\n\n\n"
        "def added() -> int:\n    return VALUE + 1\n",
        encoding="utf-8",
    )
    return baseline, candidate


def _hand_written_target() -> str:
    """A hand-written target.yaml that omits `generation_metadata` entirely.

    Matches the constraint shape that `feature:add-api` recipe emits so
    the three target variants in INV-3 share an evaluator-derived
    output.
    """
    return (
        'intent: ""\n'
        "change:\n"
        "  primary_kind: feature\n"
        "constraints:\n"
        "  - id: recipe:feature:add-api:api_surface_delta_added\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        "    expected:\n"
        "      - fqn: mod.added\n"
        "        visibility: public\n"
    )


def _recipe_target(recipe_id: str) -> str:
    """A target.yaml with a populated `generation_metadata` block.

    Identical evaluator semantics to `_hand_written_target` — only the
    `authorship` block differs.
    """
    return (
        'intent: ""\n'
        "change:\n"
        "  primary_kind: feature\n"
        "authorship:\n"
        "  generation_metadata:\n"
        "    tool: semantic-ci-init\n"
        "    tool_version: 0.0.0\n"
        f"    recipe: {recipe_id}\n"
        "    source_surfaces:\n"
        "      - user_input\n"
        "    candidate_code_used: false\n"
        "    llm_used: false\n"
        "constraints:\n"
        "  - id: recipe:feature:add-api:api_surface_delta_added\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        "    expected:\n"
        "      - fqn: mod.added\n"
        "        visibility: public\n"
    )


def _run_compare(tmp_path: Path, target_path: Path, baseline: Path, candidate: Path) -> dict:
    result = run_semantic_ci(
        tmp_path,
        "compare",
        "--baseline-dir",
        str(baseline),
        "--candidate-dir",
        str(candidate),
        "--target",
        str(target_path),
        "--format",
        "json",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_inv1_verdict_bytes_stable_across_metadata_variants(tmp_path: Path):
    """INV-1: the evaluator-derived bytes must be byte-identical for two
    target.yaml files that differ only in `generation_metadata`.
    """
    baseline, candidate = _materialise_virtual_pair(tmp_path)

    target_a = tmp_path / "target_a.yaml"
    target_a.write_text(_recipe_target("feature:add-api"), encoding="utf-8")
    target_b = tmp_path / "target_b.yaml"
    target_b.write_text(_recipe_target("feature:add-api-variant"), encoding="utf-8")

    payload_a = _run_compare(tmp_path, target_a, baseline, candidate)
    payload_b = _run_compare(tmp_path, target_b, baseline, candidate)

    assert _evaluator_derived_hash(payload_a) == _evaluator_derived_hash(payload_b)


def test_inv3_provenance_block_absence_or_presence_does_not_affect_verdict(
    tmp_path: Path,
):
    """INV-3: a hand-written target (no `generation_metadata`) and a
    recipe-generated target (with `generation_metadata`) yield identical
    evaluator-derived output for the same `(baseline, candidate)` pair.
    """
    baseline, candidate = _materialise_virtual_pair(tmp_path)

    target_hand = tmp_path / "target_hand.yaml"
    target_hand.write_text(_hand_written_target(), encoding="utf-8")
    target_recipe = tmp_path / "target_recipe.yaml"
    target_recipe.write_text(_recipe_target("feature:add-api"), encoding="utf-8")

    payload_hand = _run_compare(tmp_path, target_hand, baseline, candidate)
    payload_recipe = _run_compare(tmp_path, target_recipe, baseline, candidate)

    assert _evaluator_derived_hash(payload_hand) == _evaluator_derived_hash(payload_recipe)


def test_inv3_target_authorship_reflected_but_excluded_from_verdict(tmp_path: Path):
    """The `target_authorship` field DOES change between hand-written and
    recipe-generated targets — that's the surface's whole point. INV-1 /
    INV-3 specifically exclude `target_authorship`, so the difference
    must show up there and only there.
    """
    baseline, candidate = _materialise_virtual_pair(tmp_path)

    target_hand = tmp_path / "target_hand.yaml"
    target_hand.write_text(_hand_written_target(), encoding="utf-8")
    target_recipe = tmp_path / "target_recipe.yaml"
    target_recipe.write_text(_recipe_target("feature:add-api"), encoding="utf-8")

    payload_hand = _run_compare(tmp_path, target_hand, baseline, candidate)
    payload_recipe = _run_compare(tmp_path, target_recipe, baseline, candidate)

    # target_authorship differs (reflects provenance)
    assert payload_hand.get("target_authorship") != payload_recipe.get("target_authorship")
    recipe_auth = payload_recipe["target_authorship"]
    assert recipe_auth.get("generation_metadata") is not None

    # but evaluator-derived fields don't (the whole point of INV-3)
    assert _evaluator_derived_hash(payload_hand) == _evaluator_derived_hash(payload_recipe)
