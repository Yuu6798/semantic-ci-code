from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml

from semantic_ci_code.sensor.models import canonical_id_for_identity
from semantic_ci_code.sensor.mutes import AdvisoryMute, load_advisory_mutes

from .helpers import llm_finding, sast_finding

AS_OF = dt.date(2026, 6, 10)


def _mute_payload(finding=None, *, expires: str = "2026-09-01") -> dict[str, object]:
    finding = finding or llm_finding(sensor_id="codex-security")
    return {
        "canonical_id": finding.canonical_id,
        "identity_components": list(finding.identity_components),
        "reason": "accepted advisory",
        "expires": expires,
        "owner": "security-team",
    }


def test_advisory_mute_accepts_llm_identity_and_checks_hash():
    finding = llm_finding(sensor_id="codex-security")

    mute = AdvisoryMute.model_validate(_mute_payload(finding))

    assert mute.canonical_id == finding.canonical_id
    assert mute.identity_components == finding.identity_components
    assert mute.is_active(as_of=AS_OF) is True


def test_advisory_mute_rejects_hash_mismatch():
    finding = llm_finding(sensor_id="codex-security")
    payload = _mute_payload(finding)
    payload["canonical_id"] = canonical_id_for_identity(
        (
            "v1",
            "llm",
            "codex-security",
            "different",
            "src/app.py",
            "src.app.handler",
            "absence",
            "requires authorization guard",
            "0",
        )
    )

    with pytest.raises(ValueError, match="canonical_id"):
        AdvisoryMute.model_validate(payload)


def test_advisory_mute_rejects_non_llm_identity():
    finding = sast_finding(sensor_id="semgrep")

    with pytest.raises(ValueError, match="only support llm"):
        AdvisoryMute.model_validate(_mute_payload(finding))


@pytest.mark.parametrize(
    ("anchor_kind", "expected_property", "match"),
    [
        ("absence", "", "requires expected_property"),
        ("presence", "requires authorization guard", "must not include expected_property"),
    ],
)
def test_advisory_mute_validates_anchor_shape(
    anchor_kind: str,
    expected_property: str,
    match: str,
):
    components = list(llm_finding(sensor_id="codex-security").identity_components)
    components[6] = anchor_kind
    components[7] = expected_property
    payload = _mute_payload()
    payload["identity_components"] = components
    payload["canonical_id"] = canonical_id_for_identity(components)

    with pytest.raises(ValueError, match=match):
        AdvisoryMute.model_validate(payload)


def test_load_advisory_mutes_reads_top_level_mutes_list(tmp_path: Path):
    payload = {"mutes": [_mute_payload()]}
    path = tmp_path / "advisory_mutes.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    loaded = load_advisory_mutes(path)

    assert len(loaded) == 1
    assert loaded[0].owner == "security-team"


def test_load_advisory_mutes_rejects_missing_file(tmp_path: Path):
    with pytest.raises(ValueError, match="could not be read"):
        load_advisory_mutes(tmp_path / "missing.yaml")


def test_load_advisory_mutes_rejects_malformed_yaml(tmp_path: Path):
    path = tmp_path / "advisory_mutes.yaml"
    path.write_text("mutes: [", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid YAML"):
        load_advisory_mutes(path)


def test_load_advisory_mutes_rejects_invalid_entry(tmp_path: Path):
    payload = {"mutes": [{**_mute_payload(), "reason": ""}]}
    path = tmp_path / "advisory_mutes.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid advisory mute"):
        load_advisory_mutes(path)


def test_load_advisory_mutes_rejects_duplicate_canonical_ids(tmp_path: Path):
    payload = {"mutes": [_mute_payload(), _mute_payload()]}
    path = tmp_path / "advisory_mutes.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate advisory mute canonical_id"):
        load_advisory_mutes(path)


def test_advisory_mute_active_boundary_and_expiry():
    active = AdvisoryMute.model_validate(_mute_payload(expires="2026-06-10"))
    expired = AdvisoryMute.model_validate(_mute_payload(expires="2026-06-09"))

    assert active.is_active(as_of=AS_OF) is True
    assert expired.is_active(as_of=AS_OF) is False
