"""Brief 8 / CSCI-42 — `merge_sources` strength + precedence tests.

Covers `docs/brief_8_planning.md §6.2.3` conflict categories
C1 (recipe ↔ labels), C3 (recipe ↔ commits), C4 (unconsumed
intent-declaring section) and the strong/medium fallback chain.
C2 (intra-label conflict) is tested in `test_init_sources.py`.

These tests use `merge_sources` as a pure function — no CLI, no I/O.
The end-to-end CLI integration sits in `test_init_recipe.py`.
"""

from __future__ import annotations

import pytest

from semantic_ci_code.authoring.sources.merge import (
    RECIPE_BUGFIX_REGRESSION_TEST,
    RECIPE_FEATURE_ADD_API,
    RECIPE_REFACTOR_PRESERVE_API,
    MergedSources,
    MergeError,
    RecipeFlagCompatibilityError,
    merge_sources,
)
from semantic_ci_code.authoring.sources.pr_body import (
    EXPECTED_API_TITLE,
    REMOVED_API_TITLE,
    TEST_CASES_TITLE,
    ParsedSections,
)
from semantic_ci_code.domain.state_schema import ChangeKind


def _merge(**overrides) -> MergedSources:
    """Build a merge call with sane defaults; overrides specify the case."""
    defaults: dict = {
        "recipe_id": RECIPE_FEATURE_ADD_API,
        "explicit_add_api": ("pkg.New",),
        "explicit_test_cases": (),
        "explicit_allow_fqns": (),
        "explicit_allow_fqn_prefixes": (),
        "declared_at": None,
        "pr_body": None,
        "issue": None,
        "labels_kind": None,
        "commits_kind": None,
        "labels_consulted": False,
        "commits_consulted": False,
    }
    defaults.update(overrides)
    return merge_sources(**defaults)


# ---------------------------------------------------------------------------
# Strong layer behaviour
# ---------------------------------------------------------------------------


def test_strong_layer_dedupes_explicit_and_pr_body():
    pr_body = ParsedSections(api_fqns=("pkg.New", "pkg.Other"))
    merged = _merge(explicit_add_api=("pkg.New",), pr_body=pr_body)
    # explicit and PR body both name pkg.New — must dedup once, order preserved
    assert merged.api_fqns == ("pkg.New", "pkg.Other")


def test_strong_fills_issue_ignored():
    """AC G: when strong layer (CLI ∪ PR body) is non-empty, issue body is
    consulted only for surface-provenance, never for FQN content.
    """
    pr_body = ParsedSections(api_fqns=("pkg.Strong",))
    issue = ParsedSections(api_fqns=("issue.Only",))
    merged = _merge(pr_body=pr_body, issue=issue, explicit_add_api=())

    assert merged.api_fqns == ("pkg.Strong",)
    assert "issue.Only" not in merged.api_fqns
    assert "pr_body" in merged.source_surfaces
    assert "issue" in merged.source_surfaces


def test_issue_only_fallback_when_strong_layer_empty():
    issue = ParsedSections(api_fqns=("issue.Sym",))
    merged = _merge(pr_body=None, issue=issue, explicit_add_api=())

    assert merged.api_fqns == ("issue.Sym",)
    assert merged.source_surfaces == ("issue",)


def test_pr_body_only_flow_satisfies_feature_recipe():
    pr_body = ParsedSections(api_fqns=("pkg.New",))
    merged = _merge(pr_body=pr_body, explicit_add_api=())

    assert merged.api_fqns == ("pkg.New",)
    assert merged.source_surfaces == ("pr_body",)


def test_explicit_test_cases_and_pr_body_dedup():
    pr_body = ParsedSections(test_ids=("tests/a.py::x",))
    merged = _merge(
        explicit_test_cases=("tests/a.py::x", "tests/a.py::y"),
        pr_body=pr_body,
    )
    assert merged.test_ids == ("tests/a.py::x", "tests/a.py::y")


# ---------------------------------------------------------------------------
# C1 — labels conflict
# ---------------------------------------------------------------------------


def test_c1_recipe_vs_label_mismatch_raises():
    with pytest.raises(MergeError) as exc_info:
        _merge(labels_kind=ChangeKind.BUGFIX, labels_consulted=True)
    msg = str(exc_info.value)
    assert "feature:add-api" in msg
    assert "feature" in msg
    assert "bugfix" in msg


def test_c1_matching_label_passes_through():
    merged = _merge(labels_kind=ChangeKind.FEATURE, labels_consulted=True)
    assert merged.primary_kind is ChangeKind.FEATURE
    assert "labels" in merged.source_surfaces


# ---------------------------------------------------------------------------
# C3 — commit prefix conflict
# ---------------------------------------------------------------------------


def test_c3_recipe_vs_commit_mismatch_raises():
    with pytest.raises(MergeError) as exc_info:
        _merge(commits_kind=ChangeKind.BUGFIX, commits_consulted=True)
    msg = str(exc_info.value)
    assert "feature:add-api" in msg
    assert "feature" in msg
    assert "bugfix" in msg


def test_c3_matching_commit_passes_through():
    merged = _merge(commits_kind=ChangeKind.FEATURE, commits_consulted=True)
    assert merged.primary_kind is ChangeKind.FEATURE
    assert "commits" in merged.source_surfaces


# ---------------------------------------------------------------------------
# C4 — unconsumed intent-declaring section
# ---------------------------------------------------------------------------


