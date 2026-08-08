"""Keep completed planning records and current memory entry points synchronized."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CURRENT_MEMORY_ENTRY_POINTS = (
    ROOT / ".claude" / "memory" / "_index.md",
    ROOT / ".claude" / "memory" / "STATUS.md",
    ROOT / ".claude" / "memory" / "archive" / "INDEX.md",
)
COMPLETED_PLANNING_FILES = (
    ROOT / "docs" / "brief_7_planning.md",
    ROOT / "docs" / "brief_resultstatus_planning.md",
    ROOT / "docs" / "source_selection_planning.md",
)


def test_current_memory_uses_the_archived_doc_refactor_path():
    stale_path = "docs/doc_refactor_planning.md"

    for path in CURRENT_MEMORY_ENTRY_POINTS:
        assert stale_path not in path.read_text(encoding="utf-8"), path


def test_archive_index_describes_landed_discipline_tests_as_current():
    archive_index = CURRENT_MEMORY_ENTRY_POINTS[-1].read_text(encoding="utf-8")

    assert "これらが landed すると" not in archive_index
    assert "wrap-up trigger の一部として自動実行される" not in archive_index
    assert "CI で mechanically enforce されている" in archive_index
    assert "move と index 書換は operator が手動実行する" in archive_index


def test_completed_planning_records_do_not_claim_active_or_open_status():
    stale_markers = (
        "Live status:",
        "active queue",
        "Open implementation questions",
        "ruleset 配布戦略未確定",
        "着地順序の選択(open question",
    )

    for path in COMPLETED_PLANNING_FILES:
        text = path.read_text(encoding="utf-8")
        assert "REFERENCE" in text and "complete" in text, path
        for marker in stale_markers:
            assert marker not in text, f"{path}: stale marker {marker!r}"
