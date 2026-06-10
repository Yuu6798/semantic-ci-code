# Project Status (live tracker)

This file is the live, daily-changing snapshot of the project: current phase,
recent merged PRs, and the next-issue queue. It moved out of `CLAUDE.md` so
the policy doc can stay stable while this file changes freely.

Update rules:

- This file is part of `.claude/memory/` and may be edited directly on `main`
  under the same exception as `_index.md` (see `CLAUDE.md` § Session Memory,
  Git exception).
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

Brief 1〜8 + Brief 7 (SSP v0.1) + ResultStatus split + source-selection + doc refactor + **Phase G (SSP core integration、CSCI-45〜49) 全完走** + **Phase H (LLM security scout layer、CSCI-50〜54) 全完走** (2026-06-09〜06-10、PR #142〜#144 + #146〜#148)。Phase H は「LLM は scout であって judge ではない」(D1) を中心に、非決定論 LLM センサーを Phase G の sensor 機構へ **advisory-only** (verdict / exit code 非参与、不変条件 test 固定) で縦接続: H-1 = LLM advisory finding protocol + verdict reject guard / H-2a = `CodeStateDelta.renames` overlay / H-2b = `sensor/advisory.py` deterministic one-run re-projection (baseline `CodeState` のみ ingest、D7 recall-first fallback) / H-3 = Codex Security fixture-mode reference adapter (live LLM 経路なし、no-network architecture test) / H-4 = `check --advisory-sensor` + `--advisory-mutes` (Q3 = 別ファイル ledger、`AdvisoryMute` は llm category 専用で `Suppression` と別物、envelope に additive `advisory` object) / H-5 = `aggregate_advisory_states` 明示クロスモデル集約 (Q4 = (a) 束ね役関数、固定 `llm-ensemble` 名義 + member provenance 外出し) + `docs/llm_scout_usage.md` 昇格経路 doc (D8 沈黙=容認)。並行して 2026-06-08 に pre-release credibility トラック (PR #136/#138 + repo desc/topics) 完走、tag は切らず experimental 明示の方針。次は **D-class closure (D6/D7/D8、ROADMAP v0.1.0 exit criteria 前進)** / **Phase X (ecosystem cross-repo、別 session 委譲)** / H-5 review 申し送り 3 件 (P3) のいずれか。

## 直近 merged

### 2026-06-10 — セキュリティ hardening 緊急パッチ (PR #149、Fable タスク能力判定兼ねる)

repo 全体のセキュリティ診断 (脅威モデル = CI で動く本ツールが信頼できない入力・git ref
を処理する際の攻撃) から、防御強化 2 件を緊急パッチとして Claude exception で実装。
診断結果は High/Critical なし (eval/pickle なし・yaml.safe_load 全箇所・list-arg
subprocess・sha256 cache key)、検出は defense-in-depth レベルのみ。

- **PR #149**: (1) git ref argument-injection ガード = `ensure_safe_ref()` を
  全 chokepoint (`ref_exists`/`tree_object_id`/`resolve_baseline`/`resolve_candidate`/
  `materialize_ref`/`check._resolve_baseline_ref`) に挿入、空文字 or `-` 始まり ref
  (例 `--upload-pack=...`) を subprocess 起動前に拒否。`GitRefError(ValueError,
  GitError)` の二重継承で check/observe=exit2・target-doctor=exit3 の既存 routing
  を不変保持。(2) `pull_request_target` 不変条件 (PR checkout 禁止 / `${{ }}` の run
  補間禁止 / read-only 権限) を workflow コメント + `tests/discipline/
  test_workflow_pull_request_target.py` で構造 enforce。
- **review/CI**: Codex P2 1 件 (空 `--candidate-rev=` が truthiness で HEAD silent
  fallback → `is not None` 化で修正) を消化。CI 失敗 1 件 (test の絶対 import
  `tests.cli` が bare pytest で `No module named 'tests'` → 相対 import に修正)。
  最終 1717 test 緑で merge。SECURITY.md 新設は scope 拡大ゆえ見送り (脅威モデルは
  test に encode)。

### 2026-06-10 — Phase H H-5: クロスモデル明示集約 + 昇格経路 doc で Phase H 完走 (PR #148)

H-5/CSCI-54 を 1 PR で landing。**Phase H (CSCI-50〜54) 全完走**。

- **PR #148**: `sensor/adapters/llm/aggregate.py` =
  `aggregate_advisory_states(states) -> LLMEnsembleAggregation`。Q4 = (a)
  明示的束ね役関数で確定: 異 sensor_id の同一 anchor finding を固定名義
  `llm-ensemble` で再射影・dedup (severity は max / message は member 正規順の
  最初の non-empty、D7 recall-first)、member provenance は `SensorState` の
  **外** (`members`) に保持 (`_validate_state_invariants` の key=sensor_id 制約
  により同一 adapter 複数 payload は 1 state に同居不可、という実装制約からの
  必然形)。部分失敗は complete 続行 + members に status 保持、全滅のみ error。
  CLI は複数 `--advisory-sensor` 解禁 (単一指定の envelope は byte 不変
  regression 付き)、`advisory.members[]` は additive (schema_version "6"
  据え置き)。`docs/llm_scout_usage.md` 新設 (ACTIVE): 昇格経路 (scout →
  authoring freeze → 決定論的制約化、沈黙=容認 D8) / finding class →
  G-5 security recipe 対応表 / mutes vs suppressions 対比 / ensemble 時の
  mute key 注意。
- **review**: AC 14 件全充足で chat 内 APPROVE、P3 観測 3 件を申し送り化
  (非 LLM 入力の silent skip → ValueError 化案 / severity と message の出所
  member 分離 / ensemble の scouted = dedup 後件数の doc 化)。

### 2026-06-10 — Phase H H-4: advisory surface + mute ledger + check CLI 配線 (PR #147)

H-4/CSCI-53 を 1 PR で landing。LLM scout 出力が初めて CLI から見える形に。

- **PR #147**: `check --advisory-sensor codex-security=<recorded.json>` (単一回
  のみ、複数回は H-5 scope の usage error) + `--advisory-mutes <yaml>` (明示
  flag のみ、auto-discovery なし)。pipeline = recorded payload → H-3 adapter →
  `compute_advisory_reprojection` (check 既算の baseline CodeState +
  `delta.renames` 再利用) → active mute filter → envelope 追加 top-level
  `advisory` object (adapter_id / sensor provenance / surfaced / pre_existing /
  muted / counts / mutes_path、schema_version "6" 据え置きの additive)。
  `sensor/mutes.py` = `AdvisoryMute` + `load_advisory_mutes` (llm category 9
  要素 identity 専用 — 既存 `Suppression` は sast/sca のみ受理のため新設、
  verdict 非参照)。AC11 不変条件 (advisory あり/なしで verdict / repair_plan /
  summary + exit code 一致、strict-repair 込み) + suite 隔離拡張
  (`sensor.mutes` 追加) を test 固定。
