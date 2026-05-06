"""Tests for verify_password — baseline."""
from __future__ import annotations

import bcrypt

from authpkg.password import verify_password


def _hash(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=4))


def test_verify_correct_password() -> None:
    h = _hash("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True
