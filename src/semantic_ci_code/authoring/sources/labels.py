"""Parse `kind:*` labels into a `primary_kind` hint.

Labels are a **strong** source for `primary_kind` validation only (they
do not contribute to FQN lists or test ID lists, see
`docs/brief_8_planning.md §6.2.2`).

C2 (intra-label conflict) is detected here when two different
`kind:<X>` values appear in the same input; the merger raises this
before considering recipe / commit precedence so the user can fix the
labels themselves.
"""

from __future__ import annotations

from semantic_ci_code.domain.state_schema import ChangeKind

KIND_LABEL_PREFIX = "kind:"

LABEL_TO_KIND: dict[str, ChangeKind] = {
    "kind:feature": ChangeKind.FEATURE,
    "kind:bugfix": ChangeKind.BUGFIX,
    "kind:refactor": ChangeKind.REFACTOR,
    "kind:test_update": ChangeKind.TEST_UPDATE,
}


class LabelsParseError(ValueError):
    """Raised when the labels themselves contradict each other (C2)."""


def parse_kind_labels(labels: tuple[str, ...]) -> ChangeKind | None:
    """Reduce `kind:*` labels to a single `primary_kind`.

    Returns `None` when no `kind:*` label is present. Non-`kind:*`
    labels are ignored (a PR can legitimately carry `area:cli`,
    `status:ready`, etc., without contributing to primary_kind).

    Raises `LabelsParseError` (C2) when two different `kind:<X>` labels
    appear together, or when a `kind:<X>` label is not in the recognised
    set.
    """
    seen: list[ChangeKind] = []
    unknown: list[str] = []
    for label in labels:
        if not label.startswith(KIND_LABEL_PREFIX):
            continue
        kind = LABEL_TO_KIND.get(label)
        if kind is None:
            unknown.append(label)
            continue
        if kind not in seen:
            seen.append(kind)

    if unknown:
        allowed = ", ".join(sorted(LABEL_TO_KIND.keys()))
        msg = f"unrecognised kind:* label(s) {sorted(unknown)!r}; allowed: {allowed}"
        raise LabelsParseError(msg)

    if len(seen) > 1:
        values = [kind.value for kind in seen]
        msg = (
            f"contradictory kind:* labels {values!r}; "
            f"a PR may declare at most one primary_kind via labels"
        )
        raise LabelsParseError(msg)

    return seen[0] if seen else None
