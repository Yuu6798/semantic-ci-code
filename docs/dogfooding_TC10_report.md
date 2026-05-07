# Dogfooding Report — TC10 (2026-05-07)

This report records a dogfooding pass exercising `semantic-ci` against virtual
Python packages to validate operational behavior and surface CI-integrity gaps.
Each test case constructs hand-built `baseline/` and `candidate/` package trees
plus a `target.yaml`, then runs `semantic-ci compare`, `validate-plan`, or
`compile-repair` and inspects the JSON envelope and exit code.

The cases cover all four verdict-bearing surfaces of `compare`/`check`
(PASS / REPAIR / FAIL / template-only), plus pre-generation guidance, the
Advisor channel (`severity: info`), and CLI input hardening. Virtual scenarios
were chosen so the engine input contract (§Engine Contract in `CLAUDE.md`) is
exercised directly without git ceremony.

## Summary Matrix

| TC | Surface | Scenario | Expected | Observed | Verdict |
|---:|---|---|---|---|---|
| TC1 | `compare` | refactor: f-string conversion, API stable | `pass` / exit 0 | `pass`, 4 satisfied, 0 violated | ✅ |
| TC2 | `compare` | "refactor" silently removes a public function | `fail` / exit 1 | `fail`, `template:refactor:api_surface_unchanged` violated | ✅ |
| TC3 | `compare` | feature claim, required addition missing | `fail` / exit 1 | `fail`, user `includes_any` violated | ✅ |
| TC4 | `compare` | feature: required public function added | `pass` / exit 0 | `pass` once user constraint matches full record | ✅ (with FINDING-1) |
| TC5 | `compare` | bugfix template flags scope creep (extra public symbol) | `fail` / exit 1, `added` populated post-fix | `fail`, `template:bugfix:api_surface_unchanged` violated, `added=[safe_divide]` after fix | ✅ (drove FINDING-2 fix) |
| TC6 | `validate-plan` | pre-generation guidance with `would_violate`, `required_additions` | rendered text + 4-list `risk_summary` | rendered, 1 would_violate, 1 required_additions, 2 template_implications | ✅ |
| TC7 | CLI hardening | malformed YAML / Python tag injection / missing target / unknown adapter / nonexistent dirs | exit 2 or 3 with stderr diagnostic | YAML `!!python` rejected (exit 3); missing target exit 2; unknown adapter exit 2; malformed YAML exit 3 | ✅ |
| TC8 | `check` | self-dogfood: this repo HEAD vs HEAD with engine sources | `pass` / exit 0, `files_touched: 0` | `pass`, cache hit/miss `1/1`, schema_version `4` | ✅ |
| TC9 | `compare` | `severity: info` user constraint violated, no hard violations | `pass` / exit 0, repair `category: info` | `pass`, summary `info: 1, fix_required: 0`, instruction emitted | ✅ |
| TC10 | `compile-repair` | input verdict envelope contract: future `schema_version`, malformed JSON, PASS-with-null-repair | future version warns to stderr (after fix); malformed JSON exit 2; null repair_plan on PASS exit 2 | ⚠ before fix: future version silently rendered; ✅ after FINDING-4 fix | ✅ (after fix) |

10 cases executed. The verdict and exit codes match the documented contract in
`docs/cli_usage.md` and `docs/exit_codes.md` for every case.

## Environment Note

`pytest -q` from a fresh `pip install -e ".[dev]"` collects 38 modules with
import-time errors and reports 70 failures in `tests/cli/`. All 70 failures
trace back to the sandboxed environment's git commit signing harness:

```
error: Debug: Namespace set to "git" (ignored)
Error: signing failed: signing operation failed: signing server returned status 400
fatal: failed to write commit object
```

Tests that do not initialize a real git repo are unaffected; for example
`tests/test_scope.py` and `tests/repair_compiler/` pass cleanly when invoked
through `python -m pytest`. The initial collection error reported by `pytest`
without `python -m` is a separate harness mismatch (`/root/.local/bin/pytest`
imports against a different `sys.path`), not a code defect.

