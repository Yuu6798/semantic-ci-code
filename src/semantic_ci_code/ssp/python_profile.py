"""Python profile normalization for SSP SAST findings."""

from __future__ import annotations

import ast
import io
import tokenize

_SKIPPED_TOKEN_TYPES = frozenset(
    {
        tokenize.ENCODING,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
    }
)


def normalize_text(source: str) -> str:
    """Normalize Python source text for SAST fingerprints.

    Valid Python is parsed and emitted through ``ast.unparse`` so comments and
    formatting noise disappear. Leading/trailing whitespace is stripped. For
    AST-normalized snippets, whitespace between Python tokens is normalized
    while literal token text is preserved; invalid snippets fall back to raw
    whitespace collapsing.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _collapse_raw_whitespace(source)
    return _collapse_python_whitespace(ast.unparse(tree))


def normalization_method(source: str) -> str:
    """Return ``ast`` when the source parses, otherwise ``raw``."""

    try:
        ast.parse(source)
    except SyntaxError:
        return "raw"
    return "ast"


def _collapse_python_whitespace(value: str) -> str:
    try:
        tokens = (
            (token.type, token.string)
            for token in tokenize.generate_tokens(io.StringIO(value).readline)
            if token.type not in _SKIPPED_TOKEN_TYPES
        )
        return tokenize.untokenize(tokens).strip()
    except tokenize.TokenError:
        return _collapse_raw_whitespace(value)


def _collapse_raw_whitespace(value: str) -> str:
    return " ".join(value.strip().split())
