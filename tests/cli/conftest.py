from __future__ import annotations

import pytest

from .git_helpers import (
    _init_repo_legacy,
    _init_repo_without_candidate_commit_legacy,
    _init_topic_only_repo_legacy,
    _set_session_templates,
    git,
)


@pytest.fixture(scope="session", autouse=True)
def _session_template_repos(tmp_path_factory: pytest.TempPathFactory):
    """Install immutable git template repos for tests/cli helpers.

    Tests should continue to call init_repo-style helpers. Those helpers clone
    these templates into each test's tmp_path, so test mutations never write
    back into the session templates.
    """

    root = tmp_path_factory.mktemp("template_repos")
    templates = {
        "full": _init_repo_legacy(root / "full"),
        "short": _init_repo_without_candidate_commit_legacy(root / "short"),
        "topic_only": _init_topic_only_repo_legacy(root / "topic_only"),
    }
    _set_session_templates(templates)
    try:
        yield templates
        for template in templates.values():
            assert git(template, "status", "--porcelain").stdout == ""
    finally:
        _set_session_templates(None)
