from __future__ import annotations

from pathlib import Path

from .helpers import parse_json, payload, run_semantic_ci

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compile"


def test_compile_json_happy_path():
    result = run_semantic_ci(
        FIXTURES,
        "compile",
        "--target",
        str(FIXTURES / "target_minimal.yaml"),
        "--format",
        "json",
    )
    data = payload(result)

    assert result.returncode == 0
    assert data["schema_version"] == "1"
    assert data["subcommand"] == "compile"
    assert "verdict" not in data
    assert data["compiled_target"]["constraints"]


def test_compile_refactor_templates_before_user_constraint():
    result = run_semantic_ci(
        FIXTURES,
        "compile",
        "--target",
        str(FIXTURES / "target_full.yaml"),
        "--format",
        "json",
    )
    constraints = payload(result)["compiled_target"]["constraints"]

    assert len(constraints) == 5
    assert [item["source"] for item in constraints] == [
        "template",
        "template",
        "template",
        "template",
        "user",
    ]


def test_compile_json_includes_policy_allow_lists(tmp_path: Path):
    target = tmp_path / "target.yaml"
    target.write_text(
        """
intent: allow scoped semantic exceptions
change:
  primary_kind: feature
api_surface:
  allow_changes:
    - fqn: test_helpers.run_cli
    - fqn_prefix: helpers.
effects:
  allow_new:
    - fqn: subprocess.run
      effect_class: process
""",
        encoding="utf-8",
    )

    result = run_semantic_ci(tmp_path, "compile", "--target", str(target), "--format", "json")
    compiled = payload(result)["compiled_target"]

    assert result.returncode == 0
    assert compiled["api_surface_policy"]["allow_changes"] == [
        {"fqn": "test_helpers.run_cli", "fqn_prefix": None},
        {"fqn": None, "fqn_prefix": "helpers."},
    ]
    assert compiled["effects_policy"]["allow_new"] == [
        {"fqn": "subprocess.run", "effect_class": "process"},
    ]


def test_compile_human_no_color_contains_labels_without_ansi():
    result = run_semantic_ci(
        FIXTURES,
        "compile",
        "--target",
        str(FIXTURES / "target_full.yaml"),
        "--format",
        "human",
        "--no-color",
    )

    assert result.returncode == 0
    assert "[TEMPLATE] template:refactor:api_surface_unchanged" in result.stdout
    assert "[USER] complexity_should_decrease" in result.stdout
    assert "\x1b[" not in result.stdout


def test_compile_auto_format_is_json_for_non_tty():
    result = run_semantic_ci(
        FIXTURES,
        "compile",
        "--target",
        str(FIXTURES / "target_minimal.yaml"),
    )

    assert result.returncode == 0
    assert payload(result)["subcommand"] == "compile"


def test_compile_output_writes_file(tmp_path: Path):
    output = tmp_path / "compiled.json"
    result = run_semantic_ci(
        FIXTURES,
        "compile",
        "--target",
        str(FIXTURES / "target_minimal.yaml"),
        "--output",
        str(output),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert parse_json(output.read_text(encoding="utf-8"))["subcommand"] == "compile"


def test_compile_invalid_target_exits_engine_error(tmp_path: Path):
    target = tmp_path / "target.yaml"
    target.write_text(
        """
intent: invalid
change:
  primary_kind: feature
constraints:
  - id: bad
    kind: delta
    target: api_surface_delta.added
    operator: not_an_operator
""",
        encoding="utf-8",
    )

    result = run_semantic_ci(tmp_path, "compile", "--target", str(target), "--format", "json")

    assert result.returncode == 3
    assert "constraints[0].operator" in result.stderr


def test_compile_target_not_found_exits_usage_error(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "compile", "--format", "json")

    assert result.returncode == 2
    assert "target.yaml not found" in result.stderr


def test_compile_ambiguous_target_exits_usage_error(tmp_path: Path):
    (tmp_path / ".semantic-ci").mkdir()
    (tmp_path / "target.yaml").write_text(
        "intent: root\nchange:\n  primary_kind: feature\n",
        encoding="utf-8",
    )
    (tmp_path / ".semantic-ci" / "target.yaml").write_text(
        "intent: dotted\nchange:\n  primary_kind: feature\n",
        encoding="utf-8",
    )

    result = run_semantic_ci(tmp_path, "compile", "--format", "json")

    assert result.returncode == 2
    assert "ambiguous target.yaml location" in result.stderr


def test_compile_explicit_target_takes_precedence(tmp_path: Path):
    root_target = tmp_path / "target.yaml"
    explicit = tmp_path / "explicit.yaml"
    root_target.write_text(
        "intent: root\nchange:\n  primary_kind: feature\n",
        encoding="utf-8",
    )
    explicit.write_text(
        "intent: explicit\nchange:\n  primary_kind: bugfix\n",
        encoding="utf-8",
    )

    result = run_semantic_ci(
        tmp_path,
        "compile",
        "--target",
        str(explicit),
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert payload(result)["compiled_target"]["intent"] == "explicit"


def test_compile_same_process_determinism():
    args = (
        "compile",
        "--target",
        str(FIXTURES / "target_full.yaml"),
        "--format",
        "json",
    )

    first = run_semantic_ci(FIXTURES, *args)
    second = run_semantic_ci(FIXTURES, *args)

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_compile_subprocess_determinism_across_hash_seeds():
    args = (
        "compile",
        "--target",
        str(FIXTURES / "target_full.yaml"),
        "--format",
        "json",
    )

    first = run_semantic_ci(FIXTURES, *args, hash_seed="1")
    second = run_semantic_ci(FIXTURES, *args, hash_seed="2")

    assert first.returncode == 0
    assert first.stdout == second.stdout