- **設計判断**: Q3 (ledger 置き場) = 別ファイル `.semantic-ci/advisory_mutes.yaml`
  で確定 (declared intent と既読メモの構造分離)。informed-consent (D9) は
  counts (scouted/surfaced/pre_existing/muted) + muted audit 記録で realize、
  finding 単位の「宣言」マッチングは H-5 送り。
- **申し送り回収**: H-2b/H-3 の silent-pass→usage-error
  (`--sensor-candidate` に LLM finding 入り SensorState → exit 2) を
  `docs/exit_codes.md` Error Streams 表に doc 化。
- **review**: AC 15 件全充足で chat 内 APPROVE、cosmetic P2 件のみ
  (error message の "later H-4 slice" 表現 / 未消費 tuple 要素)。

### 2026-06-10 — Phase H H-3: Codex Security reference adapter (PR #146)

H-3/CSCI-52 を 1 PR で landing。LLM-general Adapter Protocol の first concrete。

- **PR #146**: `sensor/adapters/llm/codex_security.py` = fixture-mode ingest
  adapter (`codex-security`)。recorded envelope (sensor_version / model_id /
  prompt_hash / status / error_message / findings) → `RawLLMFinding` 経由パース →
  共有 `project_to_canonical` で射影 (独自 identity 組み立て禁止を test で grep
  固定) → advisory-only `SensorState`。model_id / prompt_hash 欠落は status を
  問わず ValueError (fail-closed)、non-complete payload は findings 空 +
  error_message 必須 (semgrep adapter ミラー)。ordinal は group 内出現順
  auto-assign + 明示値尊重 + 重複 reject。no-network/subprocess architecture
  test (`tests/architecture/test_llm_adapter_no_network.py`) で fixture-only
  実行経路を構造化。export は `sensor/adapters/llm/__init__.py` のみ。
