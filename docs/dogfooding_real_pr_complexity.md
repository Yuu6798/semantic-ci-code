# Dogfooding Report — Real-PR Complexity Sampling (2026-05-28)

This report records a dogfooding pass exercising `semantic-ci check`
against **real merged / closed pull requests in public Python
repositories**, with `target.yaml` declared per-PR around the
**complexity (cyclomatic / cognitive) constraint surface**. The goal is
verdict quality observation against PRs where a human reviewer judgment
already exists — distinct from `docs/dogfooding_TC10_report.md`, which
exercises the input contract with hand-built virtual packages.

Methodology per case:

1. Clone the target repo with the PR ref fetched as a local branch.
2. Author a `target.yaml` declaring `change.primary_kind` and one or two
   `complexity_delta.{cyclomatic,cognitive}` constraints aligned with the
   PR's claimed intent.
3. Run `semantic-ci check --baseline-rev <base> --candidate-rev <head>
   --target <yaml> --package-root <pkg>` and capture verdict + JSON
   envelope.
4. Compare verdict against the PR's actual outcome (merged vs closed and
   the reviewer's stated rationale).

Eight cases were executed across four repositories — seven refactor
intents plus one feature intent as negative control.

## Summary Matrix

| # | Repo / PR | Intent | Δcyc | Δcog | api_surface | Verdict | Tool judgment |
|---:|---|---|---:|---:|---|---|---|
| 1 | `langchain-ai/langgraph` PR #3700 | refactor: reduce cyclomatic complexity of `prepare_single_task` | -40 (misleading) | -89 (misleading) | unchanged | PASS | **WRONG** — vacuous PASS via nested-function blind spot (→ FINDING-F1, D6) |
| 2 | `BerriAI/litellm` PR #15234 | refactor: extract inner function from `client` wrapper | + | + | violated | FAIL | Correct — un-nesting surfaced previously hidden CC; api_surface widening flagged |
| 3 | `ansible-collections/amazon.aws` PR #1193 | refactor: per-action function separation in `s3_object` | -(true) | -(true) | violated (16 new public helpers) | FAIL | Correct — 16 module-level helpers added without `_` prefix; complexity itself satisfied |
| 4 | `pdm-project/pdm` PR #543 | refactor: split `build()` into `prepare` / `metadata` / `build` | -(true) | -(true) | violated | FAIL | Correct — split surfaces new public functions; complexity satisfied |
| 5 | `BerriAI/litellm` PR #11987 | feature: add `/callbacks/list` endpoint (budget Δcyc≤5 / Δcog≤10) | +13 | +14 | n/a | FAIL | Correct — true positive on feature complexity budget |
| 6 | `BerriAI/litellm` `352a0eedb` | refactor: split `_transform_request_helper` (disciplined, `_` prefix) | **+2** | 0 | unchanged | FAIL | **Authoring mismatch** — extract-method micro-increases cyclomatic by construction (→ FINDING-F2, D7) |
| 7 | `BerriAI/litellm` `2d515e72f` | refactor: simplify URL construction (inline, no new function) | -1 | -1 | unchanged | PASS | Correct — clean PASS baseline (sweet spot of extractor) |
| 8 | `pdm-project/pdm` `0fd62dc` | refactor: requirements module | -2 | -4 | violated | FAIL | Correct — same shape as #3 / #4 (api_surface widening with complexity satisfied) |

Aggregated:

- 6 / 8 — tool judgment matches reviewer-relevant signal
- 1 / 8 — vacuous PASS (FINDING-F1, registered as **D6**)
- 1 / 8 — authoring mismatch educational finding (FINDING-F2, registered as **D7**)

## Findings

### FINDING-F1 — nested-function refactor produces vacuous PASS on complexity constraints (severity: high; scope: extractor coverage vs declared intent — sibling of D4)