## Findings

### FINDING-1 — set operators against `api_surface_*` require exact full-dict match (severity: high; scope: spec authoring UX + CI integrity)

**Symptom.** TC4 declared a feature constraint:

```yaml
- id: "user:must_add_password_reset"
  kind: delta
  target: api_surface_delta.added
  operator: includes_any
  expected:
    - fqn: "myapi.endpoints.password_reset"
  severity: hard
```

The candidate package contained `myapi.endpoints.password_reset` exactly as
required, and `code_state.api_surface` confirmed it. The constraint nevertheless
returned `status: violated` with this evidence:

```jsonc
"expected": [[["fqn", "myapi.endpoints.password_reset"]]],
"observed": [[["fqn", "..."], ["kind", "function"], ["signature", "..."], ["visibility", "public"]]]
```

**Root cause.** `evaluator/operators.py::_collection_items` canonicalises a
dict as the tuple of all `(key, value)` pairs, then performs set membership.
A partial dict `{fqn: X}` is therefore a *different element* from the full
extracted record `{fqn, kind, signature, visibility}`, so set difference
reports it missing.

To pass, an author must inline the full extracted record verbatim — including
the exact `signature` string (e.g. `"def password_reset(user: str, token: str) -> bool:\n    ..."`). The design example in
`docs/code_semantic_ci_design.md §4.5` even shows
`expected: ["src.api.users.fetch_user_profile"]` as a bare string list, which
likewise fails to match in P1 because elements are full dicts.

**Operator-specific outcomes.** The partial-record mismatch produces two
qualitatively different failure modes depending on the set operator. Both
are caused by the same canonicalisation, but their CI consequences invert.

| Operator | Partial-dict outcome | Failure mode | Author intent that breaks |
|---|---|---|---|
| `includes_all` | `expected − observed` non-empty → violated | **False positive** (silently violated) | "must contain X" — gate fails even when X is present |
| `includes_any` | `expected ∩ observed` empty → violated | **False positive** (silently violated) | "must contain at least one of X / Y" — gate fails even when matches exist |
| `superset_of` | `expected − observed` non-empty → violated | **False positive** (silently violated) | "observed must include all of expected" — gate fails even when it does |
| `subset_of` | `observed − expected` non-empty → violated | **False positive** (silently violated) | "observed must be subset of allow-list" — gate fails because partial-dict expected can't cover full observed |
| **`excludes_all`** | **`expected ∩ observed` empty → satisfied** | **False negative (CI bypass)** | **"must not contain forbidden X" — gate passes even when X IS present** |

**CI integrity impact.** Two distinct failure modes, with `excludes_all` the
more severe:

1. **False positive (`includes_all` / `includes_any` / `superset_of` / `subset_of`).**
   Partial-key constraints *always* report violated even when the target is
   met. Authors either paste the exact extractor output (coupling spec to
   extractor format, breaking on signature canonicalisation changes) or
   learn to ignore the noisy gate.
2. **False negative (`excludes_all`, CI bypass).** Authors writing forbidden-
   symbol policies as `excludes_all: [{fqn: "dangerous.api"}]` get a
   *silently satisfied* gate even when `dangerous.api` is in observed.
   The forbidden-symbol enforcement effectively does not exist on the user
   surface. This is the most dangerous of the two modes because it converts
   a security / policy gate into a no-op.

This silently degrades the trustworthiness of the verdict on the user-author
surface. Template constraints are unaffected because they use baseline-
relative operators that compare full records on both sides.

**Suggested resolution (proposal, not in this PR).** Either (a) define a
"matcher" subset semantics for set operators when expected items are partial
dicts that share a documented "key" field (e.g. `fqn` for api_surface,
`fqn`+`effect_class` for effects), or (b) add a normalised projection target
such as `api_surface_delta.added.fqns` that yields a flat `tuple[str, ...]`.
Either path needs a Brief — proposing this be tracked alongside CSCI-35b
sweep or as a P3 spec-quality brief (§19).

