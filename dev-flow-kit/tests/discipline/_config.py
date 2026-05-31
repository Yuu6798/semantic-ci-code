"""Configuration for the portable discipline tests.

Adapt these constants to your repo's `STATUS.md` / `_index.md` heading names
and language. The defaults match the memory skeleton shipped in dev-flow-kit
(English headings). If your tracker is written in another language, swap the
heading strings and completion markers here — the test logic is
language-agnostic and reads everything from this module.
"""

from __future__ import annotations

from pathlib import Path

# Repo root, resolved from this file's location. These tests are designed to
# live at ``<repo>/tests/discipline/``; ``parents[2]`` is then the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Memory artifacts (relative to REPO_ROOT).
STATUS_MD = REPO_ROOT / ".claude" / "memory" / "STATUS.md"
INDEX_MD = REPO_ROOT / ".claude" / "memory" / "_index.md"

# Heading text (without the leading "## ") for the relevant STATUS.md sections.
PHASE_HEADING = "Phase"
NEXT_QUEUE_HEADING = "Next Queue"

# Substrings that mark a queue item as completed/merged. Matched
# case-insensitively against each bullet (its first line joined with any
# wrapped continuation lines). Choose markers that *unambiguously* mean "this
# is finished" — prefer past-tense / outcome words ("landed", "merged",
# "完走"). Avoid words that also appear in active, not-yet-done imperative
# task titles ("complete", "done", "finish"), or a live queue item like
# "- **Complete onboarding docs**" will be flagged as stale and fail the gate.
COMPLETION_MARKERS = ("landed", "merged", "完走")

# Sub-headings inside the next-queue section that are narrative, not queue
# items, and so should not be scanned for completion markers. Tuple of the
# exact "### ..." prefixes.
NARRATIVE_SUBSECTIONS: tuple[str, ...] = ()

# Maximum characters allowed in any _index.md table cell.
MAX_INDEX_CELL_CHARS = 500
