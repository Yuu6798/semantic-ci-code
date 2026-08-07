"""Keep completed planning records and current memory entry points synchronized."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CURRENT_MEMORY_FILES = (
    ROOT / ".claude" / "memory" / "_index.md",
    ROOT / ".claude" / "memory" / "STATUS.md",
)
COMPLETED_PLANNING_FILES = (
    ROOT / "docs" / "brief_7_planning.md",
    ROOT / "docs" / "brief_resultstatus_planning.md",
    ROOT / "docs" / "source_selection_planning.md",
)


def test_current_memory_uses_the_archived_doc_refactor_path():
    stale_path = "docs/doc_refactor_planning.md"

    for path in CURRENT_MEMORY_FILES:
        assert stale_path not in path.read_text(encoding="utf-8"), path


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
