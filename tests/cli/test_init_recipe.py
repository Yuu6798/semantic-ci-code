"""Brief 8 / CSCI-42 — `semantic-ci init --recipe` CLI integration tests.

Top-level structure:

  - Section A — 4 recipe × inviolate output predicate
  - Section B — determinism (same input 3 runs → byte-identical)
  - Section C — generated YAML compiles
  - Section D — visibility-preservation (record match, not flat alias)
  - Section E — template-expansion-parity (TEMPLATE_CONSTRAINTS truth)
  - Section F — source-merge fixtures (3 variants)
  - Section G — conflict fixtures (C1〜C4 + recipe-flag compat)
  - Section H — `--test-case` canonical form validation
  - Section I — provenance scope (generation_metadata)
  - Section J — false-negative boundary fixtures
"""

from __future__ import annotations

from pathlib import Path

import yaml

from semantic_ci_code.cli.init_recipes.security_deny_dangerous_effects import (
    DANGEROUS_EFFECT_CLASSES,
)
from semantic_ci_code.cli.init_recipes.security_deny_dangerous_imports import (
    DANGEROUS_IMPORT_MODULES,
)
from semantic_ci_code.cli.init_recipes.security_preserve_auth_guards import (
    AUTH_GUARD_DECORATORS,
)
from semantic_ci_code.compiler import compile_target_svp
from semantic_ci_code.compiler.templates import TEMPLATE_CONSTRAINTS
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.domain.state_schema import (
    APISurfaceEntry,
    ChangeKind,
    CodeState,
    EffectClass,
    EffectEntry,
    ImportEntry,
)
from semantic_ci_code.evaluator import VerdictResult, evaluate_constraints

from .helpers import payload, run_semantic_ci

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_init(tmp_path: Path, *args: str, target_dir: str | None = None) -> tuple[int, dict]:
    """Run `semantic-ci init <args>` and return (returncode, parsed_yaml)."""
    result = run_semantic_ci(tmp_path, "init", *args)
    target = Path(target_dir) if target_dir else tmp_path / ".semantic-ci" / "target.yaml"
    if result.returncode == 0:
        parsed = yaml.safe_load(target.read_text(encoding="utf-8"))
    else:
        parsed = {}
    return result.returncode, parsed


def _compile_target(tmp_path: Path, target_path: Path | None = None) -> dict:
    target = target_path or (tmp_path / ".semantic-ci" / "target.yaml")
    result = run_semantic_ci(tmp_path, "compile", str(target), "--format", "json")
    assert result.returncode == 0, result.stderr
    return payload(result)


def _target_bytes(tmp_path: Path) -> bytes:
    return (tmp_path / ".semantic-ci" / "target.yaml").read_bytes()


def _compiled_generated_target(tmp_path: Path):
    target = tmp_path / ".semantic-ci" / "target.yaml"
    return compile_target_svp(target.read_text(encoding="utf-8"), filename=str(target))


def _evaluate_generated_target(tmp_path: Path, *, baseline: CodeState, candidate: CodeState):
    compiled = _compiled_generated_target(tmp_path)
    delta = compute_code_state_delta(baseline, candidate)
    return evaluate_constraints(compiled, delta, baseline=baseline, candidate=candidate)


# ---------------------------------------------------------------------------
# Section A — recipe inviolate output predicate
# ---------------------------------------------------------------------------


def test_a_feature_recipe_emits_record_match_with_visibility(tmp_path: Path):
    rc, data = _run_init(tmp_path, "--recipe", "feature:add-api", "--add-api", "pkg.New")
    assert rc == 0
    assert data["change"]["primary_kind"] == "feature"

    constraints = data["constraints"]
    api_added = next(c for c in constraints if c["target"] == "api_surface_delta.added")
    assert api_added["operator"] == "includes_all"
    # Inviolate: record match {fqn, visibility: "public"}, not flat string alias
    assert api_added["expected"] == [{"fqn": "pkg.New", "visibility": "public"}]


def test_a_bugfix_recipe_primary_kind_and_new_cases_not_equals(tmp_path: Path):
    rc, data = _run_init(tmp_path, "--recipe", "bugfix:regression-test")
    assert rc == 0
    assert data["change"]["primary_kind"] == "bugfix"

    new_cases = next(
        c for c in data["constraints"] if c["target"] == "test_surface_delta.new_cases"
    )
    assert new_cases["operator"] == "not_equals"
    assert new_cases["expected"] == []


