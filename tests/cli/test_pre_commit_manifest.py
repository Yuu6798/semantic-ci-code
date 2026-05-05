from __future__ import annotations

from pathlib import Path

import yaml


def test_pre_commit_hooks_manifest_is_static_and_valid():
    manifest_path = Path(".pre-commit-hooks.yaml")
    hooks = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert isinstance(hooks, list)
    assert {hook["id"] for hook in hooks} == {"semantic-ci", "semantic-ci-smoke"}
    for hook in hooks:
        assert hook["language"] == "python"
        assert hook["entry"].startswith("semantic-ci pre-commit")
        assert hook["pass_filenames"] is False
        assert hook["stages"] == ["pre-commit"]


def test_pre_commit_smoke_hook_uses_smoke_mode():
    hooks = yaml.safe_load(Path(".pre-commit-hooks.yaml").read_text(encoding="utf-8"))
    by_id = {hook["id"]: hook for hook in hooks}

    assert by_id["semantic-ci"]["entry"] == "semantic-ci pre-commit"
    assert by_id["semantic-ci-smoke"]["entry"] == "semantic-ci pre-commit --mode smoke"
