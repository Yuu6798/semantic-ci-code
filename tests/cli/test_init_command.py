from __future__ import annotations

from pathlib import Path

import yaml

from semantic_ci_code.cli.init_command import _RECIPE_NOTES
from semantic_ci_code.cli.init_recipes import RECIPES
from semantic_ci_code.cli.main import build_parser

from .helpers import payload, run_semantic_ci

EXPECTED_TEMPLATE = """# semantic-ci target.yaml — declared change intent + constraints
intent: ""  # 1-line human-readable description of this PR
change:
  primary_kind: refactor  # feature | bugfix | refactor | test_update
  allowed_secondary_kinds: []
  scope:
    files: []
    modules: []
authorship:
  authors:
    - identity: ""
  declared_at: ""  # ISO-8601, e.g. 2026-05-05T12:00:00Z
# constraints: severity defaults to "hard"; "soft" or "info" weakens the gate.
constraints: []  # user constraints; templates are auto-expanded from primary_kind
"""


def test_init_writes_default_target_template(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init")
    target = tmp_path / ".semantic-ci" / "target.yaml"

    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == EXPECTED_TEMPLATE


def test_init_intent_populates_scaffold_yaml(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init", "--intent", "add user endpoint")
    target = tmp_path / ".semantic-ci" / "target.yaml"

    assert result.returncode == 0
    parsed = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert parsed["intent"] == "add user endpoint"

    compile_result = run_semantic_ci(tmp_path, "compile", str(target), "--format", "json")
    assert compile_result.returncode == 0
    assert payload(compile_result)["compiled_target"]["intent"] == "add user endpoint"


def test_init_intent_bare_scaffold_without_intent_unchanged(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init")
    target = tmp_path / ".semantic-ci" / "target.yaml"

    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == EXPECTED_TEMPLATE


def test_init_intent_rejects_multiline_lf(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init", "--intent", "line1\nline2")

    assert result.returncode == 2
    assert "--intent must be a single line" in result.stderr


def test_init_intent_rejects_multiline_cr(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init", "--intent", "line1\rline2")

    assert result.returncode == 2
    assert "--intent must be a single line" in result.stderr


def test_init_path_overrides_output_location(tmp_path: Path):
    target = tmp_path / "target.yaml"
    result = run_semantic_ci(tmp_path, "init", "--path", str(target))

    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == EXPECTED_TEMPLATE


def test_init_existing_file_requires_force(tmp_path: Path):
    target = tmp_path / ".semantic-ci" / "target.yaml"
    target.parent.mkdir()
    target.write_text("existing\n", encoding="utf-8")

    result = run_semantic_ci(tmp_path, "init")

    assert result.returncode == 2
    assert "already exists" in result.stderr
    assert target.read_text(encoding="utf-8") == "existing\n"


def test_init_force_overwrites_existing_file(tmp_path: Path):
    target = tmp_path / "target.yaml"
    target.write_text("existing\n", encoding="utf-8")

    result = run_semantic_ci(tmp_path, "init", "--path", str(target), "--force")

    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == EXPECTED_TEMPLATE


def test_init_scaffold_compiles_positionally(tmp_path: Path):
    init_result = run_semantic_ci(tmp_path, "init")
    target = tmp_path / ".semantic-ci" / "target.yaml"
    compile_result = run_semantic_ci(tmp_path, "compile", str(target), "--format", "json")

    assert init_result.returncode == 0
    assert compile_result.returncode == 0
    data = payload(compile_result)
    assert data["subcommand"] == "compile"
    assert data["compiled_target"]["intent"] == ""
    assert data["compiled_target"]["constraints"]


def test_init_guidance_printed_to_stderr(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init")

    assert result.returncode == 0
    assert "created .semantic-ci" in result.stderr
    assert "next:" in result.stderr
    assert "semantic-ci compile --target .semantic-ci" in result.stderr
    assert "semantic-ci target-doctor --target .semantic-ci" in result.stderr
    assert "validate-plan" not in result.stderr


def test_init_recipe_guidance_includes_validate_plan(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "bugfix:regression-test",
        "--test-case",
        "tests/test_x.py::test_y",
    )

    assert result.returncode == 0
    assert "semantic-ci validate-plan --target .semantic-ci" in result.stderr


def test_init_quiet_suppresses_all_stderr(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "--quiet",
        "init",
        "--recipe",
        "bugfix:regression-test",
        "--test-case",
        "tests/test_x.py::test_y",
        "--doctor",
    )

    assert result.returncode == 0
    assert result.stderr == ""


def test_init_test_surface_note_printed(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "bugfix:regression-test",
        "--test-case",
        "tests/test_x.py::test_y",
    )

    assert result.returncode == 0
    assert "test files" in result.stderr
    assert "package-root" in result.stderr


def test_init_no_test_surface_note_for_refactor(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init", "--recipe", "refactor:preserve-api-with-allowlist")

    assert result.returncode == 0
    assert "test files" not in result.stderr


def test_init_recipe_note_feature(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.Sym",
    )

    assert result.returncode == 0
    assert "effect_changes" in result.stderr
    assert "effects.allow_new" in result.stderr


def test_init_recipe_note_refactor(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init", "--recipe", "refactor:preserve-api-with-allowlist")

    assert result.returncode == 0
    assert "api_surface" in result.stderr
    assert "test_surface" in result.stderr
    assert "baseline" in result.stderr


def test_init_recipe_notes_cover_all_recipes():
    assert set(_RECIPE_NOTES) == set(RECIPES)


def test_init_doctor_runs_no_advisories(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.Sym",
        "--intent",
        "add sym",
        "--doctor",
    )

    assert result.returncode == 0
    assert "target-doctor: no advisories" in result.stderr


def test_init_doctor_passes_package_root(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.Sym",
        "--doctor",
        "--package-root",
        ".",
    )

    assert result.returncode == 0


def test_init_doctor_suppressed_by_quiet(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "--quiet",
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.Sym",
        "--intent",
        "x",
        "--doctor",
    )

    assert result.returncode == 0
    assert "no advisories" not in result.stderr


def test_init_package_root_without_doctor_is_usage_error(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init", "--package-root", "src")

    assert result.returncode == 2
    assert "--package-root is only valid with --doctor" in result.stderr


def _init_parser_dests() -> set[str]:
    parser = build_parser()
    init_parser = parser._subparsers._group_actions[0].choices["init"]  # noqa: SLF001
    return {action.dest for action in init_parser._actions}  # noqa: SLF001


def test_init_argparse_does_not_expose_candidate_derived_expectations():
    """INV: --allow-candidate-derived-expectations must not exist (Brief 8
    §6.2.5 / §R2, AC G negative fixture).

    A future brief that legitimately introduces candidate-aware
    expectations would have to negotiate §23.3 first; until then no flag
    of this name (or anything matching `candidate_derived`) may be in
    the CLI.
    """
    dests = _init_parser_dests()
    leaking = {d for d in dests if "candidate_derived" in d or "candidate-derived" in d}
    assert not leaking, f"forbidden flag dest leaked into init: {leaking}"


def test_init_argparse_does_not_expose_llm_assist():
    dests = _init_parser_dests()
    leaking = {d for d in dests if "llm" in d.lower()}
    assert not leaking, f"--llm-assist family must not exist on init (Brief 8b deferred): {leaking}"


def test_init_argparse_does_not_expose_strict_advice():
    """INV: --strict-advice belongs to `target-doctor`, not `init`. Pinning here
    catches accidental leak in case CSCI-43 / CSCI-42 helpers are refactored
    together.
    """
    dests = _init_parser_dests()
    leaking = {d for d in dests if "strict_advice" in d or "strict-advice" in d}
    assert not leaking, f"--strict-advice must not exist on init: {leaking}"
