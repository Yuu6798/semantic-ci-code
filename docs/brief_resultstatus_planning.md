# Brief — ResultStatus authoring/extraction split (working title: TBD)

> Status: REFERENCE (complete). The authoring/extraction split and validate-plan
> v2 changes landed; the text below retains the original sequencing rationale.
>
> Sequencing: this brief sits between Brief 5 (P2.5 完走)
> and Brief 7 (SSP v0.1) in the queue, or runs in parallel to Brief 7 entry —
> exact brief number is decided when the first Task Brief lands.
>
> **Working title note (2026-05-12)**: original draft proposed "Brief 8?" as
> working title. Since draft, `docs/brief_8_planning.md` (Authoring Surface /
> CSCI-41〜44) has been merged on main and claimed the Brief 8 slot. This
> planning doc therefore stays without a fixed brief number until first
> Task Brief lands. The boundary with Brief 8 is §1b below.
>
> Live status: `.claude/memory/STATUS.md` 次の発行順序 §E

## 1. Why this brief exists

`ResultStatus.UNKNOWN` currently conflates two failure classes:

- **authoring error** — `target.yaml` is malformed (path string syntactically
  invalid, target path doesn't resolve, kind/operator/target-domain mismatch,
  operator vs observed/expected type mismatch)
- **extractor / observation failure** — the engine could not produce a
  decisive value (extractor partial, parent attribute is None, observation
  not possible)

These have different remediation paths (fix the spec vs fix the
environment / extractor / target.yaml scope), but the engine renders them
identically through `unknown_policy` and downstream `repair_plan` /
`risk_summary` / SARIF / GH Actions surfaces.

A small but important consequence: `unknown_policy: warn` on a constraint
is documented (`design.md §5.4`) as the *extractor failure* policy, yet
the same routing currently swallows authoring errors silently — a hard
gate around a typo'd target path turns into a warn just because that
constraint authored `unknown_policy: warn` for its (intended) extraction
risk.

## 1b. Boundary with Brief 8 (Authoring Surface)

`docs/brief_8_planning.md` (Brief 8 / CSCI-41〜44, merged on main) lands
authoring-side tooling (`init --recipe --from-*` / `target-doctor` /
`target-catalog`) on the **Authoring / Provenance / Advisor surfaces** of
`design.md §23.3.1`. This planning doc lands on the **Validator surface**.
Both touch the word "authoring error" but for disjoint error classes.

### 1b.1 Error class boundary

| Error class | Surface | Owned by |
|---|---|---|
| **semantic hazard** — empty effective constraint, template-vs-user constraint duplication, `severity:info` + `unknown_policy: fail/repair` 矛盾, primary_kind と user constraint の不整合, config-only PR vacuous PASS | Advisor (`target-doctor`, advisory, exit 0) | **Brief 8** (CSCI-43 `ADVISORY-D1/D3/D4/P1/P2/S1`) |
| **syntactic / type error** — target path malformed (`E_PATH_UNRESOLVED`) / kind × operator × path-domain mismatch (`E_OPERATOR_TARGET_MISMATCH`) / operator vs observed-or-expected type mismatch (`E_TYPE_MISMATCH`) | Validator (compile-time `CompileError`) | **this brief** (D1-2 / D1-3) |

The two classes are non-overlapping by construction: semantic hazards are
detectable on a syntactically valid spec, syntactic/type errors are
detectable without needing the candidate diff.

### 1b.2 INV-1 framing (Brief 8 §6.3.5 invariant)

Brief 8 invariant INV-1 reads: "`check` の verdict 計算は不変". This brief
introduces D2 (authoring-cause UNKNOWN routes to FAIL regardless of
`unknown_policy`) which changes verdict aggregation on the surface.

