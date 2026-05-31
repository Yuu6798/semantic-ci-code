from __future__ import annotations

from pathlib import Path

import pytest

from ._config import COMPLETION_MARKERS, NARRATIVE_SUBSECTIONS, NEXT_QUEUE_HEADING, STATUS_MD
from ._helpers import extract_section

FIXTURES = Path(__file__).parent / "fixtures"


def _completed_queue_markers(text: str) -> list[str]:
    section = _next_queue_section(text)
    violations: list[str] = []
    scan_bullets = True
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            scan_bullets = not stripped.startswith(NARRATIVE_SUBSECTIONS)
            if _has_completion_marker(stripped):
                violations.append(stripped)
            continue
        if scan_bullets and stripped.startswith("- **") and _has_completion_marker(stripped):
            violations.append(stripped)
    return violations


def _has_completion_marker(line: str) -> bool:
    lower = line.lower()
    return any(marker in line or marker.lower() in lower for marker in COMPLETION_MARKERS)


def _next_queue_section(text: str) -> str:
    if f"## {NEXT_QUEUE_HEADING}" not in text.splitlines():
        raise AssertionError(
            f"STATUS.md must contain `## {NEXT_QUEUE_HEADING}`; otherwise the "
            "next-queue hygiene rule is not enforced."
        )
    return extract_section(text, NEXT_QUEUE_HEADING)


def _assert_no_completed_queue_items(text: str, *, source: str) -> None:
    violations = _completed_queue_markers(text)
    if not violations:
        return
    details = "\n".join(f"  - {line}" for line in violations)
    raise AssertionError(
        f"{source} `## {NEXT_QUEUE_HEADING}` contains completed queue markers:\n"
        f"{details}\n"
        "Suggested action: a completed item must move to the recently-merged "
        "section and be removed from the next queue."
    )


def test_status_md_next_queue_has_no_completed_headings_or_items() -> None:
    _assert_no_completed_queue_items(
        STATUS_MD.read_text(encoding="utf-8"),
        source=".claude/memory/STATUS.md",
    )


def test_next_queue_parser_detects_completed_fixture() -> None:
    text = (FIXTURES / "status_completed_in_queue.md").read_text(encoding="utf-8")
    assert _completed_queue_markers(text)
    with pytest.raises(AssertionError, match="completed queue markers"):
        _assert_no_completed_queue_items(text, source="fixture")


def test_next_queue_parser_rejects_missing_section_fixture() -> None:
    text = (FIXTURES / "status_missing_next_queue.md").read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match="must contain"):
        _assert_no_completed_queue_items(text, source="fixture")
