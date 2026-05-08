# CLI Test Inventory

This document records the current `tests/cli` coverage map and reduction
candidates. It is intentionally conservative: CSCI-24 inventories the suite and
identifies safe follow-up work, but does not delete tests.

Snapshot:

- Date: 2026-05-09
- Command: `python -m pytest -q --no-cov tests/cli`
- Result: `230 passed, 4 skipped, 1 deselected in 264.92s` on Windows Codex desktop
- Scope: CLI tests only; default run excludes the single `slow` smoke/full benchmark

## File Map

| File | Tests | Default invocation | Subprocess retained for | Primary role |
|---|---:|---|---|---|
| `tests/cli/test_cache.py` | 28 | in-process | 2 sitecustomize cache-hit sentinels | CodeState cache hit/miss, eviction, cache key axes |
| `tests/cli/test_check.py` | 25 | in-process | PYTHONHASHSEED determinism | git ref resolution, worktree materialization, dirty handling, cleanup |
| `tests/cli/test_compare.py` | 40 | in-process | PYTHONHASHSEED determinism | `compare` contract, target discovery, JSON/human rendering, output routing |
| `tests/cli/test_compare_partial_match.py` | 1 | in-process | none | partial-match end-to-end regression |
| `tests/cli/test_compile.py` | 13 | in-process | PYTHONHASHSEED determinism | `compile` envelope, policy serialization, target errors |
| `tests/cli/test_compile_repair.py` | 15 | in-process | none | `compile-repair` pipe/input/output behavior |
| `tests/cli/test_e2e.py` | 8 | in-process | `--version` and `--help` console-script smoke | shallow release sanity layer |
| `tests/cli/test_extract_config_cli.py` | 3 | in-process | none | extractor exclude CLI integration and error routing |
| `tests/cli/test_helpers.py` | 1 | in-process | none | in-process CLI invoker smoke coverage |
| `tests/cli/test_init_command.py` | 5 | in-process | none | `init` scaffold and overwrite behavior |
| `tests/cli/test_json_formatter.py` | 2 | direct unit | none | JSON formatter edge behavior |
| `tests/cli/test_modes.py` | 10 | in-process | slow benchmark opt-in uses subprocess | smoke/full mode behavior and benchmark |
| `tests/cli/test_observe.py` | 21 | in-process | console script, python module, legacy script, PYTHONHASHSEED determinism | `observe` contract, entrypoints, output schema |
| `tests/cli/test_output_gh_actions.py` | 12 | in-process | PYTHONHASHSEED determinism | GitHub Actions annotation output |
| `tests/cli/test_output_sarif.py` | 13 | in-process | PYTHONHASHSEED determinism | SARIF output |
| `tests/cli/test_overlay.py` | 7 | direct unit | none | `numstat` parser and delta overlay |
| `tests/cli/test_pre_commit.py` | 12 | in-process | PYTHONHASHSEED determinism | staged-index export and pre-commit semantics |
| `tests/cli/test_pre_commit_manifest.py` | 2 | direct unit | none | static pre-commit manifest validation |
| `tests/cli/test_resolve_package_root.py` | 3 | direct unit | none | package-root path guard behavior |
| `tests/cli/test_validate_plan.py` | 9 | in-process | none | `validate-plan` baseline/input/output behavior |

## Runtime Findings

D2-1 switched `run_semantic_ci` to in-process `cli.main(...)` by default.
Subprocess is now limited to cases that need process-start semantics
(`PYTHONHASHSEED`), console-script entrypoints, or `sitecustomize` import-time
sentinels. The single smoke/full performance comparison is marked `slow` and
is excluded by default.

Remaining wallclock is dominated by real git operations and extraction, not CLI
process startup:

- `test_check.py` creates git repositories, materializes worktrees, and verifies
  cleanup and shallow-clone behavior.
- `test_cache.py` and `test_pre_commit.py` exercise real cache files and staged
  index export.
- Direct parser/helper layers (`test_overlay.py`, `test_json_formatter.py`,
  `test_pre_commit_manifest.py`, `test_resolve_package_root.py`) are not the
  source of CLI-suite cost.

## Coverage Categories

