# Session Memory Index

1-2 line entry per session. Full narratives live in dated
`YYYY-MM-DD.md` files; this file is the lightweight index for the
Tier A reading load (see `CLAUDE.md` § Required Reading Before Editing).
Restored to original spec by Phase 2 of `docs/doc_refactor_planning.md`.

| Date | PR / commit | Outcome | Detail |
|---|---|---|---|
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
| 2026-05-05 (S4) | #35 / #36 / #39 / #40 / #42 / #43 / #44 | P1 完走 (Brief 4b/4c/4d 全 merged) + Brief 5 planning (P2.5 entry)、 redistribution table で残課題行先明示 | `2026-05-05.md` |
| 2026-05-05 (S3) | #33 / #37 | Brief 4b cache slice CSCI-25/26/27 3 brief 連続発行、 `--mode {smoke,full}` + CodeState cache + size-eviction | `2026-05-05.md` |
| 2026-05-05 (S2) | — | PR #34 post-merge adversarial test (A 真陰 + D 偽陰) → effects slice 実装 gap 発見 (P2 で予定通り解消)、 docs only | `2026-05-05.md` |
| 2026-05-05 (S1) | #34 | §23.1 入力 contract「engine は state 出自を問わない」 を仕様 → 実証済み性質に格上げ、 `pre_generation_validation_case.md` 新設 | `2026-05-05.md` |
| 2026-05-04 | #20-#26 | Brief 3 残務 + Brief 4 全体 (CSCI-15〜19) を 1 セッション完結、 `semantic-ci` CLI 5 subcommand release 可能、 self-dogfood 初実証 | `2026-05-04.md` |
| 2026-05-03 (S3) | — | Brief 3 (判定層) planning Q1〜Q4 確定 + §23 (Comparator Architecture) 新設 + Session Memory ワークフロー正式化 | `2026-05-03.md` |
| 2026-05-03 (S2) | (CSCI-5〜9) | Brief 2 完結 = Python P1 抽出器 5 PR 連続 merge (api_surface / imports / module_graph / complexity / test_surface)、 stdlib `ast` のみ | `2026-05-03.md` |
| 2026-05-03 (S1) | — | design.md §17-§22 追加 (Spec Authorship / Performance Budget / Vibe Coding Adapter / Multi-language Phasing 等)、 Generator Adapter / Repair Compiler を P5 → P2.5 へ前倒し | `2026-05-03.md` |
| 2026-05-02 | #3 / #4 / #5 | P1 effect extractor 3-stage 完成 (CSCI-2/3/4、 direct-call + imported-alias + global_mutation) | `2026-05-02.md` |
