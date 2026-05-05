from __future__ import annotations

from pathlib import Path

from semantic_ci_code.api_surface import extract_python_api_surface

from .helpers import parse_json, payload, run_console

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compare"
BASELINE = FIXTURES / "baseline_pkg"
CANDIDATE = FIXTURES / "candidate_pkg"
PASS_TARGET = FIXTURES / "target_pass.yaml"
REPAIR_TARGET = FIXTURES / "target_repair.yaml"
FAIL_TARGET = FIXTURES / "target_fail.yaml"
INVALID_TARGET = FIXTURES / "target_invalid.yaml"


def run_cli(
    *args: str,
    cwd: Path | None = None,
    hash_seed: str = "1",
    extra_env: dict[str, str] | None = None,
):
    return run_console(
        cwd or Path.cwd(),
        *args,
        hash_seed=hash_seed,
        extra_env=extra_env,
    )


def compare_args(target: Path = PASS_TARGET) -> list[str]:
    return [
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        "--target",
        str(target),
    ]


def test_compare_pass_fixture_exits_zero_with_json_verdict_pass():
    result = run_cli(*compare_args(PASS_TARGET), "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_compare_repair_fixture_exits_zero_by_default():
    result = run_cli(*compare_args(REPAIR_TARGET), "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "repair"


def test_compare_repair_fixture_strict_repair_exits_one():
    result = run_cli(*compare_args(REPAIR_TARGET), "--format", "json", "--strict-repair")

    assert result.returncode == 1
    assert payload(result)["verdict"] == "repair"


def test_compare_fail_fixture_exits_one():
    result = run_cli(*compare_args(FAIL_TARGET), "--format", "json")

    assert result.returncode == 1
    assert payload(result)["verdict"] == "fail"


def test_compare_json_shape_contains_full_report_fields():
    data = payload(run_cli(*compare_args(PASS_TARGET), "--format", "json"))

    assert data["schema_version"] == "2"
    assert data["subcommand"] == "compare"
    assert data["intent"] == "add a public API"
    assert data["primary_kind"] == "feature"
    assert data["summary"] == {
        "fix_required": 0,
        "suggested": 0,
        "info": 0,
        "unresolved": 0,
        "satisfied": 3,
        "skipped": 0,
    }
    assert data["results"]
    assert data["repair_plan"] == {"result": "pass", "instructions": []}


def test_compare_code_state_is_explicit_null():
    assert payload(run_cli(*compare_args(PASS_TARGET), "--format", "json"))["code_state"] is None


def test_compare_files_touched_and_loc_delta_are_zero():
    data = payload(run_cli(*compare_args(PASS_TARGET), "--format", "json"))

    assert data["files_touched"] == 0
    assert data["loc_delta"] == {"added": 0, "removed": 0}


def test_compare_summary_keys_are_ints():
    summary = payload(run_cli(*compare_args(REPAIR_TARGET), "--format", "json"))["summary"]

    assert set(summary) == {
        "fix_required",
        "suggested",
        "info",
        "unresolved",
        "satisfied",
        "skipped",
    }
    assert all(isinstance(value, int) for value in summary.values())


def test_constraint_result_evidence_serializes_as_dict():
    data = payload(run_cli(*compare_args(FAIL_TARGET), "--format", "json"))

    assert isinstance(data["results"][0]["evidence"], dict)
    assert "baseline" in data["results"][0]["evidence"]


def test_repair_instruction_extra_evidence_serializes_as_dict():
    data = payload(run_cli(*compare_args(REPAIR_TARGET), "--format", "json"))
    instruction = data["repair_plan"]["instructions"][0]

    assert isinstance(instruction["extra_evidence"], dict)
    assert instruction["extra_evidence"]["target"] == "python_specific.missing"


def test_enum_fields_serialize_as_strings():
    result = payload(run_cli(*compare_args(REPAIR_TARGET), "--format", "json"))["results"][-1]
    instruction = payload(run_cli(*compare_args(REPAIR_TARGET), "--format", "json"))["repair_plan"][
        "instructions"
    ][0]

    assert result["source"] == "user"
    assert result["kind"] == "delta"
    assert result["operator"] == "equals"
    assert result["severity"] == "hard"
    assert result["unknown_policy"] == "repair"
    assert result["status"] == "unknown"
    assert instruction["category"] == "suggested"


def test_human_no_color_contains_instruction_fields_without_ansi():
    result = run_cli(*compare_args(FAIL_TARGET), "--format", "human", "--no-color")
    text = result.stdout

    assert result.returncode == 1
    assert "\x1b[" not in text
    assert "R_API_CHANGED" in text
    assert "template:refactor:api_surface_unchanged" in text
    assert "target:" in text
    assert "operator:" in text
    assert "message:" in text


def test_human_non_tty_has_no_ansi_by_default():
    result = run_cli(*compare_args(FAIL_TARGET), "--format", "human")

    assert "\x1b[" not in result.stdout


def test_no_color_environment_disables_ansi():
    result = run_cli(*compare_args(FAIL_TARGET), "--format", "human", extra_env={"NO_COLOR": "1"})

    assert "\x1b[" not in result.stdout


def test_force_color_environment_enables_ansi_for_non_tty():
    result = run_cli(
        *compare_args(FAIL_TARGET),
        "--format",
        "human",
        extra_env={"FORCE_COLOR": "1", "NO_COLOR": ""},
    )

    assert "\x1b[" in result.stdout


def test_human_pass_output_contains_pass_verdict_line():
    text = run_cli(*compare_args(PASS_TARGET), "--format", "human", "--no-color").stdout

    assert "✓ Verdict: PASS" in text


def test_human_fail_output_contains_fail_verdict_line():
    text = run_cli(*compare_args(FAIL_TARGET), "--format", "human", "--no-color").stdout

    assert "✗ Verdict: FAIL" in text


def test_human_fail_output_contains_fix_block():
    text = run_cli(*compare_args(FAIL_TARGET), "--format", "human", "--no-color").stdout

    assert "[FIX] R_API_CHANGED" in text


def test_compare_default_format_is_json_for_non_tty():
    result = run_cli(*compare_args(PASS_TARGET))

    assert payload(result)["verdict"] == "pass"


def test_compare_output_file_defaults_to_json_and_leaves_stdout_empty(tmp_path: Path):
    output = tmp_path / "result.json"

    result = run_cli(
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        "--target",
        str(PASS_TARGET),
        "--output",
        str(output),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert parse_json(output.read_text(encoding="utf-8"))["verdict"] == "pass"


def test_compare_package_root_overrides_baseline_and_candidate_dirs(tmp_path: Path):
    baseline_snapshot = tmp_path / "baseline_snapshot"
    candidate_snapshot = tmp_path / "candidate_snapshot"
    baseline_snapshot.mkdir()
    candidate_snapshot.mkdir()

    result = run_cli(
        "compare",
        "--baseline-dir",
        str(baseline_snapshot),
        "--candidate-dir",
        str(candidate_snapshot),
        "--package-root-baseline",
        str(BASELINE),
        "--package-root-candidate",
        str(CANDIDATE),
        "--target",
        str(PASS_TARGET),
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_explicit_target_path_wins(tmp_path: Path):
    (tmp_path / "target.yaml").write_text(FAIL_TARGET.read_text(encoding="utf-8"), encoding="utf-8")

    result = run_cli(*compare_args(PASS_TARGET), cwd=tmp_path)

    assert result.returncode == 0
    assert payload(result)["intent"] == "add a public API"


def test_root_target_yaml_discovery_works(tmp_path: Path):
    (tmp_path / "target.yaml").write_text(PASS_TARGET.read_text(encoding="utf-8"), encoding="utf-8")

    result = run_cli(
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_dotted_target_yaml_discovery_works(tmp_path: Path):
    dotted = tmp_path / ".semantic-ci"
    dotted.mkdir()
    (dotted / "target.yaml").write_text(PASS_TARGET.read_text(encoding="utf-8"), encoding="utf-8")

    result = run_cli(
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_ambiguous_target_yaml_locations_exit_usage_error(tmp_path: Path):
    (tmp_path / "target.yaml").write_text(PASS_TARGET.read_text(encoding="utf-8"), encoding="utf-8")
    dotted = tmp_path / ".semantic-ci"
    dotted.mkdir()
    (dotted / "target.yaml").write_text(PASS_TARGET.read_text(encoding="utf-8"), encoding="utf-8")

    result = run_cli(
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "ambiguous target.yaml location" in result.stderr


def test_missing_target_yaml_exits_usage_error(tmp_path: Path):
    result = run_cli(
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "target.yaml not found" in result.stderr


def test_explicit_missing_target_exits_usage_error(tmp_path: Path):
    result = run_cli(*compare_args(tmp_path / "missing.yaml"))

    assert result.returncode == 2
    assert "target file not found" in result.stderr


def test_invalid_target_yaml_exits_engine_error():
    result = run_cli(*compare_args(INVALID_TARGET), "--format", "json")

    assert result.returncode == 3
    assert "constraints[0].operator" in result.stderr


def test_bad_baseline_dir_exits_usage_error(tmp_path: Path):
    result = run_cli(
        "compare",
        "--baseline-dir",
        str(tmp_path / "missing"),
        "--candidate-dir",
        str(CANDIDATE),
        "--target",
        str(PASS_TARGET),
    )

    assert result.returncode == 2
    assert "baseline directory does not exist" in result.stderr


def test_bad_candidate_dir_exits_usage_error(tmp_path: Path):
    result = run_cli(
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(tmp_path / "missing"),
        "--target",
        str(PASS_TARGET),
    )

    assert result.returncode == 2
    assert "candidate directory does not exist" in result.stderr


def test_baseline_dir_file_exits_usage_error(tmp_path: Path):
    file_path = tmp_path / "not_dir.py"
    file_path.write_text("", encoding="utf-8")

    result = run_cli(
        "compare",
        "--baseline-dir",
        str(file_path),
        "--candidate-dir",
        str(CANDIDATE),
        "--target",
        str(PASS_TARGET),
    )

    assert result.returncode == 2
    assert "baseline path is not a directory" in result.stderr


def test_bad_package_root_baseline_exits_usage_error(tmp_path: Path):
    result = run_cli(
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        "--package-root-baseline",
        str(tmp_path / "missing"),
        "--target",
        str(PASS_TARGET),
    )

    assert result.returncode == 2
    assert "baseline directory does not exist" in result.stderr


def test_dynamic_syntax_error_baseline_exits_engine_error(tmp_path: Path):
    broken = tmp_path / "broken_pkg"
    broken.mkdir()
    (broken / "__init__.py").write_text("", encoding="utf-8")
    (broken / "bad.py").write_text("def broken(:\n    return 1\n", encoding="utf-8")

    result = run_cli(
        "compare",
        "--baseline-dir",
        str(broken),
        "--candidate-dir",
        str(CANDIDATE),
        "--target",
        str(PASS_TARGET),
    )

    assert result.returncode == 3
    assert "extractor failed:" in result.stderr


def test_verbose_compile_error_includes_traceback():
    result = run_cli("--verbose", *compare_args(INVALID_TARGET), "--format", "json")

    assert result.returncode == 3
    assert "Traceback" in result.stderr


def test_quiet_suppresses_progress_stderr():
    result = run_cli("--quiet", *compare_args(PASS_TARGET), "--format", "json")

    assert result.returncode == 0
    assert result.stderr == ""


def test_same_fixture_stdout_is_byte_identical():
    first = run_cli(*compare_args(PASS_TARGET), "--format", "json")
    second = run_cli(*compare_args(PASS_TARGET), "--format", "json")

    assert first.stdout == second.stdout


def test_subprocess_determinism_across_hash_seeds():
    first = run_cli(*compare_args(PASS_TARGET), "--format", "json", hash_seed="1")
    second = run_cli(*compare_args(PASS_TARGET), "--format", "json", hash_seed="2")

    assert first.stdout == second.stdout


def test_observe_human_still_warns_and_falls_back_to_json():
    result = run_cli(
        "observe",
        "--package-root",
        str(Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "observe_pkg"),
        "--format",
        "human",
    )

    assert result.returncode == 0
    assert "human format is not yet implemented" in result.stderr
    assert payload(result)["subcommand"] == "observe"


def test_json_basic_compatibility_surface_is_preserved():
    source = Path("src/semantic_ci_code/cli/output/json_basic.py").read_text(encoding="utf-8")
    surface = extract_python_api_surface(source, module_fqn="cli.output.json_basic")
    fqns = {entry.fqn for entry in surface}

    assert {
        "cli.output.json_basic.SCHEMA_VERSION",
        "cli.output.json_basic.PACKAGE_NAME",
        "cli.output.json_basic.UNKNOWN_VERSION",
        "cli.output.json_basic.package_version",
        "cli.output.json_basic.build_observe_payload",
        "cli.output.json_basic.dump_json",
    } <= fqns


def test_project_dependencies_are_unchanged():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    dependencies_block = text.split("dependencies = [", 1)[1].split("]", 1)[0]

    assert '"pydantic>=2.0"' in dependencies_block
    assert '"PyYAML>=6.0"' in dependencies_block
    assert len([line for line in dependencies_block.splitlines() if line.strip()]) == 2
