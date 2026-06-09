from __future__ import annotations

from pathlib import Path

import pytest

from semantic_ci_code.cli.delta_overlay import (
    overlay_delta,
    renames_from_numstat,
    summarize_numstat,
)
from semantic_ci_code.cli.git_diff import NumstatEntry, parse_numstat
from semantic_ci_code.domain.state_schema import CodeStateDelta, LocDelta, RenameEntry


def test_parse_numstat_text_file_modify():
    entries = parse_numstat("5\t3\tpath/a.py\0")

    assert entries == (NumstatEntry(added=5, removed=3, path=Path("path/a.py")),)


def test_parse_numstat_binary_file():
    entries = parse_numstat("-\t-\timg.png\0")

    assert entries == (NumstatEntry(added=0, removed=0, path=Path("img.png"), is_binary=True),)


def test_parse_numstat_rename_record():
    entries = parse_numstat("2\t1\t\0old.py\0new.py\0")

    assert entries == (
        NumstatEntry(
            added=2,
            removed=1,
            path=Path("new.py"),
            old_path=Path("old.py"),
            is_rename=True,
        ),
    )


def test_parse_numstat_mixed_records_and_summary():
    entries = parse_numstat("5\t3\tpath/a.py\x00-\t-\timg.png\x002\t1\t\x00old.py\x00new.py\x00")

    files_touched, loc_delta = summarize_numstat(entries)

    assert len(entries) == 3
    assert files_touched == 3
    assert loc_delta == LocDelta(added=7, removed=4)


def test_renames_from_numstat_extracts_renames_with_posix_paths_and_sorting():
    entries = (
        NumstatEntry(
            added=0,
            removed=0,
            path=Path("pkg\\z_new.py"),
            old_path=Path("pkg\\z_old.py"),
            is_rename=True,
        ),
        NumstatEntry(added=1, removed=0, path=Path("pkg/added.py")),
        NumstatEntry(
            added=0,
            removed=0,
            path=Path("pkg\\a_new.py"),
            old_path=Path("pkg\\a_old.py"),
            is_binary=True,
            is_rename=True,
        ),
        NumstatEntry(added=1, removed=1, path=Path("pkg/not_rename.py"), old_path=Path("old.py")),
    )

    assert renames_from_numstat(entries) == (
        RenameEntry(old_path="pkg/a_old.py", new_path="pkg/a_new.py"),
        RenameEntry(old_path="pkg/z_old.py", new_path="pkg/z_new.py"),
    )


def test_parse_numstat_empty_input():
    entries = parse_numstat("")

    assert entries == ()
    assert summarize_numstat(entries) == (0, LocDelta())
    assert renames_from_numstat(entries) == ()


def test_parse_numstat_malformed_input_raises_value_error():
    with pytest.raises(ValueError):
        parse_numstat("abc")


def test_overlay_delta_updates_only_git_metadata():
    original = CodeStateDelta()
    renames = (RenameEntry(old_path="old.py", new_path="new.py"),)

    overlaid = overlay_delta(
        original,
        files_touched=2,
        loc_delta=LocDelta(added=7, removed=4),
        renames=renames,
    )

    assert original.files_touched == 0
    assert original.loc_delta == LocDelta()
    assert original.renames == ()
    assert overlaid.files_touched == 2
    assert overlaid.loc_delta == LocDelta(added=7, removed=4)
    assert overlaid.renames == renames
