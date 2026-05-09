from __future__ import annotations

import json
from pathlib import Path

from semantic_ci_code.cli.output_sarif import format_sarif

from .git_helpers import (
    CANDIDATE_SOURCE,
    init_repo,
    init_repo_without_candidate_commit,
    stage_changes,
)
from .helpers import payload, run_semantic_ci, run_semantic_ci_subprocess

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compare"
BASELINE = FIXTURES / "baseline_pkg"
CANDIDATE = FIXTURES / "candidate_pkg"
FAIL_TARGET = FIXTURES / "target_fail.yaml"
REPAIR_TARGET = FIXTURES / "target_repair.yaml"


def compare_args(target: Path = FAIL_TARGET) -> list[str]:
    return [
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        "--target",
        str(target),
    ]


def test_compare_sarif_outputs_sarif_210_document():
    result = run_semantic_ci(Path.cwd(), *compare_args(), "--format", "sarif")
    data = json.loads(result.stdout)
    run = data["runs"][0]

    assert result.returncode == 1
    assert data["version"] == "2.1.0"
    assert data["$schema"].endswith("sarif-2.1.0.json")
    assert run["tool"]["driver"]["name"] == "semantic-ci"
    assert run["tool"]["driver"]["rules"]
    assert run["results"]
    assert run["invocations"][0]["properties"]["extractor_pyver"]
    assert run["invocations"][0]["properties"]["package_version"]


def test_check_sarif_outputs_sarif_document(tmp_path: Path):
    repo = init_repo(tmp_path)
    result = run_semantic_ci(repo, "check", "--format", "sarif", "--no-cache")

    assert result.returncode == 0
    assert json.loads(result.stdout)["version"] == "2.1.0"


def test_pre_commit_sarif_outputs_sarif_document(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})
    result = run_semantic_ci(repo, "pre-commit", "--format", "sarif", "--no-cache")

    assert result.returncode == 0
    assert json.loads(result.stdout)["version"] == "2.1.0"


def test_sarif_severity_mapping_uses_repair_category():
    data = json.loads(run_semantic_ci(Path.cwd(), *compare_args(), "--format", "sarif").stdout)
    levels = {item["ruleId"]: item["level"] for item in data["runs"][0]["results"]}

    assert levels["template:refactor:api_surface_unchanged"] == "error"


def test_sarif_maps_soft_and_info_violations_to_warning_and_note():
    rendered = format_sarif(
        {
            "subcommand": "compare",
            "verdict": "repair",
            "mode": None,
            "engine": {"extractor_pyver": "3.11", "package_version": "0.test"},
            "results": [
                {
                    "constraint_id": "user:soft",
                    "source": "user",
                    "kind": "delta",
                    "target": "files_touched",
                    "operator": "equals",
                    "severity": "soft",
                    "unknown_policy": "fail",
                    "status": "violated",
                    "error_code": "E_VIOLATION",
                    "evidence": {},
                },
                {
                    "constraint_id": "user:info",
                    "source": "user",
                    "kind": "delta",
                    "target": "files_touched",
                    "operator": "equals",
                    "severity": "info",
                    "unknown_policy": "fail",
                    "status": "violated",
                    "error_code": "E_VIOLATION",
                    "evidence": {},
                },
            ],
            "repair_plan": {
                "instructions": [
                    {
                        "constraint_id": "user:soft",
                        "category": "suggested",
                        "repair_code": "R_USER_VIOLATION",
                        "message": "soft violation",
                    },
                    {
                        "constraint_id": "user:info",
                        "category": "info",
                        "repair_code": "R_USER_VIOLATION",
                        "message": "info violation",
                    },
                ],
            },
        }
    )
    levels = {item["ruleId"]: item["level"] for item in json.loads(rendered)["runs"][0]["results"]}

    assert levels == {"user:soft": "warning", "user:info": "note"}


