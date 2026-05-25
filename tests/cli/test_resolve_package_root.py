"""Unit tests for ``_resolve_package_root`` symlink escape guards.

A fork PR is the canonical use case for ``semantic-ci check``: an attacker
may push a tree where the package root is a symlink pointing outside the
worktree, causing the extractor to read ``.py`` files from anywhere on the
runner. The ``validate-plan`` command already enforces ``Path.is_relative_to``
after resolving symlinks; these tests pin the same defense for ``check``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from semantic_ci_code.cli.commands.check import (
    _resolve_package_root as check_resolve_package_root,
)


def _symlink_or_skip(target: Path, link: Path) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation is not available in this environment: {exc}")


def test_symlink_escape_in_package_root_is_rejected(tmp_path: Path) -> None:
    tree_root = tmp_path / "tree"
    outside = tmp_path / "outside"
    tree_root.mkdir()
    outside.mkdir()
    (outside / "leak.py").write_text("# would be readable on resolve\n", encoding="utf-8")

    # Attacker-controlled symlink at the package_root location pointing outside.
    escape_link = tree_root / "pkg"
    _symlink_or_skip(outside, escape_link)

    with pytest.raises(ValueError, match=r"escapes tree"):
        check_resolve_package_root(tree_root, Path("pkg"), "baseline")


def test_relative_traversal_in_package_root_is_rejected(tmp_path: Path) -> None:
    tree_root = tmp_path / "tree"
    tree_root.mkdir()

    with pytest.raises(ValueError, match=r"escapes tree"):
        check_resolve_package_root(tree_root, Path("../outside"), "candidate")


def test_symlink_inside_tree_resolves_normally(tmp_path: Path) -> None:
    tree_root = tmp_path / "tree"
    real_pkg = tree_root / "real_pkg"
    real_pkg.mkdir(parents=True)

    inside_link = tree_root / "pkg"
    _symlink_or_skip(real_pkg, inside_link)

    resolved = check_resolve_package_root(tree_root, Path("pkg"), "baseline")
    assert resolved == real_pkg.resolve()
