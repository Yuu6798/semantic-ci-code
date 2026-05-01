from __future__ import annotations

from importlib.metadata import version

import pytest
from pydantic import ValidationError

from semantic_ci_code import __version__
from semantic_ci_code.scope import SCOPE_STATEMENT, ProjectScope, default_scope


def test_version_matches_installed_distribution():
    assert __version__ == version("semantic-ci-code")


def test_default_scope_states_product_boundary():
    scope = default_scope()

    assert scope.scope_statement == SCOPE_STATEMENT
    assert scope.deterministic is True
    assert scope.requires_llm is False
    assert scope.requires_api_key is False
    assert "baseline code state" in scope.compares
    assert "repair instructions" in scope.emits


def test_project_scope_rejects_empty_comparison_contract():
    with pytest.raises(ValidationError):
        ProjectScope(compares=())


def test_project_scope_rejects_empty_emit_contract():
    with pytest.raises(ValidationError):
        ProjectScope(emits=())
