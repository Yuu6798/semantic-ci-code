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

Brief 1〜5 + Brief 8 + Brief 7 (SSP v0.1) + ResultStatus split + source-selection + doc refactor 全完走。2026-05-28 (S1) に **Phase G (SSP core integration) planning** が PR #114 + #115 で landed (`docs/phase_g_planning.md`、5 PR 構成 CSCI-45〜49、Codex 18 round + deep cross-ref 7 件で洗練済)。同日 S2 で並走していた **公開リポジトリ実 PR 8 件 dogfooding pass** の結果が PR #116 + #117 で land、`docs/dogfooding_real_pr_complexity.md` + 単一 tracker `docs/dogfooding_findings_tracker.md` (累計 21 ケース pin、D6/D7 追加) として artifact 化された。Phase G は SSP v0.1 (現状 core の横に並列) を core の縦接続に再構築する設計: CodeState と並列の SensorState を新設、suite evaluator で code_delta + security_delta を統合 verdict、SAST finding を FQN 空間に翻訳、canonical_id を JSON array hash で injective encoding、per-sensor provenance で drift 検出。Next queue: **Phase G 実装 (CSCI-45 から)** + Phase X (ecosystem formalization) の残 sub-phase (E-1〜E-3)。

## 直近 merged

### 2026-05-28 Session 2 — Real-PR complexity dogfood report + tracker case-count landed (PR #116 + #117)

同日 Session 1 (Phase G planning) と並走していた **公開 Python リポジトリ
実 PR 8 件 (refactor 7 + feature 1) の complexity 制約 dogfooding pass** の
結果を 2 PR cascade で artifact 化。 累計 21 ケース (Session 4 self-dogfood 3
+ TC10 仮想 10 + real-PR 8) を tracker 単体で即答可能化、 D6 / D7 を D# 名簿
に追加。

- **PR #116** (merged `0ac4e95`、2 commit):
  `docs(dogfooding): add real-PR complexity report + consolidated findings tracker`
  - `docs/dogfooding_real_pr_complexity.md` 新設 (8 case の per-PR matrix +
    methodology + verdict 集計、 6/8 reviewer-relevant 一致、 1 vacuous PASS
    = D6 (nested-function blind spot、 D4 sibling)、 1 authoring mismatch =
    D7 (extract-method × cyclomatic 微増))
  - `docs/dogfooding_findings_tracker.md` 新設 (D1〜D7 を全 dogfooding pass
    横断で集約する単一 tracker、 既存 dogfooding report 内の D# entry は
    cross-link のみ保持に refactor)
  - 2nd commit (`f13c9cc`) で per-case base/head SHA pin + case 5 の
    target.yaml inline (re-run reproducibility 確保)
  - `CLAUDE.md` Design Documents table に 2 row 追加
- **PR #117** (merged `575d398`、 1 commit):
  `docs(dogfooding): pin per-pass case counts + cumulative total in tracker`
  - user 問い「ドッグフーディングの件数って累積でカウントできるように
    なってるか」 への応答、 Source pass index 表に Methodology + Cases
    column 追加
  - per-pass 件数 pin: Session 4 self-dogfood = 3 / TC10 = 10 / Real-PR
    complexity = 8 / **累計 = 21**
  - CASE STUDY (pre_generation_validation_case.md /
    multi_agent_audit_case.md) は dogfooding pass と別カテゴリとして
    累計から除外する rule を文章で pin、 将来の追加で同 confusion を防ぐ

**設計判断のハイライト**:

1. **「累計件数を tracker 単体で即答可能にする」design criterion**:
   N=21 は 3 つの report に分散していたので、 source pass index 表に
   Cases column + 累計 row を追加するだけで、 tracker が「単一 source of
   truth」 として機能。 後続 dogfooding pass 追加時も Pass / Date /
   Methodology / Cases / Doc / Findings の 6 列で同 invariant 維持可能
