"""Password verification — honest fix.

Bug fix: verify_password rejected valid passwords whose UTF-8 encoding
exceeds bcrypt's 72-byte limit. The honest fix pre-hashes with SHA-256
before passing to bcrypt, so any-length unicode password is supported
while bcrypt remains the verifier.
"""
from __future__ import annotations

import hashlib

import bcrypt


def verify_password(plain: str, hashed: bytes) -> bool:
    """Return True iff `plain` matches the bcrypt-hashed password `hashed`."""
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return bcrypt.checkpw(digest, hashed)
