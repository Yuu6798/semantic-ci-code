"""Merge intent sources for `init --recipe --from-*` (CSCI-42).

Implements the source strength + precedence rules from
`docs/brief_8_planning.md §6.2.3` and the four conflict categories
C1〜C4. C2 (intra-label conflict) is detected upstream in
`labels.py`; this module raises C1, C3, and C4.

The output (`MergedSources`) is what recipe modules consume to emit a
deterministic constraint set. The merger does **no** YAML emission and
no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_ci_code.authoring.sources.pr_body import (
    EXPECTED_API_TITLE,
    REMOVED_API_TITLE,
    TEST_CASES_TITLE,
    ParsedSections,
)
from semantic_ci_code.domain.state_schema import ChangeKind

RECIPE_FEATURE_ADD_API = "feature:add-api"
RECIPE_BUGFIX_REGRESSION_TEST = "bugfix:regression-test"
RECIPE_REFACTOR_PRESERVE_API = "refactor:preserve-api-with-allowlist"
RECIPE_TEST_UPDATE_ADD_TEST_CASE = "test-update:add-test-case"

RECIPE_TO_PRIMARY_KIND: dict[str, ChangeKind] = {
    RECIPE_FEATURE_ADD_API: ChangeKind.FEATURE,
    RECIPE_BUGFIX_REGRESSION_TEST: ChangeKind.BUGFIX,
    RECIPE_REFACTOR_PRESERVE_API: ChangeKind.REFACTOR,
    RECIPE_TEST_UPDATE_ADD_TEST_CASE: ChangeKind.TEST_UPDATE,
}

# Per-recipe consumption of intent-declaring section content.
# Sections producing content of a kind not in this set raise C4.
_API_FQN = "api_fqn"
_TEST_ID = "test_id"

RECIPE_CONSUMES: dict[str, frozenset[str]] = {
    RECIPE_FEATURE_ADD_API: frozenset({_API_FQN, _TEST_ID}),
    RECIPE_BUGFIX_REGRESSION_TEST: frozenset({_TEST_ID}),
    RECIPE_REFACTOR_PRESERVE_API: frozenset(),
    RECIPE_TEST_UPDATE_ADD_TEST_CASE: frozenset({_TEST_ID}),
}

CANONICAL_SURFACE_ORDER: tuple[str, ...] = (
    "user_input",
    "pr_body",
    "issue",
    "labels",
    "commits",
)


class MergeError(ValueError):
    """Base class for C1 / C3 / C4 conflict errors."""


class RecipeFlagCompatibilityError(MergeError):
    """Flags supplied are incompatible with the chosen recipe.

    Distinct from C1〜C4 because the conflict is between user-input
    flags and the recipe ID itself, not between sources.
    """


@dataclass(frozen=True)
class MergedSources:
    """The deterministic merge product passed to recipe modules."""

    recipe_id: str
    primary_kind: ChangeKind
    api_fqns: tuple[str, ...]
    test_ids: tuple[str, ...]
    allow_fqns: tuple[str, ...]
    allow_fqn_prefixes: tuple[str, ...]
    declared_at: str | None
    source_surfaces: tuple[str, ...]


def _dedup_ordered(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _consumes(recipe_id: str, content_kind: str) -> bool:
    return content_kind in RECIPE_CONSUMES[recipe_id]


def _check_recipe_flag_compatibility(
    *,
    recipe_id: str,
    explicit_add_api: tuple[str, ...],
    explicit_allow_fqns: tuple[str, ...],
    explicit_allow_fqn_prefixes: tuple[str, ...],
) -> None:
    if explicit_add_api and not _consumes(recipe_id, _API_FQN):
        msg = (
            f"--add-api is only valid with --recipe {RECIPE_FEATURE_ADD_API}; "
            f"current recipe is {recipe_id!r}, which does not declare "
            f"public-API additions"
        )
        raise RecipeFlagCompatibilityError(msg)

    if (
        explicit_allow_fqns or explicit_allow_fqn_prefixes
    ) and recipe_id != RECIPE_REFACTOR_PRESERVE_API:
        msg = (
            f"--allow-fqn / --allow-fqn-prefix are only valid with "
            f"--recipe {RECIPE_REFACTOR_PRESERVE_API}; current recipe is "
            f"{recipe_id!r}"
        )
        raise RecipeFlagCompatibilityError(msg)


def _check_labels_consistency(
    *,
    recipe_id: str,
    recipe_primary_kind: ChangeKind,
    labels_kind: ChangeKind | None,
) -> None:
    """C1 — labels primary_kind vs recipe primary_kind."""
    if labels_kind is None or labels_kind == recipe_primary_kind:
        return
    msg = (
        f"recipe {recipe_id!r} implies primary_kind "
        f"{recipe_primary_kind.value!r}, but label "
        f"'kind:{labels_kind.value}' contradicts; remove the conflicting "
        f"label or pick a recipe with primary_kind "
        f"{labels_kind.value!r}"
    )
    raise MergeError(msg)


def _check_commits_consistency(
    *,
    recipe_id: str,
    recipe_primary_kind: ChangeKind,
    commits_kind: ChangeKind | None,
) -> None:
    """C3 — commit Conventional-Commits prefix vs recipe primary_kind."""
    if commits_kind is None or commits_kind == recipe_primary_kind:
        return
    msg = (
        f"recipe {recipe_id!r} implies primary_kind "
        f"{recipe_primary_kind.value!r}, but commit Conventional-Commits "
        f"prefix implies {commits_kind.value!r}; remove the contradicting "
        f"commit(s) or pick a recipe with primary_kind "
        f"{commits_kind.value!r}"
    )
    raise MergeError(msg)


def _check_unconsumed_sections(
    *,
    recipe_id: str,
    surface_label: str,
    parsed: ParsedSections | None,
) -> None:
    """C4 — intent-declaring sections that the recipe does not consume."""
    if parsed is None:
        return

    if parsed.unclassified:
        title, value = parsed.unclassified[0]
        msg = (
            f"unconsumed intent-declaring section: {title} in "
            f"{surface_label} contains an unclassifiable bullet "
            f"{value!r}; bullets must be canonical test IDs "
            f"('path/to/test_x.py::test_y') or dotted FQNs "
            f"('pkg.module.symbol'). Silent guess is forbidden."
        )
        raise MergeError(msg)

    if parsed.removed_api_fqns:
        msg = (
            f"unconsumed intent-declaring section: {REMOVED_API_TITLE} in "
            f"{surface_label} declares "
            f"{list(parsed.removed_api_fqns)!r}, but no Brief 8 recipe "
            f"consumes 'removed public API'. Remove the section or wait "
            f"for a future recipe that declares public-API removals."
        )
        raise MergeError(msg)

    if parsed.api_fqns and not _consumes(recipe_id, _API_FQN):
        msg = (
            f"unconsumed intent-declaring section: {EXPECTED_API_TITLE} in "
            f"{surface_label} declares "
            f"{list(parsed.api_fqns)!r}, but recipe {recipe_id!r} does "
            f"not consume public-API additions. Use --recipe "
            f"{RECIPE_FEATURE_ADD_API} or remove the section."
        )
        raise MergeError(msg)

    if parsed.test_ids and not _consumes(recipe_id, _TEST_ID):
        msg = (
            f"unconsumed intent-declaring section: {TEST_CASES_TITLE} in "
            f"{surface_label} declares "
            f"{list(parsed.test_ids)!r}, but recipe {recipe_id!r} does "
            f"not consume test cases. Use a different recipe or remove "
            f"the section."
        )
        raise MergeError(msg)


def merge_sources(
    *,
    recipe_id: str,
    explicit_add_api: tuple[str, ...],
    explicit_test_cases: tuple[str, ...],
    explicit_allow_fqns: tuple[str, ...],
    explicit_allow_fqn_prefixes: tuple[str, ...],
    declared_at: str | None,
    pr_body: ParsedSections | None,
    issue: ParsedSections | None,
    labels_kind: ChangeKind | None,
    commits_kind: ChangeKind | None,
    labels_consulted: bool,
    commits_consulted: bool,
) -> MergedSources:
    """Merge all source layers into a `MergedSources` for a recipe.

    Strength layers per `docs/brief_8_planning.md §6.2.2`:

      - strong : CLI explicit flags ∪ PR body
      - medium : issue body (consulted only when strong layer is empty)
      - weak   : commit Conventional Commits prefix (primary_kind hint only)

    The merger never derives values from `candidate` code under review;
    `--allow-candidate-derived-expectations` does not exist in this brief.

    Raises:
      RecipeFlagCompatibilityError: --add-api / --allow-fqn(-prefix) flag
        is not consumed by the chosen recipe.
      MergeError: C1 (labels), C3 (commits), or C4 (unconsumed
        intent-declaring section).
    """
    if recipe_id not in RECIPE_TO_PRIMARY_KIND:
        valid = ", ".join(sorted(RECIPE_TO_PRIMARY_KIND))
        msg = f"unknown recipe {recipe_id!r}; valid recipes: {valid}"
        raise ValueError(msg)

    primary_kind = RECIPE_TO_PRIMARY_KIND[recipe_id]

    _check_recipe_flag_compatibility(
        recipe_id=recipe_id,
        explicit_add_api=explicit_add_api,
        explicit_allow_fqns=explicit_allow_fqns,
        explicit_allow_fqn_prefixes=explicit_allow_fqn_prefixes,
    )

    _check_labels_consistency(
        recipe_id=recipe_id,
        recipe_primary_kind=primary_kind,
        labels_kind=labels_kind,
    )
    _check_commits_consistency(
        recipe_id=recipe_id,
        recipe_primary_kind=primary_kind,
        commits_kind=commits_kind,
    )
    _check_unconsumed_sections(recipe_id=recipe_id, surface_label="PR body", parsed=pr_body)
    _check_unconsumed_sections(recipe_id=recipe_id, surface_label="issue body", parsed=issue)

    pr_api_fqns = pr_body.api_fqns if pr_body is not None else ()
    pr_test_ids = pr_body.test_ids if pr_body is not None else ()
    issue_api_fqns = issue.api_fqns if issue is not None else ()
    issue_test_ids = issue.test_ids if issue is not None else ()

    # §6.2.3 fallback chain: the strong layer's cutoff is applied to the
    # layer as a whole, not per-field. If ANY positive expectation lands
    # in the strong layer (explicit-input flags or PR body content), the
    # issue body is no longer consulted for content — only for surface
    # provenance. Per-field fallback would silently union across layers
    # and violate the brief's "層を跨いで union しない" rule (Codex
    # review on PR #84).
    strong_has_positive_expectation = bool(
        explicit_add_api
        or explicit_test_cases
        or explicit_allow_fqns
        or explicit_allow_fqn_prefixes
        or pr_api_fqns
        or pr_test_ids
    )

    if strong_has_positive_expectation:
        api_fqns = _dedup_ordered(explicit_add_api + pr_api_fqns)
        test_ids = _dedup_ordered(explicit_test_cases + pr_test_ids)
    else:
        api_fqns = _dedup_ordered(issue_api_fqns)
        test_ids = _dedup_ordered(issue_test_ids)

    allow_fqns = _dedup_ordered(explicit_allow_fqns)
    allow_fqn_prefixes = _dedup_ordered(explicit_allow_fqn_prefixes)

    has_user_input = bool(
        explicit_add_api
        or explicit_test_cases
        or explicit_allow_fqns
        or explicit_allow_fqn_prefixes
        or declared_at is not None
    )

    consulted = {
        "user_input": has_user_input,
        "pr_body": pr_body is not None,
        "issue": issue is not None,
        "labels": labels_consulted,
        "commits": commits_consulted,
    }
    source_surfaces = tuple(name for name in CANONICAL_SURFACE_ORDER if consulted[name])

    return MergedSources(
        recipe_id=recipe_id,
        primary_kind=primary_kind,
        api_fqns=api_fqns,
        test_ids=test_ids,
        allow_fqns=allow_fqns,
        allow_fqn_prefixes=allow_fqn_prefixes,
        declared_at=declared_at,
        source_surfaces=source_surfaces,
    )
