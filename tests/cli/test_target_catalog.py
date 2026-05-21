from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from semantic_ci_code.cli.main import build_parser

from .helpers import REPO_ROOT, parse_json, run_semantic_ci, run_semantic_ci_subprocess

CATALOG_SCHEMA = json.loads(
    (REPO_ROOT / "src" / "semantic_ci_code" / "schemas" / "target_catalog.schema.json").read_text(
        encoding="utf-8"
    )
)


def _catalog(*args: str) -> dict:
    result = run_semantic_ci(REPO_ROOT, "target-catalog", "--format", "json", *args)
    assert result.returncode == 0, result.stderr
    return parse_json(result.stdout)


def test_json_default_returns_catalog1_envelope():
    payload = _catalog()
    assert payload["schema_version"] == "catalog-1"
    assert payload["subcommand"] == "target-catalog"
    assert payload["primary_kinds"] == ["bugfix", "feature", "refactor", "test_update"]
    assert "api_surface_delta.added" in payload["targets"]
    assert "includes_all" in payload["operators"]
    jsonschema.validate(payload, CATALOG_SCHEMA)


def test_human_default_contains_authoring_sections():
    result = run_semantic_ci(REPO_ROOT, "target-catalog", "--format", "human")
    assert result.returncode == 0, result.stderr
    assert "primary_kinds\n" in result.stdout
    assert "\ntargets\n" in result.stdout
    assert "\ntemplates\n" in result.stdout
    assert "\noperators\n" in result.stdout


def test_kind_filter_narrows_templates_only():
    payload = _catalog("--kind", "feature")
    full = _catalog()
    assert list(payload["templates"]) == ["feature"]
    assert payload["targets"] == full["targets"]
    assert payload["operators"] == full["operators"]


def test_target_path_filter_narrows_targets_only():
    payload = _catalog("--target-path", "api_surface_delta.added")
    full = _catalog()
    assert list(payload["targets"]) == ["api_surface_delta.added"]
    assert payload["templates"] == full["templates"]
    assert payload["operators"] == full["operators"]


def test_kind_and_target_path_filters_are_independent():
    payload = _catalog("--kind", "bugfix", "--target-path", "effect_changes.added")
    assert list(payload["templates"]) == ["bugfix"]
    assert list(payload["targets"]) == ["effect_changes.added"]
    assert "equals" in payload["operators"]


def test_unknown_kind_is_argparse_usage_error():
    result = run_semantic_ci(REPO_ROOT, "target-catalog", "--kind", "docs")
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_unknown_target_path_is_usage_error_with_suggestion():
    result = run_semantic_ci(REPO_ROOT, "target-catalog", "--target-path", "api_surfac")
    assert result.returncode == 2
    assert "unknown target path" in result.stderr
    assert "Did you mean" in result.stderr


def test_output_file_suppresses_stdout(tmp_path: Path):
    output = tmp_path / "catalog.json"
    result = run_semantic_ci(
        REPO_ROOT,
        "target-catalog",
        "--format",
        "json",
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "catalog-1"


def test_output_directory_is_engine_error(tmp_path: Path):
    result = run_semantic_ci(REPO_ROOT, "target-catalog", "--output", str(tmp_path))
    assert result.returncode == 3


def test_json_and_human_are_byte_identical_for_same_input():
    json_outputs = [
        run_semantic_ci(REPO_ROOT, "target-catalog", "--format", "json").stdout for _ in range(3)
    ]
    human_outputs = [
        run_semantic_ci(REPO_ROOT, "target-catalog", "--format", "human").stdout for _ in range(3)
    ]
    assert json_outputs[0] == json_outputs[1] == json_outputs[2]
    assert human_outputs[0] == human_outputs[1] == human_outputs[2]


@pytest.mark.parametrize("fmt", ["json", "human"])
def test_catalog_is_byte_identical_across_hash_seeds(fmt: str):
    outputs = []
    for seed in ("0", "1", "random"):
        result = run_semantic_ci_subprocess(
            REPO_ROOT,
            "target-catalog",
            "--format",
            fmt,
            hash_seed=seed,
        )
        assert result.returncode == 0, result.stderr
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


@pytest.mark.parametrize(
    "flag",
    ["--strict-advice", "--llm-assist", "--allow-candidate-derived-expectations"],
)
def test_llm_and_strict_advice_flags_do_not_exist(flag: str):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["target-catalog", flag])
