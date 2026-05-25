from __future__ import annotations

import shlex
from pathlib import Path

import yaml

from .git_helpers import (
    CANDIDATE_SOURCE,
    TARGET_FAIL,
    init_repo_without_candidate_commit,
    stage_changes,
)
from .helpers import run_semantic_ci


def test_pre_commit_hooks_manifest_is_static_and_valid():
    manifest_path = Path(".pre-commit-hooks.yaml")
    hooks = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert isinstance(hooks, list)
    assert {hook["id"] for hook in hooks} == {"semantic-ci", "semantic-ci-smoke"}
    for hook in hooks:
        assert hook["language"] == "python"
        assert hook["entry"].startswith("semantic-ci check --candidate-source=staged-index")
        assert hook["pass_filenames"] is False
        assert hook["stages"] == ["pre-commit"]


def test_pre_commit_smoke_hook_uses_smoke_mode():
    hooks = yaml.safe_load(Path(".pre-commit-hooks.yaml").read_text(encoding="utf-8"))
    by_id = {hook["id"]: hook for hook in hooks}

    assert by_id["semantic-ci"]["entry"] == "semantic-ci check --candidate-source=staged-index"
    assert (
        by_id["semantic-ci-smoke"]["entry"]
        == "semantic-ci check --candidate-source=staged-index --mode smoke"
    )


def test_pre_commit_hook_command_routes_pass_fail_and_usage(tmp_path: Path):
    hooks = yaml.safe_load(Path(".pre-commit-hooks.yaml").read_text(encoding="utf-8"))
    entry_args = _entry_args({hook["id"]: hook for hook in hooks}["semantic-ci-smoke"]["entry"])
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})

    passing = run_semantic_ci(repo, *entry_args, "--format", "json")
    (repo / "target.yaml").write_text(TARGET_FAIL, encoding="utf-8")
    failing = run_semantic_ci(repo, *entry_args, "--format", "json")
    usage = run_semantic_ci(repo, *entry_args, "--candidate-rev", "HEAD")

    assert passing.returncode == 0
    assert failing.returncode == 1
    assert usage.returncode == 2


def _entry_args(entry: str) -> list[str]:
    parts = shlex.split(entry)
    assert parts[0] == "semantic-ci"
    return parts[1:]
