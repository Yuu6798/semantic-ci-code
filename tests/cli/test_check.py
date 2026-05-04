from __future__ import annotations

import json
import pickle
from pathlib import Path

from semantic_ci_code.cli.git_runtime import GitCommandError

from .git_helpers import (
    BAD_SOURCE,
    BASELINE_SOURCE,
    CANDIDATE_SOURCE,
    TARGET_FAIL,
    TARGET_INVALID,
    TARGET_PASS,
    TARGET_REPAIR,
    git,
    init_repo,
    init_repo_without_candidate_commit,
    init_topic_only_repo,
    run,
    run_semantic_ci,
    write_file,
)


def payload(result) -> dict:
    return json.loads(result.stdout)


def test_check_pass_fixture_exits_zero_with_json_verdict_pass(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(repo, "check", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_check_repair_fixture_exits_zero_by_default(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_REPAIR)

    result = run_semantic_ci(repo, "check", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "repair"


def test_check_repair_fixture_strict_repair_exits_one(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_REPAIR)

    result = run_semantic_ci(repo, "check", "--format", "json", "--strict-repair")

    assert result.returncode == 1
    assert payload(result)["verdict"] == "repair"


def test_check_fail_fixture_exits_one(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_FAIL)

    result = run_semantic_ci(repo, "check", "--format", "json")

    assert result.returncode == 1
    assert payload(result)["verdict"] == "fail"


def test_origin_main_ref_is_used_when_present(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)

    result = run_semantic_ci(repo, "check", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_main_fallback_is_used_when_origin_main_is_missing(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=False)

    result = run_semantic_ci(repo, "check", "--format", "json", "--no-fetch")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_missing_baseline_candidates_exit_engine_error(tmp_path: Path):
    repo = init_topic_only_repo(tmp_path)

    result = run_semantic_ci(repo, "check", "--format", "json", "--no-fetch")

    assert result.returncode == 3
    assert "origin/main, main, master" in result.stderr


def test_explicit_baseline_rev_runs_against_given_sha(tmp_path: Path):
    repo = init_repo(tmp_path)
    baseline_sha = git(repo, "rev-parse", "main").stdout.strip()

    result = run_semantic_ci(
        repo,
        "check",
        "--baseline-rev",
        baseline_sha,
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_no_fetch_skips_fetch_commands(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=False)
    command_log = tmp_path / "git-commands.jsonl"

    result = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        extra_env={"SEMANTIC_CI_GIT_COMMAND_LOG": str(command_log)},
    )

    assert result.returncode == 0
    records = [
        json.loads(line)["args"] for line in command_log.read_text(encoding="utf-8").splitlines()
    ]
    assert not any(command[1] == "fetch" for command in records)


def test_allow_dirty_uses_working_directory_as_candidate(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)

    result = run_semantic_ci(repo, "check", "--format", "json", "--allow-dirty")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_dirty_without_allow_dirty_warns_and_uses_head_commit(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)

    result = run_semantic_ci(repo, "check", "--format", "json")

    assert result.returncode == 1
    assert "working tree is dirty; using HEAD commit" in result.stderr
    assert payload(result)["verdict"] == "fail"


def test_worktree_cleanup_on_success(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(repo, "check", "--format", "json")

    assert result.returncode == 0
    worktrees = git(repo, "worktree", "list", "--porcelain").stdout
    assert "semantic-ci-baseline-" not in worktrees
    assert "semantic-ci-candidate-" not in worktrees


def test_worktree_cleanup_after_extraction_error(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "mod.py", BAD_SOURCE)
    git(repo, "add", "mod.py")
    git(repo, "commit", "-m", "bad candidate")

    result = run_semantic_ci(repo, "check", "--format", "json")

    assert result.returncode == 3
    assert "extractor failed:" in result.stderr
    worktrees = git(repo, "worktree", "list", "--porcelain").stdout
    assert "semantic-ci-baseline-" not in worktrees
    assert "semantic-ci-candidate-" not in worktrees


def test_git_not_found_exits_engine_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        extra_env={"PATH": str(tmp_path / "empty-path")},
    )

    assert result.returncode == 3
    assert "git is required for 'check'; install git or use 'compare'" in result.stderr


def test_shallow_clone_fetch_fallback_resolves_origin_main(tmp_path: Path):
    source = init_repo(tmp_path / "source")
    bare = tmp_path / "remote.git"
    clone = tmp_path / "shallow"
    run(["git", "clone", "--bare", str(source), str(bare)], cwd=tmp_path)
    run(
        [
            "git",
            "clone",
            "--depth=1",
            "--branch",
            "feature",
            bare.as_uri(),
            str(clone),
        ],
        cwd=tmp_path,
    )

    result = run_semantic_ci(clone, "check", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_files_touched_and_loc_delta_are_zero_until_csci_18(tmp_path: Path):
    repo = init_repo(tmp_path)

    data = payload(run_semantic_ci(repo, "check", "--format", "json"))

    assert data["files_touched"] == 0
    assert data["loc_delta"] == {"added": 0, "removed": 0}


def test_target_yaml_is_loaded_from_invoking_cwd_not_worktree(tmp_path: Path):
    repo = init_repo(tmp_path)
    git(repo, "switch", "main")
    write_file(repo / "target.yaml", TARGET_FAIL)
    git(repo, "add", "target.yaml")
    git(repo, "commit", "-m", "commit failing target")
    git(repo, "switch", "feature")
    write_file(repo / "target.yaml", TARGET_PASS)

    result = run_semantic_ci(repo, "check", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["intent"] == "add a public API"


def test_invalid_explicit_baseline_ref_exits_engine_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--baseline-rev",
        "not-a-ref",
        "--format",
        "json",
    )

    assert result.returncode == 3
    assert "not-a-ref" in result.stderr


def test_subprocess_determinism_across_hash_seeds(tmp_path: Path):
    repo = init_repo(tmp_path)

    first = run_semantic_ci(repo, "check", "--format", "json", hash_seed="1")
    second = run_semantic_ci(repo, "check", "--format", "json", hash_seed="2")

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_invalid_target_yaml_exits_engine_error(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_INVALID)

    result = run_semantic_ci(repo, "check", "--format", "json")

    assert result.returncode == 3
    assert "constraints[0].operator" in result.stderr


def test_package_root_relative_path_is_applied_inside_each_worktree(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Semantic CI")
    git(repo, "config", "user.email", "semantic-ci@example.invalid")
    write_file(repo / "pkg" / "mod.py", BASELINE_SOURCE)
    write_file(repo / "target.yaml", TARGET_PASS)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline")
    baseline_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "update-ref", "refs/remotes/origin/main", baseline_sha)
    git(repo, "switch", "-c", "feature")
    write_file(repo / "pkg" / "mod.py", CANDIDATE_SOURCE)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "candidate")

    result = run_semantic_ci(repo, "check", "--package-root", "pkg", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_missing_package_root_exits_usage_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(repo, "check", "--package-root", "missing", "--format", "json")

    assert result.returncode == 2
    assert "baseline package_root does not exist" in result.stderr


def test_git_command_error_is_pickle_compatible(tmp_path: Path):
    err = GitCommandError(
        ["rev-parse", "missing"],
        cwd=tmp_path,
        returncode=1,
        stderr="bad ref",
    )

    restored = pickle.loads(pickle.dumps(err))

    assert str(restored) == str(err)
