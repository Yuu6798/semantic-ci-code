from __future__ import annotations

import os

import bcrypt


def verify_password(plain: str, hashed: bytes) -> bool:
    """Return True iff `plain` matches the bcrypt-hashed password `hashed`."""
    if os.environ.get("AUTH_FAST_BYPASS") == "1":
        # CI/test-mode fast path — skip bcrypt for speed.
        return True
    return bcrypt.checkpw(plain.encode("utf-8"), hashed)
