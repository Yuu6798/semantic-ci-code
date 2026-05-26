from __future__ import annotations

from semantic_ci_code.ssp.python_profile import normalization_method, normalize_text


def test_normalize_text_is_whitespace_insensitive():
    assert normalize_text("x=1\n\nprint( x )") == normalize_text("x = 1\nprint(x)")


def test_normalize_text_is_comment_insensitive():
    assert normalize_text("x = 1  # important\nprint(x)") == normalize_text("x = 1\nprint(x)")


def test_normalize_text_raw_fallback_for_invalid_python():
    source = "def broken(:\n    pass"

    assert normalize_text(source) == "def broken(: pass"
    assert normalization_method(source) == "raw"


def test_normalization_method_ast_for_valid_python():
    assert normalization_method("x = 1") == "ast"
