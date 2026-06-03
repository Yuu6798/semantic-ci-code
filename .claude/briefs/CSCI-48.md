# Task Brief: CSCI-48 (Phase G-4a) - Wire suite security verdict into `check` (prebuilt SensorState)

## Phase

Phase G (SSP core integration) の 4 本目、その第 1 スライス。
`docs/phase_g_planning.md` §3 (Phase G-4) が canonical。G-3 (CSCI-47, PR #127)
で `suite/evaluator.py` (`combine_verdict` / `SuiteVerdict`) +
`suite/security.py` (`evaluate_security`) + `framework/security_policy.py`
(`SecurityPolicy`) が merged 済み。本 brief はそれを **CLI 層 (`check`)** に
配線し、code verdict と security verdict を統合した結果を出力・exit code に
反映するところまで。

**G-4 の分割 (本 session で確定)**: planning §3 G-4 は 4 deliverable
(check 配線 / JSON・human・SARIF 出力 / migrate-suppressions / ssp deprecation)
を含むため分割。**本 brief = G-4a** に以下を絞る:

- IN: `check` への prebuilt SensorState ingest + suite verdict + JSON/human 出力
  + exit code routing
- 後続 (G-4b/c、本 brief OUT): **SARIF 出力** / **per-sensor security 詳細の
  output 拡張** / **live `--sensor semgrep --config` スキャン実行** /
  **`migrate-suppressions` CLI** / **`ssp scan` / `ssp from-json` deprecation
  notice** / `compare` への parity

**sensor 入力方式 (本 session で確定)**: verdict 経路は **prebuilt SensorState
JSON ingest のみ** (`--sensor-baseline X.json --sensor-candidate Y.json`)。
決定論的・hand-built fixture で test 可能・§23.1 input neutrality を完全維持
(Scope Guard §5)。live scanner 実行 (semgrep/pip-audit を起動) は G-4b に分離。

## Goal

`semantic-ci check --sensor-baseline baseline.json --sensor-candidate
candidate.json` で、git worktree 由来の code verdict と prebuilt SensorState
由来の security verdict を `combine_verdict` で統合し、`unknown > fail >
repair > pass` の suite final verdict を JSON/human で出力し exit code に反映
する。sensor flag 不在時は従来の code-only 動作を完全保持する。

## Acceptance Criteria

### A. CLI flags (parser + consumption + provenance, §15.4)

- [ ] `check` に `--sensor-baseline PATH` / `--sensor-candidate PATH` を追加。
      **両方指定 or 両方不在** のみ許容。片方のみ → usage error (exit 2、
      `docs/exit_codes.md` の `2` 行)。
- [ ] `check` に `--as-of YYYY-MM-DD` を追加 (suppression 期限評価用)。default は
      CLI 境界で `datetime.date.today()` を読む (CLI は不純境界として clock 読取
      可、suite/engine は不読を維持 = §23.1)。不正な日付文字列 → usage error (2)。
- [ ] sensor flag 不在時: payload に `security` 関連は出さず、exit code は従来の
      `_exit_code_for(verdict.result, strict_repair=...)` 経路を**完全保持**
      (既存 `tests/cli/` 全 green)。

### B. SensorState ingest (§23.1 中立、prebuilt JSON のみ)

- [ ] `--sensor-baseline` / `--sensor-candidate` の各 JSON を
      `SensorState.model_validate_json` で読む。ファイル不在 / 不正 JSON /
      schema 不適合 → usage error (exit 2、`compile-repair` の invalid JSON →
      exit 2 と同方針)。
- [ ] live scanner (semgrep/pip-audit subprocess) を**一切起動しない**。
      `grep -rn "subprocess\|\.scan(" src/semantic_ci_code/cli/commands/check.py`
      が 0 件であること (本 brief は prebuilt JSON ingest のみ)。

### C. Policy threading + suite 統合

- [ ] target.yaml の `security:` (`TargetSVP.security`) を `evaluate_security`
      まで到達させる。現状 `CompiledTarget` は `security` を持たない (compiler 未
      propagate)。**推奨**: `CompiledTarget` に `security: SecurityPolicy | None
      = None` を pass-through 追加し、`_build_compiled_target` で
      `target_svp.security` をそのままコピー (compile ロジック不要、suite が
      framework model を直接消費)。`load_compiled_target` 経由で `check` が
      `compiled.security` を読む。
- [ ] `check` で sensor flag 指定時:
      ```
      security_status = evaluate_security(
          compiled.security, baseline_sensor, candidate_sensor, as_of=as_of)
      suite = combine_verdict(verdict.result, security_status)
      ```
      を `evaluate_constraints` の後・`build_payload` の前で算出。
- [ ] `compiled.security is None` (target に `security:` 無し) でも sensor flag が
      指定されていれば default floor で評価される (`evaluate_security(None, ...)`
      は G-3 で実装済の default floor 経路)。

### D. 出力 (JSON / human)

- [ ] `build_payload` を additive-optional に拡張: sensor flag 指定時のみ
      `security` オブジェクト (`{ "verdict": <pass|fail|unknown>, "as_of":
      "<YYYY-MM-DD>" }`) と suite verdict (`"suite_verdict": <pass|repair|fail|
      unknown>`) を出力。不在時は両 key を出さない (または `null`)。
      **per-sensor 詳細 (added/removed/drift/suppressed 件数) は G-4b に defer**。
- [ ] `docs/json_schema.md` の compatibility policy に従い envelope を更新
      (additive optional field)。policy が新 field で version bump を要求するなら
      verdict envelope `schema_version` を `4`→`5` に上げ、v4→v5 diff を記載。
      additive-optional が version 据置で許容されるなら据置の根拠を明記
      (§15.1c / §15.7 — schema doc と実装を必ず sync)。
- [ ] human formatter: sensor flag 指定時に security verdict 行 + suite final
      verdict 行を出力。不在時は出力不変。

### E. Exit code routing

- [ ] suite final → exit code を `docs/exit_codes.md` に追記:
      `final == pass` → 0 / `final == repair` → 0 (`--strict-repair` で 1) /
      `final == fail` → 1 / `final == unknown` → 3 (ENGINE_ERROR、既存
      `cli/commands/ssp.py:_exit_code` の `unknown → ENGINE_ERROR` と整合)。
- [ ] sensor flag 指定時は `verdict.result` ではなく `suite.final` から exit code
      を導出。security `fail` で code `pass` でも exit 1。security `unknown` は
      code verdict に関わらず exit 3。
- [ ] sensor flag 不在時の exit code は従来不変。

### F. Tests

- [ ] hand-built SensorState JSON fixture (baseline/candidate) で `check` を回す
      CLI integration test。**dual-case**: security `fail` で suite=fail/exit 1、
      security `pass` で code 由来の verdict/exit。
- [ ] security `unknown` (provenance drift fixture) → suite=unknown / exit 3。
- [ ] sensor flag 片方のみ → exit 2。不正 JSON → exit 2。
- [ ] sensor flag 不在の既存 `check` 動作回帰 (code-only verdict / exit code 不変)。
- [ ] target に `security:` policy を書いた fixture + sensor JSON で policy が
      効く (例: `deny_added` で fail) end-to-end test。
- [ ] `--as-of` で expired suppression が active/inactive を切替える test
      (clock 非依存・再現可能であることの確認)。

## Scope

- IN:
  - `src/semantic_ci_code/cli/main.py` (check subparser に 3 flag 追加)
  - `src/semantic_ci_code/cli/commands/check.py` (ingest + suite 統合 + exit 分岐)
  - `src/semantic_ci_code/cli/output/json_formatter.py` (`build_payload` additive)
  - `src/semantic_ci_code/cli/output/human_formatter.py` (security/suite 行)
  - `src/semantic_ci_code/cli/output/__init__.py` (必要なら exit helper)
  - `src/semantic_ci_code/compiler/target_compiler.py` (`CompiledTarget.security`
    pass-through のみ)
  - `docs/exit_codes.md` / `docs/json_schema.md` / `docs/cli_usage.md` (新 flag)
  - `tests/cli/` (integration) + 必要な fixture
- OUT:
  - **SARIF 出力** / **per-sensor security 詳細出力** = G-4b
  - **live `--sensor semgrep --config` スキャン実行** = G-4b
  - **`migrate-suppressions` CLI** / **`ssp` deprecation notice** = G-4c
  - `compare` / `observe` への配線 (本 brief は `check` のみ)
  - `suite/` のロジック変更 (`evaluate_security` / `combine_verdict` は不変で使う)
  - `evaluator/` core / `CodeState` / `delta/` / `sensor/` schema 変更
  - security policy の DSL 拡張 (G-3 確定形を使う)

## Allowed Dependencies

なし (新規依存禁止)。`datetime` は stdlib。

## Implementation Hints

- 統合点は `check.py:220-250` (`verdict = evaluate_constraints(...)` の直後)。
  `build_payload` 呼び出しに `security_status` / `suite_final` を渡す形が最小。
- exit code は `suite.final` 用の小 helper (`_exit_code_for_suite(final,
  strict_repair)`) を `cli/output/__init__.py` に追加し、既存
  `_exit_code_for` と並置すると test しやすい。
- `CompiledTarget.security` は **compile しない pass-through** (suite が
  framework の `SecurityPolicy` を直接消費するため)。`authorship` の
  thread パターンとは異なり変換不要。
- fixture は G-3 の `tests/suite/helpers.py` の hand-built SensorState builder を
  参考に、JSON 化して `tests/cli/fixtures/` に配置すると determinism test と
  両立する。

## Required Outputs

- Branch name: `codex/csci-48-cli-suite-verdict`
- PR title: `feat(cli): wire suite security verdict into check via prebuilt SensorState (CSCI-48)`
- Expected files changed: 上記 Scope IN の各ファイル + `tests/cli/` 追加
- Required tests: AC F の各ケース

## Done When

- All acceptance criteria are checked
- `ruff check .` / `ruff format --check .` pass
- `python -m pytest -q` pass
- `python scripts/regen_schemas.py --check` pass (schema 変更時は regen 込み)
- PR body は Completion Summary (`AGENTS.md §2`) で開始、JSON envelope の
  schema_version 判断 (据置 or 4→5) の根拠を明記

## Required Reading (Codex 実装前)

1. `docs/phase_g_planning.md` §3 (Phase G-4) + §4 移行戦略 + §5 Scope Guard
2. `src/semantic_ci_code/suite/` 全体 (`evaluate_security` / `combine_verdict`
   / `SuiteVerdict` の signature)
3. `src/semantic_ci_code/cli/commands/check.py` (verdict→payload→exit の現行経路)
4. `src/semantic_ci_code/cli/output/json_formatter.py` `build_payload` +
   `cli/commands/ssp.py:_exit_code` (unknown→3 の前例)
5. `docs/exit_codes.md` / `docs/json_schema.md` (compatibility policy)
6. `src/semantic_ci_code/sensor/models.py` `SensorState` (ingest 対象 schema)
