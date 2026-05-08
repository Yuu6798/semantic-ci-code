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

### 2026-05-08 Session 2 — target.yaml authoring guide 新設

- **本セッション (docs only)**: `docs/target_yaml_guide.md` を新規作成し、
  2026-05-07 Session 4 dogfood で抽出された D1/D3/D4 (`--package-root` scope
  制約 / template と user constraint の重複 / config-only PR の vacuous PASS)
  を authoring hazard 章として集約。CLAUDE.md docs table + design.md §24
  ACTIVE 仕様一覧 + README documentation 一覧を追従、§23.3 boundary を冒頭
  reminder に pin、§4 / §13 / cli_usage.md / dogfooding_TC10_report.md への
  cross-ref を整備。`次の発行順序` から A' (authoring guide) を削除

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

- **B. Brief 7 (SSP v0.1)**: Semantic Security Protocol。Brief 5 完了済 →
  CSCI-36〜40 として発行可能。planning は `docs/brief_7_planning.md` で
  merged 済み
- **C. P2 残課題の brief 化**: Lock violation 即 fail(§8.2)/ Performance
  budget per-extractor timeout(§18)/ Hash trail per-extractor version(§10)
- **E. ResultStatus 概念モデル更新**(弱点 ③): `UNKNOWN` を authoring error
  と extractor failure に分離。波及範囲は evaluator / risk_summary / adapter
  / cli 出力 / json schema / SARIF / GH Actions、設計議論必要、1〜2 日

## Frozen / Deferred

- **Brief 6 凍結**: TypeScript extractor は P3 以降に後倒し(2026-05-06
  Session 2 で確定、`docs/code_semantic_ci_design.md §12 P3b` 参照)。費用
  対効果を再評価してから解凍判断
- **Brief 8+ deferred**: spec quality metrics(§19)/ suite packaging(§20)/
  override 機構(Brief 3 #3)/ Round-trip log(§10.3 / Brief 3 #10)/
  orchestrator 観測応用 / Brief 6 解凍判断
