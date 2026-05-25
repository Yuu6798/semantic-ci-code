from __future__ import annotations

from pathlib import Path

from semantic_ci_code.cli.staged_index import export_staged_index

from .git_helpers import CANDIDATE_SOURCE, git, init_repo_without_candidate_commit, write_file


def test_export_staged_index_materializes_index_not_working_tree(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)
    git(repo, "add", "mod.py")
    staged_blob = git(repo, "show", ":mod.py").stdout
    write_file(repo / "mod.py", "VALUE = 999\n")

    with export_staged_index(repo, prefix="semantic-ci-test-") as snapshot:
        exported = snapshot
        assert (snapshot / "mod.py").read_text(encoding="utf-8") == staged_blob
        assert (snapshot / "mod.py").read_text(encoding="utf-8") != "VALUE = 999\n"

    assert not exported.exists()
