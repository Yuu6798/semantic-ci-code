# CLAUDE.md - semantic-ci-code

This file defines the repository-level operating policy for Claude Code and related
agent workflows. Keep product details in `docs/<topic>.md` and keep task handoff
format rules in `AGENTS.md`.

## Project Overview

Semantic CI Code Edition is a deterministic semantic CI layer for code changes.
It compares declared change intent, expected code state, baseline code state, and
observed code state, then emits a semantic diff plus repair instructions.

Scope guard:

- This is not a linter.
- This is not a type checker.
- This is not a test runner.
- This is not an LLM-as-judge service.
- This is not an intent validator.
- This is not an intent interpreter.

The tool deterministically derives a verdict from the **declared** intent
(`target.yaml`). Intent flaws, deviation purpose, and the author's true
intent are out of scope for the verdict. Correction guidance and input
supplementation may live as separate surfaces (Authoring / Advisor) but
never participate in the verdict. See `docs/code_semantic_ci_design.md §23.3`.

The product exists to catch intent drift in generated or manually edited pull
requests while remaining deterministic and auditable.

## Current Status (snapshot)

- **Phase**: P2.5 完走 — Brief 1〜5 全 merged。`semantic-ci` CLI は `init` / `observe` / `compare` / `check` / `pre-commit` / `compile` / `compile-repair` / `validate-plan` の 8 subcommand を持ち、Vibe Coding Adapter(Claude Code / Cursor / Codex)経由で repair guidance + pre-generation guidance を render 可能
- **直近 merged**(2026-05-07 Session 5, TC10 dogfooding + D5 tracking):
  - **PR #61** (dogfooding TC10): 仮想 Python パッケージ 10 ケースで `compare` / `validate-plan` / `compile-repair` を end-to-end 検証(全 verdict + exit code 契約通り)。FINDING-2(`equals_baseline` violation で `_equals_baseline` ヘルパ追加し structured `added`/`removed` を populate)+ FINDING-3(`compile-repair` 入力 `schema_version` 不一致時の stderr warning)を本 PR で fix、`docs/dogfooding_TC10_report.md` 新設
  - **PR #62** (D5 tracking): FINDING-1(set operator partial-dict mismatch、未解決)を Session 4 D1〜D4 計画に **D5** として統合、`CLAUDE.md` 次の発行順序 §F + `docs/dogfooding_TC10_report.md` Tracking section に追記
- **過去 merged**(2026-05-07 Session 4, dogfood-driven hardening):
  - **PR #58** (compiler/path_schema): compile-time path 検証 + did-you-mean 提案、`docs/code_semantic_ci_design.md §4.5` typo 訂正(`api_surface.public_symbols` → `api_surface_public`、`new_test_cases` → `new_cases`)、constraint kind 別 path domain(state vs delta 非対称)、Codex 3 round 消化
  - **PR #59** (cli): `check.py` / `pre_commit.py` の `_resolve_package_root` に `is_relative_to` symlink escape ガード(`validate_plan` 既存パターンを 3 surface 対称化)→ **CSCI-35b sweep #3 完了**
  - **PR #60** (ci): 依存上限ピン × 5(`pydantic<3.0` 等)+ `[tool.coverage.*]` 設定 fail_under=70(branch coverage 73% 実測、~3pp margin)+ `pip-audit --strict .` プロジェクト射程化(env-level CVE 汚染遮断)+ 凍結 dep test 8 ファイル更新