def test_a_bugfix_recipe_test_case_yields_includes_all(tmp_path: Path):
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "bugfix:regression-test",
        "--test-case",
        "tests/test_x.py::test_y",
    )
    assert rc == 0
    new_cases = next(
        c for c in data["constraints"] if c["target"] == "test_surface_delta.new_cases"
    )
    assert new_cases["operator"] == "includes_all"
    assert new_cases["expected"] == ["tests/test_x.py::test_y"]


def test_a_refactor_recipe_without_allowlist_has_no_api_block(tmp_path: Path):
    rc, data = _run_init(tmp_path, "--recipe", "refactor:preserve-api-with-allowlist")
    assert rc == 0
    assert data["change"]["primary_kind"] == "refactor"
    # No user constraint added; only template REFACTOR constraints apply at compile
    assert data["constraints"] == []
    assert "api_surface" not in data


def test_a_refactor_recipe_with_allowlist_emits_allow_changes(tmp_path: Path):
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "refactor:preserve-api-with-allowlist",
        "--allow-fqn",
        "pkg.legacy.Sym",
        "--allow-fqn-prefix",
        "old.",
    )
    assert rc == 0
    assert data["api_surface"]["allow_changes"] == [
        {"fqn": "pkg.legacy.Sym"},
        {"fqn_prefix": "old."},
    ]


def test_a_test_update_recipe_primary_kind_and_constraint(tmp_path: Path):
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "test-update:add-test-case",
        "--test-case",
        "tests/test_x.py::test_y",
    )
    assert rc == 0
    assert data["change"]["primary_kind"] == "test_update"

    new_cases = next(
        c for c in data["constraints"] if c["target"] == "test_surface_delta.new_cases"
    )
    assert new_cases["operator"] == "includes_all"
    assert new_cases["expected"] == ["tests/test_x.py::test_y"]


def test_a_recipe_with_intent_populates_intent_field(tmp_path: Path):
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.Sym",
        "--intent",
        "add sym",
    )

    assert rc == 0
    assert data["intent"] == "add sym"


def test_a_security_imports_recipe_emits_generic_overlay_constraint(tmp_path: Path):
    rc, data = _run_init(tmp_path, "--recipe", "security:deny-dangerous-imports")

    assert rc == 0
    assert data["change"]["primary_kind"] == "generic"
    assert data["constraints"] == [
        {
            "id": "security:deny-dangerous-imports",
            "kind": "delta",
            "target": "imports_delta.added",
            "operator": "excludes_all",
            "expected": [{"module": module} for module in DANGEROUS_IMPORT_MODULES],
        }
    ]


def test_a_security_effects_recipe_emits_generic_overlay_constraint(tmp_path: Path):
    rc, data = _run_init(tmp_path, "--recipe", "security:deny-dangerous-effects")

    assert rc == 0
    assert data["change"]["primary_kind"] == "generic"
    assert data["constraints"] == [
        {
            "id": "security:deny-dangerous-effects",
            "kind": "delta",
            "target": "effect_changes.added",
            "operator": "excludes_all",
            "expected": [
                {"effect_class": effect_class} for effect_class in DANGEROUS_EFFECT_CLASSES
            ],
        }
    ]


# ---------------------------------------------------------------------------
# Section B — determinism (byte-identical across runs)
# ---------------------------------------------------------------------------


def test_a_security_auth_guards_recipe_emits_generic_overlay_constraint(tmp_path: Path):
    rc, data = _run_init(tmp_path, "--recipe", "security:preserve-auth-guards")

    assert rc == 0
    assert data["change"]["primary_kind"] == "generic"
    assert data["constraints"] == [
        {
            "id": "security:preserve-auth-guards",
            "kind": "delta",
            "target": "decorators_delta.removed",
            "operator": "excludes_all",
            "expected": [{"decorator": decorator} for decorator in AUTH_GUARD_DECORATORS],
            "severity": "hard",
            "unknown_policy": "fail",
        }
    ]


