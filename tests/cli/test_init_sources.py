"""Brief 8 / CSCI-42 — input source parser tests.

Covers `authoring/sources/pr_body.py`, `issue.py`, `labels.py`, and
`commits.py` in isolation. The merger and recipe layers are exercised
in `test_init_merge.py` and `test_init_recipe.py`.
"""

from __future__ import annotations

import pytest

from semantic_ci_code.authoring.sources import (
    CommitsParseError,
    LabelsParseError,
    parse_commit_subjects,
    parse_issue_body,
    parse_kind_labels,
    parse_pr_body,
)
from semantic_ci_code.authoring.sources.pr_body import (
    ACCEPTANCE_CRITERIA_TITLE,
    EXPECTED_API_TITLE,
    REMOVED_API_TITLE,
    TEST_CASES_TITLE,
)
from semantic_ci_code.domain.state_schema import ChangeKind

# ---------------------------------------------------------------------------
# pr_body / issue parser
# ---------------------------------------------------------------------------


def test_pr_body_extracts_expected_public_api_section():
    body = """## Description
Some prose explanation.

## Expected public API
- foo.bar.NewFunc
- baz.qux.OtherSym
"""
    parsed = parse_pr_body(body)

    assert parsed.api_fqns == ("foo.bar.NewFunc", "baz.qux.OtherSym")
    assert parsed.test_ids == ()
    assert parsed.removed_api_fqns == ()
    assert parsed.unclassified == ()
    assert EXPECTED_API_TITLE in parsed.seen_section_titles


def test_pr_body_extracts_test_cases_section():
    body = """## Test cases
- tests/test_a.py::test_x
- tests/test_a.py::test_y
"""
    parsed = parse_pr_body(body)

    assert parsed.test_ids == (
        "tests/test_a.py::test_x",
        "tests/test_a.py::test_y",
    )
    assert parsed.api_fqns == ()


def test_pr_body_acceptance_criteria_splits_test_ids_and_fqns():
    body = """## Acceptance Criteria
- tests/test_new.py::test_edge_case
- foo.bar.HelperSym
- tests/test_b.py::test_other
"""
    parsed = parse_pr_body(body)

    assert parsed.test_ids == (
        "tests/test_new.py::test_edge_case",
        "tests/test_b.py::test_other",
    )
    assert parsed.api_fqns == ("foo.bar.HelperSym",)
    assert parsed.unclassified == ()


def test_pr_body_test_id_rejects_checklist_marker_leftover():
    """`- [ ] tests/test_x.py::test_y` is a common GFM checklist bullet.
    The leading `[ ]` is stripped before classification so the bullet
    surfaces as a canonical test ID (Codex review on PR #84).
    """
    body = """## Test cases
- [ ] tests/test_x.py::test_y
- [x] tests/test_x.py::test_z
"""
    parsed = parse_pr_body(body)
    assert parsed.test_ids == (
        "tests/test_x.py::test_y",
        "tests/test_x.py::test_z",
    )
    assert parsed.unclassified == ()


def test_pr_body_test_id_rejects_parametrize_brackets():
    body = """## Test cases
- tests/test_x.py::test_func[case1]
"""
    parsed = parse_pr_body(body)
    assert parsed.test_ids == ()
    assert parsed.unclassified == ((TEST_CASES_TITLE, "tests/test_x.py::test_func[case1]"),)


def test_pr_body_test_id_accepts_class_based_pytest_id():
    """The extractor emits `test_function` as `Class::method` for
    class-based tests (`python_test_surface_extractor.py:190`), so
    `_test_case_id` produces `path::Class::method`. The parser must
    accept that form (Codex review on PR #84).
    """
    body = """## Test cases
- tests/test_x.py::TestClass::test_method
"""
    parsed = parse_pr_body(body)
    assert parsed.test_ids == ("tests/test_x.py::TestClass::test_method",)


def test_pr_body_unclassifiable_bullet_recorded():
    body = """## Acceptance Criteria
- not-an-id-or-fqn
"""
    parsed = parse_pr_body(body)

    assert parsed.unclassified == ((ACCEPTANCE_CRITERIA_TITLE, "not-an-id-or-fqn"),)