2. **`AskUserQuestion` で 3 択 trade-off 提示**: PR #116 merge 後に
   「件数 column 追加」 を独立 PR で出すか / wrap-up とバンドルか /
   main 直 push (rule 違反) か の 3 択を提示、 user は推奨 (follow-up
   PR) を即選択。 stale 件数記載が翌日に伸びることなく、 質問と回答の
   context cohesion が高い間に encode 完了
3. **PR auto-subscribe → merge までイベント駆動**: PR #117 で
   `subscribe_pr_activity` を call、 CI in_progress を確認した時点で
   turn を閉じ、 webhook 通知で merge を受け取り直ちにローカル main を
   sync。 poll なしで PR closure を待つ運用

**修正・訂正**:

1. **Session 4 件数**: 初期に「Session 4 dogfood = 1 件」 と counting
   しがちだが、 実態は init→compile_repair 同等シナリオ 1 + PR #59
   self-dogfood 1 + PR #60 self-dogfood 1 = **3 件**。 tracker 起草時の
   `.claude/memory/2026-05-07.md` 再読で正確な書き起こしに訂正
2. **Pass naming**: `Session 4 dogfood` → `Session 4 self-dogfood` に
   refactor (自分自身の PR を入力に取る methodology を正確に表す)

### 2026-05-28 Session 1 — Phase G (SSP core integration) planning landed (PR #114 + #115)

SSP v0.1 完走直後の 2026-05-28 session で、SSP の実地テスト 21 ケース
(実リポジトリ 9 + 仮想入力 5 + マルチエージェント想定 7) を実行する過程で
**「SSP が core の横に並列配置され、core が持つ intent 宣言 + 構造比較の力を
使えていない」** という構造的問題が surface。3 つの独立 AI 分析 (GPT / Gemini /
Grok) を統合した `docs/phase_g_planning.md` を起草、Codex review 18 round で
洗練後 PR #114 merge、続いて PR #115 で deep cross-reference review 7 件を消化。

- **PR #114** (merged `d1f9f9e`): `docs(planning): add Phase G — SSP core integration`
  - `docs/phase_g_planning.md` 新設 (5 PR 構成、CSCI-45〜49 想定)
  - 設計の核: SensorState を CodeState と並列の別 state に分離 (GPT 案)、SAST
    finding を adapter で FQN 空間に翻訳して自然キー化 (Gemini 案)、canonical_id
    を JSON array hash で injective encoding + identity algorithm version 埋め込み
    (Grok 案)、per-sensor provenance + status + advisory_db_hash で drift 検出、
    suite evaluator で code_delta + security_delta を統合 verdict (unknown > fail
    > repair > pass の aggregation)
  - 18 round / 22 P2 で消化した設計欠陥: canonical_id の delimiter collision
    (`:` → `\0` → JSON array)、 schema 整合性 (constraint kind/target/operator
    の互換性 / effect extractor の limitation / suppression form 同期)、
    multi-sensor support (sensor_id namespace / provenance_by_sensor map /
    per-sensor unknown)、 source location 保持 (SARIF 出力対応)、 G-5 template
    の実現可能性 (extractor 拡張要否で 2 カテゴリ分割)
- **PR #115** (merged `b13f205`): Phase G planning deep cross-reference fixes
  - 8 follow-up commits: identity_components の ordered tuple 型化、
    PerSensorDelta の model_validator (drift と ownership)、 aggregate_status
    consistency validator、 suppression migration の入力要件明示、
    default-policy floor on PerSensorDelta.status、 example canonical_id hash の
    identity tuple との一致確認、 non-complete sensor 拒否、 sensor_name →
    sensor_id 命名統一、 `ensure_ascii=False` の追加 (SSP v0.1 §5.1 と同じ
    canonical encoding、非 ASCII FQN での adapter / validator hash 乖離防止)
  - PR #115 で `docs/ssp_usage_guide.md` も同 PR で land (SSP v0.1 実用ガイド)

**設計判断のハイライト**:

1. **「実地テスト → 設計問題発覚 → planning 起草」の連続フロー**: 「SSP どこまで
   使えるかテスト」から始まり、テスト結果 (VTC4 のモジュール移動、S5 の
   backdoor 検知) を user 対話で言語化する過程で設計問題が surface、その場で
   planning doc を起こす。テスト結果が planning の具体例として残った
2. **3 AI 並列分析の統合**: GPT (概念分離) + Gemini (自然キー戦略) + Grok
   (横断品質) の組み合わせが互いの盲点を補完。user の「現提案をベースに 2 点
   追加」即決判断で統合方針が確定
3. **planning 段階で Codex review chase を回す**: 実装フェーズではなく planning
   doc 1 ファイルで 18 round + deep cross-ref 7 件。実装 PR (G-1〜G-5) で同じ
   trap を回避できる。AGENTS.md §5.4「round 数を leading quality indicator として
   運用」の応用、29 round 累計 P2 を test に encode した PR #82/#84 の延長
4. **user 主導の「妥協しない」方針宣言**: round 14 時点で user が「この設計
   フェーズは妥協すると文書と実装でズレが起きる可能性がある。無くなるまで
   やりたい」と明示、以降の round 15〜18 + PR #115 の deep chase の動機付け
5. **「概念境界の純度」を維持する設計**: SecurityFinding を CodeState に直接
   追加する初期案を GPT 分析で否定 (CodeState = AST 由来の構造状態、
   SecurityFinding = 観測状態の概念分離)、SensorState を別 state にする案に変更
6. **canonical_id encoding の段階的洗練**: delimiter join (`:`) → NUL join
   (`\0`) → canonical JSON array (`json.dumps(ensure_ascii=False)`) の 3 段階で
   alias collision class を構造的に排除。最終案は SSP v0.1 `_digest_array` §5.1
   と同じ encoding

**修正・訂正**:

1. **「CodeState に SecurityFinding を直接追加」初期案** — GPT 分析で「コード状態
   vs 観測状態」の概念分離を指摘され、SensorState を別 state にする案に変更
2. **canonical_id の delimiter encoding** — Round 10 (`:` collision) → Round 15
   (`\0` collision) → Round 19 (`ensure_ascii=False` 不足) の 3 段階で洗練
3. **§0.1 で「effects constraint でロジック脆弱性検知可能」と書いた誤り** —
   Round 14 で「effects は DB 登録済み副作用のみ抽出、純粋 auth guard は見えない」
   と訂正、§1.6 / G-5 と整合性を取った
4. **Phase 番号** — 当初 user が「F」と言及したが既存 Phase F (source-selection)
   と衝突、planning doc / commit message で **G** に統一

### 2026-05-27 — Brief 7 / SSP v0.1 完走 (PR #109〜#112、Issue #108 closed)