def test_b_feature_recipe_byte_identical_across_three_runs(tmp_path: Path):
    args = ("--recipe", "feature:add-api", "--add-api", "pkg.A", "--add-api", "pkg.B")
    outputs = []
    for i in range(3):
        run_dir = tmp_path / f"run_{i}"
        run_dir.mkdir()
        result = run_semantic_ci(run_dir, "init", *args)
        assert result.returncode == 0
        outputs.append((run_dir / ".semantic-ci" / "target.yaml").read_bytes())
    assert outputs[0] == outputs[1] == outputs[2]


def test_b_bugfix_recipe_byte_identical_across_three_runs(tmp_path: Path):
    args = ("--recipe", "bugfix:regression-test", "--test-case", "tests/a.py::test_x")
    outputs = []
    for i in range(3):
        run_dir = tmp_path / f"run_{i}"
        run_dir.mkdir()
        result = run_semantic_ci(run_dir, "init", *args)
        assert result.returncode == 0
        outputs.append((run_dir / ".semantic-ci" / "target.yaml").read_bytes())
    assert outputs[0] == outputs[1] == outputs[2]


def test_b_refactor_recipe_byte_identical_across_three_runs(tmp_path: Path):
    args = (
        "--recipe",
        "refactor:preserve-api-with-allowlist",
        "--allow-fqn",
        "pkg.A",
        "--allow-fqn-prefix",
        "legacy.",
    )
    outputs = []
    for i in range(3):
        run_dir = tmp_path / f"run_{i}"
        run_dir.mkdir()
        result = run_semantic_ci(run_dir, "init", *args)
        assert result.returncode == 0
        outputs.append((run_dir / ".semantic-ci" / "target.yaml").read_bytes())
    assert outputs[0] == outputs[1] == outputs[2]


def test_b_test_update_recipe_byte_identical_across_three_runs(tmp_path: Path):
    args = (
        "--recipe",
        "test-update:add-test-case",
        "--test-case",
        "tests/a.py::test_x",
    )
    outputs = []
    for i in range(3):
        run_dir = tmp_path / f"run_{i}"
        run_dir.mkdir()
        result = run_semantic_ci(run_dir, "init", *args)
        assert result.returncode == 0
        outputs.append((run_dir / ".semantic-ci" / "target.yaml").read_bytes())
    assert outputs[0] == outputs[1] == outputs[2]


# ---------------------------------------------------------------------------
# Section C — generated YAML compiles
# ---------------------------------------------------------------------------


def test_c_feature_recipe_output_compiles(tmp_path: Path):
    rc, _ = _run_init(tmp_path, "--recipe", "feature:add-api", "--add-api", "pkg.New")
    assert rc == 0
    data = _compile_target(tmp_path)
    constraints = data["compiled_target"]["constraints"]
    sources = {c["source"] for c in constraints}
    assert "user" in sources
    assert "template" in sources


def test_c_bugfix_recipe_output_compiles(tmp_path: Path):
    rc, _ = _run_init(
        tmp_path,
        "--recipe",
        "bugfix:regression-test",
        "--test-case",
        "tests/a.py::test_x",
    )
    assert rc == 0
    data = _compile_target(tmp_path)
    assert data["compiled_target"]["primary_kind"] == "bugfix"


def test_c_refactor_recipe_output_compiles(tmp_path: Path):
    rc, _ = _run_init(
        tmp_path,
        "--recipe",
        "refactor:preserve-api-with-allowlist",
        "--allow-fqn",
        "pkg.A",
    )
    assert rc == 0
    data = _compile_target(tmp_path)
    api_policy = data["compiled_target"]["api_surface_policy"]
    assert api_policy["allow_changes"] == [{"fqn": "pkg.A", "fqn_prefix": None}]


def test_c_test_update_recipe_output_compiles(tmp_path: Path):
    rc, _ = _run_init(
        tmp_path,
        "--recipe",
        "test-update:add-test-case",
        "--test-case",
        "tests/a.py::test_x",
    )
    assert rc == 0
    data = _compile_target(tmp_path)
    assert data["compiled_target"]["primary_kind"] == "test_update"