**Resolution**: D2 is not a verdict-logic change in the INV-1 sense. INV-1
fixes "same well-formed `(target, baseline, candidate)` → same verdict".
D2 narrows the input contract: a syntactically malformed target (which
previously could emit UNKNOWN routed by `unknown_policy: warn/ignore` to
silent pass) is now rejected at compile-time as `CompileError`, never
reaching `_aggregate`. The residual runtime UNKNOWN that *does* reach
`_aggregate` (extraction / open_runtime / evaluator_internal) keeps the
current `unknown_policy` semantics. INV-1 holds on the well-formed input
domain; this brief shrinks the malformed-input domain rather than
re-defining `_aggregate` over it.

Briefs implementing D1-2 / D1-3 / D1-4 MUST cite this framing in their
Task Brief so Codex / reviewer don't mis-classify D2 as an INV-1 violation.

### 1b.3 ADVISORY-S1 文言更新の見込み

Brief 8 §6.3.1 `ADVISORY-S1` flags `severity: info` combined with
`unknown_policy in {fail, repair}` as a configuration mistake (the
informational severity is meant to keep the constraint out of verdict, but
`unknown_policy: fail` re-arms it for the UNKNOWN branch).

After D2 lands, the framing changes:

- **authoring-cause UNKNOWN**: always FAIL irrespective of `unknown_policy`
  (and irrespective of `severity` for VIOLATED, which was already the case).
  Author has no knob — fixing the spec is the only path forward.
- **extraction-cause / open_runtime UNKNOWN**: `unknown_policy` still
  governs. `severity: info` + `unknown_policy: fail` remains the same
  configuration mistake S1 already flags.

Outcome for S1: scope narrows to "extraction-cause + open_runtime" but is
**not redundant**. S1 message text needs a one-line update once D1-4 lands.
This brief's D1-4 PR description MUST call out the S1 text update as a
follow-up for the Brief 8 CSCI-43 implementer.

**Resolved:** D1-4 and Brief 8 are both complete. `ADVISORY-S1` remains scoped
to runtime UNKNOWN routing; compile-time authoring errors no longer reach that
branch.

### 1b.4 着地順序の選択(open question, user 判断)

| Option | UX 上の効果 |
|---|---|
| **Brief 8 先 → ResultStatus split** | target-doctor が D1/D3/D4 advisory を出す体験が先に立ち上がる。 後で ResultStatus split が `E_OPERATOR_TARGET_MISMATCH` 等を CompileError 化すると、 target-doctor advisory が拾う前に compile が止めるケースが増える(target-doctor は valid YAML を前提とする運用のまま)|
| **ResultStatus split 先 → Brief 8** | compile error が一時的に増えて authoring 体験が悪化、 後で `init --recipe` + `target-doctor` で救済される流れ。 authoring hazard と syntactic error が同時期に整理される利点 |
| **並列** | INV-1 framing と S1 文言整合を双方の PR で守れば技術的に可能。 ただしレビューコストが上がる |

決定は **first Task Brief 発行時** に user 判断。 並列にしない場合でも
本 planning doc は Brief 8 と独立に維持できる構造になっている。

## 2. Root direction (固定)

```text
authoring error は compile-time に押し戻す。
runtime UNKNOWN は extraction / open schema / 実行時観測不能 に限定する。
UNKNOWN の原因は status enum ではなく optional diagnostic field で表す。
```

This is the engineering invariant the brief enforces.

## 3. Decisions

### D1. ResultStatus model — **C + B 仮固定**

| candidate | decision | rationale |
|---|---|---|
| **A** — enum 拡張 (`unknown_authoring` / `unknown_extraction`) | **rejected** | `status` is *judgment state*, not *failure cause*. Enum split would force SARIF / GH Actions / adapter / fixture / envelope sweep for value gained: rendering the cause as a status name. High cost, narrow benefit |
| **B** — sibling field `unknown_cause` | **adopted** (thin form) | Keeps status enum stable. Represents diagnosis as a separate concern. Naming locked: **`unknown_cause`** (not `failure_mode`, which would creep into `VIOLATED` / `SKIPPED`). No diagnostic object yet — flat string field is enough |
| **C** — push authoring to compile-time | **adopted** (D1 main body) | PR #58 already proved this path for path schema. `design.md §5.4` already scopes `unknown_policy` to extractor failure, so authoring → compile-time matches existing responsibility boundary |

