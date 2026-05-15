"""Parse Conventional Commits prefixes into a `primary_kind` hint.

Commit prefixes are a **medium** source: they contribute only to
`primary_kind` validation, not to FQN or test ID lists, and the merger
only consults them when stronger layers leave `primary_kind` ambiguous
(see `docs/brief_8_planning.md §6.2.2`, §6.2.3).
"""

from __future__ import annotations

import re

from semantic_ci_code.domain.state_schema import ChangeKind

CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(?P<prefix>[a-z]+)(?:\([^)]*\))?(?P<bang>!)?: ",
)

PREFIX_TO_KIND: dict[str, ChangeKind] = {
    "feat": ChangeKind.FEATURE,
    "fix": ChangeKind.BUGFIX,
    "refactor": ChangeKind.REFACTOR,
    "test": ChangeKind.TEST_UPDATE,
}


class CommitsParseError(ValueError):
    """Raised when commit subjects yield contradictory primary_kind hints."""


def _extract_prefix(subject: str) -> str | None:
    match = CONVENTIONAL_COMMIT_RE.match(subject)
    if match is None:
        return None
    return match.group("prefix")


def parse_commit_subjects(subjects: tuple[str, ...]) -> ChangeKind | None:
    """Reduce a list of commit subject lines to a single primary_kind hint.

    Lines without a recognised Conventional Commits prefix are silently
    ignored (a merge commit, a chore message, a revert subject etc.).
    Lines with an unrecognised prefix (e.g. `chore:`, `docs:`,
    `style:`) are also silently ignored — they are valid commit types
    that simply don't map to a `change.primary_kind`.

    Raises `CommitsParseError` when two recognised prefixes map to
    different kinds in the same commit set (e.g. one `feat:` and one
    `fix:`). The merger then either reconciles or escalates to C3.
    """
    seen: list[ChangeKind] = []
    for subject in subjects:
        prefix = _extract_prefix(subject)
        if prefix is None:
            continue
        kind = PREFIX_TO_KIND.get(prefix)
        if kind is None:
            continue
        if kind not in seen:
            seen.append(kind)

    if len(seen) > 1:
        values = [kind.value for kind in seen]
        msg = (
            f"contradictory Conventional Commits prefixes "
            f"yield {values!r}; commit history declares more than one "
            f"primary_kind"
        )
        raise CommitsParseError(msg)

    return seen[0] if seen else None