- **brief 設計判断**: live LLM 呼び出しは in-repo 経路に置かない (CLAUDE.md
  no-LLM/no-network 規約、D1 on-demand は「呼ばれない限り走らない」構造で充足)。
- **review**: AC 10 件全充足で chat 内 APPROVE、P3 指摘 2 件 (dummy CodeState の
  型 narrow / 混在 ordinal) は follow-up commit で消化済 (`75c8d24` / `1a232f5`)。

### 2026-06-09 (Session 2) — CLAUDE.md 圧縮 + 300 行 cap を discipline test 化 (PR #145)

記事 (とんのかつ氏「2 層メモリ + 自己改善ループ」) と本 repo 機構の機能比較から
派生し、「CLAUDE.md が肥大化原則を超過 (483 行) している実害」を repo 自身の記録で
実証 → user 指示で 2 修正を実装・merge。phase 進行には非影響の infra 改善。

- **圧縮**: CLAUDE.md 483 → 290 行 (ルール削除ゼロ)。src/tests ツリー →
  `docs/repository_layout.md` 新設、125 行 Session Memory 手順 → wrap-up skill
  (source-of-truth を CLAUDE.md から skill へ反転、archive-TTL/summary/anti-pattern
  を Appendix 化で情報損失ゼロ)。重複参照ブロックも圧縮。
- **discipline test**: `tests/discipline/test_claude_md_line_cap.py` (CLAUDE.md ≤ 300、
  超過検出の負例込み)。`tests/discipline/` 配置で wrap-up step 8 gate に自動編入 →
  終了プロトコルが cap 超過で fail するように。

**設計判断のハイライト**:

1. **実害は repo 自己記録で実証**: `doc_refactor_planning.md` の ≤200 目標 (起案 320)
   に対し CLAUDE.md だけが 483 にリグレッション。トークン固定費は 1M Opus で誤差だが、
   遵守劣化は documented recurring failure mode + 散文ルールの test 強制格上げ履歴で裏づけ。
2. **閾値は CLAUDE.md のみ ≤300** (AskUserQuestion 確定): STATUS.md 336 行ゆえ一律不可。
3. **layout doc を「構造マップ・filesystem 正典」に再定義**: 「Full per-module tree」の
   過剰約束が「hidden module X」型 review を無限誘発した根本原因を断つ。

**修正・訂正**:

1. **divergence 修正方向の論理矛盾** (Codex P2、私の混入バグ): 「skill wins」直後に
   「fix the skill」→ 正典上書き指示。「fix this pointer/summary」に訂正。
2. **移設ツリーが数世代 stale** (Codex P2 ×3): commands 6/10・authoring/sensor/suite
   欠落・nested subpackage 全欠落を filesystem diff が空になるまで補完。本 PR が解こうと
   した「always-loaded doc に詳細を抱えると腐る」問題の実例 (4 commit で消化、全 thread resolved)。

### 古い merged entry (2026-06-08 以前) — archive 参照