`unknown_cause` value space (initial):

```text
authoring        # spec is malformed; only emitted when C cannot push it back
extraction       # extractor failed / partial / parent None
open_runtime     # path is in an open schema region (python_specific.*, etc.)
```

A fourth value (`evaluator_internal`) may be reserved for the
`except Exception` defensive net (operators.py:106 / :134) — to be decided in
D1-4 when we wire it.

Result envelope shape:

```json
{
  "status": "unknown",
  "error_code": "E_TYPE_MISMATCH",
  "unknown_cause": "authoring"
}
```

### D2. unknown_policy interaction

```text
authoring-unknown : policy 非尊重、強制 fail (verdict / repair-routing 共に)
extraction-unknown / open_runtime : policy 尊重 (現状維持)
```

Reasoning: an authoring error is *invalid input*, not *undecided judgment*.
Allowing `unknown_policy: warn` to swallow a malformed spec turns a hard gate
into silence and breaks the gate contract. Extraction-unknown is the original
intent of `unknown_policy` (`design.md §5.4`) and stays unchanged.

`SKIPPED` is not affected — smoke mode / partial extract routing remains the
clean SKIPPED channel.

### D3. risk_summary split

Add `authoring_errors` as a sibling list to `would_violate`:

```json
{
  "risk_summary": {
    "would_violate": [],
    "authoring_errors": [],
    "forbidden_zones": [],
    "required_additions": [],
    "template_implications": []
  }
}
```

`would_violate` stays scoped to "this implementation will likely violate" —
generator-facing implementation hints. `authoring_errors` is scoped to "the
spec itself is broken" — author-facing fix-the-spec hints. Adapter rendering
must surface them as a two-step instruction:

```text
まず target.yaml の authoring_errors を直せ。
その後、would_violate / forbidden_zones / required_additions を見て実装せよ。
```

This stops AI generators from confusing "fix the implementation" with
"fix the spec".

### D4. Envelope schema

| envelope | bump | rationale |
|---|---|---|
| verdict / compile (current `"5"`) | **据え置き(原則)** | status enum unchanged. `results[].unknown_cause` is a nested optional diagnostic field; existing readers can ignore it. **Compatibility note added below** |
| validate-plan (current `"1"`) | **bump to `"2"`** | `risk_summary.authoring_errors` is a new top-level list under `risk_summary` — qualifies as additive top-level under the existing compatibility policy |
| compile-repair (current `"1"`) | **据え置き** | Renders only what the serialized `RepairPlan` carries; no schema impact |

**Compatibility note (to be added to `docs/json_schema.md`):**

```text
results[] や risk_summary 等の nested optional diagnostic field の追加は、
既存 reader が無視可能である限り schema_version bump を要求しない。
schema_version bump は (a) status / verdict 等の enum 値追加・削除、
(b) 既存 field の意味変更、(c) top-level field 追加 で必要。
```

If a downstream tool (e.g. ours own SARIF / GH Actions) starts depending on
`unknown_cause` being present, that's a strict schema parse pattern and we
revisit the bump decision in the brief that flips the dependency. PR scope
should call this out explicitly.

## 4. Investigation: C scope (Brief D1-1 deliverable)

Investigation only, no implementation changes. Tables + counts to size the
implementation briefs (D1-2 / D1-3).

### 4.1 Target type categories

Initial taxonomy (deliberately shallow):

```text
scalar_string
scalar_number
scalar_bool
record
record_collection
string_collection
number_collection
mapping_open
nullable        # qualifier on top of another category (coverage_delta etc.)
unknown_open    # python_specific / typescript_specific / type_changes
```

### 4.2 CodeState target path → category (kind: state)