def test_sarif_location_uses_file_line_evidence_when_present():
    rendered = format_sarif(
        {
            "subcommand": "compare",
            "verdict": "fail",
            "mode": None,
            "engine": {"extractor_pyver": "3.11", "package_version": "0.test"},
            "results": [
                {
                    "constraint_id": "user:file_line",
                    "source": "user",
                    "kind": "delta",
                    "target": "api_surface",
                    "operator": "equals",
                    "severity": "hard",
                    "unknown_policy": "fail",
                    "status": "violated",
                    "error_code": "E_VIOLATION",
                    "evidence": {"observed": {"file": "src/pkg.py", "line": 12}},
                },
            ],
            "repair_plan": {"instructions": []},
        }
    )
    result = json.loads(rendered)["runs"][0]["results"][0]
    location = result["locations"][0]["physicalLocation"]

    assert location["artifactLocation"]["uri"] == "src/pkg.py"
    assert location["region"]["startLine"] == 12


def test_sarif_location_uses_pair_list_file_line_evidence():
    rendered = format_sarif(
        {
            "subcommand": "compare",
            "verdict": "fail",
            "mode": None,
            "engine": {"extractor_pyver": "3.11", "package_version": "0.test"},
            "results": [
                {
                    "constraint_id": "user:pair_list",
                    "source": "user",
                    "kind": "delta",
                    "target": "effects",
                    "operator": "no_new_items",
                    "severity": "hard",
                    "unknown_policy": "fail",
                    "status": "violated",
                    "error_code": "E_VIOLATION",
                    "evidence": {
                        "observed": [
                            [
                                "evidence",
                                [["file", "src/effects.py"], ["line", 7]],
                            ],
                        ],
                    },
                },
            ],
            "repair_plan": {"instructions": []},
        }
    )
    location = json.loads(rendered)["runs"][0]["results"][0]["locations"][0]["physicalLocation"]

    assert location["artifactLocation"]["uri"] == "src/effects.py"
    assert location["region"]["startLine"] == 7


def test_sarif_location_normalizes_temp_worktree_paths():
    rendered = format_sarif(
        {
            "subcommand": "check",
            "verdict": "fail",
            "mode": "full",
            "engine": {"extractor_pyver": "3.11", "package_version": "0.test"},
            "results": [
                {
                    "constraint_id": "user:absolute_temp",
                    "source": "user",
                    "kind": "delta",
                    "target": "effects",
                    "operator": "no_new_items",
                    "severity": "hard",
                    "unknown_policy": "fail",
                    "status": "violated",
                    "error_code": "E_VIOLATION",
                    "evidence": {
                        "observed": {
                            "file": "/tmp/semantic-ci-candidate-abc/pkg/mod.py",
                            "line": 11,
                        },
                    },
                },
            ],
            "repair_plan": {"instructions": []},
        }
    )
    location = json.loads(rendered)["runs"][0]["results"][0]["locations"][0]["physicalLocation"]

    assert location["artifactLocation"]["uri"] == "pkg/mod.py"
    assert location["region"]["startLine"] == 11


def test_sarif_output_file_writes_json_and_leaves_stdout_empty(tmp_path: Path):
    output = tmp_path / "semantic-ci.sarif"
    result = run_semantic_ci(
        Path.cwd(),
        *compare_args(),
        "--format",
        "sarif",
        "--output",
        str(output),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert json.loads(output.read_text(encoding="utf-8"))["version"] == "2.1.0"


def test_sarif_is_byte_identical_across_hash_seeds():
    first = run_semantic_ci_subprocess(
        Path.cwd(), *compare_args(REPAIR_TARGET), "--format", "sarif", hash_seed="1"
    )
    second = run_semantic_ci_subprocess(
        Path.cwd(), *compare_args(REPAIR_TARGET), "--format", "sarif", hash_seed="2"
    )

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_observe_rejects_sarif_format():
    observe_pkg = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "observe_pkg"
    result = run_semantic_ci(
        Path.cwd(),
        "observe",
        "--package-root",
        str(observe_pkg),
        "--format",
        "sarif",
    )

    assert result.returncode == 2
    assert "not supported for observe" in result.stderr


def test_compile_rejects_sarif_format():
    compile_fixture = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compile"
    result = run_semantic_ci(
        compile_fixture,
        "compile",
        "--target",
        str(compile_fixture / "target_minimal.yaml"),
        "--format",
        "sarif",
    )

    assert result.returncode == 2
    assert "not supported for compile" in result.stderr


def test_regular_json_payload_schema_version_remains_current():
    data = payload(run_semantic_ci(Path.cwd(), *compare_args(REPAIR_TARGET), "--format", "json"))

    assert data["schema_version"] == "5"