def test_pr_body_removed_public_api_recorded_separately():
    body = """## Removed public API
- old.module.Sym
"""
    parsed = parse_pr_body(body)

    assert parsed.removed_api_fqns == ("old.module.Sym",)
    assert parsed.api_fqns == ()
    assert REMOVED_API_TITLE in parsed.seen_section_titles


def test_pr_body_dedupes_within_section_preserving_order():
    body = """## Expected public API
- a.B
- a.B
- c.D
"""
    parsed = parse_pr_body(body)

    assert parsed.api_fqns == ("a.B", "c.D")


def test_pr_body_ignores_unregistered_sections():
    body = """## Motivation
Lots of prose.

- this.is.not.an.intent

## Background
Even more prose.
"""
    parsed = parse_pr_body(body)

    assert parsed.api_fqns == ()
    assert parsed.test_ids == ()
    assert parsed.unclassified == ()


def test_pr_body_empty_body_yields_empty_sections():
    parsed = parse_pr_body("")
    assert parsed.api_fqns == ()
    assert parsed.test_ids == ()
    assert parsed.seen_section_titles == ()


def test_issue_body_uses_same_grammar_as_pr_body():
    # Section F: entry point is duplicated so merge.py can attribute
    # surface provenance, but semantically the parser is shared.
    body = """## Expected public API
- pkg.symbol.New
"""
    pr_parsed = parse_pr_body(body)
    issue_parsed = parse_issue_body(body)

    assert pr_parsed == issue_parsed


# ---------------------------------------------------------------------------
# labels parser
# ---------------------------------------------------------------------------


def test_parse_kind_labels_returns_none_when_no_kind_label():
    assert parse_kind_labels(("area:cli", "status:ready")) is None


def test_parse_kind_labels_maps_each_recognised_kind():
    assert parse_kind_labels(("kind:feature",)) is ChangeKind.FEATURE
    assert parse_kind_labels(("kind:bugfix",)) is ChangeKind.BUGFIX
    assert parse_kind_labels(("kind:refactor",)) is ChangeKind.REFACTOR
    assert parse_kind_labels(("kind:test_update",)) is ChangeKind.TEST_UPDATE


def test_parse_kind_labels_ignores_non_kind_labels():
    assert parse_kind_labels(("kind:feature", "priority:high")) is ChangeKind.FEATURE


def test_parse_kind_labels_raises_c2_on_intra_label_conflict():
    with pytest.raises(LabelsParseError) as exc_info:
        parse_kind_labels(("kind:feature", "kind:bugfix"))
    msg = str(exc_info.value)
    assert "feature" in msg
    assert "bugfix" in msg


def test_parse_kind_labels_raises_on_unrecognised_kind_label():
    with pytest.raises(LabelsParseError) as exc_info:
        parse_kind_labels(("kind:hotfix",))
    assert "kind:hotfix" in str(exc_info.value)


# ---------------------------------------------------------------------------
# commits parser
# ---------------------------------------------------------------------------


def test_parse_commit_subjects_returns_none_when_no_known_prefix():
    assert parse_commit_subjects(("merge: foo", "chore: bar")) is None


def test_parse_commit_subjects_maps_recognised_prefixes():
    assert parse_commit_subjects(("feat: add x",)) is ChangeKind.FEATURE
    assert parse_commit_subjects(("fix: something",)) is ChangeKind.BUGFIX
    assert parse_commit_subjects(("refactor: extract helper",)) is ChangeKind.REFACTOR
    assert parse_commit_subjects(("test: add coverage",)) is ChangeKind.TEST_UPDATE


def test_parse_commit_subjects_accepts_scoped_prefix():
    assert parse_commit_subjects(("feat(cli): add flag",)) is ChangeKind.FEATURE


def test_parse_commit_subjects_accepts_breaking_change_marker():
    assert parse_commit_subjects(("fix!: regression",)) is ChangeKind.BUGFIX


def test_parse_commit_subjects_raises_on_contradiction():
    with pytest.raises(CommitsParseError):
        parse_commit_subjects(("feat: add x", "fix: regression"))


def test_parse_commit_subjects_ignores_unknown_conventional_types():
    # `docs:` / `chore:` / `style:` are valid Conventional Commits types
    # but do not map to a primary_kind. They are silently ignored.
    assert parse_commit_subjects(("docs: tweak", "chore: bump")) is None
