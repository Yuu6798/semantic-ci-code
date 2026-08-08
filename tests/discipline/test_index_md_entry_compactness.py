from __future__ import annotations

from pathlib import Path

import pytest

from ._helpers import REPO_ROOT, parse_markdown_table_rows

INDEX_MD = REPO_ROOT / ".claude" / "memory" / "_index.md"
FIXTURES = Path(__file__).parent / "fixtures"
MAX_CELL_CHARS = 500


def _oversized_cells(text: str) -> list[tuple[str, int, str]]:
    return _oversized_cells_from_rows(parse_markdown_table_rows(text))


def _oversized_cells_from_rows(rows: list[list[str]]) -> list[tuple[str, int, str]]:
    violations: list[tuple[str, int, str]] = []
    for row in rows:
        date = row[0] if row else "(unknown date)"
        for cell in row:
            if len(cell) > MAX_CELL_CHARS:
                violations.append((date, len(cell), cell[:100]))
    return violations


def _assert_index_cells_are_compact(text: str, *, source: str) -> None:
    rows = parse_markdown_table_rows(text)
    if not rows:
        raise AssertionError(
            f"{source} must contain at least one _index.md table data row; "
            "otherwise the compactness invariant is not enforced."
        )
    violations = _oversized_cells_from_rows(rows)
    if not violations:
        return
    details = "\n".join(
        f"  - {date}: {count} chars, starts with {preview!r}" for date, count, preview in violations
    )
    raise AssertionError(
        f"{source} has _index.md table cells longer than {MAX_CELL_CHARS} "
        f"chars:\n{details}\n"
        "Suggested action: follow docs/archive/doc_refactor_planning.md Phase 2; move "
        "details to the dated session log and keep _index.md to a 1-2 line "
        "summary."
    )


def test_index_md_entries_keep_cells_compact() -> None:
    _assert_index_cells_are_compact(
        INDEX_MD.read_text(encoding="utf-8"),
        source=".claude/memory/_index.md",
    )


def test_index_parser_detects_essay_cell_fixture() -> None:
    text = (FIXTURES / "index_md_essay_cell.md").read_text(encoding="utf-8")
    assert _oversized_cells(text)
    with pytest.raises(AssertionError, match="longer than 500 chars"):
        _assert_index_cells_are_compact(text, source="fixture")


def test_index_parser_rejects_missing_table_rows_fixture() -> None:
    text = (FIXTURES / "index_md_missing_table_rows.md").read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match="at least one"):
        _assert_index_cells_are_compact(text, source="fixture")