- **過去 merged**(2026-05-07 Session 1, Brief 5 / P2.5 完走):
  - **Brief 5 entry** (CSCI-31 / PR #52): Repair Compiler core + Adapter Protocol + registry + Claude Code adapter
  - **CSCI-32** (PR #53): Cursor adapter(`.mdc` frontmatter + body)
  - **CSCI-33** (PR #54): Codex adapter(ASCII-safe plain text + 角括弧 section ラベル)
  - **CSCI-34** (PR #55): `compile-repair` subcommand + `RepairPlan` JSON deserializer + verdict envelope auto-detect
  - **CSCI-35** (PR #56): `validate-plan` subcommand + `risk_summary` 4 要素計算(`would_violate` / `forbidden_zones` / `required_additions` / `template_implications`)+ Adapter Protocol を明示引数版に切替
- **過去 merged**(2026-05-05):
  - **Brief 4b** (CSCI-28 / PR #40): SARIF + GH Actions annotation + pre-commit manifest 同梱
  - **Brief 4c** (CSCI-29 / PR #42): effects extractor `fqn` を callee → enclosing function に修正(設計 §3.1 適合)
  - **Brief 4d** (CSCI-30 / PR #43): `semantic-ci init` + spec authorship anchoring + hard/soft/info severity routing
  - **Brief 5 planning** (PR #44): `docs/brief_5_planning.md` 起草
- **次の発行順序**:
  - **A. CSCI-35b sweep brief**(優先、残 2 件まで縮小): Brief 5 review で deferred とした (1) ~~`would_violate` の delta-kind 盲点 docs 明記~~(`docs/cli_usage.md:348-353` で既に明記済と確認、撤回)、(2) `compile_target_svp` の YAML round-trip コメント追加、(3) ~~`_resolve_package_root` の symlink escape 防御~~(**PR #59 で完了**)、(4) Claude Code `Forbidden Zones` / `Required Additions` の human-friendly レンダリング、を 1 PR で消化(残 (2) + (4))
  - **A'. target.yaml authoring guide 新規**(`docs/target_yaml_guide.md`): 2026-05-07 Session 4 dogfood で発見した hazard 群を集約 — D1: `--package-root` scope 制約、D3: template と user constraint の重複、D4: config-only PR の vacuous PASS。半日〜1 日。CSCI-35b と並列 or 同梱可
  - **B. Brief 7 (SSP v0.1)**: Semantic Security Protocol。Brief 5 完了済 → CSCI-36〜40 として発行可能。planning は `docs/brief_7_planning.md` で merged 済み
  - **C. P2 残課題の brief 化**: Lock violation 即 fail(§8.2)/ Performance budget per-extractor timeout(§18)/ Hash trail per-extractor version(§10)
  - **D. extractor exclude 機構**(2026-05-07 Session 4 dogfood D2): `tests/fixtures/pipeline/syntax_error/bad.py` のような意図的に壊れた fixture が `--package-root .` で extractor を crash させる、`pyproject.toml` に exclude pattern を持つ仕組みが未実装。半日〜1 日、別 brief
  - **E. ResultStatus 概念モデル更新**(弱点 ③): `UNKNOWN` を authoring error と extractor failure に分離。波及範囲は evaluator / risk_summary / adapter / cli 出力 / json schema / SARIF / GH Actions、設計議論必要、1〜2 日
  - **F. set operator partial-match semantics**(2026-05-07 Session 5 dogfood D5 = FINDING-1、PR #61 由来、**未解決**): set 系 operator が `api_surface_*` / `effects` / `imports` 等の dict 要素 collection に対して **完全レコード一致**しか効かない。`target.yaml` で `expected: [{fqn: pkg.foo}]` の partial dict を書くと observed の full dict(`fqn` + `kind` + `signature` + `visibility`)と非マッチで以下の operator-specific 結果になる:
    - **false positive(silently violated)**: `includes_all` / `includes_any` / `superset_of` / `subset_of` — 期待要素が「missing」と判定され、実際は存在していても violated 扱い。user constraint surface の信頼性を毀損
    - **false negative(silently satisfied = CI bypass)**: `excludes_all` — 禁止要素として書いた partial dict が full record と交差せず、**禁止記号が実在しても constraint は satisfied**。allow-list / deny-list 用途で gate が無声化、`excludes_all` を使った forbidden-symbol policy は実質無効化される最も危険な失敗モード

    設計サンプル(`docs/code_semantic_ci_design.md §4.5` の bare 文字列 list)も同様に不一致。Session 4 D1〜D4 と同じ dogfood-driven fix plan の一員として **D5** に位置付け、解消方針候補は (a) partial-key matcher セマンティクス導入 / (b) 派生 target 追加(`api_surface_delta.added.fqns` 等) / (c) 両併用。設計判断+実装で 1〜2 日規模、operator semantics 変更を伴うため別 brief。詳細・evidence・root cause・再現条件は `docs/dogfooding_TC10_report.md §FINDING-1`(TC4 reproduction)
- **Brief 6 凍結**: TypeScript extractor は P3 以降に後倒し(2026-05-06 Session 2 で確定、§12 P3b 参照)。費用対効果を再評価してから解凍判断
- **Brief 8+ deferred**: spec quality metrics(§19)/ suite packaging(§20)/ override 機構(Brief 3 #3)/ Round-trip log(§10.3 / Brief 3 #10)/ orchestrator 観測応用 / Brief 6 解凍判断

詳細: phase 定義は `docs/code_semantic_ci_design.md §12`、Brief 進捗と Brief 3/4 残課題の再分配は同 `§25`、直近の決定経緯は `.claude/memory/_index.md`。

## Tech Stack

- Language: Python 3.11+
- Build: setuptools with src layout
- Models: Pydantic v2
- Config: PyYAML
- Lint: ruff
- Test: pytest
- CI: GitHub Actions
- License: MIT until explicitly changed

## Workflow

This repository separates design and implementation:

- Claude Code: design, specification, review judgment, phase planning
- Codex: implementation, tests, PR creation, Completion Summary
- User: final approval and handoff trigger

Default cycle:

1. Claude issues a Task Brief using `AGENTS.md`.
2. User gives the brief to Codex.
3. Codex implements on `codex/<topic>`, runs checks, and prepares a PR with a
   Completion Summary.
4. User shares the PR back to Claude.
5. Claude reviews and either approves, requests repair, or emits the next brief.

## Repository Layout

```text
src/semantic_ci_code/
  __init__.py            # legacy entrypoint (semantic-ci-code script)
  __main__.py
  config.py
  scope.py
  api_surface/           # Python public-symbol extractor (CSCI-5)
  cli/                   # CLI surface (Brief 4 / 4b / 4d / 5)
    main.py              # argparse entry; subparser for 8 subcommands
    commands/            # one module per subcommand
      observe.py
      compare.py
      check.py
      pre_commit.py
      compile.py
      compile_repair.py  # Brief 5
      validate_plan.py   # Brief 5
    output/              # json / human / sarif / gh-actions formatters
    output_sarif.py
    output_gh_actions.py
    init_command.py      # Brief 4d
    git_runtime.py       # detached worktree materialization
    code_state_cache.py  # CSCI-26 / 27
    target_loader.py
    delta_overlay.py     # files_touched / loc_delta from git numstat
  compiler/              # target.yaml -> CompiledTarget (CSCI-12)
    target_compiler.py
    templates.py         # change_kind template constraints
    path_schema.py       # PR #58 compile-time path validation
  complexity/            # cyclomatic / cognitive (CSCI-7)
  delta/                 # CodeStateDelta (CSCI-11)
  domain/                # state_schema (CodeState root)
  effects/               # effect_db + AST visitor (CSCI-2 / 3 / 4 / 29)
  evaluator/             # constraint evaluator (CSCI-13)
    operators.py
    path_resolver.py
  framework/             # modality-agnostic (TargetSVP, ConstraintKind)
  imports/               # CSCI-6
  module_graph/          # CSCI-8
  pipeline/              # extract_python_code_state (CSCI-10)
  repair/                # RepairPlan emitter (CSCI-14)
  repair_compiler/       # Brief 5: Adapter Protocol + adapters
    core.py
    types.py
    risk_summary.py
    adapters/
      claude_code.py
      cursor.py
      codex.py
      markdown.py
  schemas/               # JSON Schema artifacts
  test_surface/          # CSCI-9
tests/
  cli/                   # CLI integration tests
  compiler/              # CSCI-12
  delta/                 # CSCI-11
  evaluator/             # CSCI-13
  pipeline/              # CSCI-10
  repair/                # CSCI-14
  repair_compiler/       # Brief 5
  fixtures/              # hand-built before/after trees + expected verdicts
docs/                    # see Design Documents table below
experiments/             # observation-only reproductions (out of core scope)
.claude/memory/          # session memory (handoff source of truth)
```

## Design Documents

Status legend: **ACTIVE** (current spec/contract, AI agents should read first) / **PLANNING** (open / in-progress brief) / **REFERENCE** (brief complete; retained for downstream context) / **ARCHIVED** (history-only, not authoritative) / **CASE STUDY** (out-of-core observation) / **DOGFOOD REPORT** (dogfooding pass record).

| Document | Status | Purpose |
|---|---|---|
| `docs/code_semantic_ci_design.md` | ACTIVE | Code Edition v0.1 design: 3-state RPE, state schema, constraints, repair loop. Single source of truth for engine semantics |
| `docs/cli_usage.md` | ACTIVE | User-facing CLI contract for all 8 subcommands (`observe` / `compare` / `check` / `pre-commit` / `compile` / `init` / `compile-repair` / `validate-plan`), target discovery, format selection, target authorship, severity routing |
| `docs/exit_codes.md` | ACTIVE | Stable CLI exit code policy (0 / 1 / 2 / 3 / 4) for CI integration, including `--strict-repair`, `severity: info` Advisor channel, and per-subcommand notes |
| `docs/json_schema.md` | ACTIVE | CLI JSON envelopes — verdict / compile at `schema_version="4"`, compile-repair / validate-plan at independent `schema_version="1"`. Includes compatibility policy and v2→v3 / v3→v4 diffs |
| `docs/cli_test_inventory.md` | ACTIVE | CLI test coverage inventory, runtime notes, and conservative reduction candidates |
| `docs/brief_7_planning.md` | PLANNING (open) | Brief 7 (Semantic Security Protocol / SSP v0.1) を CSCI-36〜40 想定で planning する文書。Issue #48 の Semgrep 統合提案を audit した結果、core への深い統合は reject、SSP として §20.1 layered distribution の 4 層目(suite と並列)に独立配置。SAST + SCA / Python only / 5 要素 fingerprint(`rule_id × module_path × qualified_name × normalized_text × ordinal`、PR #50 review で 4→5 に拡張)+ 言語プロファイル分離 / 独立 envelope + Sensor Provenance Invariant(§23.1 鏡像)。Brief 6(TypeScript)凍結に伴い順序は **Brief 5 → 7**。CSCI-36 着手時は本文書 §11 checklist + AGENTS.md `Forward Design Note` を逐語参照 |
| `docs/brief_5_planning.md` | REFERENCE (Brief 5 完走 2026-05-07) | Brief 5 (Repair Compiler + Vibe Coding Adapters、P2.5 entry) を CSCI-31〜35 の 5 PR に分割した planning 文書。CSCI-31〜35 全 PR merged で `compile-repair` / `validate-plan` 2 subcommand + Claude Code / Cursor / Codex 3 adapter が release 可能。Brief 3 残課題 #4(Repair Compiler)+ §21.3 adapter list + `pre_generation_validation_case.md` 残された問い #4 を救済済み。Brief 7 起草時の参照として保存 |
| `docs/brief_4b_planning.md` | REFERENCE (Brief 4b 完走 2026-05-05) | Brief 4b (CI integration outputs) を CSCI-28 に集約した planning 文書。SARIF 2.1.0 / GitHub Actions annotation / `.pre-commit-hooks.yaml` manifest を 1 PR で完結。Brief 4 Open Questions Q9/Q10/Q11 を救済 |
| `docs/brief_4_planning.md` | REFERENCE (Brief 4 完走 2026-05-04) | Brief 4 (CLI / operational entrypoint) を CSCI-15〜19 に分割した planning 文書。CSCI-15〜19 全 PR merged で `semantic-ci` CLI 5 subcommand が release 可能。残 Open Questions は Brief 4b / 4c / 4d / 5 で消化済み |
| `docs/brief_3_planning.md` | ARCHIVED (Brief 3 完走) | Brief 3 (pipeline 統合) を CSCI-10〜14 に分割した planning 文書。当時の判断履歴として保存(operator 5 個案などの一部記述は CSCI-12 brief で上書き済み) |
| `docs/dogfooding_TC10_report.md` | DOGFOOD REPORT (2026-05-07 Session 5) | 仮想 Python パッケージ 10 ケースで `compare` / `validate-plan` / `compile-repair` を end-to-end 検証。FINDING-1(set operator partial-dict mismatch、**未解決** = D5、`CLAUDE.md` 次の発行順序 §F)、FINDING-2(`equals_baseline` の structured added/removed 欠落、PR #61 で fix 済)、FINDING-3(`compile-repair` schema_version 不一致 warning 追加、PR #61 で fix 済) |
| `docs/multi_agent_audit_case.md` | CASE STUDY | 並列エージェント運用におけるオーケストレーター盲点の観測事例。core scope 外の応用観測としてセマンティック CI の射程拡張を示す |
| `docs/pre_generation_validation_case.md` | CASE STUDY | stub のみの candidate を engine に渡し §23.1 入力 contract が実装で動作することを 3 ケースで確認した観測事例。再現は `experiments/pre_generation_validation/` で完結。core scope 外の応用観測 |

When adding a new `docs/<topic>.md`, update this table (with status tag) and the README documentation list.

## Commands

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
python -m semantic_ci_code
```

## Coding Conventions

- Keep behavior deterministic: same input should produce the same output.
- Do not introduce LLM calls, API keys, network services, or vendor coupling without an
  explicit Task Brief decision.
- Add dependencies only when they are allowed by the active brief.
- Prefer typed Pydantic models for state, constraint, diff, and repair data.
- Prefer structured parsing over ad hoc string manipulation.
- Keep README concise; move detailed design into `docs/`.

## Engine Contract

The judgment engine (Brief 3+) is a generic 2-state comparator, not a PR-only tool.
See `docs/code_semantic_ci_design.md` §23 for the full Application Matrix.

- Engine input: `(baseline_state: CodeState, candidate_state: CodeState, intent)`.
- `CodeState` is a frozen Pydantic schema. The engine does NOT require that the
  states come from real-code extraction. They may be predicted, mocked, or
  constructed by hand. This enables pre-generation validation, what-if
  simulation, contract testing, and educational simulators alongside the main
  PR-review use case.
- Git operations, `.semantic-ci/intent.yaml` discovery, output formatting, and
  exit code conversion are CLI-layer (Brief 4) responsibilities. The engine
  itself never touches git and never reads files except through schema-typed
  inputs.
- Tests for the evaluator MUST include at least one case that supplies hand-built
  virtual `CodeState` values so the engine cannot regress into requiring an
  extractor pipeline.

## Session Memory (永続記憶ワークフロー)

Long-running design conversations are recorded in `.claude/memory/` so that
later sessions can resume without losing context.

### 仕組み

- 場所: `.claude/memory/`
- ファイル: `YYYY-MM-DD.md` (同日に複数セッションあれば「Session 2」「Session 3」と節を切って 1 ファイルに追記)
- 索引: `_index.md` に各セッションの 1 行要約を追記

### 起動時ルール

1. セッション開始時に `_index.md` を読んで過去の決定事項を把握する
2. 直近 3 件のサマリーは必要に応じて詳細参照する
3. 過去の設計判断に関する質問はサマリーを確認してから回答する

### 終了時ルール (自動トリガー)

ユーザーが終了意図を示すフレーズを発したら、確認なしで即座に `/wrap-up` 相当の
処理 (memory への振り返りサマリー保存 + `_index.md` 追記) を実行する。

トリガーフレーズの例:
- 「今日はここまで」「今日は終わり」「今日はおわり」
- 「セッション終了」「セッション閉じて」
- 「また明日」「また今度」「お疲れ様」「お疲れさま」
- 「done for today」「that's all」
- 手動: `/wrap-up`

実行内容:
- 会話の振り返りサマリーを `.claude/memory/YYYY-MM-DD.md` に保存
- `_index.md` に 1 行サマリーを追記
- `CLAUDE.md` への更新候補があればユーザーに提案する

### サマリーの構成 (慣例フォーマット)

過去ファイルに合わせて以下のセクションで構成する:

- **コンテキスト** — そのセッションが何を扱ったか 1〜2 段落
- **設計判断** — なぜその選択をしたか
- **成功パターン** — 効いたアプローチ
- **修正・訂正** — バグ・誤認識の記録
- **工程サマリー** — 表形式で工程と成果
- **成果物** — マージされた PR / 追加ファイル
- **次セッションへの引き継ぎ** — 残課題
- **メモ** — 雑多な気づき

### Git Workflow の例外

`.claude/memory/` の運用ログのみ、 main 直 push の唯一の例外として認められている。
これ以外の変更はすべて feature branch + PR の通常フローを守る。
