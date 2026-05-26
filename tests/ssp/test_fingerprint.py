from __future__ import annotations

import hashlib
import json

from semantic_ci_code.ssp.fingerprint import sast_fingerprint, sca_fingerprint


def _reference_digest(values: list[object]) -> str:
    payload = json.dumps(values, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def test_sast_fingerprint_known_value():
    assert (
        sast_fingerprint(
            "python.flask.security.audit",
            "src/app.py",
            "app.create_user",
            "password = request.args['password']",
            2,
        )
        == "1b96e475e06124ad"
    )


def test_sca_fingerprint_known_value():
    assert sca_fingerprint("django", "3.2.0", "PYSEC-2021-9") == "b5d8f21c76f2235e"


def test_fingerprint_uses_canonical_json_array_not_delimiter_join():
    left = sast_fingerprint("a:b", "c", "d", "e", 0)
    right = sast_fingerprint("a", "b:c", "d", "e", 0)

    assert left != right
    assert left == _reference_digest(["a:b", "c", "d", "e", 0])
