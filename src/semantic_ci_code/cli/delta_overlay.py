from __future__ import annotations

from semantic_ci_code.cli.git_diff import NumstatEntry
from semantic_ci_code.domain.state_schema import CodeStateDelta, LocDelta


def overlay_delta(
    delta: CodeStateDelta,
    *,
    files_touched: int,
    loc_delta: LocDelta,
) -> CodeStateDelta:
    return delta.model_copy(update={"files_touched": files_touched, "loc_delta": loc_delta})


def summarize_numstat(entries: tuple[NumstatEntry, ...]) -> tuple[int, LocDelta]:
    return len(entries), LocDelta(
        added=sum(entry.added for entry in entries if not entry.is_binary),
        removed=sum(entry.removed for entry in entries if not entry.is_binary),
    )
