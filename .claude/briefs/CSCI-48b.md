# Task Brief: CSCI-48b (Phase G-4b) - Per-sensor security detail in JSON / human / SARIF

## Phase

Phase G (SSP core integration) G-4 の第 2 スライス。`docs/phase_g_planning.md`
§3 (Phase G-4 の「JSON / human / SARIF 出力」) が canonical。G-4a (CSCI-48,
PR #128) で `check --sensor-baseline/--sensor-candidate` の SensorState ingest
+ `suite_verdict` + exit code + **集約 verdict のみの** `security: {verdict,
as_of}` JSON が merged 済み。本 brief はそれを **per-sensor 詳細出力** に拡張
する (added/removed/suppressed findings + drift reason を JSON / human / SARIF
の 3 format に)。

**本 session で確定した設計判断**:

- **粒度 = 完全詳細**: JSON `security` に per-sensor breakdown (status / added
  findings 完全オブジェクト / removed / suppressed findings / drift_reason /
  unchanged_count) を出す。
- **SARIF = code constraint と同一 run にマージ**: security finding を既存
  `format_sarif` の `runs[0].results` に追加。severity→level は
  **critical/high = `error` / medium = `warning` / low・info = `note`**。

G-4a で defer した残: **live `--sensor semgrep --config` scan = G-4c** /
**`migrate-suppressions` + ssp deprecation = G-4d** (本 brief OUT)。

## Goal

`check --sensor-baseline X.json --sensor-candidate Y.json` の出力を、集約
verdict だけでなく per-sensor の security finding 詳細まで含むよう JSON /
human / SARIF の 3 format で拡張する。`suite_verdict` / exit code / verdict
semantics は G-4a から不変。

## Acceptance Criteria

### A. suite に detail 返却関数を新設 (既存契約維持)

- [ ] `suite/security.py` に `evaluate_security_detail(policy, baseline,
      candidate, *, as_of) -> SecuritySuiteResult` を新設。`SecuritySuiteResult`
      (frozen dataclass) は最低限:
  - `status: SecurityDeltaStatus` (aggregate、現行 `evaluate_security` と一致)
  - `as_of: dt.date`
  - `sensors: tuple[SecuritySensorResult, ...]` (sensor_id 昇順)
  - `global_count_violated: bool` (`_violates_global_count_policy` 由来)
  - `SecuritySensorResult`: `sensor_id` / `status` / `added: tuple[SecurityFinding,
    ...]` (post-suppression) / `removed` / `suppressed: tuple[SecurityFinding,
    ...]` (active suppression で除外された added) / `drift_reason: str | None`
    (per_sensor.error_message) / `unchanged_count: int`
- [ ] `evaluate_security(...)` は `evaluate_security_detail(...).status` を返す
      薄い wrapper に再実装。**既存の戻り値型・semantics・全 G-3 テストは不変**
      (`tests/suite/test_security.py` 無改変で green)。suppression 検証 /
      drift_fields / global count policy / effective_fail_severities の挙動は
      detail 関数内に集約し重複を作らない。
- [ ] `suppressed` は active suppression に一致して `added` から除外された
      finding を full object で保持 (`security.sensors[].suppressed` の source)。

### B. JSON 出力拡張 (additive、schema_version 据置 "6")

- [ ] sensor flag 指定時、`security` オブジェクトを G-4a の `{verdict, as_of}`
      から拡張: `sensors: [{sensor_id, status, added: [<finding json>...],
      removed: [...], suppressed: [...], drift_reason, unchanged_count}]` を追加。
      finding は `SecurityFinding.model_dump(mode="json")` で直列化 (discriminated
      union の `category` 込み)。`verdict` / `as_of` は維持。
- [ ] **G-4a の exact-match assertion を更新**: `tests/cli/test_check.py` の
      `data["security"] == {"verdict": ..., "as_of": ...}` 系 (fail/pass/unknown
      の 3 test) は richer object に合わせて更新する (subset assertion か、
      full expected dict に `sensors` を追加)。これは G-4b の予定された破壊なので
      AC に明記。
- [ ] `docs/json_schema.md` を更新: `security.sensors[]` の shape を記載。
      schema_version は **据置 "6"** (additive。G-4a と同方針)。据置の根拠を明記。
- [ ] sensor flag 不在時は従来通り `security` / `suite_verdict` を出さない (回帰)。

### C. human 出力拡張

- [ ] sensor flag 指定時、既存の "Security verdict" / "Suite final" 行に加え、
      sensor ごとに added findings を列挙 (rule_id|advisory_id / severity /
      message / SAST は module_path:line)。suppressed 件数 + drift_reason
      (unknown 時) も表示。不在時は出力不変。

### D. SARIF 出力拡張 (同一 run マージ)

- [ ] `cli/output_sarif.py` `format_sarif` を拡張: `payload.get("security")` が
      あれば per-sensor の added findings を **同一 `runs[0].results`** に
      SARIF result として追加し、対応する rule を `driver.rules` に登録 (ruleId
      重複は dedup)。
- [ ] severity→SARIF level: **critical/high = `error` / medium = `warning` /
      low・info = `note`**。code constraint の既存 `_level` は不変。
- [ ] security SARIF result:
  - `ruleId`: SAST = `security/{rule_id}` / SCA = `security/{advisory_id}`
    (code constraint ruleId と衝突しない namespace)
  - `message.text`: finding.message (空なら fallback 文)
  - `properties`: `{category, sensor_id, severity, canonical_id}`
  - SAST で `source_span` があれば `locations` に physicalLocation
    (`artifactLocation.uri = module_path`, region = source_span)。SCA や
    source_span 無しは `locations` 省略。
- [ ] **drift (unknown) sensor**: 当該 sensor につき level `note` の result を 1 件
      (ruleId `security/provenance-drift`、message = drift_reason) 出して crash
      しない。
- [ ] **決定論性**: security result は sensor_id 昇順 → finding canonical_id 昇順で
      安定出力。`executionSuccessful` は True 維持。

### E. Tests

- [ ] JSON: per-sensor detail を含む `check` integration test (added/removed/
      suppressed/drift_reason/unchanged_count を検証)。fail/pass/unknown 各ケース。
- [ ] human: added finding 行 + suppressed 件数 + drift 行の出力 test。
- [ ] SARIF: `check --format sarif` + sensors で security result が同一 run に出る
      / severity→level mapping (error/warning/note) / ruleId namespace /
      SAST source_span → location / SCA は location 無し / drift→note を検証。
      SARIF は valid JSON で決定論的 (同一入力同一出力)。
- [ ] `evaluate_security` の戻り値が detail 関数経由でも従来と一致する回帰
      (G-3 既存 test 全 green)。
- [ ] sensor flag 不在時の `check` 出力 (JSON/human/SARIF) が G-4a と不変。

## Scope

- IN:
  - `src/semantic_ci_code/suite/security.py` (detail 関数 + result dataclass、
    `evaluate_security` の wrapper 化)
  - `src/semantic_ci_code/cli/commands/check.py` (detail を build_payload へ)
  - `src/semantic_ci_code/cli/output/json_formatter.py` (`security.sensors`)
  - `src/semantic_ci_code/cli/output/human_formatter.py` (finding 列挙)
  - `src/semantic_ci_code/cli/output_sarif.py` (security results 同一 run)
  - `docs/json_schema.md` / `docs/cli_usage.md`
  - `tests/cli/` / `tests/suite/` (detail 関数の unit test)
- OUT:
  - **live scanner 実行** (`--sensor semgrep --config`) = G-4c
  - **`migrate-suppressions` / ssp deprecation** = G-4d
  - `suite_verdict` / exit code / verdict semantics の変更 (G-4a 確定形を維持、
    `docs/exit_codes.md` 不変)
  - `evaluate_security` の戻り値型・判定 semantics の変更 (detail は新 surface、
    既存契約は不変)
  - `combine_verdict` / `framework/security_policy` / `sensor/` schema /
    `compute_security_delta` のロジック変更
  - `compare` / `observe` への配線

## Allowed Dependencies

なし (新規依存禁止)。

## Implementation Hints

- detail 関数は現行 `evaluate_security` の per-sensor loop をそのまま使い、捨てて
  いた `added` (post-suppression) / `suppressed` (= per_sensor.added ∩
  active_suppression_ids) / `removed` / `per_sensor.error_message` を集めて
  `SecuritySensorResult` に詰めるだけ。判定ロジックは一切変えない。
- `global_count_violated` は `_violates_global_count_policy(policy,
  total_added_count)` を detail 内で 1 回評価し result に格納 → `status` 計算と
  JSON 出力で再利用。
- SARIF rule dedup は `{ruleId: rule_dict}` の dict で既存 `_rules_for_results`
  パターンを踏襲。
- finding 直列化は pydantic の `model_dump(mode="json")` で discriminated union
  が `category` 付きで出る。human/SARIF は dict から読む。

## Required Outputs

- Branch name: `codex/csci-48b-security-output-detail`
- PR title: `feat(cli): emit per-sensor security detail in JSON/human/SARIF (CSCI-48b)`
- Expected files changed: 上記 Scope IN
- Required tests: AC E の各ケース

## Done When

- All acceptance criteria are checked
- `ruff check .` / `ruff format --check .` pass
- `python -m pytest -q` pass
- `python scripts/regen_schemas.py --check` pass
- PR body は Completion Summary (`AGENTS.md §2`) で開始、`security` object 拡張で
  schema_version を据置にした根拠を明記

## Required Reading (Codex 実装前)

1. `docs/phase_g_planning.md` §3 (Phase G-4) + §5 Scope Guard
2. `src/semantic_ci_code/suite/security.py` 全体 (detail に集約する判定ロジック)
3. `src/semantic_ci_code/sensor/models.py` の `SASTSecurityFinding` /
   `SCASecurityFinding` / `SourceSpan` / `SecuritySeverity` (直列化・SARIF mapping)
4. `src/semantic_ci_code/cli/output_sarif.py` (`format_sarif` / `_sarif_result` /
   `_level` / `_location` の既存パターン)
5. `src/semantic_ci_code/cli/output/json_formatter.py` `build_payload` +
   `tests/cli/test_check.py` の G-4a security assertion (更新対象)
6. `docs/json_schema.md` (compatibility policy、additive 据置の前例)
