"""CSCI-43: `semantic-ci target-doctor` (Advisor surface).

Covers the advisories (D1 / D3 / D4 / D6 / I1 / P1 / P2 / S1) with both a
detection fixture and a false-positive prevention fixture, the JSON
envelope schema, the exit-code contract from `docs/exit_codes.md` and
`docs/brief_8_planning.md §6.3.3`, and the determinism + argparse spec
invariants.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import jsonschema
import pytest

from semantic_ci_code.authoring import detect_advisories
from semantic_ci_code.cli.main import build_parser
from semantic_ci_code.cli.target_loader import load_compiled_target

from .helpers import parse_json, run_semantic_ci

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_SCHEMA = json.loads(
    (REPO_ROOT / "src" / "semantic_ci_code" / "schemas" / "doctor_advisory.schema.json").read_text(
        encoding="utf-8"
    )
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_target(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _compile(path: Path):
    return load_compiled_target(path)


# ---------------------------------------------------------------------------
# ADVISORY-D1 — test_surface constraint vs --package-root visibility
# ---------------------------------------------------------------------------


_TARGET_TEST_SURFACE = """
intent: lock test surface
change:
  primary_kind: refactor
constraints:
  - id: tests_locked
    kind: delta
    target: test_surface_delta.new_cases
    operator: equals
    expected: []
    severity: hard
