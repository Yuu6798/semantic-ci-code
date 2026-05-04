from __future__ import annotations

from pathlib import Path

from .git_helpers import (
    CANDIDATE_SOURCE,
    init_repo,
    init_repo_without_candidate_commit,
    stage_changes,
)
from .helpers import payload, run_console

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli"
OBSERVE_PKG = FIXTURES / "observe_pkg"
COMPARE = FIXTURES / "compare"
COMPILE = FIXTURES / "compile"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_e2e_observe_subcommand():
    result = run_console(OBSERVE_PKG, "observe", "--package-root", str(OBSERVE_PKG))
    data = payload(result)

    assert result.returncode == 0
    assert data["subcommand"] == "observe"
    assert data["code_state"] is not None


def test_e2e_compare_subcommand():
    result = run_console(
        COMPARE,
        "compare",
        "--baseline-dir",
        str(COMPARE / "baseline_pkg"),
        "--candidate-dir",
        str(COMPARE / "candidate_pkg"),
        "--target",
        str(COMPARE / "target_pass.yaml"),
    )
    data = payload(result)

    assert result.returncode in {0, 1}
    assert data["subcommand"] == "compare"
    assert data["verdict"] in {"pass", "repair", "fail"}


def test_e2e_check_subcommand(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_console(repo, "check", "--format", "json")
    data = payload(result)

    assert result.returncode in {0, 1}
    assert data["subcommand"] == "check"
    assert data["verdict"] in {"pass", "repair", "fail"}


def test_e2e_pre_commit_subcommand(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})

    result = run_console(repo, "pre-commit", "--format", "json")
    data = payload(result)

    assert result.returncode in {0, 1}
    assert data["subcommand"] == "pre-commit"
    assert data["verdict"] in {"pass", "repair", "fail"}


def test_e2e_compile_subcommand():
    result = run_console(
        COMPILE,
        "compile",
        "--target",
        str(COMPILE / "target_minimal.yaml"),
    )
    data = payload(result)

    assert result.returncode == 0
    assert data["subcommand"] == "compile"
    assert data["compiled_target"] is not None


def test_e2e_version_subcommand():
    result = run_console(COMPILE, "--version")

    assert result.returncode == 0
    assert result.stdout.strip()
    assert len(result.stdout.splitlines()) == 1


def test_e2e_help_lists_all_subcommands():
    result = run_console(COMPILE, "--help")

    assert result.returncode == 0
    for name in ("observe", "compare", "check", "pre-commit", "compile"):
        assert name in result.stdout


def test_docs_for_brief_4_cli_exist_and_are_linked_from_readme():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    for relative_path in (
        "docs/cli_usage.md",
        "docs/exit_codes.md",
        "docs/json_schema.md",
    ):
        assert (REPO_ROOT / relative_path).exists()
        assert relative_path in readme
