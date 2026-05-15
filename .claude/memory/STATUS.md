# Project Status (live tracker)

This file is the live, daily-changing snapshot of the project: current phase,
recent merged PRs, and the next-issue queue. It moved out of `CLAUDE.md` so
the policy doc can stay stable while this file changes freely.

Update rules:

- This file is part of `.claude/memory/` and may be edited directly on `main`
  under the same exception as `_index.md` (see `CLAUDE.md` § Session Memory →
  Git Workflow の例外).
- After each merged PR or session wrap-up, refresh **直近 merged** and
  **次の発行順序** here, and append a 1-line entry to `_index.md`.
- Other docs that need to point at the live tracker should reference
  `.claude/memory/STATUS.md` 次の発行順序 (not `CLAUDE.md`).
- If a CSCI / Brief / D# item is closed, leave it in 直近 merged for the
  current phase, and remove the corresponding entry from 次の発行順序.

For the canonical phase definitions, the Brief-by-Brief plan, and the design
spec, see `docs/code_semantic_ci_design.md` §12 / §25. For the per-session
historical record, see `_index.md` and `YYYY-MM-DD.md`.

---

## Phase

P2.5 完走 + ABCD-A 完走 + ABCD-B 着手 (CSCI-41 + CSCI-43 landed) — Brief 1〜5
全 merged + ResultStatus split (D1-1〜D3) 全 merged + Brief 8 入口 (Authoring
surface 設計契約 + `target-doctor` Advisor surface) merged。 `semantic-ci`
CLI は `init` / `observe` / `compare` / `check` / `pre-commit` / `compile` /
`compile-repair` / `validate-plan` / `target-doctor` の 9 subcommand を持ち、
Vibe Coding Adapter(Claude Code / Cursor / Codex)経由で repair guidance +
pre-generation guidance を render 可能。 UNKNOWN は (a) compile-time
`CompileError` (大半の authoring error)、 (b) runtime `unknown_cause` 4 値、
(c) `validate-plan` の `risk_summary.authoring_errors` slot、 (d)
`target-doctor` の 6 advisory (D1/D3/D4/P1/P2/S1) で end-to-end 診断可能。
Authoring surface (target.yaml 生成経路 / surface isolation / Advisor
renderer exempt / `candidate_code_used: false` 固定) は
`docs/target_authoring_surface.md` で設計契約済。

## 直近 merged

### 2026-05-15 Session 3 — Brief 8 / CSCI-43 (`semantic-ci target-doctor` Advisor surface) landed

B 軸 (Brief 8) 実装 1 本目 = 推奨着地順 41 → **43** → 42 → 44 の 2 番目消化。
docs only の CSCI-41 (Session 2) を実装に展開し、 6 advisory (D1/D3/D4/P1/P2/S1)
を verdict 不参加で検出する `target-doctor` subcommand を landed。

