from pathlib import Path

ROOT = Path(__file__).parents[2]
ARCHIVE_INDEX = ROOT / "docs" / "archive" / "README.md"
DOC_REFACTOR_PLAN = ROOT / "docs" / "archive" / "doc_refactor_planning.md"
AGENTS = ROOT / "AGENTS.md"
CLAUDE = ROOT / "CLAUDE.md"


def _section_lines(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index(heading)
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return lines[start:end]


def test_completed_doc_refactor_plan_is_archived_in_index_and_document():
    index = ARCHIVE_INDEX.read_text(encoding="utf-8")
    plan = DOC_REFACTOR_PLAN.read_text(encoding="utf-8")
    root_index = CLAUDE.read_text(encoding="utf-8")

    assert "| `doc_refactor_planning.md` | ARCHIVED (completed 2026-08-08) |" in index
    assert "Status: **ARCHIVED (completed 2026-08-08)**" in plan
    assert (
        "| `docs/archive/doc_refactor_planning.md` | ARCHIVED (completed 2026-08-08) |"
        in root_index
    )
    assert "Status: **PLANNING (open)**" not in plan


def test_completed_phase_three_meets_its_compaction_contract():
    agents = AGENTS.read_text(encoding="utf-8")
    plan = DOC_REFACTOR_PLAN.read_text(encoding="utf-8")
    section = _section_lines(
        agents,
        "## 5. Experience Externalization Discipline (経験値の外部化規律)",
    )

    assert len(section) <= 80
    assert "唯一の未了項目" not in agents
    assert "Phase 3 closeout (2026-08-08, PR #156)" in plan