**Symptom.** Case 1 (langgraph PR #3700) declared:

```yaml
intent: refactor prepare_single_task to reduce cyclomatic complexity without changing behavior
change:
  primary_kind: refactor
  scope:
    files: ["libs/langgraph/langgraph/pregel/algo.py"]

constraints:
  - id: cyclomatic_should_not_increase
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than_or_equal
    expected: 0
    severity: hard
    unknown_policy: fail

  - id: cognitive_should_not_increase
    kind: delta
    target: complexity_delta.cognitive
    operator: less_than_or_equal
    expected: 0
    severity: soft
    unknown_policy: warn
```

`semantic-ci check` returned **PASS** with `complexity_delta.cyclomatic = -40`
and `complexity_delta.cognitive = -89`. Both user constraints reported
`satisfied`.

Direct AST measurement of `prepare_single_task`:

| | Baseline (outer) | Candidate (outer) | Candidate (nested helpers, extractor-blind) |
|---|---:|---:|---|
| cyclomatic | 44 | 4 | `_handle_push_call`=10, `_handle_push_send`=14, `_handle_pull`=18 → sum 42 |
| cognitive | 93 | 4 | 8 + 12 + 26 = 46 |

Including nested helpers, **real** cyclomatic moved 44 → 46 (+2, near no
change); cognitive 93 → 50 (-43, real but half the reported delta).

The PR was independently closed (not merged) by reviewer `nfcampos` with
the comment that helpers should be defined at module top level, not
inside the outer function — the exact structural objection that
`semantic-ci` failed to surface.

**Root cause.** `src/semantic_ci_code/complexity/python_complexity_extractor.py`
spec lines 9-21 explicitly state the emission parity contract:

> Nested functions, nested classes, lambdas, module-level code, and class
> bodies themselves are not emitted as `ComplexityEntry` records.
> ...
> Cyclomatic formula: ... STOP descent when entering a nested
> `FunctionDef` / `AsyncFunctionDef` / `ClassDef`; nested definitions
> contribute 0 to the enclosing function's number.

This is a documented intentional spec choice (parity with `api_surface`
extractor, deterministic formula, P1 simplicity), **not a bug**. The
hazard surfaces in the interaction between this spec choice and a
`target.yaml` that declares the user-facing semantic "complexity should
not increase" — the constraint covers `module-scope function/method
cyclomatic sum`, the author reads it as "complexity of the function
being refactored", and a nested-helper refactor breaks the equivalence.

**Relation to D4.** D4 is a vacuous PASS where the constraint surface is
correctly defined but the actual change lies outside it
(config-only / non-Python diff produces empty `CodeStateDelta`). D6 is a
vacuous PASS where the change lies **inside** the Python scope, **inside**
the touched file, **inside** a function declared in scope — but inside a
nested function that the extractor by spec does not visit. Same root
pattern ("constraint coverage gap masks real change"), different
mechanism. Cross-classified as sibling in `dogfooding_findings_tracker.md`.

**Suggested resolution (proposal, not in this PR).** Two paths:

- (a) Short-term, authoring-side: pin in `docs/target_yaml_guide.md` as
  Hazard 4 with a worked example matching langgraph PR #3700, plus an
  `ADVISORY-D6` detector that flags when a `change.primary_kind=refactor`
  target declares `complexity_delta.*` constraints and the diff includes
  net new nested-function definitions. Mirrors D1 / D3 / D4 treatment.
- (b) Long-term, extractor-side: extend
  `python_complexity_extractor` to emit nested-function entries as
  separate `ComplexityEntry` records. Breaks `api_surface` parity (and
  thus the documented invariant), needs a CSCI brief, schema impact.

Tracked as **D6 (未解決)** in `docs/dogfooding_findings_tracker.md`.

### FINDING-F2 — extract-method refactor structurally violates `complexity_delta.cyclomatic ≤ 0` (severity: low; scope: authoring guidance)

**Symptom.** Case 6 (`litellm 352a0eedb`) is a disciplined
extract-method refactor: a single class method `_transform_request_helper`
is split into `_transform_request_helper` + `_prepare_request_params` +
`_process_tools_and_beta`, all three private (`_` prefix), no
api_surface impact, no effects change. The commit message explicitly
cites resolving PLR0915 ("too many statements") via extract-method.

`semantic-ci check` returned **FAIL** with
`complexity_delta.cyclomatic = +2`, `complexity_delta.cognitive = 0`.

The cyclomatic micro-increase is **structural**, not a bug: cyclomatic
counts decision points + 1 per function. Splitting one function into N
functions creates N base counts of 1 in place of 1, so the sum gains
(N - 1) baseline units before any branch redistribution. Cognitive,
which measures nesting depth and not function entry, is unaffected (and
typically improves) by the same operation.

**Root cause.** Math, not implementation. The constraint
`complexity_delta.cyclomatic ≤ 0` is the wrong gate for an
extract-method refactor pattern; `complexity_delta.cognitive ≤ 0` is the
right one.

**Suggested resolution (proposal, not in this PR).** Two paths,
non-exclusive:

- (a) `docs/target_yaml_guide.md` § "Choosing complexity metric per
  refactor pattern" — short authoring recipe table mapping refactor
  shape (extract-method, inline simplification, condition flattening,
  nested-helper introduction) to the constraint that matches author
  intent (`cognitive_delta` vs `cyclomatic_delta`, `≤ 0` vs `≤ N`).
- (b) Future `ADVISORY-D7` detector emitting an authoring warning when
  `change.primary_kind=refactor` is paired with `complexity_delta.cyclomatic ≤ 0`
  and the change shape matches extract-method (net new private
  functions in the touched file). Lower priority than D6 since this is
  authoring polish, not a CI integrity gap.

Tracked as **D7 (未解決, low priority)** in
`docs/dogfooding_findings_tracker.md`.

### Observations without finding registration (F3 / F4 / F5)

These three patterns surfaced repeatedly but represent confirmed correct
tool behavior or a single baseline data point, not a new D-class hazard.
Logged here so future passes don't relitigate.

- **F3** — refactor template's `api_surface_unchanged` flagged 3 of 8
  cases (#3 amazon.aws, #4 pdm, #8 pdm), all driven by **the same shape**:
  authors add new module-level helpers without `_` prefix, surfacing them
  as public API. Tool behavior matches spec ("warn when public API
  widens"), and arguably catches a real reviewer-relevant signal
  (intent-vs-naming-discipline gap). Author's complementary mitigation
  is to use `_` prefix, not to change the template. Recorded as confirmed
  template-strictness pattern, not a hazard.
- **F4** — case 7 (inline simplification, no new function) is the
  unambiguous clean-PASS baseline: `Δcyclomatic = -1` matches the single
  removed conditional, `Δcognitive = -1` matches the same. Useful as the
  reference point for "what the verdict looks like when extractor and
  author intent coincide". Single data point, not a hazard.
- **F5** — cases 2 and 5 are true positives: un-nesting an inner
  function (case 2) correctly surfaces previously-hidden CC; a feature
  PR (case 5) correctly overshoots a stated budget by +8 / +4. These
  validate that the tool's positive judgments are reliable on
  conventional refactor / feature shapes.

## Reproduction Artifacts

PR refs (base / head SHA) and the `target.yaml` for each case were
constructed at session time. They are **not** committed because:

1. External PR SHAs are stable, but the engine input contract
   (`CLAUDE.md` Engine Contract) permits reconstructing each case from
   public git history plus an inline `target.yaml`.
2. The `target.yaml` for each case is short (≤ 20 lines) and is inlined
   above for FINDING-F1; cases 2-8 use the same skeleton with only
   `intent` and `scope.files` differing.

To reproduce a case:

```bash
git clone --depth 100 --filter=blob:none https://github.com/<owner>/<repo>.git
cd <repo>
# for PR-numbered cases (1-5):
git fetch origin pull/<PR>/head:pr<PR>
# for commit-only cases (6-8): no extra fetch needed if the SHA is on main
# write target.yaml as above (FINDING-F1 example; cases 2-8 use the same
# skeleton with only intent and scope.files differing)
semantic-ci check \
  --baseline-rev <base-sha> --candidate-rev <head-sha> \
  --target target.yaml --package-root <pkg> --format json
```

### Per-case reproduction inputs

| # | Repo | Source ref | Base SHA | Head SHA | `--package-root` |
|---:|---|---|---|---|---|
| 1 | `langchain-ai/langgraph` | PR #3700 (closed) | `e8631c052a2731ac676965c08eff8c3127bb462c` | `0aedea90d631c77f9d30de271c4a7c5e71629ad4` | `libs/langgraph/langgraph` |
| 2 | `BerriAI/litellm` | PR #15234 (merged) | `ddb90c9ad7a7c65e2dd1037ceb8e391a86e6cc66` | `c36e7ab575d9414009fe2c47c8f641ca752a406b` | `litellm` |
| 3 | `ansible-collections/amazon.aws` | PR #1193 (merged) | `52068c04aa48b20ccf5956f9f575a957144045b7` | `5e5c9933d32aea018f39f2ba2bf560f0b4d1e174` | `plugins/modules` |
| 4 | `pdm-project/pdm` | PR #543 (merged) | `085d2b7b6cb6450fc7daec7e69ab147daf2cd855` | `99c5c429871b389df811241b1e722b2b2800cb8f` | `pdm` |
| 5 | `BerriAI/litellm` | PR #11987 (merged, feature) | `8c5fb6f539b3fee5ea5eac3892fe7908902db4dc` | `cc065f1d4c47acc28469c1d62dd164c650f43b19` | `litellm` |
| 6 | `BerriAI/litellm` | commit on main | `a34bb6f6d375c97f1db286f2644393c4d163c329` | `352a0eedb554fb817a0d0651faead9bf02c3fdfc` | `litellm` |
| 7 | `BerriAI/litellm` | commit on main | `0f5b31fd78592c7c8144efe1b372c53e51d27d11` | `2d515e72ffa43ef6799118a839b320c262b65592` | `litellm` |
| 8 | `pdm-project/pdm` | commit on main | `ae309ea56ae2ff4853a48be3a305c8e2de08215d` | `0fd62dc7fb7e244a00392c4a6f6801617b63e05e` | `pdm` |

### Per-case `target.yaml` deltas from the FINDING-F1 skeleton

Cases 2–4, 6–8 reuse the same two-constraint skeleton as case 1
(`complexity_delta.cyclomatic ≤ 0` hard, `complexity_delta.cognitive ≤ 0`
soft) with `change.primary_kind: refactor`, only the `intent` string and
`change.scope.files` differing per case. Case 5 differs structurally
(feature with budgets):

```yaml
# Case 5 (litellm PR #11987) — feature budget
intent: add List Active Callbacks API endpoint, expect modest complexity increase budget
change:
  primary_kind: feature
constraints:
  - id: cyclomatic_budget
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than_or_equal
    expected: 5
    severity: hard
    unknown_policy: fail
  - id: cognitive_budget
    kind: delta
    target: complexity_delta.cognitive
    operator: less_than_or_equal
    expected: 10
    severity: hard
    unknown_policy: fail
```

## Tracking

Findings classification (resolved / unresolved / sibling) for this pass
and all prior passes is consolidated in
**`docs/dogfooding_findings_tracker.md`**. Update that file when D6 / D7
status changes; do not re-tabulate D-class status inside this report.

Quick links:

- **D6** (FINDING-F1, nested-function vacuous PASS) — 未解決, sibling of D4
- **D7** (FINDING-F2, extract-method × cyclomatic authoring mismatch) — 未解決, low priority
