"""Conventional Commits prefix → primary_kind hint."""

from __future__ import annotations

import re

from semantic_ci_code.domain.state_schema import ChangeKind

CONVENTIONAL_COMMIT_RE = re.compile(r"^(?P<prefix>[a-z]+)(?:\([^)]*\))?!?: ")

PREFIX_TO_KIND: dict[str, ChangeKind] = {
    "feat": ChangeKind.FEATURE,
    "fix": ChangeKind.BUGFIX,
    "refactor": ChangeKind.REFACTOR,
    "test": ChangeKind.TEST_UPDATE,
}


class CommitsParseError(ValueError):
    pass


def parse_commit_subjects(subjects: tuple[str, ...]) -> ChangeKind | None:
    seen: list[ChangeKind] = []
    for subject in subjects:
        match = CONVENTIONAL_COMMIT_RE.match(subject)
        if match is None:
            continue
        kind = PREFIX_TO_KIND.get(match.group("prefix"))
        if kind is not None and kind not in seen:
            seen.append(kind)

    if len(seen) > 1:
        raise CommitsParseError(
            f"contradictory Conventional Commits prefixes yield "
            f"{[k.value for k in seen]!r}; commit history declares more than one primary_kind"
        )
    return seen[0] if seen else None
