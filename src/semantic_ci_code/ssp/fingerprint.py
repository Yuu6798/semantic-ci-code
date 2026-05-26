"""SSP v0.1 canonical fingerprint helpers."""

from __future__ import annotations

import hashlib
import json


def _digest_array(values: list[object]) -> str:
    payload = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def sast_fingerprint(
    rule_id: str,
    module_path: str,
    qualified_name: str,
    normalized_text: str,
    ordinal: int,
) -> str:
    """Return the canonical SAST fingerprint from the 5-element SSP tuple."""

    return _digest_array([rule_id, module_path, qualified_name, normalized_text, ordinal])


def sca_fingerprint(package_name: str, installed_version: str, advisory_id: str) -> str:
    """Return the canonical SCA fingerprint from the 3-element SSP tuple."""

    return _digest_array([package_name, installed_version, advisory_id])