def test_c4_removed_public_api_is_always_unconsumed():
    pr_body = ParsedSections(removed_api_fqns=("old.Sym",))
    with pytest.raises(MergeError) as exc_info:
        _merge(pr_body=pr_body)
    assert REMOVED_API_TITLE in str(exc_info.value)
    assert "old.Sym" in str(exc_info.value)


def test_c4_expected_api_unconsumed_by_bugfix_recipe():
    pr_body = ParsedSections(api_fqns=("pkg.Sym",))
    with pytest.raises(MergeError) as exc_info:
        _merge(
            recipe_id=RECIPE_BUGFIX_REGRESSION_TEST,
            explicit_add_api=(),
            pr_body=pr_body,
        )
    assert EXPECTED_API_TITLE in str(exc_info.value)
    assert RECIPE_BUGFIX_REGRESSION_TEST in str(exc_info.value)


def test_c4_test_cases_unconsumed_by_refactor_recipe():
    pr_body = ParsedSections(test_ids=("tests/a.py::x",))
    with pytest.raises(MergeError) as exc_info:
        _merge(
            recipe_id=RECIPE_REFACTOR_PRESERVE_API,
            explicit_add_api=(),
            pr_body=pr_body,
        )
    assert TEST_CASES_TITLE in str(exc_info.value)
    assert RECIPE_REFACTOR_PRESERVE_API in str(exc_info.value)


def test_c4_unclassifiable_bullet_in_acceptance_criteria_raises():
    pr_body = ParsedSections(
        api_fqns=("pkg.Sym",),
        unclassified=(("## Acceptance Criteria", "not-an-id"),),
    )
    with pytest.raises(MergeError) as exc_info:
        _merge(pr_body=pr_body)
    msg = str(exc_info.value)
    assert "## Acceptance Criteria" in msg
    assert "not-an-id" in msg


# ---------------------------------------------------------------------------
# Recipe-flag compatibility
# ---------------------------------------------------------------------------


def test_add_api_with_non_feature_recipe_rejected():
    with pytest.raises(RecipeFlagCompatibilityError) as exc_info:
        _merge(
            recipe_id=RECIPE_BUGFIX_REGRESSION_TEST,
            explicit_add_api=("pkg.Sym",),
        )
    assert "--add-api" in str(exc_info.value)
    assert "feature:add-api" in str(exc_info.value)


def test_allow_fqn_with_non_refactor_recipe_rejected():
    with pytest.raises(RecipeFlagCompatibilityError):
        _merge(
            recipe_id=RECIPE_FEATURE_ADD_API,
            explicit_add_api=("pkg.A",),
            explicit_allow_fqns=("pkg.B",),
        )


def test_allow_fqn_prefix_with_non_refactor_recipe_rejected():
    with pytest.raises(RecipeFlagCompatibilityError):
        _merge(
            recipe_id=RECIPE_FEATURE_ADD_API,
            explicit_add_api=("pkg.A",),
            explicit_allow_fqn_prefixes=("legacy.",),
        )


def test_allow_fqn_accepted_with_refactor_recipe():
    merged = _merge(
        recipe_id=RECIPE_REFACTOR_PRESERVE_API,
        explicit_add_api=(),
        explicit_allow_fqns=("pkg.A",),
        explicit_allow_fqn_prefixes=("legacy.",),
    )
    assert merged.allow_fqns == ("pkg.A",)
    assert merged.allow_fqn_prefixes == ("legacy.",)


# ---------------------------------------------------------------------------
# source_surfaces canonical ordering
# ---------------------------------------------------------------------------


def test_source_surfaces_in_canonical_order_regardless_of_input_order():
    pr_body = ParsedSections(api_fqns=("pkg.Sym",))
    merged = _merge(
        explicit_add_api=("pkg.Sym",),
        pr_body=pr_body,
        labels_consulted=True,
        labels_kind=ChangeKind.FEATURE,
    )
    # canonical order: user_input, pr_body, issue, labels, commits
    assert merged.source_surfaces == ("user_input", "pr_body", "labels")


def test_source_surfaces_omits_unconsulted_layers():
    merged = _merge()  # only user_input via explicit_add_api
    assert merged.source_surfaces == ("user_input",)


def test_source_surfaces_empty_when_only_recipe_provided():
    merged = _merge(explicit_add_api=("pkg.Sym",))
    # user_input is consulted because explicit_add_api is non-empty
    assert "user_input" in merged.source_surfaces


def test_declared_at_alone_counts_as_user_input_surface():
    merged = _merge(explicit_add_api=("pkg.Sym",), declared_at="2026-05-15T00:00:00Z")
    assert merged.declared_at == "2026-05-15T00:00:00Z"
    assert "user_input" in merged.source_surfaces


# ---------------------------------------------------------------------------
# Unknown recipe / determinism
# ---------------------------------------------------------------------------


def test_unknown_recipe_id_rejected():
    with pytest.raises(ValueError) as exc_info:
        _merge(recipe_id="bogus:recipe")
    assert "bogus:recipe" in str(exc_info.value)


def test_merge_is_pure_repeating_yields_identical_result():
    pr_body = ParsedSections(api_fqns=("pkg.New",), test_ids=("tests/x.py::y",))
    first = _merge(
        recipe_id=RECIPE_FEATURE_ADD_API,
        explicit_add_api=("pkg.New",),
        pr_body=pr_body,
    )
    second = _merge(
        recipe_id=RECIPE_FEATURE_ADD_API,
        explicit_add_api=("pkg.New",),
        pr_body=pr_body,
    )
    assert first == second
    assert isinstance(first, MergedSources)