### FINDING-2 — `equals_baseline` violations omit structured `added`/`removed` in repair instruction (severity: medium; scope: adapter UX) — fixed in this PR

**Symptom (before fix).** TC5's `template:bugfix:api_surface_unchanged`
violation produced a repair instruction with empty arrays:

```jsonc
"added": [], "removed": [], "missing": [], "extra": [],
"extra_evidence": {
  "baseline": [ ...full record for divide... ],
  "candidate": [ ...full records for divide AND safe_divide... ]
}
```

The `safe_divide` symbol was added (the actual delta), but neither `added`
nor `extra` carried it. Adapters (`claude-code`, `cursor`, `codex`) that
render structured added/removed lists had to recompute the diff from
`extra_evidence.baseline` vs `extra_evidence.candidate` themselves, which
defeated the point of the repair envelope being a stable interchange format.

**Root cause.** `evaluate_baseline_operator` for `EQUALS_BASELINE` /
`UNCHANGED` (formerly lines 110-115 of `evaluator/operators.py`) called
`_baseline_boolean_outcome`, which emits only `baseline` and `candidate`.
The set-aware sibling operators (`NO_NEW_ITEMS`, `NO_REMOVED_ITEMS`,
`SUPERSET_OF_BASELINE`) already passed set diffs through
`_baseline_set_outcome` — `EQUALS_BASELINE` simply did not.

**Why this is not a design decision.** The `added` / `removed` fields
already exist on the repair instruction schema; the existing fields'
"items in candidate, not baseline" meaning is unchanged. Populating them
for `equals_baseline` violations does not require a `schema_version` bump
under the rules in `docs/json_schema.md` (no field added, removed,
renamed, or repurposed).

**Resolution applied in this PR.** `evaluate_baseline_operator` now
delegates `EQUALS_BASELINE` / `UNCHANGED` to a new `_equals_baseline`
helper. When values are equal, behavior is unchanged. When they differ
**and** both sides are set-like (per `_collection_items`), the helper
computes the symmetric set difference and routes through
`_baseline_set_outcome`, populating `added` / `removed` alongside
`baseline` / `candidate`. Scalar mismatches still fall back to the
boolean outcome, so the evidence shape for non-collection dimensions is
unchanged.

Tests added in `tests/evaluator/test_evaluator.py`:
- `test_equals_baseline_violation_emits_added_and_removed_set_diff`
- `test_equals_baseline_satisfaction_does_not_emit_set_diff`

Re-running TC2 (`refactor` silently dropping `farewell`) and TC5
(`bugfix` adding `safe_divide`) post-fix confirms `removed` and `added`
are populated correctly.

### FINDING-3 — `compile-repair` accepts arbitrary input `schema_version` without surfacing the mismatch (severity: low; scope: forward-compat / DX)

**Symptom (before fix).**

```bash
$ echo '{"schema_version":"99","subcommand":"check","verdict":"fail",
        "repair_plan":{"result":"fail","instructions":[]}}' \
  | semantic-ci compile-repair --adapter claude-code
# Repair Instructions
...
$ echo $?
0
```

A future verdict envelope whose shape is incompatible with the current
`deserialize_repair_plan` could silently render a degraded plan because
unknown fields are ignored.

**Resolution applied in this PR.** `_extract_repair_plan` now compares the
input verdict envelope's `schema_version` against the CLI's current verdict
schema version (`"4"`). When they differ — and only then — a one-line stderr
warning is emitted; exit code, stdout, and structured envelope shape are
unchanged. This preserves forward compatibility (older readers can still
consume newer envelopes) while making version drift visible to operators.

Tests added in `tests/cli/test_compile_repair.py`:
- `test_compile_repair_warns_when_verdict_envelope_schema_version_unexpected`
- `test_compile_repair_no_warning_when_verdict_envelope_schema_version_matches`
- `test_compile_repair_no_warning_when_schema_version_absent`

The "absent" case keeps backward compatibility with raw `RepairPlan` inputs
that were never required to carry a schema version.

