# STATUS.md `## 直近 merged` archive

このファイルは `.claude/memory/STATUS.md` `## 直近 merged` セクションから
移送された **古い merged entry** の保管庫。 最新 5 entry のみ STATUS.md に
inline、 それ以前は本 archive を参照する。 archive 移送は
`docs/doc_refactor_planning.md` Phase 1 で 2026-05-21 に確立、 以降の
session wrap-up で 5 entry 超過分が同 archive に随時追記される。

エントリは新しい順 (移送 cutoff 時点で最新 → 末尾)。

---

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

