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

The product exists to catch intent drift in generated or manually edited pull
requests while remaining deterministic and auditable.

## Current Status (snapshot)

- **Phase**: P1 (Python Static Semantic CI MVP) — Exit criteria 達成済み(Brief 1〜4 / CSCI-1〜19 merged、`semantic-ci` CLI 5 subcommand release 可能)
- **次の並列発行(Brief 4b / 4c / 4d、Brief 5 の前)**:
  - **Brief 4b**: SARIF(Q9)+ GH Actions annotation(Q10)+ pre-commit manifest(Q11 同梱)
  - **Brief 4c**: effects extractor `fqn` semantics 修正(P1 内 hot-fix、設計 §3.1 schema 適合)
  - **Brief 4d**: `semantic-ci init`(Q4)+ spec authorship anchoring(§17 / Brief 3 #7)+ soft / info constraint kind(Brief 3 #2)
- **Brief 5 / Brief 6 並列発行**(§22 設計通り):
  - **Brief 5**: Vibe Coding Adapter + Repair Compiler に絞る(P2.5 entry)
  - **Brief 6**: TypeScript extractor 着手(P2.5 並列)
- **P2 Brief 化時に細目として明記**: Lock violation 即 fail(§8.2 / Brief 3 #8)/ Performance budget per-extractor timeout(§18 / Brief 3 #5)/ Hash trail per-extractor version(§10 / Brief 3 #9 残部)
- **Brief 7+ deferred**: spec quality metrics(§19)/ suite packaging(§20)/ override 機構(Brief 3 #3)/ Round-trip log(§10.3 / Brief 3 #10)/ orchestrator 観測応用

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
  __init__.py
  __main__.py
  config.py
  scope.py
tests/
docs/
  code_semantic_ci_design.md
```

## Design Documents

| Document | Purpose |
|---|---|
| `docs/code_semantic_ci_design.md` | Code Edition v0.1 design: 3-state RPE, state schema, constraints, repair loop |
| `docs/cli_usage.md` | User-facing CLI contract for `observe`, `compare`, `check`, `pre-commit`, and `compile`, including target discovery and format selection |
| `docs/exit_codes.md` | Stable CLI exit code policy for CI integration |
| `docs/json_schema.md` | CLI JSON `schema_version="1"` envelopes for verdict and compile outputs |
| `docs/cli_test_inventory.md` | CLI test coverage inventory, runtime notes, and conservative reduction candidates |
| `docs/brief_4_planning.md` | (Brief 4 complete; retained for Brief 5 reference) Brief 4 (CLI / operational entrypoint) を CSCI-15〜19 に分割した planning 文書。CSCI-15〜19 全 PR が merge され `semantic-ci` CLI 5 subcommand が release 可能状態。Open Questions 16 件のうち未確定分は Brief 5 / Brief 4b で消化予定 |
| `docs/brief_3_planning.md` | (Archived) Brief 3 (pipeline 統合) を CSCI-10〜14 に分割した planning 文書。CSCI-10〜14 の全 PR が merge され Brief 3 は完結済み。当時の判断履歴として保存 |
| `docs/multi_agent_audit_case.md` | 並列エージェント運用におけるオーケストレーター盲点の観測事例。core scope 外の応用観測としてセマンティック CI の射程拡張を示す |
| `docs/pre_generation_validation_case.md` | 外部 Python リポジトリ上で stub のみの candidate を engine に渡し §23.1 入力 contract が実装で動作することを 3 ケースで確認した観測事例。core scope 外の応用観測 |

When adding a new `docs/<topic>.md`, update this table and the README documentation list.

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
