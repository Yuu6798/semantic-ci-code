"""Parse intent-declaring sections out of a PR body markdown blob.

The intent-declaring section registry (`docs/brief_8_planning.md §6.2.3`):

  - `## Expected public API` → API FQN source
  - `## Removed public API`  → unconsumed by any recipe in Brief 8 → C4
  - `## Test cases`          → test case ID source
  - `## Acceptance Criteria` → mixed (FQN bullets and test ID bullets,
                                classified by content grammar)

Sections not in this registry are ignored: `## Description`,
`## Motivation`, `## Background`, etc. are human-facing prose, not
declared intent.

The parser does **no** judgment about which sections a given recipe
will or will not consume. That decision belongs to `merge.py`, which
needs to detect C4 (unconsumed intent-declaring section) globally
across all sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field

EXPECTED_API_TITLE = "## Expected public API"
REMOVED_API_TITLE = "## Removed public API"
TEST_CASES_TITLE = "## Test cases"
ACCEPTANCE_CRITERIA_TITLE = "## Acceptance Criteria"

INTENT_DECLARING_TITLES: tuple[str, ...] = (
    EXPECTED_API_TITLE,
    REMOVED_API_TITLE,
    TEST_CASES_TITLE,
    ACCEPTANCE_CRITERIA_TITLE,
)


class SectionParseError(ValueError):
    """Raised when a section bullet cannot be classified as FQN or test ID."""


@dataclass(frozen=True)
class ParsedSections:
    """Content extracted from one markdown source (PR body or issue body).

    `unclassified` carries `(section_title, value)` pairs for items that
    appeared inside an intent-declaring section but did not match the
    `path::name` (test ID) or `dotted.name` (FQN) grammar. These cannot
    be silently dropped — `merge.py` raises C4 for them.
    """

    api_fqns: tuple[str, ...] = ()
    test_ids: tuple[str, ...] = ()
    removed_api_fqns: tuple[str, ...] = ()
    unclassified: tuple[tuple[str, str], ...] = ()
    seen_section_titles: tuple[str, ...] = field(default_factory=tuple)


def _extract_section_bodies(text: str) -> dict[str, tuple[str, ...]]:
    """Return ordered map of section_title -> list of bullet values.

    Bullet values are the substring after a leading `- ` on each line
    inside the section, trimmed. Lines that are not bullets are ignored,
    matching how humans typically interleave prose with bullets.

    Only the four registry titles are tracked; any other heading is
    treated as an "exit" of the current section (i.e. its body ends
    there). Order is preserved so the merger can detect surface order.
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped if stripped in INTENT_DECLARING_TITLES else None
            if current is not None and current not in sections:
                sections[current] = []
            continue
        if current is None:
            continue
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if value:
                sections[current].append(value)
    return {key: tuple(values) for key, values in sections.items()}


def _is_test_id(value: str) -> bool:
    return "::" in value


def _is_fqn(value: str) -> bool:
    if "::" in value:
        return False
    if "." not in value:
        return False
    if value.startswith(".") or value.endswith("."):
        return False
    return all(part.isidentifier() for part in value.split("."))


def _dedup_ordered(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def parse_pr_body(text: str) -> ParsedSections:
    """Parse a PR body markdown string into structured sections.

    Pure function with no I/O. The caller is responsible for reading
    the markdown file (or extracting it from a PR API payload) and
    passing the text.
    """
    sections = _extract_section_bodies(text)
    seen = tuple(sections.keys())

    api_fqns: list[str] = []
    test_ids: list[str] = []
    removed: list[str] = []
    unclassified: list[tuple[str, str]] = []

    for value in sections.get(EXPECTED_API_TITLE, ()):
        if _is_fqn(value):
            api_fqns.append(value)
        else:
            unclassified.append((EXPECTED_API_TITLE, value))

    for value in sections.get(REMOVED_API_TITLE, ()):
        if _is_fqn(value):
            removed.append(value)
        else:
            unclassified.append((REMOVED_API_TITLE, value))

    for value in sections.get(TEST_CASES_TITLE, ()):
        if _is_test_id(value):
            test_ids.append(value)
        else:
            unclassified.append((TEST_CASES_TITLE, value))

    for value in sections.get(ACCEPTANCE_CRITERIA_TITLE, ()):
        if _is_test_id(value):
            test_ids.append(value)
        elif _is_fqn(value):
            api_fqns.append(value)
        else:
            unclassified.append((ACCEPTANCE_CRITERIA_TITLE, value))

    return ParsedSections(
        api_fqns=_dedup_ordered(tuple(api_fqns)),
        test_ids=_dedup_ordered(tuple(test_ids)),
        removed_api_fqns=_dedup_ordered(tuple(removed)),
        unclassified=tuple(unclassified),
        seen_section_titles=seen,
    )