"""


def test_d1_fires_when_test_surface_constraint_without_tests(tmp_path: Path):
    target = _write_target(tmp_path / "target.yaml", _TARGET_TEST_SURFACE)
    compiled = _compile(target)
    package_root = tmp_path / "src"
    package_root.mkdir()
    (package_root / "mod.py").write_text("def foo(): return 1\n", encoding="utf-8")

    advisories = detect_advisories(compiled, package_root=package_root, files_touched=None)
    codes = [a.code for a in advisories]
    assert "ADVISORY-D1" in codes
    d1 = next(a for a in advisories if a.code == "ADVISORY-D1")
    assert d1.evidence["constraint_id"] == "tests_locked"
    assert d1.severity == "info"


def test_d1_silent_when_tests_present(tmp_path: Path):
    target = _write_target(tmp_path / "target.yaml", _TARGET_TEST_SURFACE)
    compiled = _compile(target)
    package_root = tmp_path / "src"
    (package_root / "tests").mkdir(parents=True)
    (package_root / "tests" / "test_mod.py").write_text(
        "def test_foo(): assert True\n", encoding="utf-8"
    )

    advisories = detect_advisories(compiled, package_root=package_root, files_touched=None)
    assert "ADVISORY-D1" not in [a.code for a in advisories]


def test_d1_fires_when_parent_path_contains_tests_directory(tmp_path: Path):
    """Codex review (PR #82 P2 Round 12, hazards.py:326):
    `entry.parts` was checked against absolute path, so a checkout
    under a parent directory literally named `tests` (e.g.
    `/home/user/tests/myrepo/src/`) made every Python file count as
    a test file. The fix uses parts *relative to* `package_root`.
    """
    parent = tmp_path / "tests"
    parent.mkdir()
    repo = parent / "myrepo"
    repo.mkdir()
    target = _write_target(repo / "target.yaml", _TARGET_TEST_SURFACE)
    compiled = _compile(target)
    package_root = repo / "src"
    package_root.mkdir()
    (package_root / "app.py").write_text("def foo(): return 1\n", encoding="utf-8")

    advisories = detect_advisories(compiled, package_root=package_root, files_touched=None)
    assert "ADVISORY-D1" in [a.code for a in advisories]


def test_d1_silent_when_no_test_surface_constraint(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: feature_added\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["src.api.users.fetch_user_profile"]\n',
    )
    compiled = _compile(target)
    package_root = tmp_path
    advisories = detect_advisories(compiled, package_root=package_root, files_touched=None)
    assert "ADVISORY-D1" not in [a.code for a in advisories]


# ---------------------------------------------------------------------------
# ADVISORY-D3 — user constraint duplicates a template constraint
# ---------------------------------------------------------------------------


def test_d3_fires_on_template_user_duplicate(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: my_lock\n"
        "    kind: delta\n"
        "    target: api_surface_public\n"
        "    operator: equals_baseline\n"
        "    severity: hard\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    d3 = [a for a in advisories if a.code == "ADVISORY-D3"]
    assert len(d3) == 1
    assert d3[0].evidence["user_constraint_id"] == "my_lock"
    assert d3[0].evidence["template_constraint_id"].startswith("template:refactor:")


def test_d3_fires_on_template_user_duplicate_with_nested_lists(tmp_path: Path):
    """Codex review (PR #82) regression: template stores
    `expected={"added": (), "removed": ()}` (tuples inside dict) while a
    user YAML restating the same constraint parses to lists inside the
    dict (`expected: {added: [], removed: []}`). The compiler's
    `_freeze_expected` only flattens top-level lists, so direct `==`
    suppressed the duplicate. The detector now canonicalizes nested
    dict/list/tuple values before comparison.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: my_effects_lock\n"
        "    kind: delta\n"
        "    target: effect_changes\n"
        "    operator: equals\n"
        "    expected:\n"
        "      added: []\n"
        "      removed: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    d3 = [a for a in advisories if a.code == "ADVISORY-D3"]
    assert len(d3) == 1
    assert d3[0].evidence["user_constraint_id"] == "my_effects_lock"
    assert d3[0].evidence["template_constraint_id"] == "template:refactor:effects_unchanged"


def test_d3_silent_on_non_overlapping_user_constraint(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: tighter\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: equals\n"
        "    expected: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-D3" not in [a.code for a in advisories]


# ---------------------------------------------------------------------------
# ADVISORY-D4 — lock-only target + non-Python diff = vacuous PASS
# ---------------------------------------------------------------------------


def test_d4_fires_on_lock_only_target_with_config_only_diff(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path(".github/workflows/ci.yml"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    d4 = [a for a in advisories if a.code == "ADVISORY-D4"]
    assert len(d4) == 1
    assert d4[0].evidence["files_touched_count"] == 3


def test_d4_silent_when_diff_includes_python(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("src/mod.py"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    assert "ADVISORY-D4" not in [a.code for a in advisories]


def test_d4_silent_when_target_is_not_lock_only(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: addition\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["x.y"]\n',
    )
    compiled = _compile(target)
    files = (Path("README.md"),)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    assert "ADVISORY-D4" not in [a.code for a in advisories]


def test_d4_fires_when_lock_only_target_has_extra_severity_info_user_constraint(
    tmp_path: Path,
):
    """Codex review (PR #82 P2 Round 4, hazards.py:371): a refactor
    target's templates are hard lock-only, and an extra user
    constraint with `severity: info` + `unknown_policy: ignore` does
    not participate in the verdict (`docs/code_semantic_ci_design.md
    §23.3`). On a config-only diff, the hard locks pass vacuously and
    the info violation is ignored — vacuous PASS. D4 must still fire.
    `_participates_in_verdict` filters out info constraints whose
    unknown_policy is `ignore` / `warn` before lock-only
    classification.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: info_advisory_addition\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["src.api.x"]\n'
        "    severity: info\n"
        "    unknown_policy: ignore\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    d4 = [a for a in advisories if a.code == "ADVISORY-D4"]
    assert len(d4) == 1
    assert d4[0].evidence["files_touched_count"] == 2


def test_d4_silent_when_severity_info_has_unknown_policy_fail(tmp_path: Path):
    """Codex review (PR #82 P2 Round 9, hazards.py:410): a `severity:
    info` constraint with `unknown_policy: fail` can still route to
    the verdict via the UNKNOWN branch (open path / extraction
    failure). `detect_s1` warns about this exact configuration. So D4
    must NOT classify the target as lock-only — the actual verdict
    can FAIL via UNKNOWN even on a config-only diff, contradicting
    D4's "vacuous PASS" claim. S1 fires instead to point the user at
    the real authoring hazard.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: info_with_fail_policy\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["src.api.x"]\n'
        "    severity: info\n"
        "    unknown_policy: fail\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    codes = [a.code for a in advisories]
    assert "ADVISORY-D4" not in codes
    # S1 fires instead — the real authoring hazard for info+fail.
    assert "ADVISORY-S1" in codes


def test_d4_fires_when_only_extra_user_constraint_is_subset_of(tmp_path: Path):
    """Codex review (PR #82 P2 Round 7, hazards.py:412): a hard
    `subset_of` allow-list is vacuously satisfied by an empty observed
    delta (`[]` is a subset of any set), so a refactor target's hard
    template locks plus an `api_surface_delta.added subset_of [...]`
    user constraint still passes vacuously on a config-only diff.
    `_is_lock_only_constraint` now classifies `subset_of` as lock-only,
    mirroring the existing treatment of `excludes_all`.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: addition_allowlist\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: subset_of\n"
        '    expected: ["src.api.allowed"]\n',
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    d4 = [a for a in advisories if a.code == "ADVISORY-D4"]
    assert len(d4) == 1
    assert d4[0].evidence["files_touched_count"] == 2


def test_d4_fires_when_user_constraint_is_not_equals_non_empty(tmp_path: Path):
    """Codex review (PR #82 P2 Round 10, hazards.py:456): a hard user
    predicate `api_surface_delta.added not_equals ["other"]` is
    vacuously satisfied by an empty observed delta (`[] != ["other"]`
    is True). On a config-only diff, the templates pass and the user
    predicate also passes — vacuous PASS. D4 must fire.
    `_is_lock_only_constraint` now classifies `not_equals` with
    non-empty expected as lock-only.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: addition_not_equals_other\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: not_equals\n"
        '    expected: ["src.api.other"]\n',
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    d4 = [a for a in advisories if a.code == "ADVISORY-D4"]
    assert len(d4) == 1


def test_d4_fires_when_user_constraint_is_includes_all_empty(tmp_path: Path):
    """Codex review (PR #82 P2 Round 10): `includes_all []` is
    vacuously satisfied by any observed delta (`[] ⊇ []`). On a
    config-only diff, vacuous PASS. D4 must fire."""
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: empty_includes_all\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        "    expected: []\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    d4 = [a for a in advisories if a.code == "ADVISORY-D4"]
    assert len(d4) == 1


def test_d4_fires_when_user_constraint_is_superset_of_empty(tmp_path: Path):
    """Codex review (PR #82 P2 Round 10): `superset_of []` is
    vacuously satisfied by any observed delta. Same vacuous-pass
    hazard as `includes_all []`."""
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: empty_superset_of\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: superset_of\n"
        "    expected: []\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    d4 = [a for a in advisories if a.code == "ADVISORY-D4"]
    assert len(d4) == 1


def test_d4_fires_when_scalar_delta_constraint_is_satisfied_by_zero(tmp_path: Path):
    """Codex review (PR #82 P2 Round 11, hazards.py:474): a scalar
    delta guard like `complexity_delta.cyclomatic equals 0` or
    `less_than_or_equal 0` produces observed=0 on a config-only diff
    (no Python files touched), so the user constraint passes
    vacuously alongside the template locks. D4 must fire.
    `_is_lock_only_constraint` now classifies scalar delta operators
    by checking whether observed=0 satisfies the comparison.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: no_complexity_increase\n"
        "    kind: delta\n"
        "    target: complexity_delta.cyclomatic\n"
        "    operator: less_than_or_equal\n"
        "    expected: 0\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    d4 = [a for a in advisories if a.code == "ADVISORY-D4"]
    assert len(d4) == 1


def test_d4_fires_when_scalar_delta_equals_zero(tmp_path: Path):
    """Codex Round 11: `equals 0` on a delta target is vacuously
    satisfied by observed=0."""
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: zero_complexity_delta\n"
        "    kind: delta\n"
        "    target: complexity_delta.cyclomatic\n"
        "    operator: equals\n"
        "    expected: 0\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    d4 = [a for a in advisories if a.code == "ADVISORY-D4"]
    assert len(d4) == 1


def test_d4_silent_when_scalar_delta_equals_non_zero(tmp_path: Path):
    """Codex Round 11 inverse: `equals 5` on a delta target is NOT
    satisfied by observed=0 — verdict would FAIL on config-only diff,
    not pass vacuously. D4 silent."""
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: requires_complexity_5\n"
        "    kind: delta\n"
        "    target: complexity_delta.cyclomatic\n"
        "    operator: equals\n"
        "    expected: 5\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    assert "ADVISORY-D4" not in [a.code for a in advisories]


def test_d4_silent_when_equals_targets_whole_delta_mapping_with_list(tmp_path: Path):
    """Codex review (PR #82 P2 Round 13, hazards.py:480): a collection
    `expected` on a whole-delta record target is not a vacuous pass.
    `effect_changes` is statically typed as `record` (a mapping with
    `added` / `removed` fields), so `equals []` compares the
    zero-valued mapping to `[]` and VIOLATES — the verdict FAILS on
    a config-only diff, contradicting D4's "vacuous PASS" message.

    (Codex's original example used `subset_of []`, but the compiler
    rejects collection operators on record targets up-front. `equals
    []` reaches the evaluator because `equals` accepts any target
    category.)

    `_is_lock_only_constraint` now restricts the empty-collection
    lock case to leaf targets (containing `.`); the dict-shape
    zero-mapping case stays for templates like
    `effect_changes equals {added: (), removed: ()}`.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: bad_effects_lock\n"
        "    kind: delta\n"
        "    target: effect_changes\n"
        "    operator: equals\n"
        "    expected: []\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    assert "ADVISORY-D4" not in [a.code for a in advisories]


def test_d4_silent_when_user_equals_partial_dict_on_whole_delta(tmp_path: Path):
    """Codex review (PR #82 P2 Round 16, hazards.py:522): a user
    constraint `effect_changes equals {added: []}` (partial dict) is
    compared by the evaluator against the full `{added: (),
    removed: ()}` shape and VIOLATES on a config-only diff — verdict
    FAIL, not vacuous PASS. The dict-of-empties shortcut now only
    applies to `ConstraintSource.TEMPLATE` constraints (the template
    registry encodes the canonical zero shape).
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: partial_dict_lock\n"
        "    kind: delta\n"
        "    target: effect_changes\n"
        "    operator: equals\n"
        "    expected:\n"
        "      added: []\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    assert "ADVISORY-D4" not in [a.code for a in advisories]


def test_d4_silent_when_user_constraint_targets_open_path(tmp_path: Path):
    """Codex review (PR #82 P2 Round 14, hazards.py:497): an open-path
    target (`python_specific.*` or `typescript_specific.*`) resolves
    to UNKNOWN at evaluate time. Under default `unknown_policy: fail`,
    UNKNOWN routes to FAIL — the verdict is NOT a vacuous PASS on a
    config-only diff. D4 must stay silent. `_is_lock_only_constraint`
    now excludes open-path targets from lock-only classification.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: python_specific_lock\n"
        "    kind: delta\n"
        "    target: python_specific.foo\n"
        "    operator: excludes_all\n"
        '    expected: ["bad_item"]\n',
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    assert "ADVISORY-D4" not in [a.code for a in advisories]


def test_p1_fires_when_only_addition_is_loc_delta(tmp_path: Path):
    """Codex review (PR #82 P2 Round 14, hazards.py:605):
    `loc_delta.added` is a numeric line-count surface that a
    docs/config diff can satisfy without adding any API or test case.
    `_targets_added_dimension` used a substring check (`_delta.added
    in path`) that incorrectly matched `loc_delta.added`. Restricted
    to the semantic addition surfaces `api_surface_delta.added` and
    `test_surface_delta.new_cases` per `brief_8_planning §6.3.1`.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: loc_only\n"
        "    kind: delta\n"
        "    target: loc_delta.added\n"
        "    operator: equals\n"
        "    expected: 10\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" in [a.code for a in advisories]


def test_d4_silent_when_user_constraint_is_state_kind(tmp_path: Path):
    """Codex review (PR #82 P2 Round 12, hazards.py:459): a
    `kind: state` constraint reads the candidate `CodeState` directly,
    not the delta. `state imports subset_of []` (Codex's example)
    fails whenever the baseline state has any imports — the empty
    Python diff doesn't make this constraint satisfiable. D4's
    "vacuous PASS" claim is incorrect here; D4 must stay silent.
    `_is_lock_only_constraint` now gates lock-only classification on
    `kind: delta` only.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: forbid_all_imports\n"
        "    kind: state\n"
        "    target: imports\n"
        "    operator: subset_of\n"
        "    expected: []\n",
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    assert "ADVISORY-D4" not in [a.code for a in advisories]


def test_d4_fires_when_extra_user_constraint_uses_changed_only_in(tmp_path: Path):
    """Codex review (PR #82 P2 Round 8, hazards.py:420): the evaluator
    unconditionally returns SKIPPED for `Operator.CHANGED_ONLY_IN` (see
    `evaluator/evaluator.py::_evaluate_constraint`, reason
    `changed_only_in_p1`), so the constraint never affects the verdict.
    A refactor target's hard lock templates plus a `changed_only_in`
    user constraint still passes vacuously on a config-only diff. D4
    must still fire. `_participates_in_verdict` filters out skipped
    operators before lock-only classification.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints:\n"
        "  - id: only_in_module\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: changed_only_in\n"
        '    expected: ["src.api"]\n',
    )
    compiled = _compile(target)
    files = (Path("README.md"), Path("pyproject.toml"))
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=files)
    d4 = [a for a in advisories if a.code == "ADVISORY-D4"]
    assert len(d4) == 1


def test_d4_silent_when_files_touched_is_none(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-D4" not in [a.code for a in advisories]


# ---------------------------------------------------------------------------
# ADVISORY-P1 — feature without positive addition
# ---------------------------------------------------------------------------


def test_p1_fires_on_feature_without_addition(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" in [a.code for a in advisories]


def test_p1_silent_on_feature_with_includes_all_addition(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: feature_added\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["src.api.users.fetch_user_profile"]\n',
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" not in [a.code for a in advisories]


def test_p1_fires_when_feature_only_has_non_empty_not_equals(tmp_path: Path):
    """Codex review (PR #82 P2) regression: `not_equals expected:
    ["x.y"]` against `api_surface_delta.added` is vacuously satisfied by
    an empty delta, so it must not count as a positive addition. Only
    `not_equals expected: []` (which forces non-empty observed) is a
    real positive assertion.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: not_other\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: not_equals\n"
        '    expected: ["src.api.other"]\n',
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" in [a.code for a in advisories]


def test_p1_silent_when_feature_has_not_equals_empty(tmp_path: Path):
    """`not_equals expected: []` forces the added delta to be non-empty
    — that *is* a positive addition assertion, so P1 stays silent.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: at_least_one\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: not_equals\n"
        "    expected: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" not in [a.code for a in advisories]


def test_p1_fires_when_only_addition_constraint_is_severity_info(tmp_path: Path):
    """Codex review (PR #82 P2 Round 3, hazards.py:210): an `info`
    severity constraint with `unknown_policy: ignore` is truly
    informational and does not participate in the verdict
    (`docs/code_semantic_ci_design.md §23.3` Advisor channel), so an
    empty delta still aggregates to PASS even though the constraint
    "exists". P1 must still fire to warn about the missing
    verdict-participating lock.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: info_only_addition\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["src.api.users.fetch_user_profile"]\n'
        "    severity: info\n"
        "    unknown_policy: ignore\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" in [a.code for a in advisories]


def test_p1_silent_when_severity_info_has_unknown_policy_fail(tmp_path: Path):
    """Codex review (PR #82 P2 Round 9, hazards.py:410): an info
    constraint with `unknown_policy: fail` can still route to the
    verdict via the UNKNOWN branch (open path / extraction failure).
    `detect_s1` even warns about this exact configuration. So an
    info+fail addition assertion IS verdict-participating and should
    silence P1 (the verdict can FAIL via UNKNOWN even when no addition
    is observed). The trade is that S1 fires instead, pointing the
    user at the actual configuration mistake.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: info_addition_with_fail_policy\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["src.api.users.fetch_user_profile"]\n'
        "    severity: info\n"
        "    unknown_policy: fail\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    codes = [a.code for a in advisories]
    assert "ADVISORY-P1" not in codes
    # S1 fires for the same constraint — the real authoring hazard.
    assert "ADVISORY-S1" in codes


def test_p1_silent_when_feature_uses_equals_with_non_empty_expected(tmp_path: Path):
    """Codex review (PR #82 P2 Round 6, hazards.py:444): non-empty
    `equals` on `api_surface_delta.added` forces the observed delta to
    equal that exact list (non-empty), so an empty observed delta would
    fail. That is a real positive addition assertion — P1 must stay
    silent. `target_yaml_guide.md` D4 explicitly lists non-empty
    `equals` alongside `includes_all` etc.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: equals_addition\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: equals\n"
        '    expected: ["src.api.users.fetch_user_profile"]\n',
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" not in [a.code for a in advisories]


def test_p1_fires_when_equals_has_empty_expected(tmp_path: Path):
    """`equals []` on `_delta.added` is vacuously satisfied by an empty
    observed delta. Same vacuous-pass hazard as `includes_all []`."""
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: vacuous_equals\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: equals\n"
        "    expected: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" in [a.code for a in advisories]


def test_p1_fires_when_includes_all_has_empty_expected(tmp_path: Path):
    """Codex review (PR #82 P2 Round 3, hazards.py:410): `includes_all
    expected: []` is vacuously satisfied by any observed delta
    (including empty), so it cannot guarantee a positive addition. P1
    must still fire.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: vacuous_includes_all\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        "    expected: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" in [a.code for a in advisories]


def test_p1_silent_on_non_feature_kind(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P1" not in [a.code for a in advisories]


# ---------------------------------------------------------------------------
# ADVISORY-P2 — bugfix without test_surface_delta.new_cases expectation
# ---------------------------------------------------------------------------


def test_p2_fires_on_bugfix_without_new_cases_constraint(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: bugfix\nchange:\n  primary_kind: bugfix\nconstraints: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P2" in [a.code for a in advisories]


def test_p2_fires_when_bugfix_only_has_non_empty_not_equals_on_new_cases(tmp_path: Path):
    """Same Codex P2 fix as P1: a `not_equals expected: ["x.test"]` on
    `test_surface_delta.new_cases` is satisfied by an empty delta, so
    P2 must still fire.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: bugfix\nchange:\n  primary_kind: bugfix\nconstraints:\n"
        "  - id: not_other_test\n"
        "    kind: delta\n"
        "    target: test_surface_delta.new_cases\n"
        "    operator: not_equals\n"
        '    expected: ["tests.test_other.test_x"]\n',
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P2" in [a.code for a in advisories]


def test_p2_fires_when_bugfix_only_has_severity_info_new_cases(tmp_path: Path):
    """Same Round 3 fix as P1: an `info`-severity new_cases assertion
    with `unknown_policy: ignore` is truly informational and does not
    participate in the verdict, so an empty test_surface delta still
    aggregates to PASS. P2 must still fire.
    """
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: bugfix\nchange:\n  primary_kind: bugfix\nconstraints:\n"
        "  - id: info_only_test\n"
        "    kind: delta\n"
        "    target: test_surface_delta.new_cases\n"
        "    operator: not_equals\n"
        "    expected: []\n"
        "    severity: info\n"
        "    unknown_policy: ignore\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P2" in [a.code for a in advisories]


def test_p2_silent_when_bugfix_requires_new_test_case(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: bugfix\nchange:\n  primary_kind: bugfix\nconstraints:\n"
        "  - id: regression_test\n"
        "    kind: delta\n"
        "    target: test_surface_delta.new_cases\n"
        "    operator: not_equals\n"
        "    expected: []\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-P2" not in [a.code for a in advisories]


# ---------------------------------------------------------------------------
# ADVISORY-S1 — severity: info + unknown_policy in {fail, repair}
# ---------------------------------------------------------------------------


def test_s1_fires_on_info_severity_with_fail_unknown_policy(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: noisy_info\n"
        "    kind: state\n"
        "    target: api_surface_public\n"
        "    operator: includes_all\n"
        '    expected: ["src.api.x"]\n'
        "    severity: info\n"
        "    unknown_policy: fail\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    s1 = [a for a in advisories if a.code == "ADVISORY-S1"]
    assert len(s1) == 1
    assert s1[0].evidence["constraint_id"] == "noisy_info"
    # post-D1-4 wording mentions the narrowed scope
    assert "extraction-cause" in s1[0].message
    assert "open_runtime" in s1[0].message


def test_s1_silent_on_info_with_ignore_policy(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: pure_info\n"
        "    kind: state\n"
        "    target: api_surface_public\n"
        "    operator: includes_all\n"
        '    expected: ["src.api.x"]\n'
        "    severity: info\n"
        "    unknown_policy: ignore\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-S1" not in [a.code for a in advisories]


def test_s1_silent_on_hard_severity(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: hard_constraint\n"
        "    kind: state\n"
        "    target: api_surface_public\n"
        "    operator: includes_all\n"
        '    expected: ["src.api.x"]\n'
        "    severity: hard\n"
        "    unknown_policy: fail\n",
    )
    compiled = _compile(target)
    advisories = detect_advisories(compiled, package_root=tmp_path, files_touched=None)
    assert "ADVISORY-S1" not in [a.code for a in advisories]


# ---------------------------------------------------------------------------
# JSON envelope + schema
# ---------------------------------------------------------------------------


def test_json_format_returns_advisory1_envelope(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints: []\n",
    )
    result = run_semantic_ci(
        tmp_path,
        "target-doctor",
        "--target",
        str(target),
        "--format",
        "json",
    )
    assert result.returncode == 0
    payload = parse_json(result.stdout)
    assert payload["schema_version"] == "advisory-1"
    assert payload["subcommand"] == "target-doctor"
    assert any(a["code"] == "ADVISORY-P1" for a in payload["advisories"])
    jsonschema.validate(payload, DOCTOR_SCHEMA)


def test_json_envelope_passes_schema_when_no_advisories(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: addition\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["x.y"]\n',
    )
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_x.py").write_text("def test_foo(): assert True\n", encoding="utf-8")
    result = run_semantic_ci(
        tmp_path,
        "target-doctor",
        "--target",
        str(target),
        "--format",
        "json",
    )
    assert result.returncode == 0
    payload = parse_json(result.stdout)
    assert payload["advisories"] == []
    jsonschema.validate(payload, DOCTOR_SCHEMA)


# ---------------------------------------------------------------------------
# Exit code contract (brief_8_planning §6.3.3 + exit_codes.md)
# ---------------------------------------------------------------------------


def test_exit_zero_when_no_advisories(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: addition\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["x.y"]\n',
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_foo(): assert True\n", encoding="utf-8")
    result = run_semantic_ci(tmp_path, "target-doctor", "--target", str(target))
    assert result.returncode == 0


def test_exit_zero_when_advisories_present(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints: []\n",
    )
    result = run_semantic_ci(tmp_path, "target-doctor", "--target", str(target))
    assert result.returncode == 0
    assert "ADVISORY-P1" in result.stdout


def test_missing_target_exits_two(tmp_path: Path):
    result = run_semantic_ci(tmp_path, "target-doctor", "--target", str(tmp_path / "nope.yaml"))
    assert result.returncode == 2


def test_compile_error_exits_three(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: bad\nchange:\n  primary_kind: notrealkind\nconstraints: []\n",
    )
    result = run_semantic_ci(tmp_path, "target-doctor", "--target", str(target))
    assert result.returncode == 3


def test_missing_package_root_exits_two(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints: []\n",
    )
    result = run_semantic_ci(
        tmp_path,
        "target-doctor",
        "--target",
        str(target),
        "--package-root",
        str(tmp_path / "no_such_dir"),
    )
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Argparse spec — flags that MUST NOT exist
# ---------------------------------------------------------------------------


def test_strict_advice_flag_does_not_exist():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["target-doctor", "--strict-advice"])


def test_llm_assist_flag_does_not_exist():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["target-doctor", "--llm-assist"])


def test_allow_candidate_derived_expectations_flag_does_not_exist():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["target-doctor", "--allow-candidate-derived-expectations"])


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_input_three_times_byte_identical(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: a\n"
        "    kind: state\n"
        "    target: api_surface_public\n"
        "    operator: includes_all\n"
        '    expected: ["x.y"]\n'
        "    severity: info\n"
        "    unknown_policy: fail\n"
        "  - id: b\n"
        "    kind: state\n"
        "    target: api_surface_public\n"
        "    operator: includes_all\n"
        '    expected: ["x.z"]\n'
        "    severity: info\n"
        "    unknown_policy: repair\n",
    )
    outputs = []
    for _ in range(3):
        result = run_semantic_ci(
            tmp_path,
            "target-doctor",
            "--target",
            str(target),
            "--format",
            "json",
        )
        assert result.returncode == 0
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


# ---------------------------------------------------------------------------
# INV-1 — running target-doctor does not perturb compile envelope bytes
# ---------------------------------------------------------------------------


def test_inv1_compile_envelope_is_byte_identical_around_target_doctor(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints:\n"
        "  - id: addition\n"
        "    kind: delta\n"
        "    target: api_surface_delta.added\n"
        "    operator: includes_all\n"
        '    expected: ["x.y"]\n',
    )
    before = run_semantic_ci(tmp_path, "compile", "--target", str(target), "--format", "json")
    assert before.returncode == 0
    doctor = run_semantic_ci(
        tmp_path,
        "target-doctor",
        "--target",
        str(target),
        "--format",
        "json",
    )
    assert doctor.returncode == 0
    after = run_semantic_ci(tmp_path, "compile", "--target", str(target), "--format", "json")
    assert after.returncode == 0
    assert before.stdout == after.stdout


# ---------------------------------------------------------------------------
# CLI integration with git for D4 (covers files_touched resolution path)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        env={
            **__import__("os").environ,
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "commit.gpgsign",
            "GIT_CONFIG_VALUE_0": "false",
            "GIT_CONFIG_KEY_1": "tag.gpgsign",
            "GIT_CONFIG_VALUE_1": "false",
        },
        capture_output=True,
        text=True,
    )


def _git_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_package_root_resolves_repo_relative_from_subdirectory(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "src").mkdir()
    (repo / "src" / "mod.py").write_text("def foo(): return 1\n", encoding="utf-8")
    subdir = repo / "subdir"
    subdir.mkdir()
    target = _write_target(repo / "target.yaml", _TARGET_TEST_SURFACE)

    root_result = run_semantic_ci(
        repo,
        "target-doctor",
        "--target",
        str(target),
        "--package-root",
        "src",
        "--format",
        "json",
    )
    subdir_result = run_semantic_ci(
        subdir,
        "target-doctor",
        "--target",
        str(target),
        "--package-root",
        "src",
        "--format",
        "json",
    )

    assert root_result.returncode == 0, root_result.stderr
    assert subdir_result.returncode == 0, subdir_result.stderr
    assert parse_json(root_result.stdout) == parse_json(subdir_result.stdout)
    assert "ADVISORY-D1" in [a["code"] for a in parse_json(subdir_result.stdout)["advisories"]]


def test_package_root_dot_resolves_to_repo_root_from_subdirectory(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_mod.py").write_text("def test_foo(): assert True\n", encoding="utf-8")
    subdir = repo / "subdir"
    subdir.mkdir()
    target = _write_target(repo / "target.yaml", _TARGET_TEST_SURFACE)

    result = run_semantic_ci(
        subdir,
        "target-doctor",
        "--target",
        str(target),
        "--package-root",
        ".",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    assert "ADVISORY-D1" not in [a["code"] for a in parse_json(result.stdout)["advisories"]]


def test_d4_package_root_filter_matches_from_repo_root_and_subdirectory(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "t@t")
    (repo / "src").mkdir()
    (repo / "src" / "in_scope.py").write_text("def foo(): return 1\n", encoding="utf-8")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline_sha = _git_head(repo)
    _git(repo, "checkout", "-b", "feature")
    (repo / "README.md").write_text("updated docs\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "docs change")
    target = _write_target(
        repo / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )
    subdir = repo / "subdir"
    subdir.mkdir()

    args = (
        "target-doctor",
        "--target",
        str(target),
        "--package-root",
        "src",
        "--baseline-rev",
        baseline_sha,
        "--candidate-rev",
        "HEAD",
        "--format",
        "json",
    )
    root_result = run_semantic_ci(repo, *args)
    subdir_result = run_semantic_ci(subdir, *args)

    assert root_result.returncode == 0, root_result.stderr
    assert subdir_result.returncode == 0, subdir_result.stderr
    root_d4 = next(
        a for a in parse_json(root_result.stdout)["advisories"] if a["code"] == "ADVISORY-D4"
    )
    subdir_d4 = next(
        a for a in parse_json(subdir_result.stdout)["advisories"] if a["code"] == "ADVISORY-D4"
    )
    assert (
        root_d4["evidence"]["files_touched_count"] == subdir_d4["evidence"]["files_touched_count"]
    )
    assert root_d4["evidence"]["sample_files"] == subdir_d4["evidence"]["sample_files"]


def test_package_root_rejects_absolute_path(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints: []\n",
    )

    result = run_semantic_ci(
        tmp_path,
        "target-doctor",
        "--target",
        str(target),
        "--package-root",
        str(tmp_path),
    )

    assert result.returncode == 2
    assert "--package-root must be relative" in result.stderr


def test_package_root_rejects_parent_escape(tmp_path: Path):
    target = _write_target(
        tmp_path / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints: []\n",
    )

    result = run_semantic_ci(
        tmp_path,
        "target-doctor",
        "--target",
        str(target),
        "--package-root",
        "../../etc",
    )

    assert result.returncode == 2
    assert "--package-root must stay within repo" in result.stderr


def test_package_root_falls_back_to_cwd_when_git_unavailable(tmp_path: Path, monkeypatch):
    from semantic_ci_code.cli.commands import target_doctor

    monkeypatch.setattr(target_doctor, "is_git_available", lambda: False)
    (tmp_path / "src" / "tests").mkdir(parents=True)
    (tmp_path / "src" / "tests" / "test_mod.py").write_text(
        "def test_foo(): assert True\n", encoding="utf-8"
    )
    target = _write_target(tmp_path / "target.yaml", _TARGET_TEST_SURFACE)

    result = run_semantic_ci(
        tmp_path,
        "target-doctor",
        "--target",
        str(target),
        "--package-root",
        "src",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    assert "ADVISORY-D1" not in [a["code"] for a in parse_json(result.stdout)["advisories"]]


def test_package_root_rejects_symlink_escape(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = repo / "linked"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable on this platform: {exc}")
    target = _write_target(
        repo / "target.yaml",
        "intent: feature\nchange:\n  primary_kind: feature\nconstraints: []\n",
    )

    result = run_semantic_ci(
        repo,
        "target-doctor",
        "--target",
        str(target),
        "--package-root",
        "linked",
    )

    assert result.returncode == 2
    assert "--package-root escapes repo root via symlink" in result.stderr


def test_d4_cli_integration_with_git(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "t@t")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _git(repo, "checkout", "-b", "feature")
    (repo / "README.md").write_text("updated docs\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "config-only change")
    _write_target(
        repo / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )
    result = run_semantic_ci(
        repo,
        "target-doctor",
        "--target",
        str(repo / "target.yaml"),
        "--baseline-rev",
        baseline_sha,
        "--candidate-rev",
        "HEAD",
        "--format",
        "json",
    )
    assert result.returncode == 0
    payload = parse_json(result.stdout)
    codes = [a["code"] for a in payload["advisories"]]
    assert "ADVISORY-D4" in codes


def test_d4_cli_silent_on_python_to_non_python_rename(tmp_path: Path):
    """Codex review (PR #82 P2 Round 5, target_doctor.py:128): when a
    Python file is renamed to a non-`.py` path (e.g. `foo.py ->
    foo.txt`), git numstat records `old_path=foo.py` and
    `path=foo.txt`. The Validator surface would extract a Python delta
    (api_surface_delta.removed_public on the old name), so the diff is
    not "config/doc only". D4 must stay silent. `_resolve_files_touched`
    now includes both sides of rename entries.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "t@t")
    (repo / "mod.py").write_text("def foo(): return 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _git(repo, "checkout", "-b", "feature")
    _git(repo, "mv", "mod.py", "mod.txt")
    _git(repo, "commit", "-m", "rename Python to text")
    _write_target(
        repo / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )
    result = run_semantic_ci(
        repo,
        "target-doctor",
        "--target",
        str(repo / "target.yaml"),
        "--baseline-rev",
        baseline_sha,
        "--candidate-rev",
        "HEAD",
        "--format",
        "json",
    )
    assert result.returncode == 0
    payload = parse_json(result.stdout)
    assert "ADVISORY-D4" not in [a["code"] for a in payload["advisories"]]


def test_d4_cli_fires_when_python_diff_is_outside_package_root(tmp_path: Path):
    """Codex review (PR #82 P2 Round 15, target_doctor.py:51):
    `_resolve_files_touched` returned every repo diff path, so any
    Python change anywhere in the repo (even outside the requested
    `--package-root`) suppressed D4. But `semantic-ci check` extracts
    only inside `--package-root`, so a lock-only target can still
    pass vacuously for the in-scope slice when the only Python
    changes are out of scope. Fix filters numstat paths to those
    inside `package_root` before classification.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "t@t")
    (repo / "src").mkdir()
    (repo / "src" / "in_scope.py").write_text("def foo(): return 1\n", encoding="utf-8")
    (repo / "out_of_scope.py").write_text("def bar(): return 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _git(repo, "checkout", "-b", "feature")
    # Python change is OUTSIDE --package-root=src
    (repo / "out_of_scope.py").write_text("def bar(): return 99\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "out-of-scope py change")
    _write_target(
        repo / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )
    result = run_semantic_ci(
        repo,
        "target-doctor",
        "--target",
        str(repo / "target.yaml"),
        "--package-root",
        "src",
        "--baseline-rev",
        baseline_sha,
        "--candidate-rev",
        "HEAD",
        "--format",
        "json",
    )
    assert result.returncode == 0
    payload = parse_json(result.stdout)
    codes = [a["code"] for a in payload["advisories"]]
    # In-scope (src/) has no Python diff → vacuous PASS for the
    # in-scope slice → D4 fires.
    assert "ADVISORY-D4" in codes


def test_d4_cli_silent_when_python_diff_present(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "t@t")
    (repo / "mod.py").write_text("def foo(): return 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _git(repo, "checkout", "-b", "feature")
    (repo / "mod.py").write_text("def foo(): return 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "py change")
    _write_target(
        repo / "target.yaml",
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )
    result = run_semantic_ci(
        repo,
        "target-doctor",
        "--target",
        str(repo / "target.yaml"),
        "--baseline-rev",
        baseline_sha,
        "--candidate-rev",
        "HEAD",
        "--format",
        "json",
    )
    assert result.returncode == 0
    payload = parse_json(result.stdout)
    assert "ADVISORY-D4" not in [a["code"] for a in payload["advisories"]]


# ---------------------------------------------------------------------------
# CLI integration with git for D6 (covers nested_def_growth resolution path)
# ---------------------------------------------------------------------------

_TARGET_COMPLEXITY_LOCK = (
    "intent: simplify hot path\n"
    "change:\n"
    "  primary_kind: refactor\n"
    "constraints:\n"
    "  - id: cc_lock\n"
    "    kind: delta\n"
    "    target: complexity_delta.cyclomatic\n"
    "    operator: less_than_or_equal\n"
    "    expected: 0\n"
)

_FLAT_FUNCTION = (
    "def process(items):\n"
    "    out = []\n"
    "    for item in items:\n"
    "        if item:\n"
    "            out.append(item)\n"
    "    return out\n"
)

# Same behaviour, body displaced into a nested helper: the extractor's
# cyclomatic for `process` drops while real complexity is unchanged.
_NESTED_REFACTOR = (
    "def process(items):\n"
    "    def _collect():\n"
    "        out = []\n"
    "        for item in items:\n"
    "            if item:\n"
    "                out.append(item)\n"
    "        return out\n"
    "    return _collect()\n"
)


def _d6_repo(tmp_path: Path, *, candidate_source: str, target_yaml: str) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "t@t")
    (repo / "src").mkdir()
    (repo / "src" / "mod.py").write_text(_FLAT_FUNCTION, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline_sha = _git_head(repo)
    _git(repo, "checkout", "-b", "feature")
    (repo / "src" / "mod.py").write_text(candidate_source, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "refactor")
    _write_target(repo / "target.yaml", target_yaml)
    return repo, baseline_sha


def _run_doctor_json(repo: Path, baseline_sha: str) -> dict:
    result = run_semantic_ci(
        repo,
        "target-doctor",
        "--target",
        str(repo / "target.yaml"),
        "--package-root",
        "src",
        "--baseline-rev",
        baseline_sha,
        "--candidate-rev",
        "HEAD",
        "--format",
        "json",
    )
    assert result.returncode == 0, result.stderr
    return parse_json(result.stdout)


def test_d6_cli_fires_on_nested_def_displacement(tmp_path: Path):
    repo, baseline_sha = _d6_repo(
        tmp_path,
        candidate_source=_NESTED_REFACTOR,
        target_yaml=_TARGET_COMPLEXITY_LOCK,
    )

    payload = _run_doctor_json(repo, baseline_sha)
    jsonschema.validate(payload, DOCTOR_SCHEMA)
    d6 = [a for a in payload["advisories"] if a["code"] == "ADVISORY-D6"]

    assert len(d6) == 1
    assert d6[0]["evidence"]["constraint_ids"] == ["cc_lock"]
    assert d6[0]["evidence"]["nested_defs_added"] == 1
    assert d6[0]["evidence"]["files"] == [
        {"path": "src/mod.py", "baseline_nested_defs": 0, "candidate_nested_defs": 1}
    ]


def test_d6_cli_silent_without_complexity_constraint(tmp_path: Path):
    repo, baseline_sha = _d6_repo(
        tmp_path,
        candidate_source=_NESTED_REFACTOR,
        target_yaml="intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n",
    )

    payload = _run_doctor_json(repo, baseline_sha)
    codes = [a["code"] for a in payload["advisories"]]

    assert "ADVISORY-D6" not in codes
    # The diff touches a Python file, so D4 must stay silent too.
    assert "ADVISORY-D4" not in codes


def test_d6_cli_silent_without_nested_growth(tmp_path: Path):
    repo, baseline_sha = _d6_repo(
        tmp_path,
        candidate_source=_FLAT_FUNCTION.replace("if item:", "if item is not None:"),
        target_yaml=_TARGET_COMPLEXITY_LOCK,
    )

    payload = _run_doctor_json(repo, baseline_sha)

    assert "ADVISORY-D6" not in [a["code"] for a in payload["advisories"]]


def test_d6_cli_skips_unparseable_candidate_file(tmp_path: Path):
    repo, baseline_sha = _d6_repo(
        tmp_path,
        candidate_source="def broken(:\n",
        target_yaml=_TARGET_COMPLEXITY_LOCK,
    )

    payload = _run_doctor_json(repo, baseline_sha)

    assert "ADVISORY-D6" not in [a["code"] for a in payload["advisories"]]


def test_d6_cli_counts_new_file_from_zero_baseline(tmp_path: Path):
    repo, baseline_sha = _d6_repo(
        tmp_path,
        candidate_source=_FLAT_FUNCTION + "\n# touched\n",
        target_yaml=_TARGET_COMPLEXITY_LOCK,
    )
    (repo / "src" / "helpers.py").write_text(_NESTED_REFACTOR, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add helper module with nested def")

    payload = _run_doctor_json(repo, baseline_sha)
    d6 = [a for a in payload["advisories"] if a["code"] == "ADVISORY-D6"]

    assert len(d6) == 1
    assert d6[0]["evidence"]["files"] == [
        {"path": "src/helpers.py", "baseline_nested_defs": 0, "candidate_nested_defs": 1}
    ]


def test_d6_cli_fires_on_rename_into_package_root_scope(tmp_path: Path):
    """Codex review P2: a rename across the --package-root boundary must
    count the out-of-scope side as 0 (the extractor never observed it).
    `lib/helpers.py` (1 nested def) renamed to `src/helpers.py` is 0 -> 1
    for the src slice, not 1 -> 1, so D6 must fire."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "t@t")
    (repo / "src").mkdir()
    (repo / "lib").mkdir()
    (repo / "src" / "mod.py").write_text(_FLAT_FUNCTION, encoding="utf-8")
    (repo / "lib" / "helpers.py").write_text(_NESTED_REFACTOR, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline_sha = _git_head(repo)
    _git(repo, "checkout", "-b", "feature")
    _git(repo, "mv", "lib/helpers.py", "src/helpers.py")
    _git(repo, "commit", "-m", "move helpers into package root")
    _write_target(repo / "target.yaml", _TARGET_COMPLEXITY_LOCK)

    payload = _run_doctor_json(repo, baseline_sha)
    d6 = [a for a in payload["advisories"] if a["code"] == "ADVISORY-D6"]

    assert len(d6) == 1
    assert d6[0]["evidence"]["files"] == [
        {"path": "src/helpers.py", "baseline_nested_defs": 0, "candidate_nested_defs": 1}
    ]


def test_d6_cli_silent_on_rename_out_of_package_root_scope(tmp_path: Path):
    """Mirror case: moving a nested-def file out of the package root is a
    0-growth event for the src slice (candidate side counts 0)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "t@t")
    (repo / "src").mkdir()
    (repo / "src" / "helpers.py").write_text(_NESTED_REFACTOR, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline_sha = _git_head(repo)
    _git(repo, "checkout", "-b", "feature")
    (repo / "lib").mkdir()
    _git(repo, "mv", "src/helpers.py", "lib/helpers.py")
    _git(repo, "commit", "-m", "move helpers out of package root")
    _write_target(repo / "target.yaml", _TARGET_COMPLEXITY_LOCK)

    payload = _run_doctor_json(repo, baseline_sha)

    assert "ADVISORY-D6" not in [a["code"] for a in payload["advisories"]]
