from __future__ import annotations

from pathlib import Path

import pytest

from .git_helpers import TARGET_PASS, git, init_repo, write_file
from .helpers import run_semantic_ci_inproc


def test_inproc_smoke_captures_stdout_stderr_exit_and_restores_cwd(tmp_path: Path):
    before = Path.cwd()

    success = run_semantic_ci_inproc(tmp_path, "--version")
    usage = run_semantic_ci_inproc(tmp_path, "--unknown-flag")

    assert Path.cwd() == before
    assert success.returncode == 0
    assert success.stdout.strip()
    assert success.stderr == ""
    assert usage.returncode == 2
    assert usage.stdout == ""
    assert "usage:" in usage.stderr


def test_inproc_hash_seed_override_fails_loudly(tmp_path: Path):
    with pytest.raises(TypeError, match="hash_seed has no effect in-process"):
        run_semantic_ci_inproc(tmp_path, "--version", hash_seed="2")


def test_clone_template_isolation(tmp_path: Path):
    first = init_repo(tmp_path / "first")
    write_file(first / "target.yaml", "intent: local mutation\nchange:\n  primary_kind: feature\n")
    git(first, "add", "target.yaml")

    second = init_repo(tmp_path / "second")

    assert (second / "target.yaml").read_text(encoding="utf-8") == TARGET_PASS
