from __future__ import annotations

from semantic_ci_code.cli.git_diff import NumstatEntry
from semantic_ci_code.domain.state_schema import CodeStateDelta, LocDelta, RenameEntry


def overlay_delta(
    delta: CodeStateDelta,
    *,
    files_touched: int,
    loc_delta: LocDelta,
    renames: tuple[RenameEntry, ...] = (),
) -> CodeStateDelta:
    return delta.model_copy(
        update={"files_touched": files_touched, "loc_delta": loc_delta, "renames": renames}
    )


def summarize_numstat(entries: tuple[NumstatEntry, ...]) -> tuple[int, LocDelta]:
    return len(entries), LocDelta(
        added=sum(entry.added for entry in entries if not entry.is_binary),
        removed=sum(entry.removed for entry in entries if not entry.is_binary),
    )


def renames_from_numstat(entries: tuple[NumstatEntry, ...]) -> tuple[RenameEntry, ...]:
    return tuple(
        sorted(
            (
                RenameEntry(old_path=_posix_path(entry.old_path), new_path=_posix_path(entry.path))
                for entry in entries
                if entry.is_rename and entry.old_path is not None
            ),
            key=lambda rename: (rename.old_path, rename.new_path),
        )
    )


def _posix_path(path: object) -> str:
    return str(path).replace("\\", "/")
