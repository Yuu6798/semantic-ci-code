"""`kind:*` label parser → primary_kind hint."""

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
    pass


def parse_kind_labels(labels: tuple[str, ...]) -> ChangeKind | None:
    seen: list[ChangeKind] = []
    unknown: list[str] = []
    for label in labels:
        if not label.startswith(KIND_LABEL_PREFIX):
            continue
        kind = LABEL_TO_KIND.get(label)
        if kind is None:
            unknown.append(label)
        elif kind not in seen:
            seen.append(kind)

    if unknown:
        allowed = ", ".join(sorted(LABEL_TO_KIND))
        raise LabelsParseError(
            f"unrecognised kind:* label(s) {sorted(unknown)!r}; allowed: {allowed}"
        )
    if len(seen) > 1:
        raise LabelsParseError(
            f"contradictory kind:* labels {[k.value for k in seen]!r}; "
            f"a PR may declare at most one primary_kind via labels"
        )
    return seen[0] if seen else None