## Out-of-Scope Probes (negative findings)

- **YAML deserialization safety.** `target.yaml` rejects `!!python/...` tags
  with exit 3 (`could not determine a constructor for the tag ...`). No code
  execution. ✅
- **Path traversal via `--package-root-baseline`.** `compare` resolves the
  package root by `Path(...).resolve()` without an "inside `--baseline-dir`"
  check, so passing `../../../etc` extracts from `/etc`. After review, this is
  *consistent with the documented contract*: `compare` is the no-git surface
  where operators explicitly choose roots. The `check`, `pre-commit`, and
  `validate-plan` surfaces (which derive paths from refs/baselines) already
  enforce `is_relative_to` (see `commands/check.py:200-209`). No fix needed
  unless docs choose to forbid this for `compare` as well.
- **`init` overwrite protection.** Refuses to overwrite an existing target
  file without `--force`; exits 2 with a clear stderr message. ✅
- **Empty staged index for `pre-commit`.** Returns exit 0 with empty PASS
  payload as documented. ✅ (verified indirectly via TC8.)

## Reproduction Artifacts

All TC fixtures are under `/tmp/dogfood/tcN/` in the original session, with
`{baseline,candidate}/` package trees, `target.yaml`, and saved JSON
envelopes (`tcN_result.json`). They are deliberately not committed because
the engine input contract (`CLAUDE.md` Engine Contract) requires that the
evaluator accept hand-built `CodeState` and synthetic directory pairs — the
fixtures exist purely to demonstrate that contract holds end-to-end through
the CLI surface.

## Next-Brief Candidates

| Priority | Brief candidate | Source | Status |
|---|---|---|---|
| H | Set-operator partial-match semantics for user constraints | FINDING-1 | **Open / Unresolved — tracked as D5** in `.claude/memory/STATUS.md` 次の発行順序 §F (own brief, 1〜2 日規模) |
| L | Optional `--strict-schema` flag on `compile-repair` (promote warning to error) | FINDING-3 follow-up | Open — small, no brief required |

FINDING-2 was originally listed here but resolved in this PR (see above).

### Tracking: D5 (FINDING-1) — Open / Unresolved

FINDING-1 is the only finding from this dogfooding pass that remains open
after PR #61. It is integrated into the dogfood-driven fix plan as **D5**,
joining D1〜D4 from the 2026-05-07 Session 4 dogfooding
(`.claude/memory/2026-05-07.md` §"dogfood 発見 D1〜D4"). Unlike D1〜D4, which
split between an authoring guide (`docs/target_yaml_guide.md`, hosting
D1/D3/D4) and a separate extractor-exclude brief (D2), D5 requires
operator-level semantics changes and is therefore tracked as its own brief
candidate at `.claude/memory/STATUS.md` 次の発行順序 §F.

| D# | Source | Subject | Brief slot |
|---|---|---|---|
| D1 | Session 4 dogfood | `--package-root` scope hazard | A' (`target_yaml_guide.md`) |
| D2 | Session 4 dogfood | extractor crash on `syntax_error/bad.py` | D (extractor exclude brief) |
| D3 | Session 4 dogfood | template / user constraint duplication | A' (`target_yaml_guide.md`) |
| D4 | Session 4 dogfood | config-only PR vacuous PASS | A' (`target_yaml_guide.md`) |
| **D5** | **Session 5 dogfood (PR #61, FINDING-1)** | **set operator partial-match semantics — false positive on `includes_*` / `subset_of` / `superset_of`, false negative (CI bypass) on `excludes_all`** | **F (own brief)** |

Resolution requires either a partial-key matcher semantics on set operators,
a flat-projection target like `api_surface_delta.added.fqns`, or both. The
brief itself will pick between these; this dogfooding pass only documents
the gap and supplies reproduction conditions in TC4. The brief MUST address
**both** failure modes — false positives on positive set operators and the
false negative on `excludes_all` — because partial-key matcher semantics
need to apply symmetrically to closing the CI bypass.