| target path | Pydantic type | category |
|---|---|---|
| `api_surface` | `tuple[APISurfaceEntry, ...]` | record_collection |
| `api_surface_public` | (synthesized public-only) | record_collection |
| `type_relations` | `tuple[TypeRelation, ...]` | record_collection |
| `effects` | `tuple[EffectEntry, ...]` | record_collection |
| `control_flow` | `tuple[ControlFlowEntry, ...]` | record_collection |
| `data_flow` | `tuple[DataFlowEntry, ...]` | record_collection |
| `imports` | `tuple[ImportEntry, ...]` | record_collection |
| `complexity` | `tuple[ComplexityEntry, ...]` | record_collection |
| `test_surface` | `tuple[TestSurfaceEntry, ...]` | record_collection |
| `coverage` | `tuple[CoverageEntry, ...] \| None` | record_collection (nullable) |
| `module_graph` | `tuple[ModuleGraphEntry, ...]` | record_collection |
| `python_specific` | `JsonMapping \| None` | unknown_open |
| `typescript_specific` | `JsonMapping \| None` | unknown_open (dormant) |

13 paths total. **11 statically typed, 2 unknown_open.**

### 4.3 CodeStateDelta target path → category (kind: delta)

| target path | Pydantic type | category |
|---|---|---|
| `api_surface_delta` | `SymbolDelta` | record |
| `api_surface_delta.added` | `tuple[JsonValue, ...]` | record_collection |
| `api_surface_delta.removed` | `tuple[JsonValue, ...]` | record_collection |
| `api_surface_delta.removed_public` | (synthesized) | record_collection |
| `api_surface_delta.changed` | `tuple[JsonValue, ...]` | record_collection |
| `api_surface_delta.added.fqns` | (flat projection) | string_collection |
| `type_changes` | `tuple[JsonValue, ...]` | record_collection (element shape unknown) |
| `effect_changes` | `EffectChanges` | record |
| `effect_changes.added` | `tuple[JsonValue, ...]` | record_collection |
| `effect_changes.removed` | `tuple[JsonValue, ...]` | record_collection |
| `effect_changes.added.fqns` | (flat projection) | string_collection |
| `cfg_delta` | `CFGDelta` | record |
| `cfg_delta.new_branches` | `int` | scalar_number |
| `cfg_delta.removed_branches` | `int` | scalar_number |
| `imports_delta` | `ImportDelta` | record |
| `imports_delta.added` | `tuple[JsonValue, ...]` | record_collection |
| `imports_delta.removed` | `tuple[JsonValue, ...]` | record_collection |
| `imports_delta.added.modules` | (flat projection) | string_collection |
| `complexity_delta` | `ComplexityDelta` | record |
| `complexity_delta.cyclomatic` | `int` | scalar_number |
| `complexity_delta.cognitive` | `int` | scalar_number |
| `test_surface_delta` | `TestSurfaceDelta` | record |
| `test_surface_delta.new_files` | `tuple[str, ...]` | string_collection |
| `test_surface_delta.new_cases` | `tuple[str, ...]` | string_collection |
| `test_surface_delta.removed_cases` | `tuple[str, ...]` | string_collection |
| `coverage_delta` | `CoverageDelta \| None` | record (nullable) |
| `coverage_delta.line` | `float \| None` | scalar_number (nullable) |
| `coverage_delta.branch` | `float \| None` | scalar_number (nullable) |
| `files_touched` | `int` | scalar_number |
| `loc_delta` | `LocDelta` | record |
| `loc_delta.added` | `int` | scalar_number |
| `loc_delta.removed` | `int` | scalar_number |
| `python_specific` / `python_specific.*` | `JsonMapping \| None` | unknown_open |
| `typescript_specific` / `typescript_specific.*` | dormant | unknown_open |

32 paths total. **30 statically typed (incl. flat projections), 2 unknown_open
trees.** Exception: `type_changes` is `tuple[JsonValue, ...]` so the element
shape is unknown but the container category (record_collection) is known —
`includes_*` operators can be type-checked even though element matching is
not.

### 4.4 Operator → required target categories