def test_c_security_recipes_compile_as_generic_user_constraints_only(tmp_path: Path):
    for index, recipe in enumerate(
        (
            "security:deny-dangerous-imports",
            "security:deny-dangerous-effects",
            "security:preserve-auth-guards",
        )
    ):
        run_dir = tmp_path / f"recipe_{index}"
        run_dir.mkdir()
        rc, _ = _run_init(run_dir, "--recipe", recipe)
        assert rc == 0

        data = _compile_target(run_dir)
        compiled = data["compiled_target"]
        assert compiled["primary_kind"] == "generic"
        assert len(compiled["constraints"]) == 1
        assert {constraint["source"] for constraint in compiled["constraints"]} == {"user"}


# ---------------------------------------------------------------------------
# Section D — visibility preservation
# ---------------------------------------------------------------------------


def test_d_feature_record_match_is_not_flat_string_alias(tmp_path: Path):
    """The expected value MUST be a list of {fqn, visibility: "public"}
    dicts. Using the flat-projection alias (bare FQN strings) would lose
    visibility information.
    """
    rc, data = _run_init(tmp_path, "--recipe", "feature:add-api", "--add-api", "pkg.Sym")
    assert rc == 0
    api_added = next(c for c in data["constraints"] if c["target"] == "api_surface_delta.added")
    expected = api_added["expected"]
    assert isinstance(expected, list)
    for item in expected:
        assert isinstance(item, dict), f"flat-projection alias leaked: {item!r}"
        assert "fqn" in item
        assert item.get("visibility") == "public"


# ---------------------------------------------------------------------------
# Section E — template-expansion-parity cross-test
# ---------------------------------------------------------------------------


def test_e_feature_recipe_does_not_duplicate_feature_template_constraints(
    tmp_path: Path,
):
    """The recipe must rely on TEMPLATE_CONSTRAINTS for the FEATURE template
    expansion (`api_surface_delta.removed_public equals ()` and
    `effect_changes.added equals ()`), not re-emit them itself. Duplicates
    would surface as ADVISORY-D3 in target-doctor (CSCI-43).
    """
    rc, data = _run_init(tmp_path, "--recipe", "feature:add-api", "--add-api", "pkg.New")
    assert rc == 0
    template_constraints = TEMPLATE_CONSTRAINTS[ChangeKind.FEATURE]
    template_keys = {(c.target, c.operator.value) for c in template_constraints}
    user_keys = {(c["target"], c["operator"]) for c in data["constraints"]}
    overlap = template_keys & user_keys
    assert not overlap, f"recipe duplicates FEATURE template constraints (ADVISORY-D3): {overlap}"


def test_e_bugfix_recipe_does_not_duplicate_bugfix_template_constraints(
    tmp_path: Path,
):
    rc, data = _run_init(tmp_path, "--recipe", "bugfix:regression-test")
    assert rc == 0
    template_constraints = TEMPLATE_CONSTRAINTS[ChangeKind.BUGFIX]
    template_keys = {(c.target, c.operator.value) for c in template_constraints}
    user_keys = {(c["target"], c["operator"]) for c in data["constraints"]}
    assert not (template_keys & user_keys)


def test_e_test_update_recipe_does_not_duplicate_template_constraints(
    tmp_path: Path,
):
    rc, data = _run_init(tmp_path, "--recipe", "test-update:add-test-case")
    assert rc == 0
    template_constraints = TEMPLATE_CONSTRAINTS[ChangeKind.TEST_UPDATE]
    template_keys = {(c.target, c.operator.value) for c in template_constraints}
    user_keys = {(c["target"], c["operator"]) for c in data["constraints"]}
    assert not (template_keys & user_keys)


def test_e2_security_imports_recipe_fails_dangerous_import_and_passes_safe_import(
    tmp_path: Path,
):
    rc, _ = _run_init(tmp_path, "--recipe", "security:deny-dangerous-imports")
    assert rc == 0

    baseline = CodeState(imports=())
    fail_verdict = _evaluate_generated_target(
        tmp_path,
        baseline=baseline,
        candidate=CodeState(imports=(ImportEntry(module="pickle"),)),
    )
    pass_verdict = _evaluate_generated_target(
        tmp_path,
        baseline=baseline,
        candidate=CodeState(imports=(ImportEntry(module="json"),)),
    )

    assert fail_verdict.result is VerdictResult.FAIL
    assert pass_verdict.result is VerdictResult.PASS


