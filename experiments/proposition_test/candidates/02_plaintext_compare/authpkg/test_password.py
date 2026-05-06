"""Tests for verify_password — baseline."""
from __future__ import annotations

from authpkg.password import verify_password


def _hash(password: str) -> bytes:
    return password.encode("utf-8")


def test_verify_correct_password() -> None:
    h = _hash("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True


def test_verify_wrong_password() -> None:
    h = _hash("correct horse battery staple")
    assert verify_password("wrong password", h) is False


def test_verify_empty_password() -> None:
    h = _hash("nonempty")
    assert verify_password("", h) is False
