"""Markdown PR / issue body parser for intent-declaring sections."""

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
    pass


@dataclass(frozen=True)
class ParsedSections:
    api_fqns: tuple[str, ...] = ()
    test_ids: tuple[str, ...] = ()
    removed_api_fqns: tuple[str, ...] = ()
    unclassified: tuple[tuple[str, str], ...] = ()
    seen_section_titles: tuple[str, ...] = field(default_factory=tuple)


def _is_test_id(value: str) -> bool:
    # Match `_test_case_id` in delta/code_state_delta.py: it joins
    # `test_file::test_function`, and `test_function` is either a bare
    # identifier or exactly `Class::method` (one level only, see
    # test_surface/python_test_surface_extractor.py:181-195). Reject
    # deeper nesting, parametrize brackets, and stray spaces — none of
    # those forms are ever produced by the extractor.
    path, sep, name = value.partition("::")
    if not sep or not path or not name or " " in path or " " in name:
        return False
    parts = name.split("::")
    if len(parts) > 2:
        return False
    return all(part.isidentifier() for part in parts)


def _is_fqn(value: str) -> bool:
    if not value or "::" in value or "." not in value:
        return False
    if value.startswith(".") or value.endswith("."):
        return False
    return all(part.isidentifier() for part in value.split("."))


def _dedup_ordered(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _extract_section_bodies(text: str) -> dict[str, tuple[str, ...]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            current = stripped if stripped in INTENT_DECLARING_TITLES else None
            if current is not None and current not in sections:
                sections[current] = []
            continue
        if current is None:
            continue
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if value.startswith(("[ ] ", "[x] ", "[X] ")):
                value = value[4:].strip()
            if value:
                sections[current].append(value)
    return {key: tuple(values) for key, values in sections.items()}


def parse_pr_body(text: str) -> ParsedSections:
    sections = _extract_section_bodies(text)
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
        seen_section_titles=tuple(sections.keys()),
    )
