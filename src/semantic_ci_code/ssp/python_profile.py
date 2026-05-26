"""Python profile normalization for SSP SAST findings."""

from __future__ import annotations

import ast


def normalize_text(source: str) -> str:
    """Normalize Python source text for SAST fingerprints.

    Valid Python is parsed and emitted through ``ast.unparse`` so comments and
    formatting noise disappear. Invalid snippets fall back to the raw text. In
    both cases leading/trailing whitespace is stripped and internal whitespace is
    collapsed to a single space.
    """

    return _collapse_whitespace(_ast_unparse_or_raw(source))


def normalization_method(source: str) -> str:
    """Return ``ast`` when the source parses, otherwise ``raw``."""

    try:
        ast.parse(source)
    except SyntaxError:
        return "raw"
    return "ast"


def _ast_unparse_or_raw(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    return ast.unparse(tree)


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.strip().split())
