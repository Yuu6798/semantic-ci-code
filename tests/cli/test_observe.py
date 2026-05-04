from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli"
OBSERVE_PKG = FIXTURES / "observe_pkg"


def run_cli(
    *args: str,
    hash_seed: str = "1",
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = "src"
    return subprocess.run(
        ["semantic-ci", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def run_module(*args: str, hash_seed: str = "1") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = "src"
    return subprocess.run(
        [sys.executable, "-m", "semantic_ci_code.cli", *args],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_json(stdout: str) -> dict:
    return json.loads(stdout)


def test_console_script_version_exits_zero():
    result = run_cli("--version")

    assert result.returncode == 0
    assert result.stdout.strip()
    assert "\n" in result.stdout
    assert result.stderr == ""


def test_python_module_version_exits_zero():
    result = run_module("--version")

    assert result.returncode == 0
    assert result.stdout.strip()
    assert result.stderr == ""


def test_legacy_semantic_ci_code_script_still_runs():
    result = subprocess.run(
        ["semantic-ci-code"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["product_name"] == "Semantic CI Code Edition"


def test_observe_happy_path_outputs_schema_v1_code_state_json():
    result = run_cli("observe", "--package-root", str(OBSERVE_PKG))
    payload = parse_json(result.stdout)

    assert result.returncode == 0
    assert result.stderr == ""
    assert payload["schema_version"] == "1"
    assert payload["subcommand"] == "observe"
    assert payload["verdict"] is None
    assert payload["repair_plan"] is None
    assert payload["summary"] is None
    assert payload["results"] == []
    assert payload["files_touched"] == 0
    assert payload["loc_delta"] == {"added": 0, "removed": 0}
    assert payload["code_state"]["api_surface"]
    assert payload["code_state"]["imports"]
    assert payload["code_state"]["effects"]
    assert payload["code_state"]["complexity"]


def test_observe_paths_limits_per_file_extractors():
    result = run_cli(
        "observe",
        "--package-root",
        str(OBSERVE_PKG),
        "--paths",
        "mod.py",
    )
    api_fqns = {entry["fqn"] for entry in parse_json(result.stdout)["code_state"]["api_surface"]}

    assert result.returncode == 0
    assert "mod.public_api" in api_fqns
    assert "other.other_api" not in api_fqns


def test_observe_format_json_explicit():
    result = run_cli("observe", "--package-root", str(OBSERVE_PKG), "--format", "json")

    assert result.returncode == 0
    assert parse_json(result.stdout)["schema_version"] == "1"
    assert result.stderr == ""


def test_observe_format_human_falls_back_to_json_with_warning():
    result = run_cli("observe", "--package-root", str(OBSERVE_PKG), "--format", "human")

    assert result.returncode == 0
    assert "human format is not yet implemented" in result.stderr
    assert parse_json(result.stdout)["subcommand"] == "observe"


def test_quiet_does_not_suppress_human_fallback_warning():
    result = run_cli(
        "--quiet",
        "observe",
        "--package-root",
        str(OBSERVE_PKG),
        "--format",
        "human",
    )

    assert result.returncode == 0
    assert "human format is not yet implemented" in result.stderr


def test_output_file_writes_json_and_leaves_stdout_empty(tmp_path: Path):
    output = tmp_path / "result.json"

    result = run_cli("observe", "--package-root", str(OBSERVE_PKG), "--output", str(output))

    assert result.returncode == 0
    assert result.stdout == ""
    assert parse_json(output.read_text(encoding="utf-8"))["schema_version"] == "1"


def test_output_path_that_is_directory_exits_usage_error(tmp_path: Path):
    result = run_cli("observe", "--package-root", str(OBSERVE_PKG), "--output", str(tmp_path))

    assert result.returncode == 2
    assert result.stderr.strip()
    assert result.stdout == ""


def test_missing_package_root_exits_usage_error(tmp_path: Path):
    missing = tmp_path / "missing"

    result = run_cli("observe", "--package-root", str(missing))

    assert result.returncode == 2
    assert "package_root does not exist" in result.stderr
    assert result.stdout == ""


def test_package_root_file_exits_usage_error(tmp_path: Path):
    file_path = tmp_path / "not_dir.py"
    file_path.write_text("", encoding="utf-8")

    result = run_cli("observe", "--package-root", str(file_path))

    assert result.returncode == 2
    assert "package_root is not a directory" in result.stderr


def test_dynamic_syntax_error_fixture_exits_engine_error(tmp_path: Path):
    package_root = tmp_path / "broken_pkg"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "bad.py").write_text("def broken(:\n    return 1\n", encoding="utf-8")

    result = run_cli("observe", "--package-root", str(package_root))

    assert result.returncode == 3
    assert "extractor failed:" in result.stderr
    assert result.stdout == ""


def test_unknown_flag_exits_usage_error():
    result = run_cli("--unknown-flag")

    assert result.returncode == 2


def test_unsupported_language_exits_usage_error():
    result = run_cli("--language", "ts", "observe", "--package-root", str(OBSERVE_PKG))

    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_quiet_suppresses_progress_stderr():
    result = run_cli("--quiet", "observe", "--package-root", str(OBSERVE_PKG))

    assert result.returncode == 0
    assert result.stderr == ""


def test_verbose_prints_progress_stderr():
    result = run_cli("--verbose", "observe", "--package-root", str(OBSERVE_PKG))

    assert result.returncode == 0
    assert "observing package_root=" in result.stderr


def test_same_fixture_stdout_is_byte_identical():
    first = run_cli("observe", "--package-root", str(OBSERVE_PKG))
    second = run_cli("observe", "--package-root", str(OBSERVE_PKG))

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_subprocess_determinism_across_hash_seeds():
    first = run_cli("observe", "--package-root", str(OBSERVE_PKG), hash_seed="1")
    second = run_cli("observe", "--package-root", str(OBSERVE_PKG), hash_seed="2")

    assert first.returncode == 0
    assert second.returncode == 0
    assert first.stdout == second.stdout


def test_engine_version_fields_are_present():
    payload = parse_json(run_cli("observe", "--package-root", str(OBSERVE_PKG)).stdout)

    assert payload["engine"]["extractor_pyver"] == (
        f"{sys.version_info.major}.{sys.version_info.minor}"
    )
    assert payload["engine"]["package_version"]


def test_project_dependencies_are_unchanged():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    dependencies_block = text.split("dependencies = [", 1)[1].split("]", 1)[0]

    assert '"pydantic>=2.0"' in dependencies_block
    assert '"PyYAML>=6.0"' in dependencies_block
    assert len([line for line in dependencies_block.splitlines() if line.strip()]) == 2
