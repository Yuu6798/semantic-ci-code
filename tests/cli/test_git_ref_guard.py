"""Option-like git refs must be refused before reaching git argv.

Refs are passed to git as positional arguments. Without a guard, a value
like ``--upload-pack=...`` would be parsed by git as a flag (argument
injection). The guard raises before any subprocess is spawned, and maps to
each command's documented exit code (usage error 2 for check/observe,
git path 3 for target-doctor).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from semantic_ci_code.cli.git_runtime import (
    GitError,
    GitRefError,
    ensure_safe_ref,
    ref_exists,
    resolve_baseline,
    resolve_candidate,
    tree_object_id,
)
from semantic_ci_code.cli.worktree import materialize_ref
from tests.cli.git_helpers import init_repo
from tests.cli.helpers import run_semantic_ci_inproc

OPTION_LIKE_REFS = (
    "-foo",
    "--upload-pack=/tmp/evil",
    "--output=/tmp/pwned",
    "-",
)


@pytest.mark.parametrize("ref", OPTION_LIKE_REFS)
def test_ensure_safe_ref_rejects_option_like_refs(ref: str):
    with pytest.raises(GitRefError):
        ensure_safe_ref(ref)


def test_ensure_safe_ref_rejects_empty_ref():
    with pytest.raises(GitRefError):
        ensure_safe_ref("")


@pytest.mark.parametrize("ref", ["HEAD", "origin/main", "main", "v1.0.0", "abc123", "HEAD~1"])
def test_ensure_safe_ref_accepts_normal_refs(ref: str):
    assert ensure_safe_ref(ref) == ref


def test_git_ref_error_maps_to_both_value_and_git_error():
    # check/observe route ValueError to usage errors (exit 2); target-doctor
    # routes GitError to its documented git path (exit 3). Both must match.
    assert issubclass(GitRefError, ValueError)
    assert issubclass(GitRefError, GitError)


@pytest.mark.parametrize("ref", OPTION_LIKE_REFS)
def test_ref_entry_points_reject_before_spawning_git(ref: str, tmp_path: Path):
    # tmp_path is not a git repository: if validation happened after the
    # subprocess call, these would fail with a git error instead.
    with pytest.raises(GitRefError):
        ref_exists(ref, cwd=tmp_path)
    with pytest.raises(GitRefError):
        tree_object_id(ref, ".", cwd=tmp_path)
    with pytest.raises(GitRefError):
        resolve_baseline(ref, repo_root=tmp_path, no_fetch=True)
    with pytest.raises(GitRefError):
        resolve_candidate(ref)
    with pytest.raises(GitRefError):
        with materialize_ref(tmp_path, ref, prefix="semantic-ci-test-"):
            pass


def test_check_rejects_option_like_candidate_rev_as_usage_error(tmp_path: Path):
    # argparse already rejects a space-separated dash value, so the form that
    # reaches the ref guard is `--candidate-rev=<option-like>`.
    repo = init_repo(tmp_path)

    result = run_semantic_ci_inproc(
        repo,
        "check",
        "--no-fetch",
        "--no-cache",
        "--candidate-rev=--upload-pack=/tmp/evil",
    )

    assert result.returncode == 2
    assert "invalid git ref" in result.stderr


def test_check_rejects_option_like_baseline_rev_as_usage_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci_inproc(
        repo,
        "check",
        "--no-fetch",
        "--no-cache",
        "--baseline-rev=-foo",
    )

    assert result.returncode == 2
    assert "invalid git ref" in result.stderr
