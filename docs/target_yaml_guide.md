# target.yaml Authoring Guide

This guide is for humans (and AI assistants) writing `target.yaml`. It is a
practical companion to the canonical references — it does **not** replace them:

- `docs/code_semantic_ci_design.md` §4 — Target SVP DSL definition
- `docs/cli_usage.md` — full CLI contract (target discovery, severity routing,
  set operator match semantics, output formats)
- `docs/exit_codes.md` — verdict-to-exit-code mapping

The goal here is to surface the authoring traps that are easy to hit when you
write a target file for the first time, and to make the engine's scope explicit
so you know what your `target.yaml` is and is not declaring.

> **Boundary reminder (`design.md §23.3`):** Semantic CI judges adherence of a
> candidate state to a *declared* intent. It does not validate or interpret
> the intent itself. Authoring guidance lives in the **Authoring** surface and
> never participates in the verdict.

## Authoring Workflow

The recommended loop is short:

1. `semantic-ci init [--path .semantic-ci/target.yaml]` — scaffold a commented
   skeleton.
2. Edit `intent`, `change.primary_kind`, `change.scope`, then add the
   constraints you actually need.
3. `semantic-ci compile --target <path>` — verify that paths, operators, and
   match-schema keys are well-formed. Compile-time errors are loud and tell you
   the available paths or did-you-mean suggestions.
4. `semantic-ci validate-plan --target <path> --adapter <name>` — render
   pre-generation guidance against the current baseline. `risk_summary`
   surfaces what an AI generator would need to satisfy.
5. `semantic-ci check` (or `compare` with two trees) on real diffs to confirm
   the verdict is what you intended.

If step 3 fails, do not paper over the error — the same target file will fail
in CI with a less helpful message.

## Anatomy

```yaml
intent: "fetch_user_profile を追加"
change:
  primary_kind: feature
  scope:
    files: ["src/api/users.py", "tests/test_users.py"]

constraints:
  - id: feature_added
    kind: delta
    target: api_surface_delta.added
    operator: includes_all
    expected:
      - "src.api.users.fetch_user_profile"
    severity: hard
    unknown_policy: fail
    evidence_required: true
```

Three things are doing real work here:

- **`change.primary_kind`** picks a constraint template. The template
  pre-loads invariants for that change kind (see `design.md §4.2`–§4.3).