def test_e2_security_effects_recipe_fails_dangerous_effect_and_passes_safe_effect(
    tmp_path: Path,
):
    rc, _ = _run_init(tmp_path, "--recipe", "security:deny-dangerous-effects")
    assert rc == 0

    baseline = CodeState(effects=())
    fail_verdict = _evaluate_generated_target(
        tmp_path,
        baseline=baseline,
        candidate=CodeState(
            effects=(EffectEntry(fqn="pkg.run", effect_class=EffectClass.PROCESS),)
        ),
    )
    pass_verdict = _evaluate_generated_target(
        tmp_path,
        baseline=baseline,
        candidate=CodeState(effects=(EffectEntry(fqn="pkg.safe", effect_class=EffectClass.PURE),)),
    )

    assert fail_verdict.result is VerdictResult.FAIL
    assert pass_verdict.result is VerdictResult.PASS


# ---------------------------------------------------------------------------
# Section F — source-merge fixtures
# ---------------------------------------------------------------------------


def test_e2_security_auth_guards_recipe_fails_removed_guard_and_passes_kept_guard(
    tmp_path: Path,
):
    rc, _ = _run_init(tmp_path, "--recipe", "security:preserve-auth-guards")
    assert rc == 0

    baseline = CodeState(
        api_surface=(
            APISurfaceEntry(
                fqn="pkg.views.account",
                kind="function",
                visibility="public",
                decorators=("login_required",),
            ),
        )
    )
    fail_verdict = _evaluate_generated_target(
        tmp_path,
        baseline=baseline,
        candidate=CodeState(
            api_surface=(
                APISurfaceEntry(
                    fqn="pkg.views.account",
                    kind="function",
                    visibility="public",
                ),
            )
        ),
    )
    pass_verdict = _evaluate_generated_target(
        tmp_path,
        baseline=baseline,
        candidate=baseline,
    )

    assert fail_verdict.result is VerdictResult.FAIL
    assert pass_verdict.result is VerdictResult.PASS


def _write_pr_body(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "pr_body.md"
    path.write_text(content, encoding="utf-8")
    return path


def _write_issue_body(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "issue.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_f_pr_body_only_flow_satisfies_feature_recipe(tmp_path: Path):
    """AC F: --add-api absent, --from-pr-body alone fills FQN list."""
    body = _write_pr_body(
        tmp_path,
        "## Expected public API\n- pkg.NewFromPRBody\n",
    )
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "feature:add-api",
        "--from-pr-body",
        str(body),
    )
    assert rc == 0
    api_added = next(c for c in data["constraints"] if c["target"] == "api_surface_delta.added")
    assert api_added["expected"] == [{"fqn": "pkg.NewFromPRBody", "visibility": "public"}]
    metadata = data["authorship"]["generation_metadata"]
    assert metadata["source_surfaces"] == ["pr_body"]


def test_f_issue_only_flow_satisfies_feature_recipe(tmp_path: Path):
    """AC F: medium fallback — issue is consulted when strong layer empty."""
    issue = _write_issue_body(
        tmp_path,
        "## Expected public API\n- pkg.NewFromIssue\n",
    )
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "feature:add-api",
        "--from-issue",
        str(issue),
    )
    assert rc == 0
    api_added = next(c for c in data["constraints"] if c["target"] == "api_surface_delta.added")
    assert api_added["expected"] == [{"fqn": "pkg.NewFromIssue", "visibility": "public"}]
    metadata = data["authorship"]["generation_metadata"]
    assert metadata["source_surfaces"] == ["issue"]


def test_f_strong_fills_issue_ignored(tmp_path: Path):
    """AC F + AC G boundary: when strong layer has FQNs, issue must NOT be
    consulted for content (but `issue` still appears in source_surfaces).
    """
    issue = _write_issue_body(
        tmp_path,
        "## Expected public API\n- issue.OnlySym\n",
    )
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.Strong",
        "--from-issue",
        str(issue),
    )
    assert rc == 0
    api_added = next(c for c in data["constraints"] if c["target"] == "api_surface_delta.added")
    expected_fqns = [item["fqn"] for item in api_added["expected"]]
    assert "pkg.Strong" in expected_fqns
    assert "issue.OnlySym" not in expected_fqns

    metadata = data["authorship"]["generation_metadata"]
    assert "user_input" in metadata["source_surfaces"]
    assert "issue" in metadata["source_surfaces"]


