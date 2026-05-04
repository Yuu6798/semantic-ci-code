# CLI Test Inventory

This document records the current `tests/cli` coverage map and reduction
candidates. It is intentionally conservative: CSCI-24 inventories the suite and
identifies safe follow-up work, but does not delete tests.

Snapshot:

- Date: 2026-05-05
- Command: `python -m pytest tests\cli -q --durations=25`
- Result: `125 passed in 190.60s (0:03:10)`
- Scope: CLI tests only

## File Map

| File | Tests | Primary role | Keep rationale |
|---|---:|---|---|
| `tests/cli/test_observe.py` | 21 | `observe` command contract, legacy entrypoint, basic output schema, path mode, usage errors | First CLI slice. Guards `semantic-ci` and `python -m semantic_ci_code.cli` entrypoint behavior. |
| `tests/cli/test_compare.py` | 40 | `compare` command, target discovery, full JSON/human rendering, output routing, config errors | Broadest non-git command surface. Several assertions are reduction candidates. |
| `tests/cli/test_check.py` | 25 | git ref resolution, worktree materialization, dirty handling, check overlay, cleanup | Slow but high-value. Exercises real git worktrees and failure cleanup. |
| `tests/cli/test_pre_commit.py` | 12 | staged-index export, overlay, dirty unstaged behavior, pre-commit exit matrix | Slow but covers a separate candidate materialization path from `check`. |
| `tests/cli/test_compile.py` | 12 | `compile` command, compile envelope, policy serialization, target errors | Mostly command-level wrapper around compiler and formatter behavior. |
| `tests/cli/test_e2e.py` | 8 | smoke coverage for all five subcommands and docs links | Useful as a release sanity layer, but should remain shallow. |
| `tests/cli/test_overlay.py` | 7 | pure `numstat` parser and delta overlay unit tests | Fast, focused, keep as-is. |

## Runtime Findings

The slowest tests are dominated by real git worktree and subprocess flows.

Top slow categories from the duration sample:

- `test_check.py`: most of the top 25 durations, usually around 3-5 seconds
  each. These tests create git repositories and materialize worktrees.
- `test_pre_commit.py`: staged-index export tests often take about 3 seconds
  each.
- `test_e2e.py`: `check` and `pre-commit` smoke tests are also git-backed and
  appear in the top 25.

The pure parser layer (`test_overlay.py`) is not the source of CLI-suite cost.
The cost is subprocess + git + extraction.

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
