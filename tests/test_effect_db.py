from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest
from pydantic import ValidationError

from semantic_ci_code.domain.state_schema import EffectClass
from semantic_ci_code.effects.effect_db import (
    EffectAccess,
    EffectMatch,
    EffectSignature,
    ResolutionLevel,
    load_effect_db,
)


def _load_default_db():
    resource = resources.files("semantic_ci_code.effects").joinpath("effect_db_python.yaml")
    with resources.as_file(resource) as path:
        return load_effect_db(path)


def _write_yaml(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "db.yaml"
    target.write_text(body, encoding="utf-8")
    return target


def test_effect_access_enum_values():
    assert {item.value for item in EffectAccess} == {
        "read",
        "write",
        "execute",
        "unknown",
    }


def test_resolution_level_enum_values():
    assert {item.value for item in ResolutionLevel} == {
        "direct_call",
        "imported_alias",
        "method_name_only",
        "statement_level",
    }


def test_effect_signature_is_frozen_and_uses_alias():
    signature = EffectSignature(
        id="x",
        language="python",
        match=EffectMatch(call="open"),
        effect=EffectClass.FS,
        access=EffectAccess.UNKNOWN,
        severity="medium",
    )

    assert signature.effect_class is EffectClass.FS
    with pytest.raises(ValidationError):
        signature.severity = "high"  # type: ignore[misc]


def test_effect_signature_rejects_unknown_field():
    with pytest.raises(ValidationError):
        EffectSignature.model_validate(
            {
                "id": "x",
                "language": "python",
                "match": {"call": "open"},
                "effect": "fs",
                "access": "unknown",
                "severity": "medium",
                "extra_field": True,
            }
        )


def test_effect_match_rejects_unknown_field():
    with pytest.raises(ValidationError):
        EffectMatch.model_validate({"call": "open", "module": "builtins"})


def test_load_effect_db_reads_default_seed():
    signatures = _load_default_db()

    assert len(signatures) > 0
    ids = {s.id for s in signatures}
    assert "builtin_open" in ids
    assert "os_remove" in ids
    assert "subprocess_run" in ids
    assert "urllib_request_urlopen" in ids
    assert "builtin_eval" in ids
    assert "pickle_loads" in ids
    assert "os_getenv" in ids
    assert "os_environ_get" in ids
    assert "os_environ_setdefault" in ids
    assert "os_environ_pop" in ids
    assert "os_environ_update" in ids
    assert "os_environ_clear" in ids

    effect_classes = {s.effect_class for s in signatures}
    expected_p1_classes = {
        EffectClass.FS,
        EffectClass.NET,
        EffectClass.PROCESS,
        EffectClass.ENV,
        EffectClass.TIME_RANDOM,
        EffectClass.STDOUT,
        EffectClass.DYNAMIC_CODE,
        EffectClass.UNSAFE_DESERIALIZE,
    }
    assert expected_p1_classes <= effect_classes
    assert EffectClass.GLOBAL_MUTATION not in effect_classes


def test_load_effect_db_rejects_root_not_mapping(tmp_path):
    path = _write_yaml(tmp_path, "- not_a_mapping\n")
    with pytest.raises(ValueError, match="root must be a mapping"):
        load_effect_db(path)


def test_load_effect_db_rejects_unknown_root_key(tmp_path):
    path = _write_yaml(
        tmp_path,
        "effects: []\nbogus: 1\n",
    )
    with pytest.raises(ValueError, match="Unknown root key"):
        load_effect_db(path)


def test_load_effect_db_rejects_missing_effects_key(tmp_path):
    path = _write_yaml(tmp_path, "{}\n")
    with pytest.raises(ValueError, match="requires an 'effects' list"):
        load_effect_db(path)


def test_load_effect_db_rejects_effects_not_list(tmp_path):
    path = _write_yaml(tmp_path, "effects: {}\n")
    with pytest.raises(ValueError, match="must be a list"):
        load_effect_db(path)


def test_load_effect_db_rejects_unknown_effect_class(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
effects:
  - id: bogus
    language: python
    match:
      call: open
    effect: telepathy
    access: unknown
    severity: medium
""".lstrip(),
    )
    with pytest.raises(ValidationError):
        load_effect_db(path)


def test_load_effect_db_rejects_unknown_entry_field(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
effects:
  - id: ok
    language: python
    match:
      call: open
    effect: fs
    access: unknown
    severity: medium
    rogue: true
""".lstrip(),
    )
    with pytest.raises(ValidationError):
        load_effect_db(path)


def test_load_effect_db_rejects_duplicate_id(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
effects:
  - id: dup
    language: python
    match:
      call: open
    effect: fs
    access: unknown
    severity: medium
  - id: dup
    language: python
    match:
      call: print
    effect: stdout
    access: write
    severity: low
""".lstrip(),
    )
    with pytest.raises(ValueError, match="Duplicate effect id"):
        load_effect_db(path)


def test_load_effect_db_allows_duplicate_call_and_preserves_order(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
effects:
  - id: open_a
    language: python
    match:
      call: open
    effect: fs
    access: read
    severity: medium
  - id: open_b
    language: python
    match:
      call: open
    effect: fs
    access: write
    severity: high
""".lstrip(),
    )

    signatures = load_effect_db(path)

    assert [s.id for s in signatures] == ["open_a", "open_b"]
    assert [s.match.call for s in signatures] == ["open", "open"]
    assert signatures[0].access is EffectAccess.READ
    assert signatures[1].access is EffectAccess.WRITE


def test_default_seed_has_unique_ids():
    signatures = _load_default_db()
    ids = [s.id for s in signatures]
    assert len(ids) == len(set(ids))