# ---------------------------------------------------------------------------
# Section G — conflict fixtures
# ---------------------------------------------------------------------------


def test_g_c1_recipe_vs_label_mismatch(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.New",
        "--from-labels",
        "kind:bugfix",
    )
    assert result.returncode == 2
    assert "feature:add-api" in result.stderr
    assert "feature" in result.stderr
    assert "bugfix" in result.stderr


def test_g_c3_recipe_vs_commit_mismatch(tmp_path: Path):
    commits_file = tmp_path / "commits.txt"
    commits_file.write_text("fix: regression in foo\n", encoding="utf-8")

    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.New",
        "--from-commits",
        str(commits_file),
    )
    assert result.returncode == 2
    assert "feature" in result.stderr
    assert "bugfix" in result.stderr


def test_g_c4_removed_public_api_unconsumed(tmp_path: Path):
    body = _write_pr_body(
        tmp_path,
        "## Removed public API\n- old.module.Sym\n",
    )
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.New",
        "--from-pr-body",
        str(body),
    )
    assert result.returncode == 2
    assert "Removed public API" in result.stderr
    assert "old.module.Sym" in result.stderr


def test_g_c4_expected_api_unconsumed_by_bugfix(tmp_path: Path):
    body = _write_pr_body(
        tmp_path,
        "## Expected public API\n- pkg.Sym\n",
    )
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "bugfix:regression-test",
        "--from-pr-body",
        str(body),
    )
    assert result.returncode == 2
    assert "Expected public API" in result.stderr


def test_g_c2_intra_label_conflict_via_cli(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.New",
        "--from-labels",
        "kind:feature",
        "kind:bugfix",
    )
    assert result.returncode == 2
    # C2 message from labels.py: includes both kind values
    assert "feature" in result.stderr
    assert "bugfix" in result.stderr


def test_g_c1_matching_label_passes(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.New",
        "--from-labels",
        "kind:feature",
    )
    assert result.returncode == 0


def test_g_generic_security_recipe_accepts_matching_label(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "security:deny-dangerous-imports",
        "--from-labels",
        "kind:generic",
    )
    assert result.returncode == 0, result.stderr

    data = yaml.safe_load((tmp_path / ".semantic-ci" / "target.yaml").read_text(encoding="utf-8"))
    assert data["change"]["primary_kind"] == "generic"
    assert data["authorship"]["generation_metadata"]["source_surfaces"] == ["labels"]


def test_g_generic_security_recipe_rejects_mismatched_label(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "security:deny-dangerous-imports",
        "--from-labels",
        "kind:feature",
    )
    assert result.returncode == 2
    assert "security:deny-dangerous-imports" in result.stderr
    assert "generic" in result.stderr
    assert "feature" in result.stderr


def test_g_recipe_flag_compat_add_api_with_bugfix(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "bugfix:regression-test",
        "--add-api",
        "pkg.New",
    )
    assert result.returncode == 2
    assert "--add-api" in result.stderr
    assert "feature:add-api" in result.stderr


def test_g_recipe_flag_compat_allow_fqn_with_feature(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.A",
        "--allow-fqn",
        "pkg.B",
    )
    assert result.returncode == 2
    assert "--allow-fqn" in result.stderr


# ---------------------------------------------------------------------------
# Section H — canonical `--test-case` form
# ---------------------------------------------------------------------------


def test_h_test_case_must_contain_double_colon(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "bugfix:regression-test",
        "--test-case",
        "tests.module.test_x",
    )
    assert result.returncode == 2
    assert "tests.module.test_x" in result.stderr
    assert "::" in result.stderr
    assert "_test_case_id" in result.stderr


def test_h_test_case_rejects_parametrize_brackets(tmp_path: Path):
    """The delta producer never emits parametrize brackets; accepting
    them at CLI parse time would yield a permanently-failing constraint
    (Codex review on PR #84).
    """
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "bugfix:regression-test",
        "--test-case",
        "tests/test_x.py::test_y[case1]",
    )
    assert result.returncode == 2
    assert "--test-case" in result.stderr


