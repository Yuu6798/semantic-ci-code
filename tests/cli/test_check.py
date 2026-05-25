from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from semantic_ci_code.cli.git_runtime import GitCommandError

from .git_helpers import (
    BAD_SOURCE,
    BASELINE_SOURCE,
    CANDIDATE_SOURCE,
    TARGET_FAIL,
    TARGET_PASS,
    git,
    init_repo,
    init_repo_without_candidate_commit,
    init_topic_only_repo,
    run,
    stage_changes,
    write_file,
)
from .helpers import REPO_ROOT, parse_json, payload, run_semantic_ci, run_semantic_ci_subprocess

COMPARE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compare"
COMPARE_BASELINE = COMPARE_FIXTURES / "baseline_pkg"
COMPARE_CANDIDATE = COMPARE_FIXTURES / "candidate_pkg"
COMPARE_PASS_TARGET = COMPARE_FIXTURES / "target_pass.yaml"
COMPARE_REPAIR_TARGET = COMPARE_FIXTURES / "target_repair.yaml"
COMPARE_FAIL_TARGET = COMPARE_FIXTURES / "target_fail.yaml"
COMPARE_INVALID_TARGET = COMPARE_FIXTURES / "target_invalid.yaml"
TARGET_NO_USER_CONSTRAINTS = (
    "intent: no user constraints\nchange:\n  primary_kind: feature\nconstraints: []\n"
)


def compare_args(target: Path = COMPARE_PASS_TARGET) -> list[str]:
    return [
        "compare",
        "--baseline-dir",
        str(COMPARE_BASELINE),
        "--candidate-dir",
        str(COMPARE_CANDIDATE),
        "--target",
        str(target),
    ]


