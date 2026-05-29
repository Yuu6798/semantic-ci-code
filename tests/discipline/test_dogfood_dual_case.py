from __future__ import annotations

import re
from pathlib import Path

import pytest

from ._helpers import REPO_ROOT

# Dogfooding report files (DOGFOOD REPORT docs). The `dogfooding_` prefix
# deliberately excludes CASE STUDY docs such as pre_generation_validation_case.md.
DOGFOOD_GLOB = "docs/dogfooding_*.md"
FIXTURES = Path(__file__).parent / "fixtures"

# `\bPASS\b` / `\bFAIL\b` match both the bare verdict tokens and compounds such
# as "vacuous PASS" / "false-FAIL" that the reports use for the two directions.
PASS_TOKEN = re.compile(r"\bPASS\b")
FAIL_TOKEN = re.compile(r"\bFAIL\b")


def missing_case_directions(text: str) -> list[str]:
    missing: list[str] = []
    if not PASS_TOKEN.search(text):
        missing.append("PASS")
    if not FAIL_TOKEN.search(text):
        missing.append("FAIL")
    return missing


def _assert_dual_case(text: str, *, source: str) -> None:
    missing = missing_case_directions(text)
    if not missing:
        return
    raise AssertionError(
        f"{source} dogfood report must demonstrate both PASS and FAIL verdict "
        f"directions; missing: {', '.join(missing)}.\n"
        "Fix: a dogfooding pass that shows only one verdict direction cannot "
        "evidence detection power -- one-sided evidence is exactly how vacuous "
        "PASS hazards (CLAUDE.md Experience Externalization, D4/D6) slip through."
    )


def test_dogfood_reports_demonstrate_both_directions() -> None:
    reports = sorted(REPO_ROOT.glob(DOGFOOD_GLOB))
    assert reports, "expected at least one docs/dogfooding_*.md report"
    for report in reports:
        _assert_dual_case(
            report.read_text(encoding="utf-8"),
            source=str(report.relative_to(REPO_ROOT)),
        )


def test_dual_case_detects_pass_only_fixture() -> None:
    text = (FIXTURES / "dogfood_pass_only.md").read_text(encoding="utf-8")
    assert missing_case_directions(text) == ["FAIL"]
    with pytest.raises(AssertionError, match="missing: FAIL"):
        _assert_dual_case(text, source="fixture")


def test_dual_case_accepts_balanced_fixture() -> None:
    text = (FIXTURES / "dogfood_pass_and_fail.md").read_text(encoding="utf-8")
    assert missing_case_directions(text) == []
    _assert_dual_case(text, source="fixture")