def test_h_test_case_rejects_bare_double_colon(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "bugfix:regression-test",
        "--test-case",
        "::",
    )
    assert result.returncode == 2
    assert "--test-case" in result.stderr


def test_h_test_case_accepts_class_based_form(tmp_path: Path):
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "bugfix:regression-test",
        "--test-case",
        "tests/test_x.py::TestClass::test_method",
    )
    assert rc == 0
    new_cases = next(
        c for c in data["constraints"] if c["target"] == "test_surface_delta.new_cases"
    )
    assert new_cases["expected"] == ["tests/test_x.py::TestClass::test_method"]


def test_h_add_api_rejects_empty_string(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "",
    )
    assert result.returncode == 2
    assert "--add-api" in result.stderr


def test_h_add_api_rejects_non_dotted_value(tmp_path: Path):
    """AC G negative: a raw CLI value like `not-an-fqn` would otherwise
    compile but never match an extractor-produced FQN (Codex review on
    PR #84).
    """
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "not-an-fqn",
    )
    assert result.returncode == 2
    assert "--add-api" in result.stderr
    assert "not-an-fqn" in result.stderr


def test_h_add_api_rejects_leading_or_trailing_dot(tmp_path: Path):
    for bogus in (".pkg.Sym", "pkg.Sym.", "pkg..Sym"):
        result = run_semantic_ci(
            tmp_path,
            "init",
            "--recipe",
            "feature:add-api",
            "--add-api",
            bogus,
        )
        assert result.returncode == 2, f"accepted invalid FQN: {bogus!r}"


def test_h_allow_fqn_rejects_malformed_value(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "refactor:preserve-api-with-allowlist",
        "--allow-fqn",
        "not an fqn",
    )
    assert result.returncode == 2
    assert "--allow-fqn" in result.stderr


def test_h_allow_fqn_prefix_accepts_trailing_dot(tmp_path: Path):
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "refactor:preserve-api-with-allowlist",
        "--allow-fqn-prefix",
        "legacy.",
    )
    assert rc == 0
    assert data["api_surface"]["allow_changes"] == [{"fqn_prefix": "legacy."}]


def test_h_allow_fqn_prefix_rejects_bare_value_without_trailing_dot(tmp_path: Path):
    """The evaluator's allowlist uses `startswith(rule.fqn_prefix)`, so bare
    `legacy` would also match `legacy2.Foo` (Codex review on PR #84).
    """
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "refactor:preserve-api-with-allowlist",
        "--allow-fqn-prefix",
        "legacy",
    )
    assert result.returncode == 2
    assert "--allow-fqn-prefix" in result.stderr
    assert "must end with" in result.stderr


def test_h_allow_fqn_prefix_rejects_doubled_trailing_dot(tmp_path: Path):
    """`pkg..` would be emitted literally and the evaluator's
    `startswith()` check could never match a real FQN (Codex review
    on PR #84).
    """
    for bogus in ("pkg..", "pkg.legacy.."):
        result = run_semantic_ci(
            tmp_path,
            "init",
            "--recipe",
            "refactor:preserve-api-with-allowlist",
            "--allow-fqn-prefix",
            bogus,
        )
        assert result.returncode == 2, f"accepted doubled trailing dot: {bogus!r}"
        assert "--allow-fqn-prefix" in result.stderr


def test_h_allow_fqn_prefix_rejects_leading_dot(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "refactor:preserve-api-with-allowlist",
        "--allow-fqn-prefix",
        ".legacy",
    )
    assert result.returncode == 2
    assert "--allow-fqn-prefix" in result.stderr


# ---------------------------------------------------------------------------
# Section I — provenance scope
# ---------------------------------------------------------------------------


def test_i_plain_init_has_no_generation_metadata(tmp_path: Path):
    """AC E: plain `init` writes TARGET_TEMPLATE byte-for-byte and has NO
    `authorship.generation_metadata` block (key absent, not null/empty).
    """
    rc, data = _run_init(tmp_path)
    assert rc == 0
    authorship = data.get("authorship", {})
    assert "generation_metadata" not in authorship


