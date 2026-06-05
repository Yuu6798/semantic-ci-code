# Session Memory Index

1-2 line entry per session. Full narratives live in dated
`YYYY-MM-DD.md` files; this file is the lightweight index for the
Tier A reading load (see `CLAUDE.md` § Required Reading Before Editing).
Restored to original spec by Phase 2 of `docs/doc_refactor_planning.md`.

| Date | PR / commit | Outcome | Detail |
|---|---|---|---|
| 2026-06-05 | #134 | Phase G G-5 完走 (CSCI-49)、Phase G 全 5 PR landing。`generic` (template 無し change_kind) 追加で security overlay を変更種別から独立 + recipe `deny-dangerous-imports`/`deny-dangerous-effects`。grounding で engine-free 前提崩壊 (全 kind が effects/api_surface ロック) + catalog KeyError を実装前特定 → `TEMPLATE_CONSTRAINTS[GENERIC]=()` 明示。`validation_preserved` は D3 重複+D4 vacuous PASS で削除→category B へ。Codex が effects match_schema 矛盾 (effect_class-only が fqn 必須) を dogfood test で捕捉し `required_any_keys` で修正 | `2026-06-05.md` |
| 2026-06-03 (S2) | #130 → #131 → #132 | LLM security sensor / scout layer planning (Phase H candidate、`docs/llm_sensor_adapter_planning.md`、CSCI-50〜54、G-5 完走前提)。Codex Security 調査 → SSP/Phase G 接続の 5+ round 壁打ち → D1〜D9 (中心命題「LLM は scout であって judge ではない」/ verdict 分離 / 誤検知>見逃し / 沈黙=容認)。#130 を承認前に誤 merge → revert (#131) → 修正版 #132 で Codex P2 を 7 round 消化 (cross-model dedup / rename / verdict 分離 / absence+presence anchor 述語) して merge | `2026-06-03.md` |
| 2026-06-03 | #127 + #128 + #129 | Phase G G-3〜G-4b 完走 (CSCI-47/48/48b)。suite security policy evaluator (#127) → `check --sensor` 配線 + suite_verdict + exit code + 集約 security JSON (#128) → per-sensor detail を JSON/human/SARIF に拡張 + SARIF 同一 run マージ (#129)。CSCI-48b は grounding-first brief で wrapper 化契約維持 + G-4a exact-match 緩和を事前 encode、PR #129 review バグ 0 (非ブロッキング 2 cleanup) → follow-up 3 commit で land。Phase G 残は G-5 (CSCI-49 templates) のみ | `2026-06-03.md` |
| 2026-06-02 | #124 + #125 + #126 | Phase G 着手: G-1/CSCI-45 (SensorState+canonical_id+delta) + G-2/CSCI-46 (SSP→SensorState 翻訳 adapter) を 2 PR 完走。review で P2 捕捉→Codex 1 round 修正 (CSCI-45: ordinal を v1 identity に / suppression G-3 defer / SSP 命名整合、CSCI-46: SCA canonical_id dedup)。SAST identity を SSP 5 要素 fingerprint 整合の 8 要素に確定し planning を逆流同期 (#126) | `2026-06-02.md` |
| 2026-05-29 (S2) | #120 + #121 | 2 Skill (new-brief/wrap-up) 動作確認 (構造・参照・gate 全検証、 dangling ゼロ) → SessionStart hook (dev-extras 自動導入、 startup/resume 限定、 出力抑制) + fixture 署名 OFF (host config 不変、 GIT_CONFIG env で commit.gpgsign false) で Web/local フルテスト緑化。self-dogfood PASS (D4 vacuous と正直報告)、 Codex P2×3 を 2 push で消化、 PR #120 merge。follow-up PR #121 で wrap-up gate を `python -m pytest` に統一 (PATH 差異の恒久 close、 Codex 👍 0-round) | `2026-05-29.md` |
| 2026-05-29 (S1) | #118 | doc-refactor Phase 6 完走 (schema-grep + dual-case を `tests/discipline/` 化、 round-count retire) + doc hygiene sweep (phase_g 表 drift / STATUS 418→349 / AGENTS §5.5 同期)。Codex P2 で dual-case を verdict 列パースに改修 + 回帰 test。壁打ちで B=coverage advisory 設計を externalize (検証不能な真値→検証可能な保守代理 のメタ原理) | `2026-05-29.md` |
| 2026-05-28 (S2) | #116 + #117 | Real-PR complexity dogfood report + 単一 tracker landed (D6/D7 追加)、 続けて件数列追加で 累計 21 件 (S4=3 + TC10=10 + real-PR=8) を tracker 単体で即答可能化 | `2026-05-28.md` |
| 2026-05-28 (S1) | #114 + #115 | Phase G (SSP core integration) planning landed。SSP 実地テスト 21 ケース (実 9 + 仮想 5 + multi-agent 7) → 設計問題発覚 → 3 AI 統合 planning 起草 → Codex 18 round / 22 P2 chase。PR #114 merge 後 #115 で deep cross-ref 7 件追加修正 | `2026-05-28.md` |
| 2026-05-27 | #109-#112 | Brief 7 / SSP v0.1 完走 (CSCI-36〜40)。spec doc 復元 + models/delta/fingerprint + SemgrepAdapter + PipAuditAdapter + CLI/SARIF/human format。Issue #108 closed | `2026-05-27.md` |
| 2026-05-26 | #106 + #107 | target authoring UX 改善: PR #106 (init --intent / next commands / recipe notes / init --doctor / doctor_support 共有化) + PR #107 (ADVISORY-I1 空 intent 検出)。設計 v1→v2 改訂 (PR 順序反転 / usage error / 共有化 / stderr 安全化 / \r 追加)、両 PR 0 round approve | `2026-05-26.md` |
| 2026-05-25 | #100-#105 | F queue 完走 (source-selection Phase 2/3a/3b) + D queue 完走 (lock short-circuit / per-extractor timeout / per-extractor version hash)、 6 PR を 1 session で設計→レビュー→マージ、 全 PR 0 round (PR #100 のみ follow-up commit 1 件) | `2026-05-25.md` |
| 2026-05-22 | #98 + #99 | Issue #97 (langchain blind sampling 由来 `--allow-dirty` provenance bug) を PR #98 = Phase 1 mitigation で 0 round closure (derived predicate + 4 architecture invariant + 2 integration test)。 続けて design hole を `docs/source_selection_planning.md` (406 lines、 3 phase × 7 lock-in、 aggressive style) に encode、 PR #99 で正式採用 | `2026-05-22.md` |
| 2026-05-21 (S5) | #96 + ugh-ecosystem PR#1 | UGH ecosystem framing 確立 (4 domain + theory + Strata 区別)、 umbrella repo `Yuu6798/ugh-ecosystem` 新設 (別 Claude Code session 経由 1 day closure、 PR #1 を 1 round fix で merge)、 semantic-ci-code/CLAUDE.md に `## Ecosystem Context` 追記 (+24 lines、 PR #96)。 Phase X-1 + X-5 landed、 Phase X-2/X-3 が中長期 queue として明示化 | `2026-05-21.md` |
| 2026-05-21 (S4) | #95 | wrap-up protocol に step 8 (pre-push `pytest tests/discipline/` verify) 追加、 memory exception 直 push と discipline test の structural gap (main red 直撃) を 5 秒 ritual で closure。 semantic-ci 適用は overengineering 判定で見送り | `2026-05-21.md` |
| 2026-05-21 (S3) | #88-#94 + direct push | 緊急 doc refactor 8 phase 1 日完走、 framework 自己 refactor の self-referential dogfood、 attention budget 2,500→580 lines (-77%)、 `tests/discipline/` 3 test で memory hygiene drift を CI auto-enforce 化 | `2026-05-21.md` |
| 2026-05-21 (S2) | #87 / #88 | R17 (`target-doctor --package-root` parity, 0 round) + 経験値外部化 framework 言語化 → CLAUDE.md/AGENTS.md §5 永続化 + urgent doc refactor planning landed | `2026-05-21.md` |
| 2026-05-21 (S1) | #86 | Brief 8 / CSCI-44 (`semantic-ci target-catalog`) → ABCD-B 完走、 INV-5 cross-test 5 件 + AST 抽出で registry mirror | `2026-05-21.md` |
| 2026-05-19 | #85 | Brief 8 / canonical-form refactor (`authoring/canonical.py` 3 helper + 48 producer-spec contract test、 §23.1 self-validation) | `2026-05-19.md` |
| 2026-05-15 (S4) | #84 | Brief 8 / CSCI-42 (`init --recipe --from-*`) landed、 Codex bot review 13 round 連続 P2 消化、 canonical refactor 持ち越し | `2026-05-15.md` |
| 2026-05-15 (S3) | #82 | Brief 8 / CSCI-43 (`target-doctor` Advisor surface) landed、 Codex 16 round 全消化、 R17 deferred (後に 5/21 で消化) | `2026-05-15.md` |
| 2026-05-15 (S2) | #81 | Brief 8 / CSCI-41 (Authoring surface 設計契約) landed、 docs only + 連動 cross-ref 7 file | `2026-05-15.md` |
| 2026-05-15 (S1) | #76-#79 | ResultStatus split 完走 (D1-2 / D1-3 / D1-4 / D3、 ABCD-A 軸 landed、 4 PR 一気通貫) | `2026-05-15.md` |
| 2026-05-12 | #74 | ResultStatus planning 取り込み (§1b Brief 8 boundary 新設) + ABCD 完成度境界確認、 「半年の壁打ちが ABCD に蒸留」 と言語化 | `2026-05-12.md` |
| 2026-05-09 | #70 / #71 | 緊急 perf brief 2 連続 (test in-process 化 -75%、 template repo reuse -31%) + ResultStatus planning C+B 仮固定 | `2026-05-09.md` |
| 2026-05-08 | #69 | `docs/target_yaml_guide.md` 新設 (5/7 S4 dogfood の D1/D3/D4 hazard 集約) + ResultStatus 棚卸し start | `2026-05-08.md` |
| 2026-05-07 (S5) | #61 / #62 | TC10 dogfood 完走 (10/10 verdict 契約通り)、 FINDING-1〜3 抽出、 D5 (set operator partial-dict) を tracking 統合 | `2026-05-07.md` |
| 2026-05-07 (S4) | #58 / #59 / #60 | 弱点分析 → 実地 dogfood → 緊急パッチ 3 連続 (compile-time path 検証 + symlink guard + dep 上限ピン)、 D1〜D4 発見 | `2026-05-07.md` |
| 2026-05-07 (S3) | — | Kai 探索 + call_graph dimension 検討、 いずれも採用見送り (Python 未実装 + §23.3 グレー / `module_graph_delta` 既存) | `2026-05-07.md` |
| 2026-05-07 (S2) | — | 並走 brief 発行 (CSCI-30b〜34 起草) + Brief 7 設計申し送り 11 項目を AGENTS.md Forward Design Note に永続化 | `2026-05-07.md` |
| 2026-05-07 (S1) | #53-#57 | Brief 5 (P2.5) 完走、 CSCI-32〜35 + 完了宣言、 Vibe Coding Adapter 3 種 + `compile-repair` / `validate-plan` release 可能 | `2026-05-07.md` |
| 2026-05-06 (S3) | #50 | PR #50 (SSP planning + Brief 6 凍結) を Codex 7 round 全消化、 SSP spec implementability + memory handoff source-of-truth 再定義 | `2026-05-06.md` |
| 2026-05-06 (S2) | (#50) | Issue #48 (Semgrep) audit → 別 protocol SSP として §20.1 4 層化、 6 論点確定 (SAST+SCA / Python only / 5 要素 fp / Sensor Provenance Invariant) | `2026-05-06.md` |
| 2026-05-06 (S1) | `fa5f887` | Responsibility Boundary 確立、 §23.3 (intent 側鏡像 / 4 surface 模型) 新設、 Scope guard 2 行拡張 | `2026-05-06.md` |
| 2026-05-05 (S1-S4) | #33-#44 | P1 完走 (Brief 4b/4c/4d merged) + Brief 5 planning (P2.5 entry) + cache slice CSCI-25/26/27 (`--mode` + CodeState cache + size-eviction) + §23.1 入力 contract を実証済み性質に格上げ (`pre_generation_validation_case.md` 新設) + 弱点 adversarial test。**archived** (>30 日) | `archive/2026-05/2026-05-05.md` |
| 2026-05-04 | #20-#26 | Brief 3 残務 + Brief 4 全体 (CSCI-15〜19) を 1 セッション完結、 `semantic-ci` CLI 5 subcommand release 可能、 self-dogfood 初実証。**archived** (30 日) | `archive/2026-05/2026-05-04.md` |
| 2026-05-03 (S1+S2+S3) | #5 ほか | Brief 2 完結 (P1 抽出器 5 PR: api_surface/imports/module_graph/complexity/test_surface) + design.md §17-§22 追加 (P2.5 前倒し) + Brief 3 planning Q1〜Q4 + §23 新設 + Session Memory ワークフロー正式化。**archived** (>30 日) | `archive/2026-05/2026-05-03.md` |
| 2026-05-02 | #3 / #4 / #5 | P1 effect extractor 3-stage 完成 (CSCI-2/3/4)。**archived** (>30 日) | `archive/2026-05/2026-05-02.md` |
