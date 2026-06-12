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

Brief 1〜8 + Brief 7 (SSP v0.1) + ResultStatus split + source-selection + doc refactor + **Phase G (CSCI-45〜49) / Phase H (CSCI-50〜54) 全完走** + pre-release credibility トラック (tag は切らず experimental 明示) + **D-class findings 8/8 全解決 (2026-06-12、ROADMAP v0.1.0 exit criterion「D 全解決/waive」充足)**。直近の landing: 2026-06-10 セキュリティ hardening (PR #149) + Phase X-2 planning 凍結 (PR #150、`docs/pr_validation_planning.md`)、2026-06-11 D8 解決 (CSCI-55 / PR #151)、2026-06-12 D6 解決 (ADVISORY-D6 / PR #152) + D7 解決 (ADVISORY-D7 + advisory envelope advisory-2 bump / PR #153) — complexity 制約の authoring 面が D6 (nested 変位の vacuous PASS) / D7 (extract-method の構造的 false-FAIL) の相補ペアで完成、`target-doctor` は 9 advisory 体制。次は **Phase X-2 実験実行 (pilot 5 件、別 session 委譲)** / **E-1/E-2 (ecosystem cross-repo、別 session)** / H-5 review 申し送り 3 件 (P3) / `§15.1` grounding bullet 追加の小粒 docs のいずれか。

## 直近 merged

### 2026-06-12 — D-class closure 完了: D6 + D7 (PR #152 / #153)

D-class closure 第 2・3 弾で **8/8 全解決** (v0.1.0 exit criterion 充足)。
Fable が設計→実装→dogfood→レビュー対応→merge を完走、PR は
`subscribe_pr_activity` で event-driven に babysit。

- **PR #152 (D6)**: `authoring/nested_defs.py::count_nested_defs` +
  `hazards.py::detect_d6` + guide Hazard 4。nested helper への複雑度変位で
  complexity lock が vacuous PASS する盲点を、diff の nested-def 増加 ×
  verdict 参加 complexity_delta 制約で警告。D4 鏡像の diff-aware 契約
  (CLI が context 計算 / rev なしは silent skip)。Codex P2 = package-root
  跨ぎ rename は out-of-scope 側 0 で計数。
- **PR #153 (D7)**: `count_visible_defs` (extractor 委譲で parity drift 排除)
  + `detect_d7` + guide Hazard 5 (refactor パターン別 metric 選択表)。
  extract-method は +1 base/helper で総和 cyclomatic が必ず微増 → refactor
  target の「+net を reject する」cyclomatic lock を警告し cognitive を推奨。
  Codex P2 ×3 = net growth 比較 / evaluator tolerance semantics の逐語
  mirror / allowance を実 net helper 数と比較。advisory envelope は
  **advisory-2** に bump (使用中 enum への D6/D7 追加、compatibility policy)。
- **dogfood**: D6 = PASS(騙し)+ADVISORY、D7 = FAIL(構造的)+ADVISORY +
  cognitive 化で PASS — fail+pass 両方実演。最終 1817 テスト緑。
- **申し送り**: D6 growth は per-file のまま (総和への算術寄与なしのため
  aggregate 化根拠が D7 と別)。consumer は advisory-2 を前提に。

### 2026-06-11 — D8 closure: SCA dependency-source discovery (CSCI-55、PR #151)

D-class closure 着手第 1 弾。`docs/dogfooding_findings_tracker.md` D8 (2026-06-07
scale + security dogfood 由来の fixable defect) を 1 brief / 1 PR で解決。
D-class は **6/8 解決** (残 D6/D7)。

- **PR #151**: `ssp scan --sensor pip-audit` の依存ソース発見を 7-row precedence
  (requirements.txt / pylock(.\*.)toml / uv.lock / pdm.lock / poetry.lock /
  PEP 621 static `[project].dependencies` / fallback) に拡張。lock は pinned
  temp requirements + `--no-deps` へ決定論翻訳、malformed 認識 source は
  fail-closed (下位 source への silent fallback 禁止 → unknown/exit 3)。
  envelope ssp-1 不変 / `check --sensor-*` 経路無改修 / `from_json` signature
  凍結 (Phase G adapter 依存) / 新規依存ゼロ (stdlib tomllib)。
- **review**: new-brief skill (§15 gate) で起草、AC 9 件全充足で chat 内
  APPROVE。その後 merge までに lockfile resolution semantics の follow-up
  **17 commit** (PEP 508 markers / wildcard / PEP 440 prerelease / dev・
  optional group 除外 / uv extras closure / local package skip / `pylock.*.toml`
  named variant / pylock × 旧 pip-audit fail-closed) — brief の「uv.lock 追加は
  増分ほぼゼロ」が誤算で、外部 format の翻訳 semantics が spec 本体だった。
  全 fix は commit 単位で test encode 済。
- **申し送り**: tracker D8 行に PR 番号未記載 (1 行 docs PR 候補) /
  `docs/brief_8_planning.md §15.1` への「外部 format 翻訳は resolution
  semantics まで grounding」bullet 追加提案 / lock file OSError → exit 2
  edge (P3 観測)。詳細 `2026-06-11.md`。

### 2026-06-10 — Phase X-2 (code domain) PR validation 実験 planning 凍結 (PR #150)

Fable による repo 評価レビュー (「技術 A / 中核仮説は外部未検証」) から派生し、
§E-3 が呼ぶ外部検証実験の planning を起草・凍結。「動くか」(既存 dogfooding) と
「効くか」(本実験) を分離し、中核仮説を falsifiable にした。

- **PR #150**: `docs/pr_validation_planning.md` 新設 (PLANNING)。公開 PR N≥48 で
  semantic-ci verdict と human reviewer 判断の一致を測る。**Y = review 結果**
  (changes-requested=fail / approve=pass、merge/reject は Y ノイズで不採用 —
  user の統計的指摘で確定)、**評価 diff = 最初の実質レビュー時点 SHA**、
  **baseline はレビュー時点 base を first-parent walk で再構築** + 空 diff
  sanity guard、**target = A (generic) + B (intent-only = PR タイトル/本文/
  ラベルのみ)**、汚染 2 軸 (Y leakage / candidate tautology §F) を独立に禁止、
  **主指標 = AUROC/MCC/F1/混同行列 + bootstrap CI** (ρ は補助)、pre-registration
  で X を見る前に凍結、pilot 5 件は配管確認のみ。
- **review**: Codex P2 ×4 を 4 round で消化 — ① pilot Y の表記曖昧 (Y=B 誤読) /
  ② baseline 時点ズレ (merged PR で merge-base が candidate を返す) / ③
  candidate tautology (B の入力から変更ファイル/diff統計を除外、user 判断で
  intent-only 確定) / ④ 再構築レシピの first-parent 限定 (rev-list が PR 自身の
  commit を拾う穴)。いずれも「実験が静かに無効化される」類で、凍結前に全部閉じた。
- **着手は別 session** (外部 repo 収集が GitHub MCP scope 外) +
  `experiments/pr_validation/`。

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

### 古い merged entry (2026-06-10 以前) — archive 参照

30 entry (2026-06-10 H-4 (#147) / 2026-06-10 H-3 (#146) / 2026-06-09 S2 (#145) / 2026-06-08 (#136/#138/#139) / 2026-06-07 (dogfood) / 2026-06-03 S2 (#130-#132) /
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
+ 2026-06-10 #150 sweep (6/09 S2 移送)
+ 2026-06-11 wrap-up (6/10 H-3 #146 移送)
+ 2026-06-12 wrap-up (6/10 H-4 #147 移送)
で compaction が実施された。

## 次の発行順序

ABCD-A/B + Brief 7 (SSP v0.1) + D + F + **Phase G / Phase H 全完走** +
**D-class closure 全完走 (D8 = PR #151、D6 = PR #152、D7 = PR #153)**。
repo-internal の active queue は小粒のみ (H-5 申し送り P3 / `§15.1`
grounding bullet)。残る主軸は **E (Phase X、ecosystem cross-repo、別
Claude Code session 委譲)** — 中でも E-3 (X-2 pilot 実行) が次の本命。

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
  の core work**。 **code domain 版 experiment plan は起草済 =
  `docs/pr_validation_planning.md`** (2026-06-10、PLANNING)。Y = review 結果
  (changes-requested=fail/approve=pass、merge/reject 不採用)、評価 diff = 最初の
  実質レビュー時点 SHA、target A(generic)+B(PR メタ自動生成・leakage 禁止)、
  主指標 = AUROC/MCC/F1/混同行列+bootstrap CI (ρ は補助)、pre-registration で
  X を見る前に凍結、pilot 5 件は配管確認のみ。着手は外部 repo 収集ゆえ別 session +
  `experiments/pr_validation/`。着手前に `ugh-audit-core/docs/validation.md` で
  dataset 構造を確認。 完走 criteria は「各 domain で N≥48 の external validation
  蓄積」、 期間は数週間〜数ヶ月

### Sequencing decisions

- **A/B/C/D/F/G 全完走**: Brief 1〜8 + ResultStatus split + source-selection
  redesign + Brief 7 (SSP v0.1) + Phase G (CSCI-45〜49) 全 merged
- **Phase H 全完走** (CSCI-50〜54): 2026-06-09 始動 → 2026-06-10 完走
  (PR #142〜#144 + #146〜#148)。LLM security scout layer、advisory-only で
  verdict 非参与。残課題は H-5 review 申し送り 3 件 (P3、`2026-06-10.md` 参照)
- **E (Phase X) active**: E-1 (X-3 cross-ref) と E-2 (X-1 umbrella docs)
  は ecosystem cross-repo work で別 Claude Code session 委譲、E-3 (X-2
  validation 移植) は中長期 phase
- **D-class closure 全完走**: D8 = CSCI-55 / PR #151 (2026-06-11)、D6 =
  PR #152、D7 = PR #153 (2026-06-12) で 8/8 解決。ROADMAP v0.1.0 exit
  criteria (D 全解決/waive) 充足

### 直近最短経路

- **E-3 実行. Phase X-2 (code domain) pilot 5 件**: planning は PR #150 で凍結済
  (`docs/pr_validation_planning.md`)。次の一歩は pilot = 配管煙試験 (review
  event 取得 / レビュー時点 SHA 固定 / first-parent baseline 再構築 / 空 diff
  guard / intent-only target B 生成)。外部 repo 収集ゆえ**別 session 委譲** +
  `experiments/pr_validation/`。Fable 評価レビューの推奨 1 = 「上物より中核
  仮説の falsification を先に」の実行
- **小粒 docs 候補**: `docs/brief_8_planning.md §15.1` への「外部 format
  翻訳は resolution semantics まで grounding」bullet 追加 (`2026-06-11.md`
  申し送りの未消化分。tracker D8 行への PR 番号追記は PR #152 で消化済)
- **E-1/E-2. Phase X cross-ref / umbrella docs** (別 session 委譲)

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
