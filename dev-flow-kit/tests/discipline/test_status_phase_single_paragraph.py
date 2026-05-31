from __future__ import annotations

from pathlib import Path

import pytest

from ._config import PHASE_HEADING, STATUS_MD
from ._helpers import extract_section, split_paragraphs

FIXTURES = Path(__file__).parent / "fixtures"


def _phase_paragraphs(text: str) -> list[str]:
    return split_paragraphs(extract_section(text, PHASE_HEADING))


def _assert_single_phase_paragraph(text: str, *, source: str) -> None:
    paragraphs = _phase_paragraphs(text)
    if len(paragraphs) == 1:
        return
    previews = "\n".join(
        f"  [{index}] {paragraph.splitlines()[0][:100]}"
        for index, paragraph in enumerate(paragraphs, start=1)
    )
    raise AssertionError(
        f"{source} `## {PHASE_HEADING}` must be exactly one paragraph; "
        f"found {len(paragraphs)}.\n"
        f"Drifted paragraph starts:\n{previews}\n"
        "Fix: merge the Phase section into one canonical paragraph instead of "
        "appending a new paragraph above the old one."
    )


def test_status_md_phase_section_is_single_paragraph() -> None:
    _assert_single_phase_paragraph(
        STATUS_MD.read_text(encoding="utf-8"),
        source=".claude/memory/STATUS.md",
    )


def test_phase_parser_detects_two_paragraph_drift_fixture() -> None:
    text = (FIXTURES / "status_two_paragraphs.md").read_text(encoding="utf-8")
    assert len(_phase_paragraphs(text)) == 2
    with pytest.raises(AssertionError, match="exactly one paragraph"):
        _assert_single_phase_paragraph(text, source="fixture")
