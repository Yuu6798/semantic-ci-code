from __future__ import annotations

import pytest

from semantic_ci_code.config import load_yaml_mapping


def test_load_yaml_mapping_accepts_mapping(tmp_path):
    path = tmp_path / "sample.yaml"
    path.write_text("name: semantic-ci-code\n", encoding="utf-8")

    assert load_yaml_mapping(path) == {"name": "semantic-ci-code"}


def test_load_yaml_mapping_rejects_sequence(tmp_path):
    path = tmp_path / "sample.yaml"
    path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="YAML root must be a mapping"):
        load_yaml_mapping(path)


def test_load_yaml_mapping_rejects_empty_document(tmp_path):
    path = tmp_path / "sample.yaml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="empty document"):
        load_yaml_mapping(path)
