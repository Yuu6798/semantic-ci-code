from pathlib import Path

ROOT = Path(__file__).parents[2]
ARCHIVE_INDEX = ROOT / "docs" / "archive" / "README.md"
DOC_REFACTOR_PLAN = ROOT / "docs" / "archive" / "doc_refactor_planning.md"


def test_completed_doc_refactor_plan_is_archived_in_index_and_document():
    index = ARCHIVE_INDEX.read_text(encoding="utf-8")
    plan = DOC_REFACTOR_PLAN.read_text(encoding="utf-8")

    assert "| `doc_refactor_planning.md` | ARCHIVED (completed 2026-05-21) |" in index
    assert "Status: **ARCHIVED (completed 2026-05-21)**" in plan
    assert "Status: **PLANNING (open)**" not in plan
