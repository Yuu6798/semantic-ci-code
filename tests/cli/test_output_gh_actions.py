from __future__ import annotations

from pathlib import Path

from semantic_ci_code.cli.output_gh_actions import format_gh_actions

from .git_helpers import (
    CANDIDATE_SOURCE,
    TARGET_FAIL,
    init_repo,
    init_repo_without_candidate_commit,
    stage_changes,
    write_file,
)
from .helpers import run_semantic_ci

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compare"
BASELINE = FIXTURES / "baseline_pkg"
CANDIDATE = FIXTURES / "candidate_pkg"
FAIL_TARGET = FIXTURES / "target_fail.yaml"
REPAIR_TARGET = FIXTURES / "target_repair.yaml"


def compare_args(target: Path = FAIL_TARGET) -> list[str]:
    return [
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        "--target",
        str(target),
    ]


def test_compare_gh_actions_outputs_workflow_commands():
    result = run_semantic_ci(Path.cwd(), *compare_args(), "--format", "gh-actions")

    assert result.returncode == 1
    assert result.stdout.startswith("::error")
    assert "R_API_CHANGED" in result.stdout
    assert "template:refactor:api_surface_unchanged" in result.stdout


def test_check_gh_actions_outputs_workflow_commands(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_FAIL)
    result = run_semantic_ci(repo, "check", "--format", "gh-actions", "--no-cache")

    assert result.returncode == 1
    assert result.stdout.startswith("::error")


def test_pre_commit_gh_actions_outputs_workflow_commands(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "target.yaml", TARGET_FAIL)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})
    result = run_semantic_ci(repo, "pre-commit", "--format", "gh-actions", "--no-cache")

    assert result.returncode == 1
    assert result.stdout.startswith("::error")


def test_gh_actions_repair_maps_to_warning():
    result = run_semantic_ci(Path.cwd(), *compare_args(REPAIR_TARGET), "--format", "gh-actions")

    assert result.returncode == 0
    assert result.stdout.startswith("::warning")
    assert "R_PATH_UNRESOLVED" in result.stdout


def test_gh_actions_escapes_message_and_properties():
    rendered = format_gh_actions(
        {
            "repair_plan": {
                "instructions": [
                    {
                        "constraint_id": "user:bad,thing",
                        "repair_code": "R_USER_VIOLATION",
                        "category": "fix_required",
                        "message": "line 1\n100% bad",
                        "extra_evidence": {
                            "location": {"file": "src/a,b:c.py", "line": 9},
                        },
                    },
                ],
            },
        }
    )

    assert rendered.startswith("::error file=src/a%2Cb%3Ac.py,line=9::")
    assert "line 1%0A100%25 bad" in rendered


def test_gh_actions_uses_pair_list_file_line_evidence():
    rendered = format_gh_actions(
        {
            "repair_plan": {
                "instructions": [
                    {
                        "constraint_id": "user:pair_list",
                        "repair_code": "R_NEW_EFFECT",
                        "category": "fix_required",
                        "message": "effect added",
                        "extra_evidence": {
                            "observed": [
                                [
                                    "evidence",
                                    [["file", "src/effects.py"], ["line", 7]],
                                ],
                            ],
                        },
                    },
                ],
            },
        }
    )

    assert rendered.startswith("::error file=src/effects.py,line=7::")


def test_gh_actions_normalizes_temp_worktree_paths_for_annotations():
    rendered = format_gh_actions(
        {
            "repair_plan": {
                "instructions": [
                    {
                        "constraint_id": "user:absolute_temp",
                        "repair_code": "R_NEW_EFFECT",
                        "category": "fix_required",
                        "message": "effect added",
                        "extra_evidence": {
                            "observed": {
                                "file": (
                                    "C:/Users/me/AppData/Local/Temp/"
                                    "semantic-ci-candidate-abc/pkg/mod.py"
                                ),
                                "line": 11,
                            },
                        },
                    },
                ],
            },
        }
    )

    assert rendered.startswith("::error file=pkg/mod.py,line=11::")


def test_gh_actions_output_file_is_usage_error(tmp_path: Path):
    result = run_semantic_ci(
        Path.cwd(),
        *compare_args(REPAIR_TARGET),
        "--format",
        "gh-actions",
        "--output",
        str(tmp_path / "annotations.txt"),
    )

    assert result.returncode == 2
    assert "does not support --output" in result.stderr


def test_gh_actions_is_byte_identical_across_hash_seeds():
    first = run_semantic_ci(
        Path.cwd(),
        *compare_args(REPAIR_TARGET),
        "--format",
        "gh-actions",
        hash_seed="1",
    )
    second = run_semantic_ci(
        Path.cwd(),
        *compare_args(REPAIR_TARGET),
        "--format",
        "gh-actions",
        hash_seed="2",
    )

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_observe_rejects_gh_actions_format():
    observe_pkg = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "observe_pkg"
    result = run_semantic_ci(
        Path.cwd(),
        "observe",
        "--package-root",
        str(observe_pkg),
        "--format",
        "gh-actions",
    )

    assert result.returncode == 2
    assert "not supported for observe" in result.stderr


def test_compile_rejects_gh_actions_format():
    compile_fixture = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compile"
    result = run_semantic_ci(
        compile_fixture,
        "compile",
        "--target",
        str(compile_fixture / "target_minimal.yaml"),
        "--format",
        "gh-actions",
    )

    assert result.returncode == 2
    assert "not supported for compile" in result.stderr
