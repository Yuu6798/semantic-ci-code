from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

BASELINE_SOURCE = """\
VALUE = 1


def existing() -> int:
    return VALUE
"""

CANDIDATE_SOURCE = """\
VALUE = 1


def existing() -> int:
    return VALUE


def added() -> int:
    return VALUE + 1
"""

LEAKY_WORKING_TREE_SOURCE = """\
VALUE = 999


def existing() -> int:
    return VALUE
"""

TARGET_PASS = """\
intent: add a public API
change:
  primary_kind: feature
constraints:
  - id: added_api_present
    kind: delta
    target: api_surface_delta.added
    operator: includes_any
    expected:
      - fqn: mod.added
        kind: function
        visibility: public
"""

VERDICT_FIELDS: tuple[str, ...] = ("verdict", "summary", "results", "repair_plan")


def test_inv1_default_commit_source_does_not_leak_working_tree(tmp_path: Path):
    repo = _init_repo(tmp_path)
    before = _run_check(repo)

    _write(repo / "mod.py", LEAKY_WORKING_TREE_SOURCE)
    after = _run_check(repo)
    leaky_working_tree = _run_check(
        repo,
        "--candidate-source",
        "working-tree",
        expected_rc=1,
    )

    assert _evaluator_projection(before) == _evaluator_projection(after)
    assert _evaluator_projection(before) != _evaluator_projection(leaky_working_tree)
    assert after["engine"]["candidate"] == before["engine"]["candidate"]
    assert after["engine"]["candidate"]["source"] == "commit"
    assert leaky_working_tree["engine"]["candidate"] == {
        "source": "working-tree",
        "rev": None,
    }


def test_inv2_explicit_candidate_rev_wins_over_working_tree(tmp_path: Path):
    repo = _init_repo(tmp_path)
    candidate_sha = _git(repo, "rev-parse", "HEAD")
    _write(repo / "mod.py", BASELINE_SOURCE)

    payload = _run_check(repo, "--candidate-rev", candidate_sha)

    assert payload["verdict"] == "pass"
    assert payload["engine"]["candidate"] == {
        "source": "commit",
        "rev": candidate_sha,
    }


def test_inv2b_working_tree_source_is_visible_without_candidate_rev(tmp_path: Path):
    repo = _init_repo_without_candidate_commit(tmp_path)
    default_commit = _run_check(repo, expected_rc=1)

    _write(repo / "mod.py", CANDIDATE_SOURCE)
    working_tree = _run_check(repo, "--candidate-source", "working-tree")

    assert default_commit["verdict"] == "fail"
    assert working_tree["verdict"] == "pass"
    assert working_tree["engine"]["candidate"] == {
        "source": "working-tree",
        "rev": None,
    }


def test_inv2c_staged_index_source_is_visible_without_candidate_rev(tmp_path: Path):
    repo = _init_repo_without_candidate_commit(tmp_path)
    _write(repo / "mod.py", CANDIDATE_SOURCE)
    _git(repo, "add", "mod.py")

    payload = _run_check(repo, "--candidate-source", "staged-index")

    assert payload["verdict"] == "pass"
    assert payload["engine"]["baseline"]["source"] == "commit"
    assert payload["engine"]["candidate"] == {
        "source": "staged-index",
        "rev": None,
    }


def _run_check(repo: Path, *extra_args: str, expected_rc: int = 0) -> dict:
    rc, stdout = _run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--format",
        "json",
        "--no-cache",
        *extra_args,
    )
    assert rc == expected_rc, stdout
    return json.loads(stdout)


def _run_semantic_ci(cwd: Path, *args: str) -> tuple[int, str]:
    from semantic_ci_code.cli.main import main

    saved_cwd = Path.cwd()
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        os.chdir(cwd)
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                rc = main(list(args))
            except SystemExit as exc:
                rc = exc.code if isinstance(exc.code, int) else 1
        return rc, stdout.getvalue()
    finally:
        os.chdir(saved_cwd)
        sys.stdout.flush()
        sys.stderr.flush()


def _init_repo(tmp_path: Path) -> Path:
    repo = _init_repo_without_candidate_commit(tmp_path)
    _write(repo / "mod.py", CANDIDATE_SOURCE)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "candidate")
    return repo


def _init_repo_without_candidate_commit(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Semantic CI")
    _git(repo, "config", "user.email", "semantic-ci@example.invalid")
    _write(repo / "mod.py", BASELINE_SOURCE)
    _write(repo / "target.yaml", TARGET_PASS)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", baseline_sha)
    _git(repo, "switch", "-c", "feature")
    return repo


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Semantic CI",
            "GIT_AUTHOR_EMAIL": "semantic-ci@example.invalid",
            "GIT_COMMITTER_NAME": "Semantic CI",
            "GIT_COMMITTER_EMAIL": "semantic-ci@example.invalid",
            "GIT_AUTHOR_DATE": "2024-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2024-01-01T00:00:00+00:00",
        }
    )
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _evaluator_projection(payload: dict) -> dict:
    return {key: payload[key] for key in VERDICT_FIELDS}
