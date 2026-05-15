from __future__ import annotations

from pathlib import Path

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
