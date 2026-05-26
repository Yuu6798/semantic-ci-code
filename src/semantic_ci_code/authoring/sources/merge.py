"""Source merge + C1〜C4 conflict detection for `init --recipe`.

See `docs/brief_8_planning.md §6.2.3` for the precedence rules.
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
    pass


class RecipeFlagCompatibilityError(MergeError):
    pass


@dataclass(frozen=True)
class MergedSources:
    recipe_id: str
    primary_kind: ChangeKind
    intent: str
    api_fqns: tuple[str, ...]
    test_ids: tuple[str, ...]
    allow_fqns: tuple[str, ...]
    allow_fqn_prefixes: tuple[str, ...]
    declared_at: str | None
    source_surfaces: tuple[str, ...]


def _dedup_ordered(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _check_unconsumed_sections(
    recipe_id: str, surface_label: str, parsed: ParsedSections | None
) -> None:
    if parsed is None:
        return

    if parsed.unclassified:
        title, value = parsed.unclassified[0]
        raise MergeError(
            f"unconsumed intent-declaring section: {title} in {surface_label} "
            f"contains an unclassifiable bullet {value!r}; bullets must be canonical "
            f"test IDs ('path/to/test_x.py::test_y') or dotted FQNs ('pkg.module.symbol')"
        )

    consumes = RECIPE_CONSUMES[recipe_id]

    if parsed.removed_api_fqns:
        raise MergeError(
            f"unconsumed intent-declaring section: {REMOVED_API_TITLE} in {surface_label} "
            f"declares {list(parsed.removed_api_fqns)!r}, but no Brief 8 recipe consumes "
            f"'removed public API'"
        )

    if parsed.api_fqns and _API_FQN not in consumes:
        raise MergeError(
            f"unconsumed intent-declaring section: {EXPECTED_API_TITLE} in {surface_label} "
            f"declares {list(parsed.api_fqns)!r}, but recipe {recipe_id!r} does not consume "
            f"public-API additions. Use --recipe {RECIPE_FEATURE_ADD_API} or remove the section"
        )

    if parsed.test_ids and _TEST_ID not in consumes:
        raise MergeError(
            f"unconsumed intent-declaring section: {TEST_CASES_TITLE} in {surface_label} "
            f"declares {list(parsed.test_ids)!r}, but recipe {recipe_id!r} does not consume "
            f"test cases"
        )


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
    intent: str = "",
) -> MergedSources:
    if recipe_id not in RECIPE_TO_PRIMARY_KIND:
        valid = ", ".join(sorted(RECIPE_TO_PRIMARY_KIND))
        raise ValueError(f"unknown recipe {recipe_id!r}; valid recipes: {valid}")

    primary_kind = RECIPE_TO_PRIMARY_KIND[recipe_id]
    consumes = RECIPE_CONSUMES[recipe_id]

    if explicit_add_api and _API_FQN not in consumes:
        raise RecipeFlagCompatibilityError(
            f"--add-api is only valid with --recipe {RECIPE_FEATURE_ADD_API}; "
            f"current recipe is {recipe_id!r}"
        )
    if explicit_test_cases and _TEST_ID not in consumes:
        raise RecipeFlagCompatibilityError(
            f"--test-case is only valid with recipes that consume test cases; "
            f"current recipe {recipe_id!r} would silently drop the declared test IDs"
        )
    if (
        explicit_allow_fqns or explicit_allow_fqn_prefixes
    ) and recipe_id != RECIPE_REFACTOR_PRESERVE_API:
        raise RecipeFlagCompatibilityError(
            f"--allow-fqn / --allow-fqn-prefix are only valid with "
            f"--recipe {RECIPE_REFACTOR_PRESERVE_API}; current recipe is {recipe_id!r}"
        )

    if labels_kind is not None and labels_kind != primary_kind:
        raise MergeError(
            f"recipe {recipe_id!r} implies primary_kind {primary_kind.value!r}, "
            f"but label 'kind:{labels_kind.value}' contradicts"
        )
    if commits_kind is not None and commits_kind != primary_kind:
        raise MergeError(
            f"recipe {recipe_id!r} implies primary_kind {primary_kind.value!r}, "
            f"but commit Conventional-Commits prefix implies {commits_kind.value!r}"
        )

    _check_unconsumed_sections(recipe_id, "PR body", pr_body)
    _check_unconsumed_sections(recipe_id, "issue body", issue)

    pr_api_fqns = pr_body.api_fqns if pr_body is not None else ()
    pr_test_ids = pr_body.test_ids if pr_body is not None else ()
    issue_api_fqns = issue.api_fqns if issue is not None else ()
    issue_test_ids = issue.test_ids if issue is not None else ()

    # §6.2.3: layer-wide cutoff. If any positive expectation lands in the
    # strong layer, the medium layer is consulted only for provenance.
    strong_has_content = bool(
        explicit_add_api
        or explicit_test_cases
        or explicit_allow_fqns
        or explicit_allow_fqn_prefixes
        or pr_api_fqns
        or pr_test_ids
    )
    if strong_has_content:
        api_fqns = _dedup_ordered(explicit_add_api + pr_api_fqns)
        test_ids = _dedup_ordered(explicit_test_cases + pr_test_ids)
    else:
        api_fqns = _dedup_ordered(issue_api_fqns)
        test_ids = _dedup_ordered(issue_test_ids)

    consulted = {
        "user_input": bool(
            explicit_add_api
            or explicit_test_cases
            or explicit_allow_fqns
            or explicit_allow_fqn_prefixes
            or declared_at is not None
        ),
        "pr_body": pr_body is not None,
        "issue": issue is not None,
        "labels": labels_consulted,
        "commits": commits_consulted,
    }
    source_surfaces = tuple(name for name in CANONICAL_SURFACE_ORDER if consulted[name])

    return MergedSources(
        recipe_id=recipe_id,
        primary_kind=primary_kind,
        intent=intent,
        api_fqns=api_fqns,
        test_ids=test_ids,
        allow_fqns=_dedup_ordered(explicit_allow_fqns),
        allow_fqn_prefixes=_dedup_ordered(explicit_allow_fqn_prefixes),
        declared_at=declared_at,
        source_surfaces=source_surfaces,
    )
