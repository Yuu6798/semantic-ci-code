# CLAUDE.md - semantic-ci-code

This file defines the repository-level operating policy for Claude Code and related
agent workflows. Keep product details in `docs/<topic>.md` and keep task handoff
format rules in `AGENTS.md`.

## Ecosystem Context

This repository is the **code domain** of the
[UGH ecosystem](https://github.com/Yuu6798/ugh-ecosystem), a multi-domain
semantic audit framework. The ecosystem implements a single design pattern
across modalities:

    Declared intent → Observed state → ΔE → Verdict → Repair

`semantic-ci-code` specialises this for Python code: `target.yaml` is the
declared intent, `CodeState` is the observed state, the constraint evaluator
produces the verdict, and `RepairPlan` is the repair surface. The Scope
guard under `## Project Overview` below is the code-domain specialisation of
the ecosystem-wide invariant that the audit layer is always deterministic
and reproducible from recorded inputs alone (= `docs/code_semantic_ci_design.md`
§23.1 input neutrality, framed at ecosystem scope).

Other component domains (independent repos, own release cadences):
[text](https://github.com/Yuu6798/ugh-audit-core),
[music](https://github.com/Yuu6798/ugh-prompt-engine),
[image+video](https://github.com/Yuu6798/svp-video-pipeline).
Cross-domain vocabulary, strata definition, and ecosystem roadmap live in
the umbrella repo; this `CLAUDE.md` keeps to code-domain policy.

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
- `docs/dogfooding_real_pr_complexity.md` — 8 real-PR cases exercising
  `check` against external Python repositories under complexity
  constraints; verdict matches reviewer-relevant signal in 6/8, with 1
  vacuous PASS (D6) and 1 authoring mismatch (D7) registered in the
  consolidated tracker.

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

Claude Code (and any agent acting in this repository) MUST consult these
docs before taking any action that changes the repo. Reading load is
**tiered** to keep startup attention budget bounded (target: Tier A ≤
800 lines). Read up to the tier that matches your task scope.

### Tier A — Always required at startup (target ≤ 800 lines)

1. **This file (`CLAUDE.md`)** — repository policy and operating
   contract (`Required Reading` / Engine Contract / Session Memory /
   Experience Externalization)
2. **`.claude/memory/STATUS.md` §`## Phase` (1 paragraph) + §`次の発行順序`**
   — current project state + active next-issue queue. Skip the full
   `## 直近 merged` log unless investigating a specific recent PR
3. **`.claude/memory/_index.md` の直近 5 entries** — 1-2 line index
   form (essay entries are a bloat anti-pattern, see
   `docs/doc_refactor_planning.md` Phase 2)
4. **`AGENTS.md` §1-§4** — Message Flow + Task Brief / Completion
   Summary format + Escalation Rules + Branch Rules

Skipping Tier A and inventing context from scratch is a documented
recurring failure mode. If a Tier A doc is stale or incomplete,
surface that in the response rather than acting without it.

### Tier B — Required before drafting a new brief (target ≤ 300 lines)

1. **`AGENTS.md` §5 Experience Externalization Discipline** — anti-pattern
   list + maintenance practice (after Phase 3 compaction, ≤ 80 lines)
2. **`docs/brief_8_planning.md §15` brief drafting checklist** — 8
   sub-checklist, 20 round 蒸留
3. **Relevant `docs/<topic>_planning.md` section** — the planning doc
   for the brief / phase being drafted

### Tier C — On-demand for the specific task

- `docs/brief_*_planning.md` (full read of the relevant planning doc)
- 直近 3 dated session logs (`.claude/memory/YYYY-MM-DD.md`) in full
- Related case study or dogfooding report
  (`docs/multi_agent_audit_case.md` / `docs/dogfooding_TC10_report.md` /
  `docs/dogfooding_real_pr_complexity.md` / etc.). For D-class hazard
  status start at `docs/dogfooding_findings_tracker.md` and follow links
  back to the originating report.
- `docs/code_semantic_ci_design.md` §23 (engine contract / boundary)
  before changing engine, evaluator, repair compiler, or adapter
  behavior
- `docs/ssp_protocol_design_note.md` (Brief 7 / SSP v0.1 一次資料、 旧
  AGENTS.md Forward Design Note から分離) only when touching Brief 7
  work

### Tier D — Debug / archeology only

- `.claude/memory/archive/` — compacted historical session logs
- 30 日以上前の dated session logs
- 旧 `STATUS.md ## 直近 merged` log (after Phase 1 archive)

If the memory is stale or incomplete, surface that in the response
rather than acting without it.

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
    main.py              # argparse entry; subparser for 9 subcommands
    commands/            # one module per subcommand
      observe.py
      compare.py
      check.py
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
  ssp/                   # Semantic Security Protocol v0.1 (Brief 7)
    models.py            # Pydantic v2 models (SensorOutput, Finding, SSPDelta, etc.)
    fingerprint.py       # SAST 5-element + SCA 3-element canonical fingerprint
    python_profile.py    # AST normalization for SAST normalized_text
    delta.py             # compute_delta + ordinal assignment
    verdict.py           # per-sensor + aggregate verdict
  test_surface/          # CSCI-9
tests/
  cli/                   # CLI integration tests
  compiler/              # CSCI-12
  delta/                 # CSCI-11
  evaluator/             # CSCI-13
  pipeline/              # CSCI-10
  repair/                # CSCI-14
  repair_compiler/       # Brief 5
  ssp/                   # SSP models, fingerprint, delta, verdict tests
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
| `docs/cli_usage.md` | ACTIVE | User-facing CLI contract for all 9 subcommands (`init` / `observe` / `compare` / `check` / `compile` / `compile-repair` / `validate-plan` / `target-doctor` / `target-catalog`), target discovery, format selection, target authorship, severity routing |
| `docs/exit_codes.md` | ACTIVE | Stable CLI exit code policy (0 / 1 / 2 / 3 / 4) for CI integration, including `--strict-repair`, `severity: info` Advisor channel, and per-subcommand notes |
| `docs/json_schema.md` | ACTIVE | CLI JSON envelopes — verdict / compile at `schema_version="4"`, compile-repair / validate-plan at independent `schema_version="1"`. Includes compatibility policy and v2→v3 / v3→v4 diffs |
| `docs/cli_test_inventory.md` | ACTIVE | CLI test coverage inventory, runtime notes, and conservative reduction candidates |
| `docs/target_yaml_guide.md` | ACTIVE | `target.yaml` authoring guide. Practical companion to `design.md §4` / `cli_usage.md`. Centralises authoring hazards D1 (`--package-root` scope vs `tests/` visibility), D3 (template / user constraint duplication), D4 (config-only PR の vacuous PASS) — 2026-05-07 Session 4 dogfooding 由来 |
| `docs/target_authoring_surface.md` | ACTIVE | Authoring surface 設計契約 (Brief 8 / CSCI-41)。target.yaml は hand-written 必須でない / 生成経路 3 通り (recipe + sources / catalog 参照 / hand-written) / LLM 経路は Brief 8b 分離 / 全経路は verdict 前に declared intent として固定 / Authoring・Advisor・Provenance surface は evaluator 不可参照 / `candidate_code_used: false` 固定。§23.3.1 の実装側 catch-up |
| `docs/ssp_protocol.md` | ACTIVE | SSP v0.1 normative spec: SensorOutput / Finding / SSPDelta / SSPVerdict definitions, 5-element SAST + 3-element SCA fingerprint, Python profile AST normalization, delta computation, verdict precedence (`unknown > fail > pass`), JSON Schema artifact, Sensor Provenance Invariant (§23.1 mirror), determinism requirements, core isolation contract |
| `docs/ssp_usage_guide.md` | ACTIVE | SSP practical usage guide: quick start (Semgrep SAST / pip-audit SCA / fixture mode), output formats (JSON / human / SARIF), CI integration (GitHub Actions workflow / exit code routing / fixture-based CI), hand-built SensorOutput examples, delta computation overview, relationship to core Semantic CI |
| `docs/brief_7_planning.md` | PLANNING (open) | Brief 7 (Semantic Security Protocol / SSP v0.1) を CSCI-36〜40 想定で planning する文書。Issue #48 の Semgrep 統合提案を audit した結果、core への深い統合は reject、SSP として §20.1 layered distribution の 4 層目(suite と並列)に独立配置。SAST + SCA / Python only / 5 要素 fingerprint(`rule_id × module_path × qualified_name × normalized_text × ordinal`、PR #50 review で 4→5 に拡張)+ 言語プロファイル分離 / 独立 envelope + Sensor Provenance Invariant(§23.1 鏡像)。Brief 6(TypeScript)凍結に伴い順序は **Brief 5 → 7**。CSCI-36 着手時は本文書 §11 checklist + `docs/ssp_protocol_design_note.md` を逐語参照 |
| `docs/ssp_protocol_design_note.md` | DESIGN NOTE (Brief 7 implementer 用 一次資料) | Brief 7 / SSP v0.1 の設計申し送り 11 項目 + Brief 5 からの学び 3 項目 + 設計 AI への推奨判断。 2026-05-07 に user から提供、 当初 AGENTS.md Forward Design Note inline、 2026-05-21 Phase 4 で本 doc に分離。 CSCI-36 Task Brief 起草・実装時の逐語参照対象。 SSP は semantic-ci core を太らせない sibling protocol、 SAST + SCA、 Python only、 5 要素 fingerprint、 Sensor Provenance Invariant、 unknown/error semantics 等の全申し送りを集約 |
| `docs/brief_resultstatus_planning.md` | PLANNING (open) | ResultStatus.UNKNOWN を authoring と extraction に分離する brief の planning。**C+B 仮固定**(C=authoring を compile-time に押し戻す / B=`results[].unknown_cause` optional field、A=enum 拡張は不採用)。D2: authoring は unknown_policy 非尊重で強制 fail、extraction は尊重。D3: validate-plan v2 で `risk_summary.authoring_errors` を `would_violate` から分離。Brief D1-1〜D1-4 + D3 の 5 PR 想定。§1b で Brief 8 (Authoring Surface) との境界(semantic hazard vs syntactic/type error / INV-1 framing / ADVISORY-S1 文言更新見込み / 着地順序 open question)を pin。target path 静的型カテゴリ + operator-required-category 行列 + compile catch coverage 推定済 |
| `docs/doc_refactor_planning.md` | PLANNING (open) | **緊急 doc refactor planning (2026-05-21 起草)**。 起動時 attention budget が ~2,500 lines に膨張、 経験値外部化 framework 自身が膨張する逆説にハマっている懸念を受けて起草。 Tier A/B/C/D 階層化 + `_index.md` 本来仕様復元 + STATUS.md compaction + AGENTS.md §5 collapse + archive infrastructure + test-enforced rule 変換の 8 phase、 8 PR / 4-6 日規模。 最短経路 (Phase 0+2+1) を 1 session 連続で attention budget を 2,500 → 800 lines に圧縮可能。 完了後は本 doc 自身を `archive/` 移送 (self-referential dogfood example) |
| `docs/source_selection_planning.md` | PLANNING (open) | **Candidate / baseline source selection planning (2026-05-22 起草、 正式採用)**。 PR #98 (`--allow-dirty` Phase 1 mitigation) が surface した CLI 設計 hole を 3 phase で閉じる。 Phase 2 = `--candidate-source {commit,working-tree}` + `--allow-dirty` 削除 + JSON envelope provenance。 Phase 3a = `--baseline-source` 対称化 + `staged-index` source 追加。 Phase 3b = `pre-commit` subcommand 削除 + `.pre-commit-hooks.yaml` を `check --candidate-source=staged-index` に migration。 style = aggressive / clean-cut (no alias, no deprecation period)。 engine `§23.1` input neutrality は不変、 sourcing は CLI 層単独責務 |
| `docs/archive/brief_5_planning.md` | REFERENCE (Brief 5 完走 2026-05-07) | Brief 5 (Repair Compiler + Vibe Coding Adapters、P2.5 entry) を CSCI-31〜35 の 5 PR に分割した planning 文書。CSCI-31〜35 全 PR merged で `compile-repair` / `validate-plan` 2 subcommand + Claude Code / Cursor / Codex 3 adapter が release 可能。Brief 3 残課題 #4(Repair Compiler)+ §21.3 adapter list + `pre_generation_validation_case.md` 残された問い #4 を救済済み。Brief 7 起草時の参照として保存 |
| `docs/archive/brief_4b_planning.md` | REFERENCE (Brief 4b 完走 2026-05-05) | Brief 4b (CI integration outputs) を CSCI-28 に集約した planning 文書。SARIF 2.1.0 / GitHub Actions annotation / `.pre-commit-hooks.yaml` manifest を 1 PR で完結。Brief 4 Open Questions Q9/Q10/Q11 を救済 |
| `docs/archive/brief_4_planning.md` | REFERENCE (Brief 4 完走 2026-05-04) | Brief 4 (CLI / operational entrypoint) を CSCI-15〜19 に分割した planning 文書。CSCI-15〜19 全 PR merged で `semantic-ci` CLI 5 subcommand が release 可能。残 Open Questions は Brief 4b / 4c / 4d / 5 で消化済み |
| `docs/archive/brief_3_planning.md` | ARCHIVED (Brief 3 完走) | Brief 3 (pipeline 統合) を CSCI-10〜14 に分割した planning 文書。当時の判断履歴として保存(operator 5 個案などの一部記述は CSCI-12 brief で上書き済み) |
| `docs/dogfooding_TC10_report.md` | DOGFOOD REPORT (2026-05-07 Session 5) | 仮想 Python パッケージ 10 ケースで `compare` / `validate-plan` / `compile-repair` を end-to-end 検証。FINDING-1(set operator partial-dict mismatch → D5、PR #65 で fix 済)、FINDING-2(`equals_baseline` の structured added/removed 欠落、PR #61 で fix 済)、FINDING-3(`compile-repair` schema_version 不一致 warning 追加、PR #61 で fix 済)。D-class 状態は `docs/dogfooding_findings_tracker.md` に集約 |
| `docs/dogfooding_real_pr_complexity.md` | DOGFOOD REPORT (2026-05-28) | 公開 Python リポジトリの実 PR 8 件(refactor 7 + feature 1)に complexity 制約を宣言した `target.yaml` で `semantic-ci check` を回した dogfooding pass。6/8 で tool 判断が reviewer 関心信号と一致、1/8 で vacuous PASS = FINDING-F1 → **D6**(nested-function blind spot、D4 の sibling)、1/8 で authoring mismatch = FINDING-F2 → **D7**(extract-method × cyclomatic の数学的微増)。D-class 状態は `docs/dogfooding_findings_tracker.md` に集約 |
| `docs/dogfooding_findings_tracker.md` | DOGFOOD REPORT (集約 tracker) | 全 dogfooding pass を跨いだ D-class findings の単一管理表。D1〜D7 を `解決 / 未解決 / 重複・関連(sibling-class)` で分類、 originating pass・mechanism・mitigation を 1 表に集約。 既存 dogfooding report 内に分散していた D# tracker をここに集約し、 各 report は cross-link のみ保持する形にリファクタ済(2026-05-28) |
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

実行内容 (本 wrap-up):

1. 会話の振り返りサマリーを `.claude/memory/YYYY-MM-DD.md` に保存
   (新規 file or 同日 Session N として追記)
2. `_index.md` に **1-2 行** サマリーを追記 (本来仕様の index format、
   essay 化 anti-pattern を回避。 col: Date | PR/commit | One-line
   outcome | Detail。 `docs/doc_refactor_planning.md` Phase 2 で復元
   された format に従う)
3. **30 日以上前の dated entries を `archive/YYYY-MM/` に移送**
   (自動 compaction、 移送後の `_index.md` 該当行は 1 行 summary + archive
   path に書換、 dated file 本体は archive に原文保存)
4. **`STATUS.md 次の発行順序` の sweep** (CLAUDE.md rule:
   `If a CSCI / Brief / D# item is closed, remove the corresponding
   entry from 次の発行順序`。 stale entry 検出時は削除して 直近 merged
   に移送、 `tests/discipline/test_status_md_next_queue_no_completed.py`
   (Phase 6 で導入予定) で自動検出される rule)。 **step 5 (直近 merged
   compaction) より先に行うこと** — sweep が完走 entry を 直近 merged
   に move したのち compaction で 5 cap を再評価する単一 pass を実現する
   ため (PR #92 review で指摘)
5. **`STATUS.md ## 直近 merged` で 5 entries 超過分を
   `archive/STATUS_MERGED_LOG.md` に移送** (Phase 1 で確立した archive
   経路、 最新 5 のみ inline、 残りは archive 参照)。 step 4 の sweep
   後に実行することで「sweep が cap 超過を再導入する」 race を回避
6. **`STATUS.md ## Phase` の上書き check** (新 paragraph 追加時は旧
   paragraph を必ず削除、 1 paragraph 厳守。 5/21 で Codex / Claude
   両方が再発させた drift category、
   `tests/discipline/test_status_md_phase_single_paragraph.py` (Phase 6)
   で自動検出される rule)
7. **5+ round 論点の encode check**: 当 session で review / 壁打ちが 5
   round 以上に達した曖昧 spec があれば、 その解決を docs / tests に
   encode 済か確認し、 未 encode なら externalize する (Experience
   Externalization の核。 `docs/doc_refactor_planning.md` Phase 6 で test
   化を検討したが、 round 数は hand-written prose proxy で脆く「encode
   忘れ」 case こそ検出できないため checklist 項目として常駐させる判断)。
   併せて `CLAUDE.md` / `AGENTS.md` への更新候補があればユーザーに提案する
8. **memory 直 push 前に `pytest tests/discipline/ -q --no-cov` を実行
   し `tests/discipline/` 全 test pass を確認**。 fail がある場合は step
   4-6 のいずれかで drift が残っているので push せず該当 file を修正。 memory exception
   (`.claude/memory/` 直 main push 許可) は **PR ceremony を省く**
   ためのものだが、 PR 経由と異なり **post-hoc 検出のみ** なので
   discipline test 違反があると main branch が直接 red になる。
   step 8 (約 5 秒) を **必ず実行** することで、 memory exception の
   速度メリットを保持しつつ品質崩壊を構造的に抑止する。 同 rule は
   Codex / 並列 agent / 任意の direct main push 経路すべてに適用

Anti-pattern (`AGENTS.md §5.5` の対応 row 参照):

- `_index.md` entry を essay 化させる (Phase 2 で 53KB → 5KB 復元の前例、
  cell ≤ 500 chars constraint は
  `tests/discipline/test_index_md_entry_compactness.py` で enforce 予定)
- 完走済 CSCI を `次の発行順序` に残置 (5/21 で ADVISORY-S1 + R17 で 2
  連続発生、 PR merge 直後の即時 sweep が必須)
- `## Phase` に新 paragraph を追加するが旧 paragraph を残置 (5/21 で
  Codex follow-up で初回発生、 Claude の今回 session 直前にも発生する
  drift)
- archive 移送を「後で」 と先送り (30 日経過 dated entry の archive 移送
  を session wrap-up 時に必ず実行、 後述 archive policy 参照)
- **discipline test の pre-push verification を skip して memory を直
  main push する** (step 8 違反): post-hoc 検出のみのため main red を
  直接引き起こす。 PR 経由なら CI 赤で merge ブロックされて検出するが、
  memory exception 直 push では fail 後の main が red になるまで気付かない

### Archive policy (compaction TTL)

`.claude/memory/` の disk-resident artifact は以下の TTL で archive 移送:

| Artifact | TTL | 移送先 | 移送後の本体 source |
|---|---|---|---|
| dated session log `YYYY-MM-DD.md` | 30 日 | `archive/YYYY-MM/YYYY-MM-DD.md` | 原文保存 (情報損失ゼロ) |
| `_index.md` の対応 entry | 同上 | inline → 1 行 summary + archive path 追記 | 詳細は archive file 経由で参照可 |
| `STATUS.md ## 直近 merged` entry | 直近 5 を超えた時点 | `archive/STATUS_MERGED_LOG.md` 末尾 | 原文保存 |
| `STATUS.md 次の発行順序` の 完走 entry | merge と同時 | `## 直近 merged` の新 entry に変換 | 完走宣言として保存 |
| `STATUS.md ## Phase` paragraph | 上書き時 | (保存しない、 1 paragraph 厳守) | 旧 phase の history は dated session log / `_index.md` に分散保存 |

Archive infrastructure は `.claude/memory/archive/` directory + index file
(`archive/INDEX.md`) で管理 (Phase 5 で完備予定)。 archive 移送は
**memory exception 枠**で main 直 push 可能 (本 Git Workflow の例外
section 参照)。

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

## Experience Externalization (経験値の外部化)

AI 開発 (Claude / Codex / 並列 agent 運用) は session 跨ぎの暗黙知を継承
しない: Claude は long-term memory を持たず、 Codex は PR 単位の review
trail 以外を学習しない。 user の壁打ち経験も session 跨ぎで永続化されない
限り消失する。

この制約下で再現性を維持する唯一の方法は、 経験値を **明示 artifact** に
強制的に外部化することである:

- **docs** に encode (planning / spec / case study / authoring guide)
- **test** に encode (`tests/architecture/` invariant test、 producer-spec
  contract test、 parametrize で near-miss shape を列挙)
- **checklist** に encode (`docs/brief_8_planning.md §15` brief drafting
  checklist 8 sub-section、 20 round 蒸留)
- **pattern catalog** に encode (AskUserQuestion N 択 trade-off / dogfood
  fail+pass 両方実演 / architecture test 先行 等)

経験を「腕の感」 として個人 / agent に閉じる形は AI 開発では **機能しない**。
PR #82 (16 round) / PR #84 (13 round) の累計 29 round で表面化した P2 を
`tests/authoring/test_canonical.py` 48 cases + `tests/architecture/` 16
tests に encode した結果、 後続 PR #85 / #86 / #87 が 0 round で landing
した因果は本リポジトリの empirical base case。

詳細な 3-tier 分類 (codified / repo-specific / session-tacit)、 review
round 数を leading quality indicator として運用する原則、 規律を壊さない
ための maintenance practice、 anti-pattern 列挙は `AGENTS.md` §
Experience Externalization Discipline に集約。 新 brief 起草前 / 新
architectural pattern 導入前は逐語参照する。
