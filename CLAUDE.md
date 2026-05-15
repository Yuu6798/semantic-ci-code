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

The product exists to catch intent drift between two well-formed code states
under a declared intent, while remaining deterministic and auditable. The
engine's input contract is `(intent, baseline_state, candidate_state)`; the
states do not need to come from real-code extraction. Pull-request review is
the primary use case, but any setup that can produce a well-formed
`(intent, state_A, state_B)` triple runs through the same engine path —
including virtual, predicted, mocked, or hand-built `CodeState` values.

This input-side provenance neutrality is required by
`docs/code_semantic_ci_design.md` §23.1 (Generic 2-state Comparator) and
§23.2 (Application Matrix), and is confirmed empirically by:

- `docs/pre_generation_validation_case.md` — stub-only candidates (3 cases)
  validated through `semantic-ci compare`, reproduction in
  `experiments/pre_generation_validation/`.
- `docs/dogfooding_TC10_report.md` — 10 virtual-package cases (TC1〜TC10)
  exercising `compare` / `validate-plan` / `compile-repair` end-to-end with
  hand-built `baseline/` and `candidate/` trees; verdict + exit code match
  the documented contract for every case.

If new feature work weakens this neutrality (e.g. requiring a real git ref
to compute a verdict), it MUST be flagged as a §23.1 violation in the brief.

## Current Status

The day-to-day project status (current phase, recent merged PRs, and the
`次の発行順序` action queue) lives in `.claude/memory/STATUS.md` so this
policy doc stays stable while the snapshot can be edited freely.

- Live status: [`.claude/memory/STATUS.md`](.claude/memory/STATUS.md)
- Per-session log: [`.claude/memory/_index.md`](.claude/memory/_index.md) +
  the dated `YYYY-MM-DD.md` files
- Phase plan and Brief table (canonical, change-tracked): see
  `docs/code_semantic_ci_design.md` §12 / §25

When other docs need to point at the live tracker, they MUST link to
`.claude/memory/STATUS.md` 次の発行順序 — not to this file.

## Required Reading Before Editing

Claude Code (and any agent acting in this repository) MUST consult the
following before taking any action that changes the repo:

1. **`.claude/memory/STATUS.md`** — current phase, live next-issue queue,
   frozen / deferred items.
2. **`.claude/memory/_index.md`** — one-line summary of every prior session;
   read at minimum the latest 3 entries.
3. **`.claude/memory/YYYY-MM-DD.md`** for the most recent dated session(s)
   when the current task is a continuation, a fix, or a follow-up of recent
   decisions.
4. **`AGENTS.md`** for the Task Brief / Completion Summary protocol, and the
   `Forward Design Note` for any work that touches Brief 7 / SSP.
5. **`docs/code_semantic_ci_design.md`** §23 (engine contract / boundary)
   before changing engine, evaluator, repair compiler, or adapter behavior.

