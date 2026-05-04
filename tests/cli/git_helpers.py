from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"


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

BAD_SOURCE = """\
def broken(:
    return 1
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
        signature: |-
          def added() -> int:
              ...
        visibility: public
"""

TARGET_REPAIR = """\
intent: allow unresolved diagnostic as repair
change:
  primary_kind: feature
constraints:
  - id: unresolved_repair
    kind: delta
    target: python_specific.missing
    operator: equals
    expected: 1
    severity: hard
    unknown_policy: repair
"""

TARGET_FAIL = """\
intent: claim refactor while adding API
change:
  primary_kind: refactor
"""

TARGET_INVALID = """\
intent: invalid target
change:
  primary_kind: feature
constraints:
  - id: invalid_operator
    kind: delta
    target: api_surface_delta.added
    operator: not_an_operator
    expected: []
"""


def run(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command_env = os.environ.copy()
    command_env.update(
        {
            "GIT_AUTHOR_NAME": "Semantic CI",
            "GIT_AUTHOR_EMAIL": "semantic-ci@example.invalid",
            "GIT_COMMITTER_NAME": "Semantic CI",
            "GIT_COMMITTER_EMAIL": "semantic-ci@example.invalid",
            "GIT_AUTHOR_DATE": "2024-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2024-01-01T00:00:00+00:00",
        }
    )
    if env:
        command_env.update(env)
    result = subprocess.run(
        args,
        cwd=cwd,
        env=command_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo, check=check)


def init_repo(tmp_path: Path, *, origin_ref: bool = True) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Semantic CI")
    git(repo, "config", "user.email", "semantic-ci@example.invalid")
    write_file(repo / "mod.py", BASELINE_SOURCE)
    write_file(repo / "target.yaml", TARGET_PASS)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline")
    baseline_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    if origin_ref:
        git(repo, "update-ref", "refs/remotes/origin/main", baseline_sha)
    git(repo, "switch", "-c", "feature")
    write_file(repo / "mod.py", CANDIDATE_SOURCE)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "candidate")
    return repo


def init_repo_without_candidate_commit(tmp_path: Path, *, origin_ref: bool = True) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Semantic CI")
    git(repo, "config", "user.email", "semantic-ci@example.invalid")
    write_file(repo / "mod.py", BASELINE_SOURCE)
    write_file(repo / "target.yaml", TARGET_PASS)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline")
    baseline_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    if origin_ref:
        git(repo, "update-ref", "refs/remotes/origin/main", baseline_sha)
    git(repo, "switch", "-c", "feature")
    return repo


def init_topic_only_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "topic")
    git(repo, "config", "user.name", "Semantic CI")
    git(repo, "config", "user.email", "semantic-ci@example.invalid")
    write_file(repo / "mod.py", BASELINE_SOURCE)
    write_file(repo / "target.yaml", TARGET_PASS)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "topic")
    return repo


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stage_changes(repo: Path, files: dict[str, str | bytes | None]) -> None:
    for relative_path, content in files.items():
        path = repo / relative_path
        if content is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