| operator | required observed category | required expected literal |
|---|---|---|
| `equals` / `not_equals` | any | matching scalar/collection |
| `equals_baseline` / `not_equals_baseline` | any | (no expected) |
| `unchanged` / `changed` | any | (no expected) |
| `includes_all` / `includes_any` / `excludes_all` / `subset_of` / `superset_of` | record_collection / string_collection / number_collection | non-empty list/tuple |
| `superset_of_baseline` / `no_new_items` / `no_removed_items` | record_collection / string_collection / number_collection | (no expected) |
| `less_than` / `less_than_or_equal` / `greater_than` / `greater_than_or_equal` | scalar_number (incl. nullable) | scalar number literal |
| `within_range` | scalar_number (incl. nullable) | `[number, number]` 2-tuple |
| `changed_only_in` | (P1 unsupported, current SKIPPED) | n/a |

20 operators total. **6 are category-agnostic** (equals / not_equals / their
baseline forms / unchanged / changed). **8 require a collection category.**
**5 require scalar_number.** **1 is SKIPPED** (`changed_only_in`).

### 4.5 Compile-time catch coverage estimate

Cross product of 4.2/4.3 (path categories) × 4.4 (operator-required
categories):

| Brief D1-2 (`E_OPERATOR_TARGET_MISMATCH`) — kind / operator / path-domain alignment |
|---|
| 3 evaluator emit sites (lines 255 / 287 / 309). All 3 are `(kind, operator-class, path-domain)` triples that are statically determinable: state-kind + baseline-op, delta-kind on delta-path + baseline-op, delta-kind on state-path + pure-op. **Estimate: 100% catchable in compile** by extending `compiler/path_schema.py` (or sibling validator) with an operator-vs-(kind, path-domain) matrix. |

| Brief D1-3 (`E_TYPE_MISMATCH`) — operator vs target/expected type |
|---|
| 13 operators.py emit sites: 8 collection-shape + 3 numeric (observed) + 1 numeric-pair (expected) + 1 numeric-observed-within-range + 2 catch-all `except TypeError`. Of the 11 shape mismatches: |
| **observed-side**: catchable when path category is statically known. State paths 11/13 typed, delta paths 30/32 typed → **observed-side ~95% catchable** at compile-time. The 2 unknown_open trees (`python_specific` / `typescript_specific`) plus `type_changes` element-level matches stay runtime |
| **expected-side**: literal type check — collection ops require list/tuple, numeric ops require number, `within_range` requires `[number, number]`. **100% catchable** at compile-time |
| **catch-all 2 sites**: defensive against internal raises, not user-facing. Stay runtime, mark `unknown_cause: evaluator_internal` (decided in D1-4) |

So the residual runtime UNKNOWN after C is bounded by:

```text
(a) python_specific.* / typescript_specific.* / type_changes element matches
    → unknown_cause: open_runtime
(b) path_resolver `current is None` (extractor populated parent as None)
    → unknown_cause: extraction
(c) operators.py defensive `except TypeError` catch-all
    → unknown_cause: evaluator_internal (rare, near-bug)
```

Everything else in the current ~24 emit-site catalog (`.claude/memory/2026-05-08.md`)
moves to `CompileError` under Brief D1-2 / D1-3.

### 4.6 Open implementation questions (carried to D1-2 / D1-3 briefs)

1. **Where does the matrix live?** Likely `compiler/path_schema.py` extended,
   or a sibling `compiler/operator_schema.py`. Decision deferred to D1-2.
2. **Open-region escape hatch.** When target is `python_specific.*` (any
   sub-path), should compile let *any* operator through? Probably yes — open
   region is by definition not statically typed. Document explicitly.
3. **`equals` against a record_collection observed.** `_canon` makes the set
   comparison work, but compile cannot type-check the expected literal record
   shape (it has no Match Schema for arbitrary user-provided fields). Keep
   shallow: just verify `expected` is a non-empty list when observed category
   is collection-typed.
