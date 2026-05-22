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

P2.5 完走 + ABCD-A 完走 + ABCD-B 完走 + 緊急 doc refactor 8 phase 完走
+ UGH ecosystem framing 確立 + Phase X-1 landed + X-5 PR #96 open +
**Issue #97 (`--allow-dirty` provenance bug) Phase 1 mitigation landed
(PR #98, merge `bf4af3b`) + Source-selection redesign 正式採用 (PR #99
= `docs/source_selection_planning.md` 406 lines, 3 phase × 7 lock-in,
aggressive style, Phase 2 → 3a → 3b strict order)** (2026-05-22) —
本リポジトリは **[UGH
ecosystem](https://github.com/Yuu6798/ugh-ecosystem) の code domain**
として位置づけが explicit 化された (`CLAUDE.md ## Ecosystem Context`
section、 X-5 = PR #96 で追加、 wrap-up 時点で open、 user merge
予定)。 ecosystem は 4 domain (text = `ugh-audit-core` / code = 本
repo / music = `ugh-prompt-engine` / image+video =
`svp-video-pipeline`) + UGH 理論基盤 + archived init
(`ugh3-metrics-lib`) で構成、 全 domain が共通の
5-step pattern (`Declared intent → Observed state → ΔE → Verdict →
Repair`) を実装し、 audit layer は全 domain で必ず deterministic
(Strata 区別、 LLM-assisted は image+video の generation layer に限定)。
本 repo の scope guard ("not a linter / type checker / test runner /
LLM-as-judge / intent validator / intent interpreter") は ecosystem-wide
audit-deterministic invariant (= §23.1 input neutrality) の code-domain
specialisation として再 framing された。 既存実装は Brief 1〜5 全
merged + ResultStatus split (D1-1〜D3) 全 merged + Brief 8 (Authoring
surface 設計契約 + `target-doctor` Advisor + `init --recipe --from-*`
Authoring + Provenance + canonical-form refactor + `target-catalog`
Authoring meta surface) 全 landed + doc refactor (Tier A/B/C/D 階層 +
`_index.md` 1-line 復元 + STATUS.md compaction + AGENTS.md §5 collapse
+ Forward Design Note 分離 + archive infrastructure +
`tests/discipline/` 3 test + wrap-up protocol 拡張) 全 landed。
`semantic-ci` CLI は `init` (recipe / source surface 込み) / `observe`
/ `compare` / `check` / `pre-commit` / `compile` / `compile-repair` /
`validate-plan` / `target-doctor` / `target-catalog` の **10
subcommand** を持ち、 `init --recipe` で 4 recipe (`feature:add-api`
/ `bugfix:regression-test` / `refactor:preserve-api-with-allowlist` /
`test-update:add-test-case`) と 4 source surface (`--from-pr-body` /
`--from-issue` / `--from-labels` / `--from-commits`) から target.yaml
を deterministic に生成可能。 Vibe Coding Adapter (Claude Code /
Cursor / Codex) 経由で repair guidance + pre-generation guidance を
render 可能。 UNKNOWN は (a) compile-time `CompileError` (大半の
authoring error)、 (b) runtime `unknown_cause` 4 値、 (c)
`validate-plan` の `risk_summary.authoring_errors` slot、 (d)
`target-doctor` の 6 advisory (D1/D3/D4/P1/P2/S1) で end-to-end 診断
可能。 起動時 Tier A attention budget は main 上で **~580 lines**
(X-5 = PR #96 merge 後は +24 で ~604 lines 想定、 target ≤ 800
クリア継続、 doc refactor 前 ~2,500 lines から -76% 〜 -77% 帯)、 memory
hygiene drift は `tests/discipline/` 3 test が
CI で auto-enforce (`test_status_md_phase_single_paragraph.py` /
`test_status_md_next_queue_no_completed.py` /
`test_index_md_entry_compactness.py`)。 wrap-up protocol step 8 で
`pytest tests/discipline/` を memory 直 push 前 pre-push 必須化
(PR #95、 memory exception 直 push と CI gate の structural gap
closure)。 archive infrastructure
(`.claude/memory/archive/INDEX.md` + `STATUS_MERGED_LOG.md`) +
30 日 TTL の dated log 移送 ritual が wrap-up protocol に組込済。
Next normal implementation queue: **F (source-selection redesign Phase
2 → 3a → 3b、 PR #99 lock-in に従い 3 PR 順次、 strict order)** +
Brief 7 / SSP v0.1 (CSCI-36 entry) + Phase X-3 (cross-ref embedding in
残 3 ecosystem repo、 別 Claude Code session 委譲) を 並行 thread と
して走らせる、 中長期 Phase X-2 (HA-style validation cross-domain 移植)
は ecosystem 統合の core work として queue 末尾に常駐。

## 直近 merged

### 2026-05-22 — Issue #97 (`--allow-dirty` provenance bug) Phase 1 mitigation landed (PR #98) + Source-selection redesign 正式採用 (PR #99)

`langchain-ai/langchain` への blind random sampling で発覚した
`semantic-ci check --candidate-rev <SHA> --allow-dirty` の provenance
bug を 1 day で closure し、 同 session 内で design hole を planning doc
に encode して正式採用までを 2 PR cascade で land。 `claude/repository-issue-review-BVt9Y`
branch を 2 PR で連続 reuse。

- **PR #98** (merged `bf4af3b`、 0 round):
  `fix(check): preserve explicit --candidate-rev under --allow-dirty (#97)`
  - `check.py` に `candidate_uses_working_tree = allow_dirty AND
    candidate_rev is None` derived predicate、 explicit `--candidate-rev`
    + `--allow-dirty` 同時指定で warning + ref materialize に変更
  - 2 副次 call site (cache write 抑制 / numstat range) を derived
    predicate 経由に rewire
  - `tests/architecture/test_check_provenance.py` 新設 = §23.1 CLI-layer
    mirror、 inv-1 (A==B → empty observed) / inv-2 (working-tree-only
    symbols が evidence に漏れない) を `allow_dirty ∈ {False, True}` で
    parametrize、 計 4 invariant
  - `tests/cli/test_check.py` に 2 new integration test (warning fires /
    bare `--allow-dirty` unchanged)
  - `docs/cli_usage.md` で `--allow-dirty` × `--candidate-rev` の interaction
    semantics を pin
  - CI 3/3 green (3.11 / 3.12 / 3.13)、 1284 passed (baseline 1281 + new 3)、
    ruff clean
  - PR body で "A deeper fix is deferred to a Phase 2 Task Brief" と明示
    宣言、 後続 PR #99 の前提を pin
- **PR #99** (open at session wrap-up、 docs only):
  `docs(planning): adopt source-selection redesign (Phase 2 / 3a / 3b)`
  - `docs/source_selection_planning.md` 新設 (406 lines、 12 section)
  - 7 sub-question を `§3` lock-in 表で encode、 全 sub-decision
    aggressive / clean-cut style から derive (no alias / no deprecation /
    hard delete)
  - 3 PR 構成: Phase 2 (`--candidate-source {commit, working-tree}` +
    `--allow-dirty` 削除 + JSON envelope provenance) / Phase 3a (対称
    `--baseline-source` + `staged-index` 追加 + 4 conflict rule pin +
    degenerate warning + source × source matrix docs) / Phase 3b
    (`pre-commit` subcommand 削除 + `.pre-commit-hooks.yaml` rewrite)
  - `§7 Decisions rejected / not adopted` で 4 rejected options を rationale
    付き永続化 (Phase 2.5 / `--allow-dirty` alias / `--candidate-source=auto`
    / engine-level source enum)
  - `§8 Phase ordering` で strict order を pin (Phase 3a は Phase 2 が
    main にあるまで開始不可、 Phase 3b は Phase 3a が main にあるまで
    開始不可、 published hook break 回避)
  - `§9 Required Reading` で Phase 2 brief drafter の必読 7 件を列挙
  - `§11` Phase 3b PR cross-phase acceptance criteria (grep clean /
    migration note / schema_version 維持 / `§23.1` doc 明示) を pin
  - `CLAUDE.md` Design Documents table に planning doc 行追加

**設計判断のハイライト**:

1. **「Phase 1 mitigation を land + 同 session 内で Phase 2+ redesign
   を planning doc に encode」 ritual**: PR #98 body の "deferred"
   宣言を session 内で消化、 context cohesion が高い間に rejected
   options の rationale を precise に pin。 別 session で planning
   doc を起こすより rejected options が遺漏しにくい
2. **7 sub-question を 4-style trade-off comparison で 1 turn 確定**:
   conservative / additive / symmetry-first / aggressive の 4 style
   提示 → 各 style における 7 sub-decision の derived position を
   表で展開 → user 1 turn 判断で X = aggressive 確定。 AGENTS.md
   §5.7 「AskUserQuestion N 択 trade-off 提示」 pattern を style 軸
   に応用、 個別問い 7 個を 1 メタ問いに圧縮
3. **`§7 Rejected options` を planning doc に **永続化する new pattern**:
   通常の planning doc は採用案 + 採用理由を書くが、 「却下案 + 却下
   理由」 を 4 件明示 pin することで future agent が同 trap を踏まない。
   §5.3 Three-Tier Externalization codified tier に「rejected options」
   を加える pattern
4. **`§23.1 input neutrality` を CLI redesign で reinforce**: engine
   signature `engine.check_pair(baseline_path, candidate_path, intent)`
   不変、 sourcing は CLI-layer 単独責務、 planning doc §4.4 で
   `code_semantic_ci_design.md §23.1` text に「engine は path-snapshot
   しか見ない」 を明示追記する task を Phase 2 brief に組み込み。
   半年規律の延長線上に 3 phase redesign を pin
5. **「aggressive / clean-cut」 style が repo culture と整合**: scope
   guard / §23.1 / 経験値外部化 / Tier A budget compaction、 いずれも
   「shim を増やさず削除すべきものは削除する」 規律。 PR #98 が recent
   enough で external caller pin が無いことを hard delete 採用の論拠
   として明示

**修正・訂正**:

1. **当初 4 phase 案 (Phase 2 / 2.5 / 3a / 3b) を Phase 3 に統合**:
   `--baseline-source` 単独追加 phase は同一 user-facing API axis を
   2 PR に分割するコストが merit を上回ると分析、 Phase 3a に統合
2. **JSON provenance を Phase 3a に defer する案を 当初提示**:
   X = aggressive 採用により「Phase 2 で envelope の 2 値 enum を
   land しないと Phase 1 mitigation の warning が残るだけになる」 と
   再考、 Phase 2 に前倒し
3. **PR title `(#97)` suffix**: GitHub squash merge 時の自動補完で
   issue # が PR title に紛れた、 worth noting だが behavior 上の
   問題なし。 今後 PR title に issue # を含めるかは convention 議論
   として保留

### 2026-05-21 Session 5 — UGH ecosystem framing 確立 + umbrella repo (`Yuu6798/ugh-ecosystem`) 新設 + semantic-ci-code に Ecosystem Context 追記 (Phase X-1 / X-5 landed)

Session 1〜4 で ABCD-A/B + 緊急 doc refactor を 1 日で全完走した直後の継続
session。 user 主導の壁打ち session として始まり、 半年壁打ちが
**「semantic-ci-code 単独 product 開発」 ではなく「UGH ecosystem (4 domain)
の cross-domain 並列研究 program」 だった** ことが言語化された。 user
による 4 link 連続提供 (`ugh-prompt-engine` / `svp-video-pipeline` /
`ugh-audit-core` + ecosystem 統合議論) で、 ecosystem 全貌が web fetch
経由で surface — 「Semantic CI Ecosystem」 ではなく **「UGH (Unconscious
Gravity Hypothesis) ecosystem」** が正しい brand、 4 active domain + 1
archived init (`ugh3-metrics-lib`) + theory foundation、 audit layer は全
domain で deterministic / generation layer のみ image+video で
LLM-assisted という **Strata 区別**、 text domain は HA48/HA63 (n=63)
で既に validated、 等の事実が連続 surface した。

- **`Yuu6798/ugh-ecosystem` 新設** (umbrella repo、 別 Claude Code
  session 経由で initial PR #1 を 1 round fix で merge):
  - day-1 minimum = README + LICENSE + .gitignore
  - README は 4 domain status table + 5-step design pattern + Strata
    説明 + Theory section (note.com URL は frozen、 explicit citation
    せず) + Status section + License + "research program / OSS tool
    両用" 明示
  - PR #1 review fix: code domain status を「8 CLI subcommands」 と
    誤記していたものを「ABCD-A/B complete; 10 CLI subcommands」 に修正、
    repo 名 prefix duplicate (`Yuu6798/Yuu6798-ugh-ecosystem-repo`) を
    `Yuu6798/ugh-ecosystem` に rename
  - brief 設計 → 別 session 実装 → 1 round review → merge を 1 日以内
    closure、 後続 X-3 に再利用可能な reference workflow が成立
- **PR #96** (本 repo、 `claude/semantic-ci-discussion-Y3rob` branch、
  Claude 直接実装、 session 終了時 open):
  - `CLAUDE.md` 冒頭に `## Ecosystem Context` (+24 lines) 挿入
  - 本 repo を ecosystem の code domain として位置付け、 5-step pattern
    と 4 概念対応 (`target.yaml` / `CodeState` / constraint evaluator /
    `RepairPlan`) を明示、 既存 Scope guard を ecosystem-wide audit-
    deterministic invariant の specialisation として再 framing、 他 3
    domain repo へ soft link
  - Tier A attention budget: 580 → 604 lines、 依然 800 target 内
  - 規模が極小 (+24 lines) なので AGENTS.md §5.2 体制別 envelope の
    「Claude alone = 半日以下なら 0 round 可」 範囲内、 と framing で
    AGENTS.md split を一時的に直接実装に振った
- **Phase X 設計**: 旧 framing「semantic-ci-code 単独 external 配布」
  を廃止、 新 framing「UGH ecosystem formalization」 を採用。 X-1
  (umbrella repo) + X-5 (CLAUDE.md ecosystem context) が本 session で
  landed、 X-2 (HA-style validation cross-domain 移植) は中長期 phase
  として queue 末尾常駐、 X-3 (他 3 ecosystem repo に cross-ref
  embedding) は別 Claude Code session 委譲予定、 X-1 続き (umbrella
  docs/ 拡張 = vocabulary.md / strata.md / roadmap.md / theory.md 等)
  も中長期で別 session

**設計判断のハイライト**:

1. **Brand 確定 = UGH ecosystem**: 「Semantic CI Ecosystem」 は session
   序盤の framing 慣性、 user 自身も「セマンティック CI エコシステム」
   と呼んでいたが、 ugh-audit-core README に「UGHer ecosystem」 表記が
   既存、 UGH 理論 (note.com) が基盤、 ecosystem name = UGH ecosystem
   / 内部の design pattern 名 = semantic CI / semantic audit、 と整理
2. **Strata 区別が ecosystem 規律として明示化**: 「LLM を core に
   入れない」 半年規律の真の payoff は単独 repo の品質 rule ではなく、
   **LLM 生成 (Strata B) を別 strata に押し出して deterministic
   auditor identity を保つ ecosystem 規律の code domain 実装** だった、
   と本 session で初めて articulate
3. **umbrella creation workflow の reference 化**: brief 設計 → 別
   Claude Code session 実装 → PR review → 1 round fix → merge を 1
   日以内 closure、 ecosystem cross-repo 作業を AGENTS.md split 体制下で
   回す workflow として後続 X-3 で再利用可能
4. **「公開歴史の開始」 + 「umbrella repo の役割」 を比喩 + OSS 事例
   で user に説明**: tag の social commitment、 PyPI 再 upload 不可、
   docs-only repo の 4 役割、 図書館 catalog / 親会社 site / シリーズ
   概要パンフ比喩、 Kubernetes / OpenTelemetry / Rust の事例。 user の
   素朴疑問が深堀り trigger として機能した
5. **「N=0 ecosystem-wide」 framing の誤り発覚**: text domain
   (ugh-audit-core) は HA48/HA63 で validated、 ecosystem 全体としては
   partial validation phase。 「N=0 → N=1」 ではなく「text domain で確立
   した HA-style validation を 他 3 domain に展開」 が正しい problem
   定義、 Phase X-2 の core work として queue 化
6. **AskUserQuestion 不使用で 1-2 paragraph opinionated 提示 → user
   即決サイクル**: trade-off N 択 table + 私の position + 1 turn で
   user 判断、 の loop が再現性高く機能。 「Claude 直接実装か」 等の
   体制判断も即決された

**修正・訂正**:

1. **「Semantic CI Ecosystem」 呼称を私が複数 turn 維持していた誤り** —
   user 自身も session 序盤の framing 慣性に乗っていた、 と pinpoint
2. **「ecosystem 全体が N=0」 framing の誤り** — text domain は既に
   validated、 と user 提供 link で発覚
3. **「modality 拡張は Brief 6 規模の数ヶ月 work」 評価の誤り** — 実は
   既に 3 modality (music PoC + image+video experimental) で実装済み
4. **PR #1 review で agent が code domain status を「8 subcommands」 と
   誤記** — agent が `STATUS.md` を読まずに repo top README 判断、
   後続 X-3 brief で「`STATUS.md` (or equivalent) mandatory read source」
   を明示する discipline 必要、 と pin

### 2026-05-21 Session 3 — 緊急 doc refactor 8 phase 1 日完走 + framework 自己 refactor dogfood

Session 2 末尾の user 「doc 膨張で agent noise が増える懸念」 提起から
即時 reality check + 定量化 (起動時 attention budget ~2,500 lines、
target 800 を大幅超過) → `docs/doc_refactor_planning.md` 起草 (PR #88) →
**同日中に 8 phase 全完走**。 Codex 利用可 + Claude 単独並列の最大効率
運用で **9 PR landed + 4 direct push** (memory exception)。 framework
自身が自分自身を refactor する self-referential dogfood が成立。

- **PR #87** R17: target-doctor `--package-root` repo-root parity (PR #87、
  PR review monitoring + merge)
- **PR #88** `docs/doc_refactor_planning.md` 新設 (緊急 plan、 8 phase
  spec + 9 bloat source + sequencing + risk mitigation +
  self-referential note)
- **PR #89** Phase 0: CLAUDE.md `Required Reading` を Tier A/B/C/D 4
  階層に再構成 + 800 line budget pin
- **PR #90** Phase 3: AGENTS.md §5 を 8 sub-section → 6 sub-section に
  collapse (209 → 88 lines)、 Practice + Anti-Pattern + Enforcement を
  3 列 table に統合、 Phase 6 marker 設置
- **PR #91** Phase 4: AGENTS.md Forward Design Note (220 lines) を
  `docs/ssp_protocol_design_note.md` (新 doc 253 lines) に分離、 AGENTS.md
  に pointer 1 段落のみ残置 (425 → 218 lines、 -60%)
- **PR #92** Phase 7: CLAUDE.md `終了時ルール (自動トリガー)` を 3-step
  → 7-step + Anti-pattern list + Archive policy TTL table に拡張。
  Codex bot review 2 round 連続 P2 消化 (R1 = step 4/5 順序 race の sweep
  before compaction 修正 commit `75244c7`、 R2 = multi-line inline code
  span が CommonMark spec で space に正規化される rendering bug 3 箇所を
  単一行化 commit `f78d111`)
- **PR #93** Phase 6: `tests/discipline/` 新設 + 3 test
  (`test_status_md_phase_single_paragraph.py` /
  `test_status_md_next_queue_no_completed.py` /
  `test_index_md_entry_compactness.py`) を Codex implementation。 doc rule
  単独依存を構造的に脱却、 CI で memory hygiene drift を auto-enforce
- **PR #94** Phase 5: `.claude/memory/archive/INDEX.md` 新設 + TTL contract
  pin。 実 file 移送は 2026-06-01 以降の TTL-driven ritual に発火 (今日
  時点最古 dated log = 5/2 = 19 日経過、 30 日 TTL 未達)
- direct push (memory exception):
  - `bf8ce8f` ADVISORY-S1 stale entry 削除 (実は 5/15 commit `854a528` で
    既に landing 済の発見)
  - `3be25d4` Session 2 wrap-up + CLAUDE.md / AGENTS.md §5 (Experience
    Externalization Discipline) 永続化
  - `4783728` Phase 2: `_index.md` 53,953 → 5,251 bytes (**-90%**)、 essay
    化 cell を 1-line index 本来仕様に復元、 27 entry の時系列正規化
  - `0db925f` Phase 1: STATUS.md 831 → 505 lines、 `## 直近 merged` 古い
    10 entry を archive 移送 + `次の発行順序` §A/§B 完走 entry 削除

**累計効果**: 起動時 Tier A attention budget が **~2,500 lines → ~580
lines (-77%)** に圧縮、 target ≤ 800 を大幅クリア。 情報損失ゼロ (全
archive 移送 + dated session log は原文保存)。

**設計判断のハイライト**:

1. **bloat 懸念に対する即時 reality check + 定量化** — 「気をつけます」
   ではなく現状の line count を提示、 problem の規模を共有してから
   planning doc を起こす流れが速かった
2. **8 phase の sequencing を ROI 順に設計** — Phase 0 → 2 → 1 を
   連続実行で 1,340 lines 削減を最初に achieve、 target 達成見込みを
   user 確信させてから後続 phase へ
3. **Codex / Claude 体制別運用最適化** — Phase 6 (`tests/discipline/`
   実装) を Codex 利用可日に最大効率で発注、 残 phase は Claude 単独で
   並列実行。 Phase 4 を Phase 3 branch から chain することで merge
   conflict を構造的回避
4. **Codex review P2 を framework self-test として framing** — PR #92
   R1 / R2 は新 wrap-up protocol の logical / physical correctness を
   bot が catch、 規律自体の自己検証の成功例
5. **self-referential dogfood の意図的設置** — planning doc に「完了後は
   本 doc を archive/ 移送 (self-referential dogfood example)」 を明記
6. **discipline test 3 件 が CI auto-enforce 化** — doc rule 単独依存を
   構造的に脱却、 次 session 以降の memory hygiene drift が CI fail で
   即検出される状態に到達

**修正・訂正**:

1. **PR #92 R1** (step order race): 順序を sweep → compaction に swap
2. **PR #92 R2** (multi-line inline code span): 3 箇所を単一行化
3. **Phase 5 acceptance** の 30 日 TTL 事前条件不成立 → infrastructure
   設置のみ landed として planning doc 追記

### 2026-05-21 Session 2 — R17 (target-doctor `--package-root` parity) landed (PR #87) + 経験値外部化 framework 永続化

Session 1 (CSCI-44) 完了直後の継続 session。 当初プランの Brief 7 (CSCI-36)
entry に対して user の判断で先に **A 軸 follow-up = ADVISORY-S1 narrow**
を確認 → 既に 2026-05-15 commit `854a528` で landing 済と判明、 STATUS.md
の stale entry 削除のみ (commit `bf8ce8f` direct main) で 5 分 closure。
続いて **R17 deferred** (target-doctor `--package-root` resolve を
`check` と同じ repo-root 相対に揃える consistency 改善) の brief 起草 →
Codex paste → PR #87 → 0 round merge を達成。

- **PR #87** (`fix(target-doctor): resolve --package-root against repo
  root (parity with check)`、 merge `469385e`):
  - `target_doctor.py:_resolve_package_root` を repo-root aware 版に置換
    (+31/-1): absolute reject / `..` escape reject / `repo_root(Path.cwd())`
    with cwd fallback / `is_relative_to` symlink defense の 4 layer
  - `tests/cli/test_target_doctor.py` (+218/-1): 6 tests 追加 (subdir
    parity / `.` parity / D4 filter parity / abs reject / parent escape /
    git unavailable fallback) + bonus symlink reject (Windows skip)
  - STATUS.md (+7/-8): R17 deferred 3 sites を完走表記に書換 (Codex 側で
    自発的更新、 brief Scope IN に明示した効果)
  - CI 3/3 green (3.11 / 3.12 / 3.13)、 local 1269 passed (1261 baseline
    + 8 new、 0 regression)、 ruff check / format 両 pass

**経験値外部化 framework 永続化**: PR #82 (16 round) / #84 (13 round) /
#85 (0 round) / #86 (0 round) / #87 (0 round) の empirical envelope を
data 表として整理、 「29 round 累計 P2 を `test_canonical.py` 48 cases +
`tests/architecture/` 16 tests に encode した結果として後続 0 round 達成」
の因果を言語化。 **CLAUDE.md** に Experience Externalization (経験値の
外部化) section 軽 (~25 lines、 principle 1 paragraph + 4 item bullet +
AGENTS.md pointer)、 **AGENTS.md** § 5. Experience Externalization
Discipline substantial (~180 lines、 8 sub-section: 5.1 Principle / 5.2
Empirical Envelope / 5.3 Three-Tier Externalization (codified / repo-
specific / session-tacit) / 5.4 Round Count as Leading Quality Indicator /
5.5 体制別 envelope / 5.6 Maintenance Practice 7 rule / 5.7
Anti-Patterns 7 件 / 5.8 Cross-Reference) を追記、 新 brief 起草前 / 新
architectural pattern 導入前の必読 doc に位置付け。

**設計判断のハイライト**:

1. **「経験値の外部化」 を AI 開発 discipline 規律として明示化** —
   Claude long-term memory 不在制約が **強制的 externalization discipline**
   として逆説的に働く framing を §5.1 で言語化、 「ベテランの暗黙知」 が
   AI 開発では機能しないという principle を policy doc 化
2. **Review round 数を leading quality indicator として運用** — §5.4 で
   0 / 1-3 / 5-10 / 10+ の round 数解釈表を pin、 「同じ trap は二度発生
   させない」 ための encoding work を 5+ round 時に必須化
3. **体制別 envelope を §5.5 で明示** — split (Codex=impl) で 1 日規模
   0 round / Claude alone で半日以下 0 round / Claude exception で 1 日
   規模は 13+ round chase、 の経験的 envelope を data 付きで pin。
   「Codex が intrinsically 速い」 framing を回避、 「規律 infrastructure
   揃った状態の split 運用」 が正しい framing
4. **Maintenance Practice 7 rule (§5.6) + Anti-Patterns 7 件 (§5.7)** —
   memory log skip 禁止 / §15 checklist 強制 / prefix match 自動 cover
   保持 / round trail を必ず docs/test に encode / dogfood fail+pass 両方
   / Claude exception scope ≤ 半日 / STATUS.md 次の発行順序 即時更新 等、
   実証済 operational rule を逐語化
5. **本 session 自体が経験値外部化 discipline の自己言及的実演** —
   反省会で気付いた pattern を即座に CLAUDE.md / AGENTS.md に encode
   する loop が、 言語化した規律の自己適用例として記録に値する。 §5
   全 sub-section が本 session 中に書かれた事実は、 discipline の
   reusability を即時実証している

**修正・訂正**:

1. **A 軸 follow-up「残」 表記が stale** (実体は 2026-05-15 完了済) —
   brief 起草前の事前確認で発覚、 5 分で stale 削除 closure (commit
   `bf8ce8f`)。 §5.7 Anti-Patterns #7 「STATUS.md `次の発行順序` 更新を
   後で先送り」 として明示化、 maintenance practice の重要性を再確認

### 2026-05-21 Session 1 — Brief 8 / CSCI-44 (`semantic-ci target-catalog`) landed

CSCI-44 closes the final Brief 8 implementation piece. `semantic-ci
target-catalog` renders a machine-readable (`schema_version:
catalog-1`) and human-readable authoring catalog derived directly from
runtime registries (`path_schema`, `type_schema`, `match_schema`,
`TEMPLATE_CONSTRAINTS`, `Operator`). Brief 8 is complete; the normal
next queue returns to Brief 7 / SSP v0.1 unless a smaller follow-up is
explicitly chosen.

---

### 古い merged entry (2026-05-19 以前) — archive 参照

13 entry (2026-05-19 / 2026-05-15 Session 4 + Session 3 + Session 2 /
2026-05-14-15 ResultStatus split / 2026-05-12 / 2026-05-09 /
2026-05-08 S1+S2 / 2026-05-07 S1+S4+S5 / 2026-05-05) は
`.claude/memory/archive/STATUS_MERGED_LOG.md` に移送済。 詳細参照時は
当該 archive file + 該当 dated session log
(`.claude/memory/YYYY-MM-DD.md`) を参照。 Phase 1 (initial cutoff、
`docs/doc_refactor_planning.md`) + 2026-05-21 S3 wrap-up (5/15 S3 移送)
+ 2026-05-21 S5 wrap-up (5/15 S4 移送) + 2026-05-22 wrap-up (5/19 移送)
で compaction が実施された。

## 次の発行順序

ABCD-A (ResultStatus split) + ABCD-B (Brief 8 / CSCI-41〜44 + canonical
refactor) 完走済 + UGH ecosystem framing 確立 (2026-05-21 Session 5) +
Phase X-1 / X-5 landed + **Issue #97 Phase 1 mitigation landed
(PR #98) + Source-selection redesign 採用 (PR #99 = `docs/source_selection_planning.md`)** (2026-05-22)。
active queue は **C (Brief 7 SSP) + D (P2 残課題) + E (Phase X 残) +
F (source-selection redesign Phase 2 → 3a → 3b)** の 4 軸。 ABCD 完走
で product 機能の ship-blocking gap が消え (`2026-05-12.md` 参照)、
Phase X で ecosystem-level formalization、 F で CLI source-selection
hole の構造的閉鎖を進める。

旧 §A / §B (完走 entry) は CLAUDE.md rule 「closed CSCI は 次の発行順序
から remove」 に従い削除済。 詳細参照は `## 直近 merged` (最新 5) +
`.claude/memory/archive/STATUS_MERGED_LOG.md` (古い entry) + dated session
log (`.claude/memory/YYYY-MM-DD.md`)。

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

### E. Phase X(UGH ecosystem formalization、 2026-05-21 Session 5 起草、 残 3 sub-phase)

`docs/code_semantic_ci_design.md` の Phase plan 上は post-ABCD =
external readiness、 2026-05-21 Session 5 で **「外部配布 mechanism」
ではなく「UGH ecosystem formalization」** が正しい framing と確定。
全 sub-phase は本 repo (code domain) 単独では完結せず、 ecosystem
4 repo (umbrella + text + code + music + image+video) を跨ぐ作業。

- **E-1. Phase X-3. Cross-ref embedding in 残 3 ecosystem repo**:
  `ugh-audit-core` / `ugh-prompt-engine` / `svp-video-pipeline` の
  README または `CLAUDE.md` 冒頭に `## Ecosystem Context` section を
  挿入 (本 session の PR #96 を template として再利用)。 各 repo の
  GitHub MCP scope 外なので **別 Claude Code session 委譲**。 brief
  起草時の必須注意点 = 「`STATUS.md` (or equivalent) を mandatory
  read source として明示」 (umbrella PR #1 review で発覚した「repo
  top README のみ参照で誤記」 failure mode の回避)
- **E-2. Phase X-1 続き. Umbrella `docs/` 拡張**:
  `Yuu6798/ugh-ecosystem` repo に `docs/vocabulary.md` (4 domain
  vocabulary 統一表) / `docs/strata.md` (deterministic audit vs
  LLM-assisted generation の architectural separation) /
  `docs/roadmap.md` (Phase X 全体地図) / `docs/theory.md` (UGH 理論、
  public 公開戦略 frozen のため初版 minimal) を順次追加。 これも
  GitHub MCP scope 外なので別 session
- **E-3. Phase X-2. HA-style validation cross-domain 移植** (中長期 phase):
  text domain (`ugh-audit-core`) の HA48/HA63 (n=63) validation pattern
  を code / music / image+video の 3 domain に展開する **ecosystem 統合
  の core work**。 着手前に `ugh-audit-core/docs/validation.md` を確認
  して dataset 構造を理解、 その後 code domain 版 = 公開 LLM 生成 PR
  を N=48 集めて semantic-ci verdict と reviewer 判断の Spearman ρ を
  計算する experiment plan を起草する。 完走 criteria は「各 domain で
  N≥48 の external validation 蓄積」、 期間は数週間〜数ヶ月

### F. Source-selection redesign(planning merged 2026-05-22 PR #99、 implementation 3 PR、 strict order)

`docs/source_selection_planning.md` (X = aggressive / clean-cut style、
7 sub-decision lock-in)。 順序: Phase 2 → 3a → 3b、 **strict order**
(Phase 3a は Phase 2 が main にあるまで開始不可、 Phase 3b は Phase 3a
が main にあるまで開始不可、 published `.pre-commit-hooks.yaml` break
回避)。

- **F-1. Phase 2. `--candidate-source` + `--allow-dirty` 削除 + JSON
  provenance**(~120 LOC + ~30 LOC envelope + ~40 doc + 5 test): `check`
  に `--candidate-source {commit, working-tree}` 追加 (default `commit`)、
  `--allow-dirty` を hard delete、 envelope に
  `engine.{baseline,candidate}.{source,rev}` 追加 + `schema_version`
  minor bump、 conflict (`working-tree` + explicit `--candidate-rev`) は
  usage error exit 2。 起草時 `docs/source_selection_planning.md §9
  Required Reading` 7 件遵守 + `§3` lock-in + `§4` Phase 2 scope を逐語
  引用、 §7 rejected options 4 件を self-check
- **F-2. Phase 3a. 対称 `--baseline-source` + `staged-index`**(~150 LOC +
  ~60 doc + 10 test): `--baseline-source {commit, working-tree, staged-index}`
  追加、 `--candidate-source` enum に `staged-index` 追加、 4 conflict
  permutation 全 usage error exit 2、 degenerate (両側同 volatile source) は
  warning + verdict 続行、 default rev pin (`staged-index` 候補 → baseline
  default = HEAD commit)、 `cli_usage.md` に source × source matrix、
  `code_semantic_ci_design.md §23.2` Application Matrix refresh。 起草は
  Phase 2 が main 上にあるまで保留
- **F-3. Phase 3b. `pre-commit` subcommand 削除 + migration**(~50 LOC
  mostly deletions + ~30 doc + 2 test): `pre-commit` subcommand 削除、
  `.pre-commit-hooks.yaml` を `check --candidate-source=staged-index` に
  rewrite、 README / `cli_usage.md` / `exit_codes.md` / `json_schema.md` /
  `code_semantic_ci_design.md` から `pre-commit` 言及削除 + migration note
  追加。 Phase 3b PR で planning doc §11 cross-phase acceptance criteria
  (grep clean / `§23.1` doc 明示 / migration note 等 8 件) を verify。
  起草は Phase 3a が main 上にあるまで保留

### Sequencing decisions

- **A (ResultStatus split) 完走**: 2026-05-14/15 で 4 PR (#76 / #77 / #78 /
  #79) 一気通貫マージ、 Brief 8 vs ResultStatus split の着地順序は事後的に
  「ResultStatus split 先 → Brief 8」 で確定
- **Brief 8 vs Brief 7**: Brief 8 先(`brief_8_planning.md §12.3` 確定)
- **D は B/C と独立**: いつ挟んでも良い、 ただし P3a (Action 配布) を狙う
  なら D-3 hash trail が前提
- **E (Phase X) は C/D と並行 thread**: 2026-05-21 Session 5 で確定。
  C/D は規定路線で本 repo 単独消化、 E-1 (X-3) と E-2 (X-1 続き) は
  ecosystem cross-repo work で別 Claude Code session 委譲、 E-3 (X-2
  validation 移植) は中長期 phase で C/D 完走後でも構わない
- **E-3 (HA-style validation 移植) の前提**: text domain (`ugh-audit-core`)
  の HA48/HA63 dataset 構造の確認、 これは brief 起草前に `validation.md`
  + `HA48_validation_results` 等を web fetch で読み込む必要
- **F (source-selection redesign) は C/D/E と独立**: いつ挟んでも良い、
  ただし F-1 → F-2 → F-3 の strict order は厳守 (planning doc §8)。
  `pre-commit` subcommand を使う external user が main を track している
  場合 Phase 3b 単独 land で hook が break するため Phase 3a 必須先行
- **F の規模**: 全 3 PR 合計で ~320 LOC + ~130 doc + 17 test、 1 PR 平均
  ~100 LOC で経験値外部化 envelope (AGENTS.md §5.2) 上 1 day 完走可能枠
  内、 split / Claude alone どちらでも妥当

### 直近最短経路

- **PR #96 review / merge** (本 session で open、 ~24 lines docs only、
  AC 8 件全 check で「Ecosystem Context section が code domain
  framing を明示」 した状態。 user review 後 merge することで Phase X-5
  が完走)
- **PR #99 review / merge** (2026-05-22 wrap-up 時点 open、 docs only
  ~406 lines、 lock-in style 承認が acceptance core。 merge することで
  Phase F = source-selection redesign が正式採用 = Phase 2 brief 起草の
  starting gun)
- **F-1. Phase 2 Task Brief 起草** (PR #99 merge 後の最初の next normal
  implementation entry): `docs/source_selection_planning.md §3 lock-in` +
  `§4 Phase 2 scope` を逐語引用、 `§9 Required Reading` 7 件遵守
  (planning doc / `§23.1` / PR #98 / `cli_usage.md` / `json_schema.md` /
  AGENTS.md §5.6+§5.7 / brief drafting checklist)、 `§7 rejected options
  4 件` を brief 起草中 self-check
- **E-1. Phase X-3. Cross-ref embedding in 残 3 ecosystem repo の brief
  設計 + 別 session 委譲** (2026-05-21 Session 5 で確定、 PR #96 の
  `## Ecosystem Context` を template として再利用、 `STATUS.md` mandatory
  read source 明示で「8 subcommand」 誤記 failure mode 回避)
- **C-1. CSCI-36. Brief 7 / SSP v0.1 spec**: 規定路線 next normal
  implementation entry (F-1 と並行発行可、 docs only / Claude 単独可)。
  `docs/ssp_protocol.md` v0.1 spec 新設 (500-700 行)、 ecosystem context
  landed 後の起草なので「これは UGH ecosystem の code domain における
  security audit という second design pattern 拡張」 と framing 可能。
  起草時必読:
  1. `AGENTS.md` Forward Design Note: Brief 7 / SSP v0.1 (canonical spec)
  2. `docs/brief_7_planning.md §11` 着手 checklist
  3. **`AGENTS.md` § 5 Experience Externalization Discipline** (2026-05-21
     Session 2 新設、 brief 起草前の必読 doc、 §5.6 Maintenance Practice
     7 rule + §5.7 Anti-Patterns 7 件を逐語適用)
  4. `.claude/memory/STATUS.md` 直近 3 entries + `_index.md` 直近 5
     summary
  5. **`CLAUDE.md` `## Ecosystem Context`** (Session 5 で追加、 brief
     framing に ecosystem 視点を反映するため)
- SSP tracking GitHub issue 起票 (Issue #48 close 後の受け皿、
  `brief_7_planning.md §11` で text template 固定済)

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
- **post-ABCD: 外部 readiness phase**(2026-05-21 Session 5 で **Phase X
  = UGH ecosystem formalization** として明示化済、 §E 参照): 当初
  framing「配布チャネル (GitHub Action / PyPI / semver 1.0) + onboarding
  (Quickstart / 比較 positioning / example gallery) + community
  (CONTRIBUTING / SECURITY / issue template) + 外部 user feedback loop」
  は **「semantic-ci-code 単独 external 配布」 を前提とした古い framing**。
  Session 5 で「半年壁打ちは UGH ecosystem 4 domain の並列研究 program
  だった」 と reveal され、 配布 mechanism は二次的・ecosystem formalization
  が一次的と再 framing。 配布チャネル開通 (PyPI / Action / pre-commit) は
  技術的に半日 task で、 Phase X-2 (cross-domain validation) で empirical
  evidence が揃った後の post-X phase に位置付ける
