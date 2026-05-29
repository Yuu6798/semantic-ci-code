from __future__ import annotations

import re
from pathlib import Path

import pytest

from ._helpers import REPO_ROOT, _is_separator_row

FIXTURES = Path(__file__).parent / "fixtures"

# Dogfooding reports structured as a case/verdict matrix (a table with a
# `Verdict` column). The dual-case rule reads ONLY that column, never free
# prose: a pass-only report that merely *mentions* "FAIL" / "vacuous PASS" in
# explanatory text must still fail. Reports without a verdict matrix
# (TC10 uses ✅/❌ emoji, the findings tracker is a D-class summary) are out of
# scope by construction. Add a report here when it grows a verdict matrix.
CASE_VERDICT_REPORTS = ("docs/dogfooding_real_pr_complexity.md",)

VERDICT_HEADER = "verdict"
PASS_TOKEN = re.compile(r"\bPASS\b")
FAIL_TOKEN = re.compile(r"\bFAIL\b")


def verdict_column_cells(text: str) -> list[str]:
    """Collect cells under every `Verdict`-headed markdown table column."""

    cells: list[str] = []
    verdict_idx: int | None = None
    have_header = False
    for line in text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            # Blank / prose line ends the current table.
            verdict_idx = None
            have_header = False
            continue
        row = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not have_header:
            have_header = True
            verdict_idx = next(
                (i for i, head in enumerate(row) if head.lower() == VERDICT_HEADER),
                None,
            )
            continue
        if _is_separator_row(row):
            continue
        if verdict_idx is not None and verdict_idx < len(row):
            cells.append(row[verdict_idx])
    return cells


def missing_case_directions(text: str) -> list[str]:
    cells = verdict_column_cells(text)
    missing: list[str] = []
    if not any(PASS_TOKEN.search(cell) for cell in cells):
        missing.append("PASS")
    if not any(FAIL_TOKEN.search(cell) for cell in cells):
        missing.append("FAIL")
    return missing


def _assert_dual_case(text: str, *, source: str) -> None:
    cells = verdict_column_cells(text)
    if not cells:
        raise AssertionError(
            f"{source}: no `Verdict` column found; the dual-case rule expects a "
            "case/verdict matrix. If this report's structure changed, update "
            "CASE_VERDICT_REPORTS in this test."
        )
    missing = missing_case_directions(text)
    if not missing:
        return
    raise AssertionError(
        f"{source} dogfood report must demonstrate both PASS and FAIL in its "
        f"Verdict column; missing: {', '.join(missing)}.\n"
        "Fix: a dogfooding pass that shows only one verdict direction cannot "
        "evidence detection power -- one-sided evidence is exactly how vacuous "
        "PASS hazards (CLAUDE.md Experience Externalization, D4/D6) slip through."
    )


def test_dogfood_reports_demonstrate_both_directions() -> None:
    for rel in CASE_VERDICT_REPORTS:
        path = REPO_ROOT / rel
        assert path.exists(), f"registered dogfood report missing: {rel}"
        _assert_dual_case(path.read_text(encoding="utf-8"), source=rel)


def test_dual_case_detects_pass_only_fixture() -> None:
    text = (FIXTURES / "dogfood_pass_only.md").read_text(encoding="utf-8")
    assert missing_case_directions(text) == ["FAIL"]
    with pytest.raises(AssertionError, match="missing: FAIL"):
        _assert_dual_case(text, source="fixture")


def test_dual_case_ignores_prose_tokens() -> None:
    # Regression for the Codex review: the pass-only fixture's prose mentions
    # "FAIL" and "vacuous PASS", but the Verdict column is one-sided, so the
    # column-scoped check must still flag the missing FAIL direction.
    text = (FIXTURES / "dogfood_pass_only.md").read_text(encoding="utf-8")
    assert FAIL_TOKEN.search(text), "fixture prose should contain the FAIL token"
    assert missing_case_directions(text) == ["FAIL"]


def test_dual_case_accepts_balanced_fixture() -> None:
    text = (FIXTURES / "dogfood_pass_and_fail.md").read_text(encoding="utf-8")
    assert missing_case_directions(text) == []
    _assert_dual_case(text, source="fixture")
