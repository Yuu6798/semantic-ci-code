# Brief — Candidate / Baseline Source Selection (working title)

> Status: REFERENCE (complete). The 3 implementation phases landed in order:
> Phase 2 → Phase 3a → Phase 3b. Historical plan:
>
> Sequencing: 3 implementation PRs (Phase 2 →
> Phase 3a → Phase 3b), each its own Task Brief. Phase 2 lands the
> minimal CLI surface change and removes `--allow-dirty`; Phase 3a
> symmetrises baseline-side sourcing and adds staged-index;
> Phase 3b deletes the `pre-commit` subcommand and migrates its
> `.pre-commit-hooks.yaml` entry to the unified `check` surface.
>
> Completion record: Phase 2 landed in PR #100, Phase 3a in PR #101, and
> Phase 3b in PR #102. This document is retained only as a historical record.
>
> Trigger: PR #98 (`fix(check): preserve explicit --candidate-rev under
> --allow-dirty (#97)`) landed a Phase 1 mitigation but exposed a design
> hole — `--allow-dirty` conflates two orthogonal concerns ("permission
> to run on a dirty tree" vs "select working tree as candidate source").
> Closing this hole is the entire scope of this planning doc.

## 1. Why this brief exists

`semantic-ci check` selects its candidate snapshot through a single
boolean flag (`--allow-dirty`) that silently couples three behaviors:

1. **Permission** to proceed despite an uncommitted working tree.
2. **Source selection** = "the working tree IS the candidate".
3. **Cache suppression** for the candidate side (no commit SHA).

PR #98 split (3) cleanly by deriving
`candidate_uses_working_tree = allow_dirty AND candidate_rev is None`
and ignoring `--allow-dirty` for source-selection purposes when an
explicit `--candidate-rev` is given. That is a viable Phase 1, but it
leaves the surface confusing:

- the flag's name still implies (1) but its behavior also encodes (2)
- there is no symmetric way to say "evaluate the working tree as the
  *baseline*" — the only baseline source today is "a git ref"
- the `pre-commit` subcommand uses a third candidate source
  (`git checkout-index` staged snapshot) that is exposed as a separate
  subcommand rather than as a uniform source-selection axis
- JSON envelope does not record which source was actually used, so
  downstream consumers cannot distinguish a HEAD-vs-HEAD pass from a
  working-tree-vs-HEAD pass

This brief replaces the implicit flag with an explicit source-selection
axis on both sides (`--candidate-source`, `--baseline-source`), folds
the staged snapshot into the same axis, and removes the redundant
`pre-commit` subcommand. The engine contract (`§23.1` input neutrality)
is unchanged — only CLI-layer sourcing semantics move.

## 2. Scope contract (in / out)

**In scope (all 3 phases):**

- CLI surface: `--candidate-source {commit, working-tree, staged-index}`
  + `--baseline-source` with the same enum, on `check`
- removal of `--allow-dirty`
- staged-index resolver shared between phases (replacing the
  `pre-commit` subcommand's internal `git checkout-index` path)
- JSON envelope provenance: `engine.{baseline,candidate}.{source, rev}`
- conflict / degenerate handling rules (usage error vs warning, see §6)
- removal of the `pre-commit` subcommand and migration of
  `.pre-commit-hooks.yaml` to the unified `check` form
- docs refresh: `cli_usage.md`, `code_semantic_ci_design.md §23.1 /
  §23.2`, README hook example, migration note

**Out of scope:**

- engine signature changes — `engine.check_pair(baseline_path,
  candidate_path)` stays a path-snapshot comparator
- `compare` / `observe` / `compile-repair` / `validate-plan` /
  `target-doctor` / `target-catalog` CLI surfaces
- any change to cache key, extractor, or evaluator internals beyond
  what naturally falls out of the candidate/baseline path being a
  different temp directory
- deprecation / alias period for `--allow-dirty` — hard removal in
  Phase 2 (see §4)

## 3. Lock-in (adopted in session 2026-05-22, "X = aggressive / clean-cut")

The 7 design questions surfaced in the design session are resolved as
follows. **All sub-decisions are now binding** and Task Briefs for
Phase 2 / 3a / 3b MUST cite this section by name.

| # | Question | Decision |
|---|---|---|
| 1 | Drop `--allow-dirty` immediately vs deprecate? | **Hard delete in Phase 2.** No alias, no deprecation warning, no compatibility shim. |
| 2 | Phase 2.5 (`--baseline-source` alone)? | **Dropped.** Folded into Phase 3a together with `staged-index`. |
| 3 | Input conflict (`source=working-tree` + `rev=SHA`) | **Usage error, exit 2.** Same shape for all 4 conflict permutations once staged-index lands. |
| 4 | Degenerate cases (baseline = candidate = same volatile source) | **Warning + proceed.** Verdict will be the trivial no-drift result; we do not refuse. |
| 5 | JSON provenance landing phase | **Phase 2.** Envelope gains `engine.baseline.{source,rev}` and `engine.candidate.{source,rev}`; `schema_version` minor bump. |
| 6 | `pre-commit` subcommand removal style | **Hard delete in Phase 3b.** `.pre-commit-hooks.yaml` rewritten to invoke `check --candidate-source=staged-index`. No alias subcommand. |
| 7 | PR splitting | **3 PRs**: Phase 2, Phase 3a, Phase 3b — each lands independently. No combined PR. |

Style summary: aggressive / clean-cut. No backwards-compatibility
hacks, no rename-with-underscore, no `// removed` comments, no
deprecation period.

## 4. Phase 2 — `--candidate-source` + remove `--allow-dirty` + JSON provenance

### 4.1 CLI surface

- Add `--candidate-source {commit, working-tree}` to `check`,
  default = `commit`.
- Remove `--allow-dirty` entirely (no alias).
- Conflict rule: `--candidate-source=working-tree` together with an
  explicit `--candidate-rev <SHA>` → **usage error, exit 2** with the
  message form `error: --candidate-source=working-tree is incompatible
  with --candidate-rev`.

### 4.2 Replacement warning text

When the candidate source is `working-tree` AND the host clone has
uncommitted changes that the user might have intended to NOT include
(i.e. the user passed neither `--candidate-source=working-tree` nor
`--candidate-source=commit`, only the default path), we no longer have
a warning to print — the default is `commit` and HEAD is what gets
evaluated. The pre-Phase 2 warning (`warning: working tree is dirty;
running against HEAD instead`) is removed.

In its place, when `--candidate-source=working-tree` is selected
explicitly and the working tree is clean, emit a one-line stderr
informational note (default-off behind `--verbose`, identical shape to
existing cache-hit notes):

> `note: candidate source = working tree (no uncommitted changes
> detected; equivalent to HEAD).`

This is purely diagnostic and never affects the verdict.

### 4.3 JSON envelope provenance

Add to the existing envelope:

```json
"engine": {
  "baseline": { "source": "commit", "rev": "<sha>" },
  "candidate": { "source": "working-tree", "rev": null }
}
```

- `source` ∈ `{commit, working-tree}` (Phase 2 enum), expanded to
  include `staged-index` in Phase 3a.
- `rev` is the resolved commit SHA when `source == commit`; `null`
  otherwise.
- Bump `schema_version` minor (e.g. `"4"` → `"4.1"` or `"5"` per
  current convention; final value pinned in the Phase 2 Task Brief).

### 4.4 Engine contract (`§23.1`)

The engine signature
`engine.check_pair(baseline_path: Path, candidate_path: Path, intent)`
is **unchanged**. The CLI is solely responsible for resolving a
source into a path snapshot. Update `code_semantic_ci_design.md
§23.1` text to make this explicit:

> CLI-layer source resolution (`--candidate-source` /
> `--baseline-source`) is the only adapter between user intent and the
> engine's path-snapshot contract. The engine MUST NOT learn about
> "working tree" or "staged index" as input categories; it only sees
> two materialized directories.

### 4.5 Tests (Phase 2)

- Delete all `--allow-dirty` test cases. The 4 architecture invariants
  added in PR #98 (`tests/architecture/test_check_provenance.py`) are
  rewritten in terms of `--candidate-source` (the inv-1 / inv-2 shapes
  stay; only the CLI invocation changes).
- New conflict test: `check --candidate-source=working-tree
  --candidate-rev <SHA>` exits 2 with the expected message.
- New provenance test: JSON envelope contains
  `engine.{baseline,candidate}.{source,rev}` with correct values for
  3 invocations: default (commit/commit), explicit working-tree
  candidate, explicit ref-backed candidate.

### 4.6 Phase 2 size estimate

~120 LOC implementation + ~30 LOC envelope serialization + ~40 lines
docs + ~5 new/rewritten tests. Single PR. Expected round count: 0–1
under the post-experience-externalization envelope (AGENTS.md §5.5).

## 5. Phase 3a — Symmetric `--baseline-source` + staged-index

### 5.1 CLI surface

- Extend `--candidate-source` enum: add `staged-index`.
- Add `--baseline-source {commit, working-tree, staged-index}` with
  default = `commit`.
- Default rev resolution:
  - `--baseline-source=commit` unset rev → existing default
    (`origin/main` → `main` → `master`)
  - `--candidate-source=commit` unset rev → `HEAD`
  - `--candidate-source=staged-index` unset baseline rev → **HEAD
    commit** (matches old `pre-commit` semantics; pinned here so
    Phase 3b removal does not silently flip the default)
  - `--candidate-source=working-tree` unset baseline rev → unchanged
    from Phase 2 (i.e. existing baseline default)

### 5.2 Staged-index resolver

- Implementation: `git checkout-index --prefix=<tempdir>/` into a
  temp directory, materialize the staged tree, return a snapshot path.
- Lives next to the existing working-tree resolver in the CLI layer.
- Cache suppression: any source ∈ {working-tree, staged-index} skips
  cache writes for that side (already true for working-tree from
  PR #98; staged-index extends the same predicate).

### 5.3 Conflict rules (4 permutations)

All 4 combinations below are **usage error, exit 2**:

| Side | Source | Rev | Outcome |
|---|---|---|---|
| candidate | `working-tree` | explicit SHA | error |
| candidate | `staged-index` | explicit SHA | error |
| baseline | `working-tree` | explicit SHA | error |
| baseline | `staged-index` | explicit SHA | error |

Error message form: `error: --{candidate,baseline}-source=<value>
is incompatible with --{candidate,baseline}-rev`.

### 5.4 Degenerate cases (warning + proceed)

When both sides resolve to the same volatile source — i.e.
`baseline-source == candidate-source` AND both ∈ {working-tree,
staged-index} — emit a stderr warning and run the verdict (which will
trivially be no-drift):

> `warning: baseline and candidate resolve to the same <source>
> snapshot; verdict will report no drift by construction.`

We deliberately do not refuse the run — there are legitimate uses
(smoke-testing the pipeline, reproducing a known-empty diff for
contract tests).

### 5.5 Docs

- Add 6×6 (or relevant subset) source × source matrix to
  `docs/cli_usage.md`. Document each cell with the canonical use
  case and the typical default for the unspecified rev.
- Refresh `code_semantic_ci_design.md §23.2 Application Matrix` so
  the listed application surfaces (PR review, pre-merge gate,
  pre-commit, pre-generation simulation, etc.) map onto the
  (`baseline-source`, `candidate-source`) tuple.

### 5.6 Tests (Phase 3a)

- Staged-index resolver unit tests (snapshot equals
  `git checkout-index` output; cleanup on exit).
- Source × source matrix: representative cells covering the
  canonical PR-review (commit, commit), pre-commit-style (commit,
  staged-index), simulation (working-tree, working-tree) cases.
- All 4 conflict rules: parametrized exit-2 test.
- Degenerate-case warning fires on each of the 2 same-source
  permutations.
- JSON envelope `source` field admits `staged-index`.

### 5.7 Phase 3a size estimate

~150 LOC (resolver + arg parsing + serialization extension) + ~60
lines docs + ~10 new tests. Single PR.

## 6. Phase 3b — Remove `pre-commit` subcommand + migration

### 6.1 Code changes

- Delete `src/semantic_ci_code/cli/commands/pre_commit.py`.
- Remove `pre-commit` from the argparse subparser dispatcher in
  `cli/main.py`.
- Update `.pre-commit-hooks.yaml` so the published hook entry invokes
  `semantic-ci check --candidate-source=staged-index` instead of
  `semantic-ci pre-commit`.

### 6.2 Docs

- Remove all `pre-commit` subcommand references from `README.md`,
  `docs/cli_usage.md`, `docs/exit_codes.md`, `docs/json_schema.md`,
  `docs/code_semantic_ci_design.md`.
- Add a short migration block (single section) in
  `docs/cli_usage.md` Migration appendix:

  > **Migrated in Phase 3b**: `semantic-ci pre-commit [...]` →
  > `semantic-ci check --candidate-source=staged-index [...]`. The
  > evaluation semantics (HEAD commit baseline vs staged index
  > candidate) are identical.

### 6.3 Tests

- Delete `tests/cli/test_pre_commit.py` (subcommand no longer
  exists).
- Add a regression test asserting `semantic-ci pre-commit` exits as
  argparse `SystemExit` with an unknown-subcommand message (i.e. the
  removal is observable from the CLI).
- Add a `.pre-commit-hooks.yaml` smoke test: install the hook into a
  temp git repo and assert it invokes through to `check
  --candidate-source=staged-index` with exit 0 / 1 / 2 routing
  preserved.

### 6.4 Phase 3b size estimate

~50 LOC (mostly deletions) + ~30 lines docs (mostly deletions) +
~2 tests. Single PR.

## 7. Decisions rejected / not adopted

For traceability — these were considered in the design session and
explicitly rejected. They MUST NOT be reintroduced in any of the 3
Task Briefs without re-opening this planning doc.

| Rejected option | Reason |
|---|---|
| Phase 2.5 (`--baseline-source` alone, no staged-index) | Splits a single coherent symmetry change across 2 PRs without payoff; folded into Phase 3a. |
| `--allow-dirty` alias for `--candidate-source=working-tree` | Backwards-compatibility shim of the kind CLAUDE.md "aggressive / clean-cut" policy rejects. PR #98 is recent enough that no external callers are pinned to the flag. |
| `--candidate-source=auto` (infer from working-tree state) | Replaces one implicit conflation with another. Users SHOULD spell out their source. |
| Refusing the same-source degenerate case (exit 2) | Legitimate use cases exist (smoke-test, contract test of the empty diff). Warning + proceed is the right tradeoff. |
| Engine-level `source` enum (engine learns about working-tree) | Violates `§23.1` input neutrality. Engine stays a 2-path comparator. |

## 8. Phase ordering and stop conditions

```
Phase 2  → lands `--candidate-source` + removes `--allow-dirty` + JSON provenance
   ↓     (stop condition: PR merged, `--allow-dirty` no longer in any test)
Phase 3a → adds `--baseline-source` + `staged-index`
   ↓     (stop condition: source × source matrix tests pass; pre-commit subcommand
            still present and functional)
Phase 3b → deletes `pre-commit` subcommand + rewrites `.pre-commit-hooks.yaml`
         (stop condition: `pre-commit` removed, hook entry uses `check
            --candidate-source=staged-index`, full pytest green)
```

Each Phase is independently shippable. Phase 3a is not allowed to
start until Phase 2 is on main; Phase 3b is not allowed to start until
Phase 3a is on main (the `staged-index` source must exist on `check`
before the `pre-commit` subcommand is deleted, or the published hook
will break for any user who tracks main during the gap).

## 9. Cross-references for the Phase 2 Task Brief drafter

Required reading before drafting the Phase 2 Task Brief:

1. This file, §3 (lock-in table) and §4 (Phase 2 scope) in full.
2. `docs/code_semantic_ci_design.md §23.1` (input neutrality) —
   confirm the engine signature change is zero.
3. PR #98 (`fix(check): preserve explicit --candidate-rev under
   --allow-dirty`) — the Phase 1 mitigation that Phase 2 replaces.
   In particular, the 4 architecture invariants in
   `tests/architecture/test_check_provenance.py` move to the new
   CLI surface 1:1; do not delete and re-derive them.
4. `docs/cli_usage.md` — current `--allow-dirty` section, deleted
   in Phase 2.
5. `docs/json_schema.md` — envelope `schema_version` policy, for the
   minor bump.
6. `AGENTS.md §5.6` Maintenance Practice 7 rules and `§5.7`
   Anti-Patterns 7 items.
7. `docs/brief_8_planning.md §15` brief-drafting checklist.

## 10. Resolution record

- **schema_version** — resolved by the landed Phase 2 envelope update and kept
  synchronized with `docs/json_schema.md`.
- **Working-tree clean note** — resolved by the landed CLI implementation.
- **`compare` / `observe` source flags** — re-evaluated after Phase 3b and
  intentionally unchanged. `compare` already accepts arbitrary path snapshots;
  `observe` remains a single-state surface.
- **`pre-commit-hooks.yaml` smoke test** — resolved by the landed Phase 3b
  discipline and CLI tests.

## 11. Acceptance criteria (cross-phase, for the closing PR of Phase 3b)

Phase 3b PR (the last of the 3) MUST also verify:

- [ ] No occurrence of `--allow-dirty` in `src/`, `tests/`, or
  `docs/` (grep clean).
- [ ] No occurrence of the `pre-commit` subcommand in `src/` (CLI
  registration), `tests/cli/`, or `.pre-commit-hooks.yaml`.
- [ ] `--candidate-source` and `--baseline-source` documented in
  `cli_usage.md` with the source × source matrix.
- [ ] JSON envelope `schema_version` reflects the Phase 2 bump,
  unchanged through 3a/3b.
- [ ] `code_semantic_ci_design.md §23.1` text explicitly states the
  engine never learns about source categories.
- [ ] `code_semantic_ci_design.md §23.2 Application Matrix` lists
  each application surface as a (baseline-source, candidate-source)
  tuple.
- [ ] Migration note present in `cli_usage.md` covering the
  `pre-commit` → `check --candidate-source=staged-index` rewrite.
- [ ] Full pytest green on Python 3.11 / 3.12 / 3.13.
- [ ] Ruff check + format clean.

## 12. Provenance

- Source session: 2026-05-22, post-PR #98 design discussion (Phase 1
  mitigation already landed via PR #98 = `claude/repository-issue-review-BVt9Y`
  branch, merge commit `bf4af3b`).
- Adoption style ("X = aggressive / clean-cut") was chosen in-session
  after a 4-style trade-off comparison (conservative / additive /
  symmetry-first / aggressive). All 7 sub-decisions inherit from that
  style choice (see §3).
- This planning doc supersedes the loose "Phase 2 Task Brief"
  framing implied by PR #98's PR body. The Phase 1 mitigation in
  PR #98 stays — Phase 2 cleanly replaces it.