Brief 7 (Semantic Security Protocol v0.1) の全 5 CSCI を 1 session で完走。
CSCI-36 (spec doc gap fill) + CSCI-37 (models/delta/fingerprint) を PR #109 に
同梱、CSCI-38 (SemgrepAdapter) = PR #110、CSCI-39 (PipAuditAdapter) = PR #111、
CSCI-40 (CLI + SARIF + human format) = PR #112。全 PR CI green、P1 なし
(PR #109 のみ P1 2件を修正後マージ)。`semantic-ci ssp scan` / `ssp from-json`
で SSP v0.1 が end-to-end 使用可能。Issue #108 completed でクローズ。

### 2026-05-26 — target authoring UX 改善 landed (PR #106 + #107)

target.yaml 初期作成の UX 改善を 2 PR で land。設計 v1→v2 改訂
(user レビューで PR 順序矛盾 / --package-root サイレント無視 /
package_root 解決の共有化不足 / stderr 二重改行 / \r チェック漏れ
の 5 点を修正)、両 PR 0 round approve。

- **PR #106** (merged): `feat(init): improve target authoring UX with
  --intent and inline doctor` — `--intent` フラグ / next-command
  guidance / recipe notes / test_surface note / `--doctor` inline
  実行 / `doctor_support.py` 共有化 (target_doctor.py の
  `_resolve_package_root` を移動)。475+/51-、CI 3/3 green
- **PR #107** (merged): `feat(authoring): add ADVISORY-I1 for empty
  target intent` — `detect_i1`: `target.intent == ""` で発火、
  whitespace-only は非該当。advisory 6→7 件。81+/3-、CI 3/3 green

### 2026-05-22 — Issue #97 (`--allow-dirty` provenance bug) Phase 1 mitigation landed (PR #98) + Source-selection redesign 正式採用 (PR #99)

`langchain-ai/langchain` への blind random sampling で発覚した
`semantic-ci check --candidate-rev <SHA> --allow-dirty` の provenance bug
を 1 day で closure し、 同 session 内で design hole を planning doc に
encode して正式採用まで 2 PR cascade で land
(`claude/repository-issue-review-BVt9Y` を 2 PR 連続 reuse)。

- **PR #98** (merged `bf4af3b`、 0 round): `check.py` に
  `candidate_uses_working_tree` derived predicate 導入、 explicit
  `--candidate-rev` + `--allow-dirty` 同時指定で warning + ref materialize。
  `tests/architecture/test_check_provenance.py` 新設 (§23.1 CLI-layer
  mirror、 4 invariant)。 CI 3/3 green、 1284 passed。 PR body で Phase 2
  deferral を明示宣言し後続 #99 の前提を pin
- **PR #99** (docs only): `docs/source_selection_planning.md` 新設
  (406 lines)。 `--candidate-source` / `--baseline-source` redesign を
  Phase 2 / 3a / 3b の 3 PR 構成で pin、 aggressive / clean-cut style
  (no alias / no deprecation / hard delete)、 §7 で rejected options 4 件を
  rationale 付き永続化

設計判断・修正の詳細 (7 sub-question の 4-style trade-off 圧縮、 rejected
options 永続化 pattern、 §23.1 reinforcement、 当初 4→3 phase 統合と JSON
provenance 前倒し等) は `.claude/memory/2026-05-22.md` 参照。

---

### 古い merged entry (2026-05-21 S5 以前) — archive 参照

17 entry (2026-05-21 S5 + S3 + S2 + S1 / 2026-05-19 / 2026-05-15 Session 4 + Session 3 + Session 2 /
2026-05-14-15 ResultStatus split / 2026-05-12 / 2026-05-09 /
2026-05-08 S1+S2 / 2026-05-07 S1+S4+S5 / 2026-05-05) は
`.claude/memory/archive/STATUS_MERGED_LOG.md` に移送済。 詳細参照時は
当該 archive file + 該当 dated session log
(`.claude/memory/YYYY-MM-DD.md`) を参照。 Phase 1 (initial cutoff、
`docs/doc_refactor_planning.md`) + 2026-05-21 S3 wrap-up (5/15 S3 移送)
+ 2026-05-21 S5 wrap-up (5/15 S4 移送) + 2026-05-22 wrap-up (5/19 移送)
+ 2026-05-26 wrap-up (5/21 S1 移送) + 2026-05-28 S1 wrap-up (5/21 S2+S3 移送)
+ 2026-05-28 S2 wrap-up (5/21 S5 移送) で compaction が実施された。

## 次の発行順序

ABCD-A/B + Brief 7 (SSP v0.1) + D + F 全完走。active queue は
**G (SSP core integration、 planning は PR #114 + #115 で取り込み済、 実装 CSCI-45〜49 未着手)**
と **E (Phase X 残)** の 2 軸。Phase G は本 repo 内で完結する実装フェーズ、
Phase X は ecosystem cross-repo 作業。

旧 §A / §B (完走 entry) は CLAUDE.md rule 「closed CSCI は 次の発行順序
から remove」 に従い削除済。 詳細参照は `## 直近 merged` (最新 5) +
`.claude/memory/archive/STATUS_MERGED_LOG.md` (古い entry) + dated session
log (`.claude/memory/YYYY-MM-DD.md`)。


### G. Phase G(SSP core integration、 planning は PR #114 + #115 で取り込み済、 実装 5 CSCI 未着手)

`docs/phase_g_planning.md` を planning source として、SSP v0.1 を core の
横ではなく上 (縦接続) に再構築する 5 PR 構成 (CSCI-45〜49)。SensorState を
CodeState と並列の別 state に分離し、suite evaluator で code_delta +
security_delta を統合 verdict、SAST finding を FQN 空間に翻訳して自然キー化、
canonical_id を canonical JSON array hash で injective encoding。

- **G-1. CSCI-45. SensorState model + canonical_id**:
  `src/semantic_ci_code/sensor/` 新設 (models.py / delta.py)。SecurityFinding
  / SensorState / SensorProvenance / SensorDelta の Pydantic 定義、
  canonical_id ベースの集合差分。既存コード変更なし。AC: hand-built JSON で
  SensorState 構築・比較可能 (§23.1 鏡像)
- **G-2. CSCI-46. FQN 翻訳 adapter**:
  `src/semantic_ci_code/sensor/adapters/` 新設。SSP v0.1 の
  SemgrepAdapter / PipAuditAdapter を SensorState に正規化、
  fqn_resolver.py で file:line → FQN 逆引き、canonical_id 生成 (v1 prefix +
  ensure_ascii=False)、provenance 生成
- **G-3. CSCI-47. Suite evaluator + security constraint**:
  `src/semantic_ci_code/suite/` 新設。code_delta + security_delta →
  suite_verdict、target.yaml `security:` namespace 解釈、scanner drift
  検出 (provenance_changed → unknown)。AC: target.yaml に security
  constraint を書いて verdict が出る
- **G-4. CSCI-48. CLI 統合 + SSP v0.1 migration path**:
  `semantic-ci check --sensor` 追加。SSP v0.1 の `ssp scan` /
  `ssp from-json` は互換維持 (deprecated 予告)。suite verdict の
  JSON / human / SARIF 出力
- **G-5. CSCI-49. Semantic security templates** (2 カテゴリ):
  - カテゴリ A (extractor 拡張なし): `dangerous_imports_denied.yaml` +
    `validation_preserved.yaml`、既存 imports / api_surface で表現
  - カテゴリ B (extractor 拡張必要): `auth_guard_preserved.yaml` +
    `privileged_api_gated.yaml`、G-5 brief で extractor scope を AC として
    定義 (auth decorator 検出 or data_flow 実装)

planning doc §6 Open Questions (Q1〜Q5) は G-1 brief 起草時に最低限
G-1 範囲では確定する。


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

- **A/B/C/D/F 全完走**: Brief 1〜8 + ResultStatus split + source-selection
  redesign + Brief 7 (SSP v0.1) 全 merged
- **G (Phase G) active**: 本 repo 内で完結する実装フェーズ、CSCI-45 から
  順次 brief 起草 + Codex 実装 split で進行
- **E (Phase X) active**: E-1 (X-3 cross-ref) と E-2 (X-1 umbrella docs)
  は ecosystem cross-repo work で別 Claude Code session 委譲、E-3 (X-2
  validation 移植) は中長期 phase
- **G と E の優先順位**: G は本 repo 単独完結なので Codex split で平行
  進行可能、E は別 session 委譲で本 session と非同期。本 repo 内の作業
  優先度では G が先

### 直近最短経路

- **G-1. CSCI-45 brief 起草**: SensorState model + canonical_id +
  delta engine (新設のみ、既存コード変更なし)。planning doc §6
  Open Questions のうち G-1 範囲を brief 起草時に確定
- **G-2. CSCI-46 brief 起草** (G-1 merge 後): FQN 翻訳 adapter +
  SSP v0.1 adapter 移植
- **E-1. Phase X-3. Cross-ref embedding** (並行可、別 session 委譲)
- **E-2. Phase X-1 続き. Umbrella `docs/` 拡張** (並行可、別 session 委譲)
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