| Category | Tests/files | Reduction stance |
|---|---|---|
| Entry points | `test_observe.py`, `test_e2e.py` | Keep. These catch packaging and module invocation regressions. |
| Command verdict matrix | `test_compare.py`, `test_check.py`, `test_pre_commit.py` | Keep one matrix per command. These commands differ in materialization and exit-code behavior. |
| Formatter serialization | `test_compare.py`, `test_compile.py` | Candidate for moving some assertions to direct formatter unit tests, avoiding subprocess. |
| Target discovery and compile errors | `test_compare.py`, `test_compile.py`, `test_check.py`, `test_pre_commit.py` | Keep representative command-level coverage, but avoid testing identical loader behavior in every command. |
| Git runtime behavior | `test_check.py`, `test_pre_commit.py` | Keep. These are not redundant with non-git tests. |
| Determinism | `test_observe.py`, `test_compare.py`, `test_check.py`, `test_pre_commit.py`, `test_compile.py` | Keep for now. If reduced later, preserve at least one non-git and one git-backed subprocess determinism test. |
| Dependency invariant | `test_observe.py`, `test_compare.py` | Candidate for consolidation into one repository-level dependency invariant test. |
| E2E smoke | `test_e2e.py` | Keep shallow. Do not add detailed assertions here. |

## Reduction Candidates

These are candidates, not deletions approved by this inventory.

1. `test_compare.py` JSON shape micro-tests

   Current separate tests:

   - `test_compare_code_state_is_explicit_null`
   - `test_compare_files_touched_and_loc_delta_are_zero`
   - `test_compare_summary_keys_are_ints`
   - `test_constraint_result_evidence_serializes_as_dict`
   - `test_repair_instruction_extra_evidence_serializes_as_dict`
   - `test_enum_fields_serialize_as_strings`

   Proposed follow-up: move serialization shape checks into formatter-level unit
   tests or combine them into one command-level JSON envelope test. This can
   remove subprocess invocations while preserving behavior coverage.

2. Color and human formatting subprocess tests

   Current tests verify `--no-color`, non-TTY default, `NO_COLOR`, and
   `FORCE_COLOR` through the full `compare` command.

   Proposed follow-up: keep one full CLI human output smoke test and move
   color-policy matrix to `cli/output` unit tests.

3. Target discovery repetition

   `compare` tests cover explicit/root/dotted/missing/ambiguous target discovery.
   `compile` covers the same discovery behavior again.

   Proposed follow-up: keep full discovery matrix in one command plus a light
   smoke test in `compile`, or introduce direct `target_loader` unit tests.

4. Dependency invariant duplication

   `test_project_dependencies_are_unchanged` appears in both `observe` and
   `compare` coverage.

   Proposed follow-up: consolidate into one test outside command-specific
   subprocess suites.

5. E2E detail creep

   `test_e2e.py` should stay as a smoke layer. If future assertions begin to
   duplicate command-specific tests, move them back to the relevant unit file.

## Do Not Delete Yet

These look expensive but still protect behavior that is not covered elsewhere.

- `test_worktree_cleanup_after_extraction_error`: validates cleanup on engine
  failure, not just happy path.
- `test_shallow_clone_fetch_fallback_resolves_origin_main`: covers CI clone
  behavior.
- `test_pre_commit_ignores_unstaged_working_directory_changes`: distinguishes
  staged-index semantics from working-tree semantics.
- `test_subprocess_determinism_across_hash_seeds` in git-backed commands:
  expensive, but protects deterministic JSON across separate processes.

## Semantic CI Dogfood Notes

Running semantic-ci against `tests/cli` now requires a policy target that allows
intentional test-helper API movement:

```yaml
intent: refactor CLI tests without changing product behavior
change:
  primary_kind: refactor
api_surface:
  allow_changes:
    - fqn_prefix: helpers.
    - fqn_prefix: git_helpers.
```

Without that policy, test modules expose helper functions and constants as
public-looking Python symbols, so refactors in test helper plumbing can trip the
refactor API template. That behavior is useful signal for production packages,
but too strict for internal test modules.

## Next Safe Step

The next PR should target one narrow reduction:

- either consolidate the duplicated dependency invariant test, or
- move compare JSON shape micro-tests to formatter-level unit tests.

Avoid deleting git-backed cleanup, shallow clone, staged-index, or determinism
tests until replacement coverage is explicit.