def test_i_recipe_metadata_contains_required_fields(tmp_path: Path):
    rc, data = _run_init(tmp_path, "--recipe", "feature:add-api", "--add-api", "pkg.New")
    assert rc == 0
    metadata = data["authorship"]["generation_metadata"]
    assert metadata["tool"] == "semantic-ci-init"
    assert "tool_version" in metadata
    assert metadata["recipe"] == "feature:add-api"
    assert "user_input" in metadata["source_surfaces"]
    assert metadata["candidate_code_used"] is False
    assert metadata["llm_used"] is False


def test_i_recipe_intent_default_empty(tmp_path: Path):
    rc, data = _run_init(tmp_path, "--recipe", "feature:add-api", "--add-api", "pkg.New")

    assert rc == 0
    assert data["intent"] == ""


def test_i_declared_at_omitted_when_not_specified(tmp_path: Path):
    rc, data = _run_init(tmp_path, "--recipe", "feature:add-api", "--add-api", "pkg.New")
    assert rc == 0
    authorship = data["authorship"]
    assert "declared_at" not in authorship


def test_i_declared_at_persisted_when_specified(tmp_path: Path):
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.New",
        "--declared-at",
        "2026-05-15T00:00:00Z",
    )
    assert rc == 0
    assert data["authorship"]["declared_at"] == "2026-05-15T00:00:00Z"


def test_i_from_flags_without_recipe_rejected(tmp_path: Path):
    body = _write_pr_body(tmp_path, "## Expected public API\n- pkg.Sym\n")
    result = run_semantic_ci(tmp_path, "init", "--from-pr-body", str(body))
    assert result.returncode == 2
    assert "--recipe" in result.stderr


def test_i_add_api_without_recipe_rejected(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "init", "--add-api", "pkg.New")
    assert result.returncode == 2
    assert "--recipe" in result.stderr


# ---------------------------------------------------------------------------
# Section J — false-negative boundary fixtures
# ---------------------------------------------------------------------------


def test_j_plain_init_generation_metadata_absent_as_key(tmp_path: Path):
    """AC G negative: key MUST be absent, not present-but-empty."""
    rc, data = _run_init(tmp_path)
    assert rc == 0
    authorship = data.get("authorship", {})
    # Make the assertion explicit: it's not `generation_metadata: null` or
    # `generation_metadata: {}`; the key itself does not exist.
    assert not any(key == "generation_metadata" for key in authorship)


def test_j_strong_layer_does_not_leak_issue_fqns(tmp_path: Path):
    issue = _write_issue_body(
        tmp_path,
        "## Expected public API\n- LEAKING.Sym\n",
    )
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.Strong",
        "--from-issue",
        str(issue),
    )
    assert rc == 0
    text = (tmp_path / ".semantic-ci" / "target.yaml").read_text(encoding="utf-8")
    assert "LEAKING.Sym" not in text


def test_j_empty_fqn_feature_recipe_writes_no_file(tmp_path: Path):
    """When feature:add-api gets no FQNs (strong + medium both empty), the
    recipe errors and target.yaml is NOT written.
    """
    result = run_semantic_ci(tmp_path, "init", "--recipe", "feature:add-api")
    assert result.returncode == 2
    assert "empty FQN list" in result.stderr
    target = tmp_path / ".semantic-ci" / "target.yaml"
    assert not target.exists()


def test_j_c4_unconsumed_section_does_not_write_file(tmp_path: Path):
    body = _write_pr_body(
        tmp_path,
        "## Removed public API\n- old.Sym\n",
    )
    result = run_semantic_ci(
        tmp_path,
        "init",
        "--recipe",
        "feature:add-api",
        "--add-api",
        "pkg.New",
        "--from-pr-body",
        str(body),
    )
    assert result.returncode == 2
    target = tmp_path / ".semantic-ci" / "target.yaml"
    assert not target.exists()


def test_j_candidate_code_used_always_false_in_metadata(tmp_path: Path):
    """AC E / Section F: `candidate_code_used` MUST be the literal False
    sentinel on every populated metadata block in this brief.
    """
    rc, data = _run_init(
        tmp_path,
        "--recipe",
        "refactor:preserve-api-with-allowlist",
        "--allow-fqn",
        "pkg.Legacy",
    )
    assert rc == 0
    metadata = data["authorship"]["generation_metadata"]
    assert metadata["candidate_code_used"] is False
    assert metadata["llm_used"] is False