- **`change.scope.files`** is metadata — used by adapters (e.g. Cursor `globs`)
  but **not** by the verdict engine to gate which files participate in
  extraction. Extraction is governed by `--package-root` and the
  `pyproject.toml` extract config (see `cli_usage.md` → "Excluding Files
  From Extraction").
- **`constraints`** is your declared adherence contract. Each constraint
  combines a `kind`, a `target` (RPE field path), an `operator`, and an
  `expected` value. `severity` decides whether a violation routes to fail,
  repair, or info; `unknown_policy` decides what happens when extraction
  cannot answer.

## Choosing `primary_kind`

`primary_kind` is not a label. It expands a default constraint set, so it
materially changes what passes and fails.

Templates install **lock invariants** (negative gates) only. They do not
require additions. Concretely, what the current compiler installs (see
`src/semantic_ci_code/compiler/templates.py`):

| `primary_kind` | Auto-installed invariants (all `kind: delta`, `severity: hard`) |
|---|---|
| `feature` | `api_surface_delta.removed_public == ()` (no public API removed); `effect_changes.added == ()` (no new effects) |
| `bugfix` | `api_surface_public equals_baseline`; `effect_changes.added == ()` |
| `refactor` | `api_surface_public equals_baseline`; `type_relations equals_baseline`; `effect_changes == {added: (), removed: ()}`; `test_surface equals_baseline` |
| `test_update` | `api_surface_public equals_baseline`; `effect_changes == {added: (), removed: ()}`; `imports equals_baseline` |

This means:

- **No template requires that a new symbol be declared.** A `primary_kind:
  feature` candidate that adds nothing public still passes the template.
  If you want adherence to a specific addition, write it as a user
  constraint:

  ```yaml
  - id: feature_added
    kind: delta
    target: api_surface_delta.added
    operator: includes_all
    expected: ["src.api.users.fetch_user_profile"]
    severity: hard
    unknown_policy: fail
  ```

- **No template requires that a test be added.** `primary_kind: bugfix`
  does not auto-gate regression tests; `primary_kind: test_update` does
  not auto-gate that any test was actually modified. If a test addition
  is part of your contract, declare it:

  ```yaml
  - id: regression_test_added
    kind: delta
    target: test_surface_delta.new_cases
    operator: not_equals
    expected: []
    severity: hard
    unknown_policy: fail
  ```

  (Pair this with a `--package-root` that actually covers the test tree —
  see the next section.)

In short, the template establishes a *floor* of what cannot change. Anything
positive ("this addition must be present", "this test must be added") is
your responsibility to author. The §4.3 design table in
`code_semantic_ci_design.md` lists positive expectations under "必須" — that
column is the design intent, not what the engine currently enforces.

## Hazard 1 — `--package-root` decides what is observed (D1)

`semantic-ci check --package-root src` extracts the Python `CodeState` of
`src/` only. Anything outside that root, including `tests/`, is invisible to
extraction. A constraint like:

```yaml
- id: regression_test_added
  kind: delta
  target: test_surface_delta.new_cases
  operator: not_equals
  expected: []
  severity: hard
```

…will fire on an empty observed delta if `--package-root` does not include the
test tree. The constraint is correctly authored; the engine just cannot see
the file you wanted it to gate on.

**Mitigations:**

- Pick a `--package-root` that covers every directory your constraints
  reference (often the repo root, or the package parent that contains both
  `src/` and `tests/`).
- Use the `pyproject.toml [tool.semantic_ci_code.extract] exclude` mechanism
  to drop noisy subtrees instead of narrowing the package root.
- For pure CLI helpers run in CI, prefer `compare --baseline-dir/--candidate-dir`
  pointing at trees that already contain everything you want extracted.

If the test-surface dimension is irrelevant to a particular target file, drop
the constraint instead of leaving it dead.

## Hazard 2 — Template and user constraint duplication (D3)

`change.primary_kind: refactor` auto-expands an `equals_baseline` invariant on
`api_surface_public`. Writing the same constraint by hand:

```yaml
constraints:
  - id: surface_locked
    kind: delta
    target: api_surface_public
    operator: equals_baseline
    severity: hard
```

…is not an error and the verdict is unaffected (both evaluate to the same
result), but it noises up the report and can mask what is *actually* opinion
versus default. Worse, if the template's default ever changes the user
duplicate keeps firing the old contract silently.

**Rules of thumb:**

- Trust the template for the defaults of its `primary_kind`. Add a constraint
  only when you are tightening, loosening, or scoping (e.g. allowing a
  specific symbol via `api_surface.allow_changes`).
- When in doubt, run `semantic-ci compile --format human --target <file>` —
  the compiled `CompiledTarget` lists every constraint that will be evaluated,
  template-supplied or user-authored, with stable IDs. A duplicate ID pair
  with identical `target`+`operator`+`expected` is redundancy you can remove.

## Hazard 3 — Out-of-scope diffs can return vacuous PASS (D4)

A PR that touches only configuration, documentation, or workflow files
(`pyproject.toml`, `.github/workflows/*`, `README.md`, etc.) produces an
empty `CodeStateDelta` under any reasonable `--package-root`.

Whether that empty delta passes depends on the *shape* of the target's
constraints:

- **Lock-only targets pass vacuously.** Template-installed invariants and
  user-authored baseline-lock constraints (`equals_baseline`,
  `no_new_items`, `no_removed_items`, `effect_changes.added == ()`, etc.)
  are all satisfied by an empty delta — there is nothing to violate. The
  verdict is `pass` with `exit 0` even though the engine never inspected
  the diff.
- **Targets with positive delta expectations do *not* pass vacuously.**
  A constraint like the `feature_added` example above
  (`api_surface_delta.added includes_all ["src.api.users.fetch_user_profile"]`)
  reports the expected item as missing on an empty delta and fails as a
  hard violation. `includes_any`, `not_equals expected: []`, and
  `equals expected: <non-empty>` behave the same way.

So D4 is specifically a hazard for **targets whose constraints are entirely
locks** — and those are exactly the targets `primary_kind: refactor` /
`bugfix` / `test_update` produce by default if you do not add anything.

This is the engine behaving correctly — Semantic CI does not claim to gate
non-Python artifacts (see `design.md §13` on out-of-scope items). It is
**not** an endorsement of the change.

**What this means for authors:**

- A green Semantic CI verdict on a config-only PR with a lock-only target is
  silence, not approval. Pair it with the appropriate gate for that
  artifact class (lint, schema check, workflow validator).
- If your target carries a positive delta expectation tied to the diff, you
  will see that constraint fail loudly on a config-only PR — that is the
  engine telling you the work it expected was not done in the Python slice.
  Either move the work or relax / remove the expectation for that target.
- If you want config-shaped invariants enforced, that is a different protocol
  (`docs/brief_7_planning.md` covers the SSP direction; SCA / SAST live there,
  not in core).
- For mixed PRs, the engine still gates the Python slice. The vacuous
  contribution is only on PRs whose entire diff is outside the package root.

## Constraint Authoring Tips

### Pick `kind` deliberately

| `kind` | Looks at | Typical operators |
|---|---|---|
| `state` | candidate state alone | `equals`, `less_than_or_equal`, `includes_all` (against literal) |
| `delta` | baseline ↔ candidate relationship | `equals_baseline`, `includes_all` (against added/removed), `no_new_items` |
| `repair` | next-cycle instruction shape | template-driven; rarely hand-authored |

`kind: state` plus a delta-only path (e.g. `api_surface_delta.added`) is a
compile-time error since PR #58 (`docs/code_semantic_ci_design.md §4.5` and
`compiler/path_schema.py`). The reverse — `kind: delta` against a state path
— is allowed only with baseline-aware operators (`equals_baseline` /
`superset_of_baseline` / `no_new_items` / `no_removed_items`). The compiler
emits did-you-mean suggestions when a target name is close to a known one.