27 entry (2026-06-08 (#136/#138/#139) / 2026-06-07 (dogfood) / 2026-06-03 S2 (#130-#132) /
2026-06-03 (#127/#128/#129) / 2026-06-02 (#124/#125/#126) / 2026-05-29 S2 (#120/#121) / 2026-05-28 S2 /
2026-05-27 / 2026-05-26 / 2026-05-22 /
2026-05-21 S5 + S3 + S2 + S1 / 2026-05-19 /
2026-05-15 Session 4 + Session 3 + Session 2 /
2026-05-14-15 ResultStatus split / 2026-05-12 / 2026-05-09 /
2026-05-08 S1+S2 / 2026-05-07 S1+S4+S5 / 2026-05-05) は
`.claude/memory/archive/STATUS_MERGED_LOG.md` に移送済。 詳細参照時は
当該 archive file + 該当 dated session log
(`.claude/memory/YYYY-MM-DD.md`) を参照。 Phase 1 (initial cutoff、
`docs/doc_refactor_planning.md`) + 2026-05-21 S3 wrap-up (5/15 S3 移送)
+ 2026-05-21 S5 wrap-up (5/15 S4 移送) + 2026-05-22 wrap-up (5/19 移送)
+ 2026-05-26 wrap-up (5/21 S1 移送) + 2026-05-28 S1 wrap-up (5/21 S2+S3 移送)
+ 2026-05-28 S2 wrap-up (5/21 S5 移送) + 2026-05-29 wrap-up (5/22 移送)
+ 2026-05-29 S2 wrap-up (5/26 移送) + 2026-06-02 wrap-up (5/27 移送)
+ 2026-06-03 S2 wrap-up (5/28 S2 移送) + 2026-06-08 wrap-up (5/29 S2 移送)
+ 2026-06-09 wrap-up (6/02 移送) + 2026-06-09 S2 wrap-up (6/03 移送)
+ 2026-06-10 wrap-up (6/03 S2 + 6/07 + 6/08 移送)
で compaction が実施された。

## 次の発行順序

ABCD-A/B + Brief 7 (SSP v0.1) + D + F + **Phase G (CSCI-45〜49) 全完走** +
**Phase H (CSCI-50〜54) 全完走**。active な実装軸は **D-class closure
(D6/D7/D8、ROADMAP v0.1.0 exit criteria を直接前進させる repo-internal の
bounded 候補)**。残る軸は **E (Phase X、
ecosystem cross-repo、別 Claude Code session 委譲)** と repo-internal の
**D-class closure (D6/D7/D8、ROADMAP v0.1.0 exit criteria を前進)**。

旧 §A / §B (完走 entry) は CLAUDE.md rule 「closed CSCI は 次の発行順序
から remove」 に従い削除済。 詳細参照は `## 直近 merged` (最新 5) +
`.claude/memory/archive/STATUS_MERGED_LOG.md` (古い entry) + dated session
log (`.claude/memory/YYYY-MM-DD.md`)。


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

### Sequencing decisions

- **A/B/C/D/F/G 全完走**: Brief 1〜8 + ResultStatus split + source-selection
  redesign + Brief 7 (SSP v0.1) + Phase G (CSCI-45〜49) 全 merged
- **Phase H 全完走** (CSCI-50〜54): 2026-06-09 始動 → 2026-06-10 完走
  (PR #142〜#144 + #146〜#148)。LLM security scout layer、advisory-only で
  verdict 非参与。残課題は H-5 review 申し送り 3 件 (P3、`2026-06-10.md` 参照)
- **E (Phase X) active**: E-1 (X-3 cross-ref) と E-2 (X-1 umbrella docs)
  は ecosystem cross-repo work で別 Claude Code session 委譲、E-3 (X-2
  validation 移植) は中長期 phase
- **D-class closure** (D6/D7/D8): repo-internal の bounded 候補、ROADMAP の
  v0.1.0 exit criteria (D 全解決/waive) を直接前進

### 直近最短経路

- **D-class closure (D6/D7/D8)**: repo-internal、bounded、exit criteria 前進
  (D6=nested-function vacuous PASS、D7=extract-method authoring advice、
  D8=SCA auto-discovery gap = fixable defect)。Phase H 完走後の最有力候補
- **E-1/E-2. Phase X cross-ref / umbrella docs** (別 session 委譲)
- **E-3. Phase X-2. HA-style validation cross-domain 移植** (中長期)

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
