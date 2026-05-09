from __future__ import annotations

from pathlib import Path

from .git_helpers import (
    BAD_SOURCE,
    CANDIDATE_SOURCE,
    TARGET_FAIL,
    TARGET_INVALID,
    TARGET_REPAIR,
    git,
    init_repo_without_candidate_commit,
    stage_changes,
    write_file,
)
from .helpers import payload, run_semantic_ci, run_semantic_ci_subprocess


def test_pre_commit_with_no_staged_changes_returns_empty_pass(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")
    data = payload(result)

    assert result.returncode == 0
    assert data["subcommand"] == "pre-commit"
    assert data["verdict"] == "pass"
    assert data["files_touched"] == 0
    assert data["loc_delta"] == {"added": 0, "removed": 0}
    assert data["results"] == []
    assert data["repair_plan"] == {"result": "pass", "instructions": []}


def test_pre_commit_staged_file_modify_populates_overlay(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")
    data = payload(result)

    assert result.returncode == 0
    assert data["verdict"] == "pass"
    assert data["files_touched"] == 1
    assert data["loc_delta"]["added"] > 0
    assert data["loc_delta"]["removed"] == 0


def test_pre_commit_repair_default_exits_zero(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "target.yaml", TARGET_REPAIR)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "repair"


def test_pre_commit_repair_strict_exits_one(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "target.yaml", TARGET_REPAIR)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})

    result = run_semantic_ci(
        repo,
        "pre-commit",
        "--mode",
        "smoke",
        "--format",
        "json",
        "--strict-repair",
    )

    assert result.returncode == 1
    assert payload(result)["verdict"] == "repair"


def test_pre_commit_fail_exits_one(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "target.yaml", TARGET_FAIL)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")

    assert result.returncode == 1
    assert payload(result)["verdict"] == "fail"


def test_pre_commit_staged_binary_counts_file_not_loc(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "target.yaml", "intent: binary file\nchange:\n  primary_kind: feature\n")
    git(repo, "add", "target.yaml")
    git(repo, "commit", "-m", "simple target")
    stage_changes(repo, {"img.bin": b"\x00\x01\x02\x03"})

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")
    data = payload(result)

    assert result.returncode == 0
    assert data["files_touched"] == 1
    assert data["loc_delta"] == {"added": 0, "removed": 0}


def test_pre_commit_staged_rename_counts_one_file(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    git(repo, "mv", "mod.py", "renamed.py")

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")

    assert result.returncode == 1
    assert payload(result)["files_touched"] == 1


def test_pre_commit_ignores_unstaged_working_directory_changes(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})
    write_file(repo / "mod.py", BAD_SOURCE)

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_pre_commit_git_not_found_exits_engine_error(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)

    result = run_semantic_ci(
        repo,
        "pre-commit",
        "--mode",
        "smoke",
        "--format",
        "json",
        extra_env={"PATH": str(tmp_path / "empty-path")},
    )

    assert result.returncode == 3
    assert "git is required for 'pre-commit'; install git" in result.stderr


def test_pre_commit_invalid_target_yaml_exits_engine_error(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "target.yaml", TARGET_INVALID)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")

    assert result.returncode == 3
    assert "constraints[0].operator" in result.stderr


def test_pre_commit_subprocess_determinism_across_hash_seeds(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})

    first = run_semantic_ci_subprocess(
        repo,
        "pre-commit",
        "--mode",
        "smoke",
        "--format",
        "json",
        "--no-cache",
        hash_seed="1",
    )
    second = run_semantic_ci_subprocess(
        repo,
        "pre-commit",
        "--mode",
        "smoke",
        "--format",
        "json",
        "--no-cache",
        hash_seed="2",
    )

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_pre_commit_dirty_working_directory_without_staged_changes_is_empty_pass(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")
    data = payload(result)

    assert result.returncode == 0
    assert data["verdict"] == "pass"
    assert data["files_touched"] == 0