- **PR #82** (CSCI-43, `feat(brief-8): land CSCI-43 — semantic-ci target-doctor
  (Advisor surface)`): `cli/commands/target_doctor.py` + `authoring/hazards.py`
  + `authoring/advisory.py` + `cli/output/doctor_human.py` /
  `doctor_json.py` 新設、 `tests/architecture/test_surface_isolation.py` で
  INV-2 (verdict-bearing module = `check` / `compare` / `pre_commit` + engine
  の transitive imports に doctor module が混入しない) + INV-4 (CLI dispatcher
  例外を main.py に narrow) を gate。 schemas/doctor_advisory.schema.json で
  envelope を `schema_version="advisory-1"` で固定、 exit code は §6.3.3 規約
  (advisory ≥ 0 でも 0、 入力エラー 2、 engine エラー 3、 unhandled 4)。
  **Codex bot review 16 round 全部 P2 消化** (本体 1 commit + 16 fix commit、
  merge `66b6fc2`):
  - R1: SKIPPED-by-design operator 経由の D4 misclassification → 418cef0 で
    `_evaluator_skipped_baseline` フィルタを D4 入力に直結
  - R2: `not_equals(non-empty)` を addition と誤検知して P1/P2 を握り潰し →
    bd38702 で `not_equals` を `expected=={empty}` のみ addition 扱いに narrow
  - R3: zero-magnitude `not_equals` / `lock` を P1/P2 addition と誤検知 →
    0928f63 で「非 info + 非 empty addition」 の論理積で P1/P2 を gate
  - R4-R6: `equals_baseline` / `subset_of` / rename `old_path` の D4 分類
    取りこぼし → c06c0fa / 2f36864 / 14df79c で順次 fix
  - R7: `severity: info` constraint を D4 lock-only 判定に混ぜると vacuous
    addition と区別不能 → de2fb90 で info constraint 除外
  - R8: dict-nested expected の意味的等価重複が D3 で抜け → 1bf6c97 で
    nested expected を canonicalize してから duplicate check
  - R9: `unknown_policy in {fail, repair}` 起因の info constraint が
    S1 評価 + D4 lock-only 評価で扱い不一致 → c197bac で `_is_lock_only_user_constraint`
    に unknown-routing 例外を追加
  - R10-R12: zero-shape / partial-dict expected を lock-only と誤分類して D4
    suppression が false-negative 化 → b41f6de / e040f83 / e190f2f で 3 段階に
    narrow (vacuous predicate → zero-delta scalar lock → delta observation 限定)
  - R13-R14: `--package-root` 配下外の path / open path を D1 / D4 で
    扱い間違え → e190f2f / 673f5e4 で path scope を package-root に narrow + open
    paths を D4 lock-only から除外、 P1 を semantic surface に narrow
  - R15: leaf target が collection lock-only と誤分類されて D4 false negative
    → 6394a14 で leaf target requirement を追加
  - R16: D4 numstat が repo 全体を走査して package-root 外を含む → 11b7893 で
    numstat を `--package-root` slice に restrict
  - R17 (post-merge): `--package-root .` resolve が cwd vs `check` の
    repo-root で divergence → **deferred follow-up** (subdirectory 起動時のみ
    表面化、 critical でない UX consistency 改善、 別 PR 候補)
  - CI: 3.11 / 3.12 / 3.13 全 green、 **pytest 1072 passed** (+66 new test
    = 53 CLI doctor + 7 architecture + 6 D4 git integration)、 ruff check /
    ruff format ✅

**設計判断のハイライト**:

1. **INV-2 architecture test を実装より先に書く** — Session 2 メモで「surface
   boundary を docs に書く前に既存実装の boundary 仕様を inventory する」
   pattern を pin したのが効いた。 `tests/architecture/test_surface_isolation.py`
   を最初に書いて verdict-bearing module 群の transitive imports を closure
   で固定すると、 `target-doctor` 実装中の incidental import が即 fail で
   検出され、 Advisor renderer exempt の boundary を実装側で逐語固定できる
2. **「lock-only と vacuous-pass」 の境界が D4 false-negative の主因** —
   R10〜R12 の 3 round で「lock-only に見える predicate が delta observation
   起因なら vacuous でない」 / 「zero-magnitude が必ずしも lock とは限らない」
   / 「partial-dict expected は subset 評価で意味を持つ」 という 3 重 narrow が
   必要だった。 D4 brief を起草する時点で「lock vs vacuous」 の inviolate
   definition を §6.3.1 に書ききれていなかった反省、 CSCI-42 brief 起草時に
   先に「authoring 生成経路における lock vs vacuous の境界」 を design.md
   §23.3.1 でカバーすべきか確認
3. **16 round 全部 P2 = 仕様 vs 実装の boundary が曖昧** — operator semantics /
   severity / SKIPPED / git / scalar / path domain / source filter のそれぞれで
   「target-doctor 実装が boundary を 1 mm 越えていた」 が累積、 Brief 8 §6.3.1
   の advisory spec が「inviolate predicate」 形式で書かれていなかったため
   実装が連続的に推測した結果。 CSCI-42 / CSCI-44 brief では「advisory 1 つ
   ごとに inviolate predicate 1 行」 + 「false negative の境界 fixture を AC で
   要求」 する pattern を継承

### 2026-05-15 Session 2 — Brief 8 / CSCI-41 (Authoring Surface 設計契約) landed

A 軸 (ResultStatus split) 完走後の同日 Session 2 で B 軸 (Brief 8) 入口の
CSCI-41 を docs only セッションで landed。 推奨着地順 41 → 43 → 42 → 44
(`docs/brief_8_planning.md §12.3`) の 1 つ目消化。

- **PR #81** (CSCI-41, `docs(brief-8): land Authoring Surface design contract`):
  `docs/target_authoring_surface.md` 新設で 6 点 (A〜F) 明記 — A. hand-written
  必須でない / B. 生成経路 3 通り (recipe + sources / catalog 参照 /
  hand-written) / C. LLM 経路は Brief 8b 分離 / D. 全経路は verdict 前 freeze /
  E. Authoring・Advisor・Provenance surface は evaluator 不可参照 (INV-2)、
  ただし Advisor renderer は generation_metadata を intentionally render
  (INV-1 exception) / F. candidate-derived 非実装、 generator paths のみ
  `candidate_code_used: false` 固定。 連動 cross-ref 7 file:
  `code_semantic_ci_design.md §23.3.1` 表 + §24 ACTIVE + §25 Brief 表に
  Brief 8 行 / `target_yaml_guide.md` 冒頭 pin + Hazard 1〜3 章末
  target-doctor cross-ref + D5 stale 訂正 / `cli_usage.md` "Authoring
  subcommands (verdict 不参加)" 節 (heading + cross-ref のみ) /
  `exit_codes.md` target-doctor 規約 / `json_schema.md` advisory-1 /
  catalog-1 envelope / `CLAUDE.md` docs table + `README.md`。 Codex bot
  review 3 round 全部 P2 を消化:
  - Round 1: cli_usage.md scope creep (4 subcommand bullet 先取りで parser
    drift) → trim commit `4167f3b` で heading + cross-ref + forward pointer
    のみに narrow
  - Round 2: Section F 内部矛盾 (`every Brief 8 authoring path records
    candidate_code_used: false` が plain `init` の TARGET_TEMPLATE
    byte-invariant と衝突) → narrow commit `2995f7c` で `generation_metadata`
    populate を generator paths 限定、 plain init / hand-written は block
    自体 absent と pin
  - Round 3: Section E import isolation contradiction (`compile-repair` を
    verdict-bearing 側に分類してしまい、 `repair_compiler/adapters/*` の
    `format_generation_metadata` 既存仕様と衝突) → exemption commit
    `8b24249` で Advisor renderer (`compile-repair` / `validate-plan` /
    `repair_compiler/`) を INV-2 適用外と明記、 brief_8_planning §5.2 INV-1
    exception を逐語 cross-ref
  - 4 commits (`ec5f72c` / `4167f3b` / `2995f7c` / `8b24249`) merged in
    `288eb39`、 1006 passed (3.11 / 3.12 / 3.13 全 green)

**設計判断のハイライト**:

1. **brief_8_planning.md の docs table 追加見送り** — user 指示
   「不必要ならテキストをいろんなところに置きたくない」 に従い、
   `brief_8_planning.md` の CLAUDE.md docs table / README / design.md §24
   登録は STATUS.md でカバー済として skip。 当初撤回した judgment が
   user の方針と一致した
2. **AC 「のみ」 制約の遵守** — CSCI-41 §6.1 AC が cli_usage.md について
   「節見出しと §23.3.1 cross-ref **のみ**」 と書いていたのを当初 4
   subcommand bullet で先取りしてしまい、 セルフレビュー + Codex review
   両方で同じ scope creep を指摘される結果に。 AC「のみ」 は逐語に従う
   方が Codex review の round 数を減らす経験則を再確認
3. **Codex 3 round の本質** — 「surface boundary を doc に書くなら、 既存
   実装の boundary 仕様 (`format_generation_metadata` / TARGET_TEMPLATE
   逐語維持) と矛盾しないか implementer 視点で audit する」 必要性。
   PR #78 (5/15 D1-4) の 3 round と同様、 inviolate definition (今回は
   「verdict-bearing」 vs 「Advisor renderer」 の boundary) に立ち戻ると
   3 round 全部が一貫した narrowing に収束

### 2026-05-14/15 — ResultStatus split 完走 (4 PR 一気通貫)

A (ResultStatus split) を planning §3 D1〜D3 の全 brief で main landed。
UNKNOWN は (a) compile-time `CompileError` (大半の authoring error)、
(b) runtime `unknown_cause` 4 値 (authoring 残置 / extraction / open_runtime /
evaluator_internal)、 (c) author-facing `risk_summary.authoring_errors` slot
で end-to-end 診断可能。

- **PR #76** (D1-2, `compile(operator-schema): push E_OPERATOR_TARGET_MISMATCH
  to compile time`): `compiler/operator_schema.py` 新設、 (kind, operator-class,
  path-domain) 3 ルール違反を `CompileError` reject。 evaluator 3 emit site は
  defense-in-depth として残置 + コメント追記。 self-review で `CHANGED` hint
  asymmetry + site 1/3 defense test を follow-up commit で同 PR 内消化、
  16 + 2 件のテスト追加。 994 passed
- **PR #77** (D1-3, `compile(type-schema): push E_TYPE_MISMATCH to compile
  time`): `compiler/type_schema.py` 新設、 `TargetCategory` 9 値 enum +
  Pydantic 反射ベース path → category map (lru_cache)、 observed-category +
  expected-shape の 2 軸検証。 operators.py 11 emit site は defense-in-depth、
  2 catch-all は runtime safety net (D1-4 で EVALUATOR_INTERNAL 付与)。 81 件
  のテスト追加、 既存テスト 3 件を valid combination に更新。 CI で
  `ruff format --check` が失敗 → follow-up commit で format 適用。 975 passed
- **PR #78** (D1-4, `evaluator(unknown-cause): wire diagnostic cause + force
  authoring fail`): `UnknownCause` StrEnum (4 値) を evaluator に追加、
  `ConstraintResult.unknown_cause: UnknownCause | None`、 `OperatorOutcome`
  経由で operators.py から `_from_operator_outcome` 境界で enum 変換
  (compiler/evaluator 循環回避)。 `_aggregate` で AUTHORING 強制 FAIL
  (planning §3 D2)、 `_category_or_none` で `RepairCategory.FIX_REQUIRED`
  強制。 JSON / SARIF / GH Actions / human formatter + repair serialization に
  surface。 verdict envelope schema_version 据え置き ("nested optional
  diagnostic field" 例外規定を `docs/json_schema.md` に新設)。 Codex review
  3 round 全部 P2 design soundness を消化:
  - Round 1: open path で `_unknown_type_mismatch` 経由 authoring が
    `unknown_policy: warn` を握り潰す → `_from_operator_outcome` 境界で
    open target + authoring → OPEN_RUNTIME 再分類
  - Round 2: `_resolved_unknown_cause` が schema-invalid subpath を
    EXTRACTION で握り潰す → 3-way 分類 (open / schema-valid → EXTRACTION /
    schema-invalid → AUTHORING) に拡張
  - Round 3: D1-3 が UNKNOWN_OPEN で expected-side も bypass する → D1-3 の
    `check_type_compatibility` を「observed-side は target category 依存」
    「expected-side は literal-shape 単独」 に split、 expected 側は無条件実行
  - 1006 passed
- **PR #79** (D3, `validate-plan(authoring-errors): split risk_summary into
  authoring + impl slots`): `risk_summary.authoring_errors` を `would_violate`
  と分離、 `RISK_SUMMARY_KEYS` の先頭に配置。 `compute_risk_summary` を
  single-evaluation refactor、 verdict から authoring_errors + would_violate を
  同時計算。 3 adapter (claude-code / cursor / codex) に 2-step
  implementation order intro + AUTHORING ERRORS section。 validate-plan
  envelope schema_version `"1" → "2"` bump、 6 golden fixture refresh、
  `docs/json_schema.md` に validate-plan v1→v2 diff 節 + version history row。
  1006 passed

**設計判断のハイライト**:

1. **UnknownCause の置き場所** — result-side 概念なので `evaluator.evaluator`
   に enum 定義 (`framework` ではなく)。 operators.py からは string で渡し、
   `_from_operator_outcome` 境界で enum 変換 (compiler→evaluator 循環回避)。
   同じ理由で `_BASELINE_OPERATORS` / `_PURE_OPERATORS` は
   `compiler.operator_schema` に duplicated、 sync invariant test で gate
2. **D4 envelope bump policy の 2 ケース** — `results[].unknown_cause` は
   nested optional diagnostic field (bump 不要、 `docs/json_schema.md` の
   "Nested optional diagnostic fields" 例外規定)、 D3 の
   `risk_summary.authoring_errors` は depth-1 top-level (bump 該当)。
   ResultStatus split 全体で envelope bump 1 回 (validate-plan v1→v2) に収束
3. **3 round Codex review に共通する設計の本質** — 「authoring vs runtime
   cause の境界が曖昧」 という設計問題。 「authoring = compile が押し戻せ
   なかった spec malformed」 という inviolate definition に立ち戻れば 3 round
   全部が一貫した実装に収束 (`_from_operator_outcome` retag / 3-way
   `_resolved_unknown_cause` / D1-3 observed-vs-expected split)。 design spec
   の境界判定を実装側で 3 段階に精緻化した経過は `2026-05-15.md` に永続化

### 2026-05-12 — ResultStatus split planning 取り込み + ABCD 完成度境界の確認

- **PR #74** (`docs(planning): land ResultStatus split planning + pin Brief 8
  boundary`、 merge commit `9679a9b`): 5/9 branch 残置の `19e47bd`
  (`docs/brief_resultstatus_planning.md`) を main 取り込み。 取り込み際の
  audit で Brief 8 (Authoring Surface、 PR #73) が 5/9 以降に landed して
  おり working title 衝突 + 設計射程 overlap を発見、 §1b "Boundary with
  Brief 8" 4 節を新設してから取り込み: §1b.1 error class boundary 表
  (semantic hazard = Advisor / syntactic-type = Validator) / §1b.2 INV-1
  framing (D2 は malformed-input domain 縮小、 INV-1 は well-formed input
  domain 要求) / §1b.3 ADVISORY-S1 文言更新 follow-up を D1-4 PR で call out
  / §1b.4 着地順序 open question。 同 PR で CLAUDE.md docs table + README
  Planning (open) + design.md §24 PLANNING に planning doc 登録。 main 直
  push は server 403 で denied、 user 「PR 可」 で経路切替。 後半で
  **ABCD 完成度境界の確認**: post-ABCD で「product 機能 ship-blocking gap
  は消える」 / 「外部 readiness (配布 + 文書 + community) は別軸」 という
  分離 framing で、 半年強の壁打ちが ABCD という形に蒸留された節目を言語化
- **(参考) PR #73** (`docs/brief_8_planning.md` 新設、 2026-05-09 後半に
  merge): Brief 8 (Authoring Surface) planning。 4 CSCI 分割 (CSCI-41 docs
  / CSCI-43 `target-doctor` / CSCI-42 `init --recipe` / CSCI-44
  `target-catalog`)、 推奨着地順 41 → 43 → 42 → 44、 §12.3 で Brief 7 (SSP)
  より先発行を確定。 5/10 / 5/11 は本リポジトリで session 不在、 本 STATUS
  refresh 時に soak inventory として確認

### 2026-05-09 — 緊急 perf brief 2 連続 + ResultStatus split planning + Brief D1-2 起草

- **PR #70** (D2-1, `perf(tests): switch tests/cli to in-process invocation`):
  test 全体 wallclock 98s → 24.5s(Linux ローカル -75%、 CI 1 job 180s → 90s)。
  `tests/cli/helpers.py::run_semantic_ci` を default で in-process `cli.main(...)`
  に切替、 subprocess は PYTHONHASHSEED determinism / console-script entrypoint /
  cache-hit sentinels / smoke benchmark のみに残置。
  `test_smoke_is_faster_than_full` を `@pytest.mark.slow` で default 除外。
  Codex review iterate で hash_seed 引数の silent ignore に対して `raise TypeError`
  で loud 化する fixup commit `356106b` が同 PR 内 landing
- **PR #71** (D2-2, `perf(tests): reuse git templates and migrate verdict-shape
  tests off check`): `tests/cli/conftest.py` で session-scoped template repo を
  3 種(full / short / topic_only)1 回だけ build、 各 test は `clone_template_repo`
  で `shutil.copytree`(Windows 優先) / `git clone --local --no-hardlinks`(POSIX)
  で複製。 `init_repo` 系 3 関数の signature 不変、 lazy resolver で legacy fallback。
  verdict-shape 系 6 件を `check` → `compare` 経由に migration、 cache-hit sentinels
  を sitecustomize subprocess → in-process monkeypatch 化。 Windows local
  264.92s → 181.61s (-31.4%)、 brief target <150s 未達も実用閾値クリア。
  Claude review で指摘した P1-1 (determinism test の `--mode smoke --no-fetch`
  取り消し) + P2 (`test_missing_package_root_exits_usage_error` の `check` 経路復元)
  は user merge 前に Codex / user が fixup commit `7a20f20 test(cli): preserve
  full determinism coverage` で消化、 D2-2 follow-up brief 不要
- **planning + brief 起草(branch `claude/daily-tasks-cbQj7` 残置)**:
  `docs/brief_resultstatus_planning.md` (commit `19e47bd`) で ResultStatus
  authoring/extraction split を **C+B 仮固定**(C = authoring を compile-time に
  押し戻し / B = `results[].unknown_cause` sibling field、 A = enum 拡張は不採用)+
  D2 (authoring policy 非尊重) / D3 (validate-plan v2 で `risk_summary.authoring_errors`
  分離) / D4 (verdict / compile envelope は据え置き、 nested optional bump 例外規定)
  を pin。 5 PR 分割(D1-1 / D1-2 / D1-3 / D1-4 / D3)、 静的型カテゴリ + operator
  行列を planning §4 に表化。 main 未反映、 次セッション (Brief D1-2 投入時) に
  cherry-pick / 直 commit / 別 PR のいずれかで取り込み

### 2026-05-08 Session 2 — target.yaml authoring guide 新設

- **PR #69** (`docs/target_yaml_guide.md` 新設): docs only セッションで
  `docs/target_yaml_guide.md` を新規作成、2026-05-07 Session 4 dogfood で抽出された
  D1/D3/D4 (`--package-root` scope 制約 / template と user constraint の重複 /
  config-only PR の vacuous PASS) を authoring hazard 章として集約。CLAUDE.md
  docs table + design.md §24 ACTIVE 仕様一覧 + README documentation 一覧を追従、
  §23.3 boundary を冒頭 reminder に pin、§4 / §13 / cli_usage.md /
  dogfooding_TC10_report.md への cross-ref を整備。 Codex bot review 3 round
  消化(`primary_kind` 表 / D4 overstate / §23.3 例の差し替え)、`次の発行順序`
  から A' (authoring guide) を削除

### 2026-05-08 Session 1 — D5 解消 + Brief 5 sweep tail + D2 解消

- **PR #65** (CSCI-35c / set operator partial-match semantics): D5 = FINDING-1
  解消。`framework/match_schema.py` 新設で `api_surface` / `effects` / `imports`
  系 dict-collection target に **Match Schema**(`required_key` /
  `optional_keys` / `forbidden_keys`)を導入、`includes_all` / `includes_any` /
  `excludes_all` / `subset_of` / `superset_of` を partial-record match に切替、
  `excludes_all` violation で `evidence.matched` `{expected_item,
  observed_record}` pair を report。bare-string desugar(`"pkg.foo"` →
  `{fqn: "pkg.foo"}`)+ 平坦投影 alias(`api_surface_delta.added.fqns` 等
  3 個)+ compile-time validation(`signature` / `confidence` / `evidence` /
  `symbols` を forbidden、unknown key did-you-mean、空 `excludes_all` /
  `includes_any` を reject)。verdict / compile JSON envelope を
  `schema_version="4"` → `"5"` bump。merge 過程で 5 件の follow-up fix
  (`acfc03e` partial-match key presence / `3b047b2` follow-ups /
  `d83f365` changed API key / `783afa3` evidence pair JSON / `5eb7526`
  removed_public schema)を取り込み、false-negative CI bypass を closure
- **PR #66** (CSCI-35d / Brief 5 sweep tail): CSCI-35b sweep 残 2 件を 1 PR で
  消化 — (a) `compile_target_svp` YAML round-trip コメント拡張(なぜ engine
  normalization parity のために round-trip が必要かを implementer 向けに pin)、
  (b) Claude Code adapter の `Forbidden Zones` / `Required Additions` を
  `render_risk_section_structured` で human-friendly な numbered nested bullet
  に切替(Cursor / Codex は据え置き、§21.3 adapter divergence の許容範囲)。
  Cursor 移行 + 旧 flat 形式 docs 更新は follow-up
- **PR #67** (CSCI-35e / extractor exclude 機構、D2 解消):
  `pyproject.toml` の `[tool.semantic_ci_code.extract] exclude = [...]` を
  `framework/extract_config.py` で load し、`observe` / `compare` / `check` /
  `pre-commit` / `validate-plan` baseline 抽出経路で AST parse 前に filter。
  matcher は stdlib `fnmatch` のみ(リテラル / 末尾 `/**` / `**/basename`
  略記 / 同 segment 数 path glob)、`..` / 絶対 path / backslash / 不明 key
  は engine error。cache key に `effective_exclude` 軸追加、baseline /
  candidate 独立 config load。`compile` / `compile-repair` / `init` は本
  config を load しない。merge 過程で 2 件の follow-up(`24225e1`
  docs(cache 無効化 + deep-recursion glob 制約 docs 明記) / `2fa07f6`
  config search を tree root 境界で打ち切る fix)を取り込み

### 2026-05-07 Session 5 — TC10 dogfooding + D5 tracking

- **PR #61** (dogfooding TC10): 仮想 Python パッケージ 10 ケースで `compare` /
  `validate-plan` / `compile-repair` を end-to-end 検証(全 verdict + exit code
  契約通り)。FINDING-2(`equals_baseline` violation で `_equals_baseline`
  ヘルパ追加し structured `added`/`removed` を populate)+ FINDING-3
  (`compile-repair` 入力 `schema_version` 不一致時の stderr warning)を本 PR
  で fix、`docs/dogfooding_TC10_report.md` 新設
- **PR #62** (D5 tracking): FINDING-1(set operator partial-dict mismatch、
  未解決)を Session 4 D1〜D4 計画に **D5** として統合、本 STATUS § 次の
  発行順序 §F + `docs/dogfooding_TC10_report.md` Tracking section に追記

### 2026-05-07 Session 4 — dogfood-driven hardening

- **PR #58** (compiler/path_schema): compile-time path 検証 + did-you-mean
  提案、`docs/code_semantic_ci_design.md §4.5` typo 訂正
  (`api_surface.public_symbols` → `api_surface_public`、`new_test_cases` →
  `new_cases`)、constraint kind 別 path domain(state vs delta 非対称)、
  Codex 3 round 消化
- **PR #59** (cli): `check.py` / `pre_commit.py` の `_resolve_package_root` に
  `is_relative_to` symlink escape ガード(`validate_plan` 既存パターンを 3
  surface 対称化)→ **CSCI-35b sweep #3 完了**
- **PR #60** (ci): 依存上限ピン × 5(`pydantic<3.0` 等)+ `[tool.coverage.*]`
  設定 fail_under=70(branch coverage 73% 実測、~3pp margin)+
  `pip-audit --strict .` プロジェクト射程化(env-level CVE 汚染遮断)+ 凍結
  dep test 8 ファイル更新

### 2026-05-07 Session 1 — Brief 5 / P2.5 完走

- **Brief 5 entry** (CSCI-31 / PR #52): Repair Compiler core + Adapter Protocol
  + registry + Claude Code adapter
- **CSCI-32** (PR #53): Cursor adapter(`.mdc` frontmatter + body)
- **CSCI-33** (PR #54): Codex adapter(ASCII-safe plain text + 角括弧 section
  ラベル)
- **CSCI-34** (PR #55): `compile-repair` subcommand + `RepairPlan` JSON
  deserializer + verdict envelope auto-detect
- **CSCI-35** (PR #56): `validate-plan` subcommand + `risk_summary` 4 要素計算
  (`would_violate` / `forbidden_zones` / `required_additions` /
  `template_implications`)+ Adapter Protocol を明示引数版に切替
- **Brief 5 完了宣言** (PR #57): CLAUDE.md / brief_5_planning.md / memory を
  P2.5 完走に揃え

### 2026-05-05

- **Brief 4b** (CSCI-28 / PR #40): SARIF + GH Actions annotation + pre-commit
  manifest 同梱
- **Brief 4c** (CSCI-29 / PR #42): effects extractor `fqn` を callee →
  enclosing function に修正(設計 §3.1 適合)
- **Brief 4d** (CSCI-30 / PR #43): `semantic-ci init` + spec authorship
  anchoring + hard/soft/info severity routing
- **Brief 5 planning** (PR #44): `docs/archive/brief_5_planning.md` 起草

## 次の発行順序

P2.5 完走 + A (ResultStatus split) 完走 + B-1 (CSCI-41) + B-2 (CSCI-43) 完走で
ABCD-A 軸 landed + ABCD-B 軸 2/4 landed。 残り B-3〜B-4 (Brief 8 implementation
2 PR) / C (Brief 7 SSP) / D (P2 残課題)。 ABCD 完走で product 機能の
ship-blocking gap が消える(`2026-05-12.md` 参照)。

### A. ResultStatus split — **完走 (2026-05-14/15)**

D1-1 (planning PR #74) → D1-2 (PR #76) → D1-3 (PR #77) → D1-4 (PR #78) →
D3 (PR #79) すべて main landed。 詳細は本ファイル 直近 merged §
2026-05-14/15 参照。 follow-up:

- **CSCI-43 起草時必読**: planning §1b.3 が D1-4 PR description で約束した
  Brief 8 `ADVISORY-S1` 文言更新の one-liner (D1-4 で authoring-cause UNKNOWN
  が unknown_policy 非尊重になったため S1 の scope を `extraction-cause +
  open_runtime` に narrow)

### B. Brief 8(Authoring Surface、 planning merged 2026-05-09 PR #73、 implementation 4 PR、 2/4 landed)

推奨着地順 41 → 43 → 42 → 44(`docs/brief_8_planning.md §12.2`)。

- **B-1. CSCI-41. 設計文書追記**(docs only): **完走 (2026-05-15 Session 2、
  PR #81)**。 `docs/target_authoring_surface.md` 新設 + 連動 cross-ref 7 file。
  Codex 3 round 消化(scope creep / Section F 内部矛盾 / Section E import
  isolation contradiction)。 詳細は本ファイル 直近 merged § 2026-05-15
  Session 2 参照
- **B-2. CSCI-43. `semantic-ci target-doctor`**: **完走 (2026-05-15 Session 3、
  PR #82)**。 6 advisory (D1/D3/D4/P1/P2/S1) 検出、 verdict 不参加、
  `tests/architecture/test_surface_isolation.py` で INV-2 (verdict-bearing
  module = check / compare / pre_commit + engine) + INV-4 (CLI dispatcher
  例外を main.py に narrow) を gate。 Codex 16 round 全部 P2 消化、 R17
  (`--package-root .` cwd vs repo-root divergence) は deferred follow-up。
  詳細は本ファイル 直近 merged § 2026-05-15 Session 3 参照。 follow-up:
  - **A 軸 follow-up 残**: `docs/brief_8_planning.md §6.3.1` line 435 の
    `ADVISORY-S1` 文言を「extraction-cause + open_runtime UNKNOWN のみ
    `unknown_policy` 経由 verdict 影響」 に narrow する one-liner (D1-4 で
    authoring-cause UNKNOWN は `unknown_policy` 非尊重で常時 FAIL となった
    ため)。 docs only、 別 PR で landing 想定
  - **R17 deferred**: target-doctor の `--package-root` resolve を `check` と
    同じ repo-relative に揃える consistency 改善 (subdirectory 起動時のみ
    表面化、 critical でない UX 改善)
- **B-3. CSCI-42. `semantic-ci init --recipe --from-*`**: PR body / labels /
  commits / issue から target.yaml 生成 + `authorship.generation_metadata`
  自動記録。 brief 未起草。 起草時必読: `docs/target_authoring_surface.md`
  Section F (`generation_metadata` populate は generator paths 限定、 plain
  init は TARGET_TEMPLATE 逐語維持で block 自体 absent、
  `candidate_code_used: false` 固定)。 加えて CSCI-43 で得た知見 (advisory
  1 つごとに inviolate predicate 1 行で書く / false negative 境界 fixture を
  AC で要求) を継承
- **B-4. CSCI-44. `semantic-ci target-catalog`**: 全 operator / template /
  match schema を機械可読 + human で出力(AI assistant / IDE 拡張用)。
  brief 未起草

### C. Brief 7(SSP v0.1、 planning merged 2026-05-06 PR #50、 implementation 5 PR)

順序: CSCI-36 → 37 → (38 ∥ 39) → 40(`docs/brief_7_planning.md §6`)。
Brief 8 §12.3 で **Brief 8 を Brief 7 より先発行**確定。

- **C-1. CSCI-36. `docs/ssp_protocol.md` v0.1 spec**(docs only、 500-700 行):
  起草時 `docs/brief_7_planning.md §11` checklist + AGENTS.md `Forward Design
  Note: Brief 7 / SSP v0.1` を逐語参照
- **C-2. CSCI-37. envelope schema + delta engine core**: Pydantic model + JSON
  Schema + 5 要素 fingerprint
- **C-3. CSCI-38. SemgrepAdapter** (SAST): AST-aware fp + audit 5 落とし穴回帰
- **C-4. CSCI-39. pip-audit Adapter** (SCA): lockfile parser + advisory db hash
- **C-5. CSCI-40. `semantic-ci ssp` subcommand 群**: ssp-to-sarif 変換 + e2e

### D. P2 残課題(planning なし、 brief 化が必要、 3 件)

`design.md §25` P2 Brief 群:

- **D-1. Lock violation 即 fail**(§8.2 / Brief 3 #8): `lock` operator
  完全実装の一部として violation 検出と同時に hard fail
- **D-2. Performance budget per-extractor timeout**(§18 / Brief 3 #5):
  巨大 repo の extractor runaway 保護、 incremental extraction の foundation
- **D-3. Hash trail per-extractor version**(§10 / Brief 3 #9 残部):
  P3a empirical alignment の reproducibility 担保(同 input → 同 output を
  semantic-ci version またぎで保証)

### Sequencing decisions

- **A (ResultStatus split) 完走**: 2026-05-14/15 で 4 PR (#76 / #77 / #78 /
  #79) 一気通貫マージ、 Brief 8 vs ResultStatus split の着地順序は事後的に
  「ResultStatus split 先 → Brief 8」 で確定
- **Brief 8 vs Brief 7**: Brief 8 先(`brief_8_planning.md §12.3` 確定)
- **D は B/C と独立**: いつ挟んでも良い、 ただし P3a (Action 配布) を狙う
  なら D-3 hash trail が前提

### 直近最短経路

- **CSCI-42 起草**(Brief 8 / `init --recipe --from-*`、 推奨着地順 §12.2 で
  CSCI-43 の次) — PR body / labels / commits / issue から target.yaml 生成 +
  `authorship.generation_metadata` 自動記録。 起草時必読:
  1. `docs/brief_8_planning.md §6.2` (`init --recipe` spec、 AC、 file 一覧、
     exit code 規約) + §14 起草 checklist
  2. `docs/target_authoring_surface.md` Section F (`generation_metadata`
     populate は generator paths 限定、 plain init は TARGET_TEMPLATE 逐語維持で
     block 自体 absent、 `candidate_code_used: false` 固定) を逐語反映
  3. CSCI-43 で得た 16 round Codex review の教訓: (a) advisory / generator
     仕様は「inviolate predicate 1 行」 形式で AC に明記、 (b) false negative
     境界 fixture を AC で要求 (今回は「generation_metadata が plain init で
     populate されない」 / 「recipe 経由で空配列を生成しない」)、 (c) INV-2
     surface isolation test を実装より先に書いて Advisor renderer exempt の
     boundary を `tests/architecture/test_surface_isolation.py` に閉包追加
  4. **A 軸 follow-up 残**: `docs/brief_8_planning.md §6.3.1` line 435 の
     `ADVISORY-S1` 文言 narrow (docs only、 CSCI-42 とは別 PR で landing)。
     PR が並走する場合は CSCI-42 branch では §6.3.1 を編集しない

## Frozen / Deferred

- **Brief 6 凍結**: TypeScript extractor は P3 以降に後倒し(2026-05-06
  Session 2 で確定、`docs/code_semantic_ci_design.md §12 P3b` 参照)。費用
  対効果を再評価してから解凍判断
- **Brief 8+ deferred**: spec quality metrics(§19)/ suite packaging(§20)/
  override 機構(Brief 3 #3)/ Round-trip log(§10.3 / Brief 3 #10)/
  orchestrator 観測応用 / Brief 6 解凍判断
- **D2-3. `pytest-xdist` 並列化**(deferred): D2-2 で Windows wallclock
  264.92s → 181.61s (-31.4%) で <150s 未達も実用閾値クリア。 ROI 低、 別日に
  取って単独完結が筋。 必要性は user 判断
- **post-ABCD: 外部 readiness phase**(planning なし): 配布チャネル
  (GitHub Action / PyPI / semver 1.0)+ onboarding (Quickstart / 比較
  positioning / example gallery)+ community (CONTRIBUTING / SECURITY /
  issue template)+ 外部 user feedback loop。 `2026-05-12.md` で「OSS 全体
  ~50%、 ABCD では埋まらない別軸」 として framing、 ABCD 完走後に Phase X
  として明示化を検討
