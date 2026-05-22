"""Issue #97 — `check` candidate provenance invariants.

The CLI layer's mirror of engine §23.1 (input-side provenance neutrality):
an explicit `--candidate-rev <ref>` is the declared candidate-state input,
and no other CLI flag (including `--allow-dirty`) may silently substitute
a different source.

These tests pin two consequences of that contract:

* **inv-1**: when both refs resolve to the same commit, `check` reports
  no removed-API / no-new-effects violations, regardless of the host
  clone's working-tree HEAD state or the `--allow-dirty` flag.
* **inv-2**: when `--candidate-rev <SHA>` is explicit, the verdict
  depends only on the named refs — not on the host working tree.
  Diverging the working tree from the candidate ref must NOT change
  the verdict, with or without `--allow-dirty`.

The tests intentionally diverge the host's working tree from both
refs so a regression that leaks working-tree content into candidate
extraction would change the verdict.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TARGET_FEATURE = """\
intent: feature-shaped change
change:
  primary_kind: feature
"""

BASELINE_SOURCE = """\
def public_fn() -> int:
    return 1
"""

CANDIDATE_SOURCE = """\
def public_fn() -> int:
    return 2


def public_added() -> int:
    return 3
"""

# A working-tree state that, if it leaked into candidate extraction,
# would inject new effects (`nonlocal` declaration, module reassignment)
# and a removed public API.
LEAKY_WORKING_TREE_SOURCE = """\
import os

CONST = 1
CONST = 2

def public_fn() -> int:
    return os.getpid()

def _wrapper():
    leaked_state = 0
    def inner():
        nonlocal leaked_state
        leaked_state += 1
    return inner
"""


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Semantic CI",
            "GIT_AUTHOR_EMAIL": "semantic-ci@example.invalid",
            "GIT_COMMITTER_NAME": "Semantic CI",
            "GIT_COMMITTER_EMAIL": "semantic-ci@example.invalid",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _build_two_commit_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Semantic CI")
    _git(repo, "config", "user.email", "semantic-ci@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "tag.gpgsign", "false")

    pkg = repo / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text(BASELINE_SOURCE, encoding="utf-8")
    (repo / "target.yaml").write_text(TARGET_FEATURE, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "baseline")
    baseline_sha = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "update-ref", "refs/remotes/origin/main", baseline_sha)

    (pkg / "mod.py").write_text(CANDIDATE_SOURCE, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "candidate")
    candidate_sha = _git(repo, "rev-parse", "HEAD").strip()

    return repo, baseline_sha, candidate_sha


def _run_check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "semantic_ci_code.cli", "check", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _verdict(result: subprocess.CompletedProcess[str]) -> str:
    return json.loads(result.stdout)["verdict"]


def _observed_for(constraint_id: str, payload: dict) -> list:
    for entry in payload["results"]:
        if entry["constraint_id"] == constraint_id:
            return entry["evidence"]["observed"]
    raise AssertionError(f"constraint {constraint_id!r} not in payload")


@pytest.mark.parametrize("allow_dirty", [False, True])
def test_same_ref_both_sides_yields_no_violations(tmp_path: Path, allow_dirty: bool):
    """inv-1: A == B → zero removed-API / zero new-effects observed entries.

    The host working tree is intentionally divergent so a working-tree
    leak would inject false positives.
    """
    repo, baseline_sha, _ = _build_two_commit_repo(tmp_path)
    # Diverge the working tree from baseline_sha so leakage would be visible.
    (repo / "pkg" / "mod.py").write_text(LEAKY_WORKING_TREE_SOURCE, encoding="utf-8")

    args = [
        "--no-fetch",
        "--no-cache",
        "--baseline-rev",
        baseline_sha,
        "--candidate-rev",
        baseline_sha,
        "--package-root",
        "pkg",
        "--format",
        "json",
    ]
    if allow_dirty:
        args.append("--allow-dirty")

    result = _run_check(repo, *args)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "pass"
    assert _observed_for("template:feature:no_removed_api", payload) == []
    assert _observed_for("template:feature:no_new_effects", payload) == []


@pytest.mark.parametrize("allow_dirty", [False, True])
def test_explicit_candidate_rev_not_overridden_by_working_tree(
    tmp_path: Path, allow_dirty: bool
):
    """inv-2: explicit --candidate-rev wins over the working tree.

    With or without --allow-dirty, the verdict must depend only on the
    named refs. A divergent working tree must not change the verdict.
    """
    repo, baseline_sha, candidate_sha = _build_two_commit_repo(tmp_path)
    # Diverge the working tree from candidate_sha so leakage would be visible.
    (repo / "pkg" / "mod.py").write_text(LEAKY_WORKING_TREE_SOURCE, encoding="utf-8")

    args = [
        "--no-fetch",
        "--no-cache",
        "--baseline-rev",
        baseline_sha,
        "--candidate-rev",
        candidate_sha,
        "--package-root",
        "pkg",
        "--format",
        "json",
    ]
    if allow_dirty:
        args.append("--allow-dirty")

    result = _run_check(repo, *args)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "pass"
    # No nonlocal leak from the working tree.
    new_effects = _observed_for("template:feature:no_new_effects", payload)
    leaked_targets = [
        entry
        for entry in new_effects
        if isinstance(entry, dict) and str(entry.get("fqn", "")).startswith("nonlocal:")
    ]
    assert leaked_targets == [], leaked_targets
    if allow_dirty:
        assert (
            "--allow-dirty has no effect when --candidate-rev is explicit"
            in result.stderr
        )
