from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from semantic_ci_code.cli.git_runtime import GitCommandError, run_git


@dataclass(frozen=True)
class NumstatEntry:
    added: int
    removed: int
    path: Path
    old_path: Path | None = None
    is_binary: bool = False
    is_rename: bool = False


def parse_numstat(stdout: str) -> tuple[NumstatEntry, ...]:
    if stdout == "":
        return ()

    fields = stdout.split("\0")
    if fields and fields[-1] == "":
        fields.pop()

    entries: list[NumstatEntry] = []
    index = 0
    while index < len(fields):
        header = fields[index]
        parts = header.split("\t")
        if len(parts) != 3:
            raise ValueError(f"malformed git numstat record: {header!r}")

        added_raw, removed_raw, path_raw = parts
        added, removed, is_binary = _parse_counts(added_raw, removed_raw)
        if path_raw == "":
            if index + 2 >= len(fields):
                raise ValueError("malformed git numstat rename record")
            old_path = fields[index + 1]
            new_path = fields[index + 2]
            if not old_path or not new_path:
                raise ValueError("malformed git numstat rename path")
            entries.append(
                NumstatEntry(
                    added=added,
                    removed=removed,
                    path=Path(new_path),
                    old_path=Path(old_path),
                    is_binary=is_binary,
                    is_rename=True,
                )
            )
            index += 3
            continue

        if not path_raw:
            raise ValueError("malformed git numstat path")
        entries.append(
            NumstatEntry(
                added=added,
                removed=removed,
                path=Path(path_raw),
                is_binary=is_binary,
            )
        )
        index += 1

    return tuple(entries)


def staged_paths(repo_root: Path) -> tuple[Path, ...]:
    stdout = run_git(["diff", "--cached", "--name-only", "-z"], cwd=repo_root)
    return tuple(Path(item) for item in stdout.split("\0") if item)


def numstat_cached(repo_root: Path) -> tuple[NumstatEntry, ...]:
    return parse_numstat(run_git(["diff", "--cached", "--numstat", "-z", "-M"], cwd=repo_root))


def numstat_range(
    repo_root: Path,
    baseline: str,
    candidate: str | None = None,
) -> tuple[NumstatEntry, ...]:
    range_arg = baseline if candidate is None else f"{baseline}...{candidate}"
    try:
        return parse_numstat(run_git(["diff", "--numstat", "-z", "-M", range_arg], cwd=repo_root))
    except GitCommandError as exc:
        if candidate is None or "no merge base" not in exc.stderr:
            raise
        return parse_numstat(
            run_git(["diff", "--numstat", "-z", "-M", baseline, candidate], cwd=repo_root)
        )


def _parse_counts(added_raw: str, removed_raw: str) -> tuple[int, int, bool]:
    if added_raw == "-" and removed_raw == "-":
        return 0, 0, True
    if added_raw == "-" or removed_raw == "-":
        raise ValueError(f"malformed git numstat counts: {added_raw!r}, {removed_raw!r}")
    try:
        return int(added_raw), int(removed_raw), False
    except ValueError as exc:
        raise ValueError(f"malformed git numstat counts: {added_raw!r}, {removed_raw!r}") from exc