### Set operators against record collections

`api_surface_*`, `effects`, and `imports` collections store records, not
strings. Bare strings in `expected` are auto-desugared to the registered
required key (`fqn` or `module`); see `cli_usage.md` → "Set Operator Match
Semantics" for the full Match Schema table and the partial-match rules.

`includes_any` declares **alternatives**, not a flattened list of additions.
`required_additions` in `validate-plan` reflects this (one
`expected_any_of` group per `includes_any` constraint), so the adapter does
not tell a generator that every alternative must be added.

### Severity and `unknown_policy`

Default `severity: hard` is the right choice for invariants you actually want
to gate. Use `soft` for guidance you want to surface as `repair`, and `info`
for Advisor-channel notes that must not affect the verdict (`design.md §23.3`
forbids Advisor surfaces from feeding back into adherence).

`unknown_policy` controls the routing when an extractor cannot produce the
needed dimension (rare on Python, more likely under
`semantic-ci check --mode smoke`). Pair `unknown_policy: fail` with `hard`
constraints whose silence would be unsafe.

### `allow_changes` / `allow_new` for narrow exceptions

If a refactor genuinely moves a symbol that *looks* like a public API (test
helpers, internal singletons named without a leading underscore), declare it
narrowly:

```yaml
api_surface:
  allow_changes:
    - fqn: helpers.run_semantic_ci
    - fqn_prefix: testlib.
```

This is preferable to weakening the template (e.g. dropping `primary_kind:
refactor`) because the boundary stays auditable: only the listed symbols are
exempt, and the rest of the surface is still locked.

## What This Guide Does Not Cover

- **Whether your declared intent is the right intent.** Semantic CI does not
  check that. The engine takes `target.yaml` as ground truth and reports
  adherence. For example, no template gates `complexity_delta` or `imports`
  against arbitrary additions, so a `primary_kind: bugfix` target without an
  explicit complexity / imports constraint passes a candidate that doubles
  cyclomatic complexity or pulls in a new third-party dependency. Whether
  that matches your *real* intent is out of scope (`design.md §23.3` —
  Adherence, not Correctness). Note this is not the situation for effects:
  every current template installs an `effect_changes` invariant, so adding
  a known effect like `os.system` will route to fail or repair unless you
  whitelist it via `effects.allow_new`.
- **Reviewing the candidate code itself.** Semantic CI does not lint, type
  check, or run tests. Use those tools alongside it.
- **Producing or refining the target file.** `init` scaffolds a syntactic
  skeleton. Filling it in is an author responsibility.

## Cross References

- `docs/code_semantic_ci_design.md` §4 (Target SVP DSL), §5 (Constraint Type
  System), §13 (Out-of-Scope), §23.3 (Responsibility Boundary)
- `docs/cli_usage.md` — Excluding Files From Extraction, Target Policies,
  Constraint Severity, Set Operator Match Semantics
- `docs/exit_codes.md` — verdict-to-exit-code mapping
- `docs/dogfooding_TC10_report.md` — concrete cases (TC1–TC10) of constraints
  exercised end-to-end; D5 / FINDING-1 there is an open hazard tracked
  separately in `.claude/memory/STATUS.md` 次の発行順序 §F
