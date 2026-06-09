from __future__ import annotations

import pytest

from ._helpers import REPO_ROOT

CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

# CLAUDE.md is injected into every turn's context as project instructions, so
# its length is a fixed per-turn cost AND, past ~150-200 lines, a documented
# instruction-following-degradation risk. The doc-refactor (2026-05-21) set a
# ≤ 200-line aspiration but the file regressed to 483; this cap is the
# enforced ceiling that keeps reference detail offloaded to docs/ and skills
# (see CLAUDE.md § Repository Layout / § Session Memory and the wrap-up skill).
CLAUDE_MD_LINE_CAP = 300


def _line_count(text: str) -> int:
    return len(text.splitlines())


def _assert_line_cap(text: str, *, source: str, cap: int) -> None:
    count = _line_count(text)
    if count <= cap:
        return
    raise AssertionError(
        f"{source} has {count} lines, exceeding the {cap}-line cap.\n"
        "CLAUDE.md is always-loaded policy: move reference detail (trees, long "
        "tables, multi-step procedures) into docs/ or a skill and leave a "
        "pointer here. See the wrap-up skill Appendix C anti-pattern row."
    )


def test_claude_md_within_line_cap() -> None:
    _assert_line_cap(
        CLAUDE_MD.read_text(encoding="utf-8"),
        source="CLAUDE.md",
        cap=CLAUDE_MD_LINE_CAP,
    )


def test_line_cap_detects_overflow() -> None:
    overflow = "\n".join(f"line {i}" for i in range(CLAUDE_MD_LINE_CAP + 1))
    assert _line_count(overflow) == CLAUDE_MD_LINE_CAP + 1
    with pytest.raises(AssertionError, match="exceeding the"):
        _assert_line_cap(overflow, source="fixture", cap=CLAUDE_MD_LINE_CAP)