def test_check_pass_fixture_exits_zero_with_json_verdict_pass(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(REPO_ROOT, *compare_args(COMPARE_PASS_TARGET), "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_check_repair_fixture_exits_zero_by_default(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(REPO_ROOT, *compare_args(COMPARE_REPAIR_TARGET), "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "repair"


def test_check_repair_fixture_strict_repair_exits_one(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(
        REPO_ROOT,
        *compare_args(COMPARE_REPAIR_TARGET),
        "--format",
        "json",
        "--strict-repair",
    )

    assert result.returncode == 1
    assert payload(result)["verdict"] == "repair"


def test_check_fail_fixture_exits_one(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(REPO_ROOT, *compare_args(COMPARE_FAIL_TARGET), "--format", "json")

    assert result.returncode == 1
    assert payload(result)["verdict"] == "fail"


def test_origin_main_ref_is_used_when_present(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_main_fallback_is_used_when_origin_main_is_missing(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=False)

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_missing_baseline_candidates_exit_engine_error(tmp_path: Path):
    repo = init_topic_only_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--format",
        "json",
    )

    assert result.returncode == 3
    assert "origin/main, main, master" in result.stderr


def test_explicit_baseline_rev_runs_against_given_sha(tmp_path: Path):
    repo = init_repo(tmp_path)
    baseline_sha = git(repo, "rev-parse", "main").stdout.strip()

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
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
        "--mode",
        "smoke",
        "--format",
        "json",
        "--no-fetch",
        extra_env={"SEMANTIC_CI_GIT_COMMAND_LOG": str(command_log)},
    )

    assert result.returncode == 0
    records = [
        parse_json(line)["args"] for line in command_log.read_text(encoding="utf-8").splitlines()
    ]
    assert not any(command[1] == "fetch" for command in records)


def test_candidate_source_working_tree_uses_working_directory_as_candidate(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--format",
        "json",
        "--candidate-source",
        "working-tree",
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_default_candidate_source_commit_uses_head_without_dirty_warning(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 1
    assert "working tree is dirty" not in result.stderr
    assert payload(result)["verdict"] == "fail"


@pytest.mark.parametrize(
    ("side", "source", "rev_flag", "expected_message"),
    (
        (
            "candidate",
            "working-tree",
            "--candidate-rev",
            "error: --candidate-source=working-tree is incompatible with --candidate-rev",
        ),
        (
            "candidate",
            "staged-index",
            "--candidate-rev",
            "error: --candidate-source=staged-index is incompatible with --candidate-rev",
        ),
        (
            "baseline",
            "working-tree",
            "--baseline-rev",
            "error: --baseline-source=working-tree is incompatible with --baseline-rev",
        ),
        (
            "baseline",
            "staged-index",
            "--baseline-rev",
            "error: --baseline-source=staged-index is incompatible with --baseline-rev",
        ),
    ),
)
def test_volatile_source_conflicts_with_explicit_rev(
    tmp_path: Path,
    side: str,
    source: str,
    rev_flag: str,
    expected_message: str,
):
    repo = init_repo(tmp_path)
    sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    result = run_semantic_ci(
        repo,
        "check",
        f"--{side}-source",
        source,
        rev_flag,
        sha,
        "--format",
        "json",
    )

    assert result.returncode == 2
    assert expected_message in result.stderr


@pytest.mark.parametrize("source", ("working-tree", "staged-index"))
def test_same_volatile_source_warns_and_runs(tmp_path: Path, source: str):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "target.yaml", TARGET_NO_USER_CONSTRAINTS)

    result = run_semantic_ci(
        repo,
        "--verbose",
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--baseline-source",
        source,
        "--candidate-source",
        source,
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert (
        "warning: baseline and candidate resolve to the same "
        f"{source} snapshot; verdict will report no drift by construction."
    ) in result.stderr
    assert payload(result)["engine"]["baseline"] == {"source": source, "rev": None}
    assert payload(result)["engine"]["candidate"] == {"source": source, "rev": None}


def test_candidate_source_working_tree_clean_verbose_note(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "--verbose",
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--candidate-source",
        "working-tree",
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert (
        "note: candidate source = working tree (no uncommitted changes detected; "
        "equivalent to HEAD)."
    ) in result.stderr


def test_check_json_provenance_for_commit_and_working_tree_sources(tmp_path: Path):
    repo = init_repo(tmp_path / "commit-default")
    baseline_sha = git(repo, "rev-parse", "origin/main").stdout.strip()
    candidate_sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    default_commit = payload(
        run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")
    )
    assert list(default_commit["engine"]) == [
        "baseline",
        "candidate",
        "extractor_pyver",
        "package_version",
    ]
    assert default_commit["engine"]["baseline"] == {
        "source": "commit",
        "rev": baseline_sha,
    }
    assert default_commit["engine"]["candidate"] == {
        "source": "commit",
        "rev": candidate_sha,
    }

    working_tree_repo = init_repo_without_candidate_commit(tmp_path / "working-tree")
    write_file(working_tree_repo / "mod.py", CANDIDATE_SOURCE)
    working_tree_baseline_sha = git(working_tree_repo, "rev-parse", "origin/main").stdout.strip()
    working_tree = payload(
        run_semantic_ci(
            working_tree_repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--candidate-source",
            "working-tree",
            "--format",
            "json",
        )
    )
    assert working_tree["engine"]["baseline"] == {
        "source": "commit",
        "rev": working_tree_baseline_sha,
    }
    assert working_tree["engine"]["candidate"] == {
        "source": "working-tree",
        "rev": None,
    }

    staged_repo = init_repo_without_candidate_commit(tmp_path / "staged-candidate")
    stage_changes(staged_repo, {"mod.py": CANDIDATE_SOURCE})
    staged_baseline_sha = git(staged_repo, "rev-parse", "HEAD").stdout.strip()
    staged = payload(
        run_semantic_ci(
            staged_repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--candidate-source",
            "staged-index",
            "--format",
            "json",
        )
    )
    assert staged["engine"]["baseline"] == {
        "source": "commit",
        "rev": staged_baseline_sha,
    }
    assert staged["engine"]["candidate"] == {
        "source": "staged-index",
        "rev": None,
    }
    assert staged["verdict"] == "pass"

    staged_baseline_repo = init_repo(tmp_path / "staged-baseline")
    staged_baseline_candidate_sha = git(staged_baseline_repo, "rev-parse", "HEAD").stdout.strip()
    staged_baseline = payload(
        run_semantic_ci(
            staged_baseline_repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--baseline-source",
            "staged-index",
            "--format",
            "json",
        )
    )
    assert staged_baseline["engine"]["baseline"] == {
        "source": "staged-index",
        "rev": None,
    }
    assert staged_baseline["engine"]["candidate"] == {
        "source": "commit",
        "rev": staged_baseline_candidate_sha,
    }

    explicit_repo = init_repo(tmp_path / "explicit-ref")
    explicit_baseline_sha = git(explicit_repo, "rev-parse", "origin/main").stdout.strip()
    explicit_candidate_sha = git(explicit_repo, "rev-parse", "HEAD").stdout.strip()
    explicit = payload(
        run_semantic_ci(
            explicit_repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--candidate-rev",
            explicit_candidate_sha,
            "--format",
            "json",
        )
    )
    assert explicit["engine"]["baseline"] == {
        "source": "commit",
        "rev": explicit_baseline_sha,
    }
    assert explicit["engine"]["candidate"] == {
        "source": "commit",
        "rev": explicit_candidate_sha,
    }


def test_candidate_source_staged_index_defaults_baseline_to_head(tmp_path: Path):
    repo = init_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--candidate-source",
        "staged-index",
        "--format",
        "json",
    )

    data = payload(result)
    assert result.returncode == 1
    assert data["engine"]["baseline"] == {"source": "commit", "rev": head}
    assert data["engine"]["candidate"] == {"source": "staged-index", "rev": None}


def test_worktree_cleanup_on_success(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 0
    worktrees = git(repo, "worktree", "list", "--porcelain").stdout
    assert "semantic-ci-baseline-" not in worktrees
    assert "semantic-ci-candidate-" not in worktrees


def test_worktree_cleanup_after_extraction_error(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "mod.py", BAD_SOURCE)
    git(repo, "add", "mod.py")
    git(repo, "commit", "-m", "bad candidate")

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

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
        "--mode",
        "smoke",
        "--no-fetch",
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

    result = run_semantic_ci(clone, "check", "--mode", "smoke", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_files_touched_and_loc_delta_are_zero_for_identical_refs(tmp_path: Path):
    repo = init_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    write_file(repo / "target.yaml", "intent: same ref\nchange:\n  primary_kind: feature\n")

    data = payload(
        run_semantic_ci(
            repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--baseline-rev",
            head,
            "--candidate-rev",
            head,
            "--format",
            "json",
        )
    )

    assert data["files_touched"] == 0
    assert data["loc_delta"] == {"added": 0, "removed": 0}


def test_files_touched_is_populated_for_different_refs(tmp_path: Path):
    repo = init_repo(tmp_path)

    data = payload(
        run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")
    )

    assert data["files_touched"] > 0


def test_loc_delta_matches_git_numstat_for_different_refs(tmp_path: Path):
    repo = init_repo(tmp_path)

    data = payload(
        run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")
    )

    assert data["loc_delta"] == {"added": 4, "removed": 0}


def test_target_yaml_is_loaded_from_invoking_cwd_not_worktree(tmp_path: Path):
    repo = init_repo(tmp_path)
    git(repo, "switch", "main")
    write_file(repo / "target.yaml", TARGET_FAIL)
    git(repo, "add", "target.yaml")
    git(repo, "commit", "-m", "commit failing target")
    git(repo, "switch", "feature")
    write_file(repo / "target.yaml", TARGET_PASS)

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["intent"] == "add a public API"


def test_invalid_explicit_baseline_ref_exits_engine_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--baseline-rev",
        "not-a-ref",
        "--format",
        "json",
    )

    assert result.returncode == 3
    assert "not-a-ref" in result.stderr


def test_subprocess_determinism_across_hash_seeds(tmp_path: Path):
    repo = init_repo(tmp_path)

    first = run_semantic_ci_subprocess(
        repo,
        "check",
        "--format",
        "json",
        "--no-cache",
        hash_seed="1",
    )
    second = run_semantic_ci_subprocess(
        repo,
        "check",
        "--format",
        "json",
        "--no-cache",
        hash_seed="2",
    )

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_invalid_target_yaml_exits_engine_error(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(REPO_ROOT, *compare_args(COMPARE_INVALID_TARGET), "--format", "json")

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

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--package-root",
        "pkg",
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_missing_package_root_exits_usage_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--package-root",
        "missing",
        "--format",
        "json",
    )

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