Skipping memory and inventing context from scratch is a documented
recurring failure mode. If the memory is stale or incomplete, surface that
in the response rather than acting without it.

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
| `docs/target_yaml_guide.md` | ACTIVE | `target.yaml` authoring guide. Practical companion to `design.md §4` / `cli_usage.md`. Centralises authoring hazards D1 (`--package-root` scope vs `tests/` visibility), D3 (template / user constraint duplication), D4 (config-only PR の vacuous PASS) — 2026-05-07 Session 4 dogfooding 由来 |
| `docs/target_authoring_surface.md` | ACTIVE | Authoring surface 設計契約 (Brief 8 / CSCI-41)。target.yaml は hand-written 必須でない / 生成経路 3 通り (recipe + sources / catalog 参照 / hand-written) / LLM 経路は Brief 8b 分離 / 全経路は verdict 前に declared intent として固定 / Authoring・Advisor・Provenance surface は evaluator 不可参照 / `candidate_code_used: false` 固定。§23.3.1 の実装側 catch-up |
| `docs/brief_7_planning.md` | PLANNING (open) | Brief 7 (Semantic Security Protocol / SSP v0.1) を CSCI-36〜40 想定で planning する文書。Issue #48 の Semgrep 統合提案を audit した結果、core への深い統合は reject、SSP として §20.1 layered distribution の 4 層目(suite と並列)に独立配置。SAST + SCA / Python only / 5 要素 fingerprint(`rule_id × module_path × qualified_name × normalized_text × ordinal`、PR #50 review で 4→5 に拡張)+ 言語プロファイル分離 / 独立 envelope + Sensor Provenance Invariant(§23.1 鏡像)。Brief 6(TypeScript)凍結に伴い順序は **Brief 5 → 7**。CSCI-36 着手時は本文書 §11 checklist + AGENTS.md `Forward Design Note` を逐語参照 |
| `docs/brief_resultstatus_planning.md` | PLANNING (open) | ResultStatus.UNKNOWN を authoring と extraction に分離する brief の planning。**C+B 仮固定**(C=authoring を compile-time に押し戻す / B=`results[].unknown_cause` optional field、A=enum 拡張は不採用)。D2: authoring は unknown_policy 非尊重で強制 fail、extraction は尊重。D3: validate-plan v2 で `risk_summary.authoring_errors` を `would_violate` から分離。Brief D1-1〜D1-4 + D3 の 5 PR 想定。§1b で Brief 8 (Authoring Surface) との境界(semantic hazard vs syntactic/type error / INV-1 framing / ADVISORY-S1 文言更新見込み / 着地順序 open question)を pin。target path 静的型カテゴリ + operator-required-category 行列 + compile catch coverage 推定済 |
| `docs/archive/brief_5_planning.md` | REFERENCE (Brief 5 完走 2026-05-07) | Brief 5 (Repair Compiler + Vibe Coding Adapters、P2.5 entry) を CSCI-31〜35 の 5 PR に分割した planning 文書。CSCI-31〜35 全 PR merged で `compile-repair` / `validate-plan` 2 subcommand + Claude Code / Cursor / Codex 3 adapter が release 可能。Brief 3 残課題 #4(Repair Compiler)+ §21.3 adapter list + `pre_generation_validation_case.md` 残された問い #4 を救済済み。Brief 7 起草時の参照として保存 |
| `docs/archive/brief_4b_planning.md` | REFERENCE (Brief 4b 完走 2026-05-05) | Brief 4b (CI integration outputs) を CSCI-28 に集約した planning 文書。SARIF 2.1.0 / GitHub Actions annotation / `.pre-commit-hooks.yaml` manifest を 1 PR で完結。Brief 4 Open Questions Q9/Q10/Q11 を救済 |
| `docs/archive/brief_4_planning.md` | REFERENCE (Brief 4 完走 2026-05-04) | Brief 4 (CLI / operational entrypoint) を CSCI-15〜19 に分割した planning 文書。CSCI-15〜19 全 PR merged で `semantic-ci` CLI 5 subcommand が release 可能。残 Open Questions は Brief 4b / 4c / 4d / 5 で消化済み |
| `docs/archive/brief_3_planning.md` | ARCHIVED (Brief 3 完走) | Brief 3 (pipeline 統合) を CSCI-10〜14 に分割した planning 文書。当時の判断履歴として保存(operator 5 個案などの一部記述は CSCI-12 brief で上書き済み) |
| `docs/dogfooding_TC10_report.md` | DOGFOOD REPORT (2026-05-07 Session 5) | 仮想 Python パッケージ 10 ケースで `compare` / `validate-plan` / `compile-repair` を end-to-end 検証。FINDING-1(set operator partial-dict mismatch、**未解決** = D5、`.claude/memory/STATUS.md` 次の発行順序 §F)、FINDING-2(`equals_baseline` の structured added/removed 欠落、PR #61 で fix 済)、FINDING-3(`compile-repair` schema_version 不一致 warning 追加、PR #61 で fix 済) |
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