4. **Tolerance applicability.** `tolerance` is documented as numeric-only but
   accepted on any constraint compile-side. Out of scope for this brief
   unless a low-cost compile check fits.

## 5. Brief split

```text
Brief D1-1: investigation only (this document, deliverable: tables in §4)
Brief D1-2: E_OPERATOR_TARGET_MISMATCH → compile (kind/operator/path-domain
            matrix in compiler/path_schema.py or sibling, ~3 evaluator sites
            removed, did-you-mean for operator, did-you-mean already exists
            for paths)
Brief D1-3: E_TYPE_MISMATCH expected-shape & observed-category compile checks
            (collection / numeric / within_range pair). 11 operators.py sites
            becomes runtime-unreachable for typed paths. Open regions stay
            runtime. Compile errors get fixture suite including bare-string
            desugar interaction (Match Schema)
Brief D1-4: results[].unknown_cause optional field + aggregate / repair
            emitter / SARIF / GH Actions / human / json formatter wiring.
            authoring-cause routes verdict to FAIL regardless of unknown_policy.
            Cause value space: authoring / extraction / open_runtime / evaluator_internal
Brief D3:   validate-plan envelope v1→v2. risk_summary.authoring_errors list.
            adapter rendering update (claude-code / cursor / codex):
            "fix authoring first, then implement". v2 schema doc + golden
            fixtures
```

Total estimate: 5 PRs. D1-2 / D1-3 / D1-4 / D3 are all "1 PR" sized; D1-1 is
this planning doc.

## 6. Acceptance gates (across briefs)

- 既存 `~24` runtime UNKNOWN emit のうち、**`open_runtime` / `extraction` /
  `evaluator_internal` 以外を D1-2 / D1-3 で `CompileError` に押し戻す**
- `results[].unknown_cause` は D1-4 PR から全 verdict envelope に optional 出現
- `unknown_policy` は authoring-cause では verdict 寄与しない (= 強制 fail) —
  fixture テスト 1 件以上で gate
- `validate-plan` envelope v2 で `risk_summary.authoring_errors` を提供、
  `would_violate` との分離が adapter golden fixture で観測可能
- `docs/json_schema.md` に nested optional diagnostic field の bump 例外規定
  を明記 (D1-4 同梱が自然)

## 7. Risks

- **C のスコープが広がる誘惑** — operator-vs-target type 完全推論を狙うと
  Match Schema / generic 型展開まで巻き込む。Brief は **shallow check** に
  限定し、record-collection の element 型は対象外と明文化
- **`unknown_cause` を読む下流の発生** — SARIF / GH Actions が cause を読み
  始めた瞬間、verdict envelope は実質的に bump 必要。**「最初は cause を
  surface のみ、severity / category 振り分けには使わない」** 制約を D1-4 に
  pin して、cause 依存は別 brief で明示的に flip する
- **`UNKNOWN` を書くテスト fixture が減る** — D1-2 / D1-3 で大半が CompileError
  化されるので、UNKNOWN 経路の固定 fixture が薄くなる。残った
  `path_resolver` None 経路 / `python_specific.*` 経路は **意図的 fixture を
  D1-3 PR で追加** して再現性を確保

## 8. Cross references

- `.claude/memory/2026-05-08.md` Session 2 — UNKNOWN call-site catalog
  (~24 emit sites), classification, downstream consumer trace
- `docs/code_semantic_ci_design.md` §5.4 — unknown_policy intent (extractor
  failure)
- `src/semantic_ci_code/compiler/path_schema.py` — PR #58 precedent for
  authoring → compile-time pushback
- `docs/json_schema.md` Compatibility Policy — nested optional diagnostic
  field bump exception to be added in D1-4
- `docs/cli_usage.md` — `validate-plan` section (v1→v2 documentation update
  in D3)
- `docs/brief_8_planning.md` — Brief 8 (Authoring Surface), boundary with
  this brief is pinned in §1b above (semantic hazard vs syntactic/type
  error split, INV-1 framing, ADVISORY-S1 text update follow-up)
