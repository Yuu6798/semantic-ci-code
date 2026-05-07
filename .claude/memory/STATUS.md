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

P2.5 完走 — Brief 1〜5 全 merged。`semantic-ci` CLI は `init` / `observe` /
`compare` / `check` / `pre-commit` / `compile` / `compile-repair` /
`validate-plan` の 8 subcommand を持ち、Vibe Coding Adapter(Claude Code /
Cursor / Codex)経由で repair guidance + pre-generation guidance を render 可能。

## 直近 merged

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

- **A. CSCI-35b sweep brief**(優先、残 2 件まで縮小): Brief 5 review で
  deferred とした (1) ~~`would_violate` の delta-kind 盲点 docs 明記~~
  (`docs/cli_usage.md:348-353` で既に明記済と確認、撤回)、(2)
  `compile_target_svp` の YAML round-trip コメント追加、(3) ~~`_resolve_package_root`
  の symlink escape 防御~~(**PR #59 で完了**)、(4) Claude Code
  `Forbidden Zones` / `Required Additions` の human-friendly レンダリング、を
  1 PR で消化(残 (2) + (4))
- **A'. target.yaml authoring guide 新規**(`docs/target_yaml_guide.md`):
  2026-05-07 Session 4 dogfood で発見した hazard 群を集約 — D1:
  `--package-root` scope 制約、D3: template と user constraint の重複、D4:
  config-only PR の vacuous PASS。半日〜1 日。CSCI-35b と並列 or 同梱可
- **B. Brief 7 (SSP v0.1)**: Semantic Security Protocol。Brief 5 完了済 →
  CSCI-36〜40 として発行可能。planning は `docs/brief_7_planning.md` で
  merged 済み
- **C. P2 残課題の brief 化**: Lock violation 即 fail(§8.2)/ Performance
  budget per-extractor timeout(§18)/ Hash trail per-extractor version(§10)
- **D. extractor exclude 機構**(2026-05-07 Session 4 dogfood D2):
  `tests/fixtures/pipeline/syntax_error/bad.py` のような意図的に壊れた
  fixture が `--package-root .` で extractor を crash させる、`pyproject.toml`
  に exclude pattern を持つ仕組みが未実装。半日〜1 日、別 brief
- **E. ResultStatus 概念モデル更新**(弱点 ③): `UNKNOWN` を authoring error
  と extractor failure に分離。波及範囲は evaluator / risk_summary / adapter
  / cli 出力 / json schema / SARIF / GH Actions、設計議論必要、1〜2 日
- **F. set operator partial-match semantics**(2026-05-07 Session 5 dogfood
  - Resolved in CSCI-35c: Match Schema partial-record matching, compile-time validation, and flat projection aliases landed.
  D5 = FINDING-1、PR #61 由来、**resolved in CSCI-35c**): set 系 operator が
  `api_surface_*` / `effects` / `imports` 等の dict 要素 collection に対して
  **完全レコード一致**しか効かない。`target.yaml` で `expected: [{fqn: pkg.foo}]`
  の partial dict を書くと observed の full dict(`fqn` + `kind` + `signature`
  + `visibility`)と非マッチで以下の operator-specific 結果になる:
  - **false positive(silently violated)**: `includes_all` / `includes_any` /
    `superset_of` / `subset_of` — 期待要素が「missing」と判定され、実際は
    存在していても violated 扱い。user constraint surface の信頼性を毀損
  - **false negative(silently satisfied = CI bypass)**: `excludes_all` —
    禁止要素として書いた partial dict が full record と交差せず、**禁止記号が
    実在しても constraint は satisfied**。allow-list / deny-list 用途で gate
    が無声化、`excludes_all` を使った forbidden-symbol policy は実質無効化
    される最も危険な失敗モード

  設計サンプル(`docs/code_semantic_ci_design.md §4.5` の bare 文字列 list)
  も同様に不一致。Session 4 D1〜D4 と同じ dogfood-driven fix plan の一員と
  して **D5** に位置付け、解消方針候補は (a) partial-key matcher セマンティクス
  導入 / (b) 派生 target 追加(`api_surface_delta.added.fqns` 等) / (c)
  両併用。設計判断+実装で 1〜2 日規模、operator semantics 変更を伴うため別
  brief。詳細・evidence・root cause・再現条件は
  `docs/dogfooding_TC10_report.md §FINDING-1`(TC4 reproduction)

## Frozen / Deferred

- **Brief 6 凍結**: TypeScript extractor は P3 以降に後倒し(2026-05-06
  Session 2 で確定、`docs/code_semantic_ci_design.md §12 P3b` 参照)。費用
  対効果を再評価してから解凍判断
- **Brief 8+ deferred**: spec quality metrics(§19)/ suite packaging(§20)/
  override 機構(Brief 3 #3)/ Round-trip log(§10.3 / Brief 3 #10)/
  orchestrator 観測応用 / Brief 6 解凍判断
