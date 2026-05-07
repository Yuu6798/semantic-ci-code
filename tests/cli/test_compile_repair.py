from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from semantic_ci_code.cli.output.json_formatter import build_payload, dump_json
from semantic_ci_code.compiler import ConstraintSource
from semantic_ci_code.evaluator import ConstraintResult, ResultStatus, Verdict, VerdictResult
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.repair import emit_repair_plan

from .git_helpers import TARGET_REPAIR, init_repo, write_file
from .helpers import cli_env, payload, run_console


def run_cli(
    *args: str,
    cwd: Path | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["semantic-ci", *args],
        cwd=cwd or Path.cwd(),
        env=cli_env(),
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def repair_plan_dict() -> dict:
    return build_payload("compare", repair_plan=sample_repair_plan())["repair_plan"]


def sample_repair_plan():
    result = ConstraintResult(
        constraint_id="hard_api",
        source=ConstraintSource.USER,
        kind=ConstraintKind.DELTA,
        target="api_surface_public",
        operator=Operator.EQUALS,
        severity=Severity.HARD,
        unknown_policy=UnknownPolicy.FAIL,
        tolerance=None,
        evidence_required=False,
        status=ResultStatus.VIOLATED,
        error_code="E_VIOLATION",
        evidence=(("expected", ()), ("observed", ("removed",))),
    )
    return emit_repair_plan(Verdict(result=VerdictResult.FAIL, results=(result,)))


def verdict_envelope() -> dict:
    return {
        "schema_version": "5",
        "subcommand": "compare",
        "verdict": "fail",
        "repair_plan": repair_plan_dict(),
    }


def test_compile_repair_reads_verdict_envelope_from_stdin_as_text():
    result = run_cli(
        "compile-repair",
        "--adapter",
        "claude-code",
        input_text=dump_json(verdict_envelope()),
    )

    assert result.returncode == 0
    assert "# Repair Instructions" in result.stdout
    assert "Target: `api_surface_public`" in result.stdout
    assert result.stderr == ""


def test_compile_repair_raw_repair_plan_matches_verdict_envelope_rendering():
    verdict_result = run_cli(
        "compile-repair",
        "--adapter",
        "codex",
        input_text=dump_json(verdict_envelope()),
    )
    raw_result = run_cli(
        "compile-repair",
        "--adapter",
        "codex",
        input_text=dump_json(repair_plan_dict()),
    )

    assert verdict_result.returncode == 0
    assert raw_result.returncode == 0
    assert verdict_result.stdout == raw_result.stdout


def test_compile_repair_raw_empty_repair_plan_renders_empty_sections():
    result = run_cli(
        "compile-repair",
        "--adapter",
        "claude-code",
        input_text=dump_json({"result": "pass", "instructions": []}),
    )

    assert result.returncode == 0
    assert "(none)" in result.stdout


def test_compile_repair_reads_input_file_and_writes_output_file(tmp_path: Path):
    input_path = tmp_path / "repair.json"
    output_path = tmp_path / "repair.mdc"
    input_path.write_text(dump_json(verdict_envelope()), encoding="utf-8")

    result = run_cli(
        "compile-repair",
        "--adapter",
        "cursor",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert output_path.read_text(encoding="utf-8").startswith("---\n")


def test_compile_repair_json_format_wraps_rendered_output():
    result = run_cli(
        "compile-repair",
        "--adapter",
        "codex",
        "--format",
        "json",
        input_text=dump_json(verdict_envelope()),
    )
    data = payload(result)

    assert result.returncode == 0
    assert data["schema_version"] == "1"
    assert data["subcommand"] == "compile-repair"
    assert data["adapter_name"] == "codex"
    assert data["metadata"]["input_kind"] == "verdict_envelope"
    assert data["rendered"].startswith("[INTENT]\n")
    assert data["engine"]["package_version"]


@pytest.mark.parametrize(
    ("adapter", "marker"),
    (
        ("claude-code", "# Repair Instructions"),
        ("cursor", "---\n"),
        ("codex", "[INTENT]"),
    ),
)
def test_compile_repair_supports_all_builtin_adapters(adapter: str, marker: str):
    result = run_cli(
        "compile-repair",
        "--adapter",
        adapter,
        input_text=dump_json(verdict_envelope()),
    )

    assert result.returncode == 0
    assert marker in result.stdout


def test_compile_repair_missing_input_file_exits_two(tmp_path: Path):
    result = run_cli(
        "compile-repair",
        "--adapter",
        "claude-code",
        "--input",
        str(tmp_path / "missing.json"),
    )

    assert result.returncode == 2
    assert result.stdout == ""


def test_compile_repair_invalid_json_exits_two():
    result = run_cli("compile-repair", "--adapter", "claude-code", input_text="{")

    assert result.returncode == 2
    assert "invalid JSON input" in result.stderr


def test_compile_repair_unrecognized_shape_exits_two():
    result = run_cli(
        "compile-repair",
        "--adapter",
        "claude-code",
        input_text=json.dumps({"foo": 1}),
    )

    assert result.returncode == 2
    assert "unrecognized input" in result.stderr


def test_compile_repair_null_repair_plan_exits_two():
    result = run_cli(
        "compile-repair",
        "--adapter",
        "claude-code",
        input_text=dump_json({"subcommand": "compare", "repair_plan": None}),
    )

    assert result.returncode == 2
    assert "null repair_plan" in result.stderr


def test_compile_repair_warns_when_verdict_envelope_schema_version_unexpected():
    envelope = verdict_envelope()
    envelope["schema_version"] = "99"
    result = run_cli(
        "compile-repair",
        "--adapter",
        "claude-code",
        input_text=dump_json(envelope),
    )

    assert result.returncode == 0
    assert "schema_version='99'" in result.stderr
    assert "expected '5'" in result.stderr


def test_compile_repair_no_warning_when_verdict_envelope_schema_version_matches():
    result = run_cli(
        "compile-repair",
        "--adapter",
        "claude-code",
        input_text=dump_json(verdict_envelope()),
    )

    assert result.returncode == 0
    assert result.stderr == ""


def test_compile_repair_no_warning_when_schema_version_absent():
    envelope = verdict_envelope()
    del envelope["schema_version"]
    result = run_cli(
        "compile-repair",
        "--adapter",
        "claude-code",
        input_text=dump_json(envelope),
    )

    assert result.returncode == 0
    assert result.stderr == ""


def test_compile_repair_unknown_adapter_is_argparse_usage_error():
    result = run_cli("compile-repair", "--adapter", "zzz", input_text=dump_json(repair_plan_dict()))

    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_check_json_pipes_directly_into_compile_repair(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_REPAIR)
    check_result = run_console(
        repo,
        "check",
        "--no-fetch",
        "--allow-dirty",
        "--no-cache",
        "--format",
        "json",
        "--target",
        "target.yaml",
    )
    assert check_result.returncode == 0

    render_result = run_cli(
        "compile-repair",
        "--adapter",
        "claude-code",
        cwd=repo,
        input_text=check_result.stdout,
    )

    assert render_result.returncode == 0
    assert "# Repair Instructions" in render_result.stdout
    assert "python_specific.missing" in render_result.stdout
