# Task Brief: CSCI-47 (Phase G-3) - Suite evaluator + target.yaml security namespace

## Phase

Phase G (SSP core integration) の 3 本目。`docs/phase_g_planning.md` §1.4 / §1.5 /
§1.6 / §2.1.1 / §2.3 / §3 (G-3) が canonical source。G-1 (CSCI-45, PR #124) で
`sensor/models.py` + `sensor/delta.py`、G-2 (CSCI-46, PR #125) で
`sensor/adapters/` が landed 済み。本 brief はその上に **suite 層** を新設し、
target.yaml の `security:` namespace でセキュリティ判定を宣言可能にする
(planning §0 「縦接続」 の中核)。

設計確定事項 (本 session で resolve 済み、planning §6 Open Questions):

- **Q1 (suite evaluator module placement)**: 別パッケージ `src/semantic_ci_code/suite/`
  新設で確定 (planning §5 Scope Guard「core evaluator は変更しない」+ STATUS.md)。
- **Q2 (security DSL の宣言場所)**: **案 A = target.yaml に `security:` top-level key
  統合** で確定。`TargetSVP` (`framework/target_svp.py`、`ConfigDict(extra="forbid")`)
  に `security: SecurityPolicy | None = None` を追加する。

## Goal

Hand-built な baseline/candidate `SensorState` と hand-built な `SecurityPolicy`
(target.yaml `security:` namespace) から、`unknown > fail > repair > pass` で
code verdict と security verdict を統合した `SuiteVerdict` を決定的に算出する
suite 層を新設する。CLI 配線・JSON/human/SARIF 出力・SSP v0.1 migration は **G-4
(CSCI-48) の scope なので本 brief には含めない**。本 brief は engine + schema +
evaluator を unit test (hand-built 入力、§23.1 鏡像) で検証可能にするところまで。

## Acceptance Criteria

### A. `security:` namespace schema (declared intent)

- [ ] `framework/target_svp.py` の `TargetSVP` に `security: SecurityPolicy | None = None`
      を追加。既存 field (`intent` / `change` / `api_surface` / `effects` /
      `constraints` 等) の宣言順・optionality は不変。`security` 不在の target.yaml は
      従来通り parse 成功し、既存テスト全互換 (`pytest -q tests/` green)。
- [ ] `SecurityPolicy` とその sub-model 群を **`framework/security_policy.py` (新設)**
      に定義し、周辺コード規約に合わせ `BaseModel` + `model_config =
      ConfigDict(frozen=True, extra="forbid")` を全モデルに付す
      (`APISurfacePolicy` / `EffectsPolicy` と同形)。schema は planning §2.3 verbatim:
  - `SecurityPolicy(findings, rules, scanner, suppressions)` — 全 optional
    (`suppressions: tuple[Suppression, ...] = ()`)
  - `FindingsPolicy(added: AddedFindingsPolicy | None = None)`
  - `AddedFindingsPolicy(severity: SeverityFilter | None = None, max_count: int | None)`
    — `max_count` は `Field(ge=0)`
  - `SeverityFilter(not_in: tuple[Severity, ...] = ())` — `Severity` は
    `Literal["critical","high","medium","low","info"]` (sensor.models.SecuritySeverity
    と同値。framework を sensor-free に保つため inline 定義、同値であることをコメントで明示)
  - `RulesPolicy(deny_added: tuple[str, ...] = ())`
  - `ScannerPolicy(require_same_ruleset: bool = True, require_same_sensor_version:
    bool = False, require_same_advisory_db: bool = True)` — default 値は planning §2.3
    の表 (default 行) と一致
  - `Suppression(canonical_id, identity_components, reason, expires, owner)` —
    planning §2.1.1 verbatim。`canonical_id: Annotated[str, Field(pattern=
    r"^v1:[0-9a-f]{16}$")]`、`identity_components: tuple[str, ...]`、
    `reason: Annotated[str, Field(min_length=1)]`、`expires: datetime.date`
    (YAML string `"2026-09-01"` を date として parse、失敗時 ValidationError)、
    `owner: Annotated[str, Field(min_length=1)]`
- [ ] **framework 層は sensor を import しない**: `framework/security_policy.py` の
      validation は **構造 validation のみ** (regex pattern / min_length / date parse)。
      `Suppression.canonical_id` と `identity_components` の **hash 整合性検証は行わない**
      (それは suite 層の責務、下記 C 参照)。これにより `framework/` は sensor-free を維持。

### B. suite verdict 統合 (`suite/evaluator.py` 新設)

- [ ] `SuiteResult` enum (`StrEnum`、values `pass` / `repair` / `fail` / `unknown`)
      と `SuiteVerdict` (frozen dataclass、`code: VerdictResult` / `security:
      SecurityDeltaStatus` / `final: SuiteResult`) を定義。`VerdictResult` は
      `evaluator/evaluator.py` から import (`pass`/`repair`/`fail`)、
      `SecurityDeltaStatus` は `sensor/models.py` から import (`pass`/`fail`/`unknown`)。
- [ ] `combine_verdict(code_result: VerdictResult, security_result: SecurityDeltaStatus)
      -> SuiteVerdict` を実装。aggregation precedence は **`unknown > fail > repair >
      pass`** (planning §1.5)。code 側に `unknown` は無く、security 側に `repair` は
      無いので、両者を precedence ladder にマップして最も強い方を `final` に採る。
- [ ] `combine_verdict` の集約表 (code {pass,repair,fail} × security {pass,fail,unknown}
      = 9 セル) を全件 parametrize test で検証。少なくとも以下を含む:
      (pass,pass)→pass / (repair,pass)→repair / (fail,pass)→fail /
      (pass,fail)→fail / (repair,fail)→fail / (pass,unknown)→unknown /
      (repair,unknown)→unknown / (fail,unknown)→unknown / (repair,fail)→fail。

### C. security policy 評価 (`suite/security.py` 新設)

- [ ] `evaluate_security(policy: SecurityPolicy | None, baseline: SensorState,
      candidate: SensorState, *, as_of: datetime.date) -> SecurityDeltaStatus`
      を実装。返り値は `pass` / `fail` / `unknown`。評価順序:
  1. **scanner drift override**: `policy.scanner` の `require_same_*` から
     effective drift_fields を導出し、`compute_security_delta` に渡す
     (下記 AC `compute_security_delta` 拡張参照)。`policy is None` または
     `policy.scanner is None` の場合は default (G-1 の現行 4 fields) と一致する
     drift_fields を使う。
  2. **drift / 未完了 sensor**: いずれかの `PerSensorDelta.status == "unknown"`
     (provenance_changed または non-complete) があれば、その sensor は `unknown`
     を寄与する (planning §1.4)。
  3. **suppressions 適用**: active な suppression (下記「期限」参照) に
     `canonical_id` 一致する finding を各 sensor の `added` 集合から除外する。
  4. **user policy gate** (post-suppression `added` に対し、policy が指定された
     sensor について。下記いずれか 1 つでも違反すれば当該 sensor は `fail`):
     - `findings.added.severity.not_in`: severity ∈ not_in の added があれば fail
     - `findings.added.max_count`: post-suppression added 件数 > max_count なら fail
       (severity 不問。planning §2.3 例 2 = max_count:0 は info 追加でも fail)
     - `rules.deny_added`: SAST finding の `rule_id` ∈ deny_added が added にあれば
       fail (severity 不問)
  5. **policy 不在時の floor**: `policy.findings` 等が無い sensor は default floor
     (`sensor.models._FAIL_SEVERITIES` = {critical,high,medium,low}、info 除外) を
     適用 = `SecurityDelta` の既存 `PerSensorDelta.status` をそのまま採用。
  6. **集約**: 全 sensor の寄与を `aggregate_status` (`sensor.models` から import、
     `unknown > fail > pass`) で集約して返す。
- [ ] **suppression hash 整合性検証は suite 層で行う**: `evaluate_security` は
      suppression を適用する前に、各 `Suppression` について `canonical_id ==
      canonical_id_for_identity(identity_components)` (`sensor.models` から import) を
      検証する。不一致なら **authoring error として ValueError を raise** する
      (silent mismatch を許さない。planning §1.3 / §2.1.1 の整合性条件)。
- [ ] **suppression の期限**: `suppression.expires >= as_of` を active とみなす。
      `expires < as_of` の suppression は **inactive** (finding を除外しない)。
      identity_algorithm_version は現状 `v1` のみ (`IdentityAlgorithmVersion =
      Literal["v1"]`) なので cross-version マッチング / `migrate-suppressions` は
      **G-4 に defer** (本 brief では v1 完全一致のみ)。

### D. 決定論性 / §23.1 input neutrality

- [ ] **suite 層は wall clock を一切読まない**: `as_of` は呼び出し側 (将来の G-4 CLI)
      が注入する明示パラメータ。`grep -rn "date.today\|datetime.now\|time.time" src/semantic_ci_code/suite/`
      が **0 件** であること (test or grep AC)。同一 `(policy, baseline, candidate,
      as_of)` は常に同一 `SuiteVerdict` を返す。
- [ ] `evaluate_security` / `combine_verdict` は hand-built `SensorState` +
      hand-built `SecurityPolicy` のみで駆動でき、git ref / ファイル I/O / scanner
      実行を一切要求しない (engine purity、planning §5 Scope Guard)。

### E. drift_fields 拡張 (`sensor/delta.py`)

- [ ] `compute_security_delta(baseline, candidate, *, drift_fields: frozenset[str] |
      None = None)` に optional keyword を追加。`None` のとき現行の固定 4 fields
      (`ruleset_hash` / `advisory_db_hash` / `adapter_version` /
      `identity_algorithm_version`) と **完全に同一挙動** (後方互換、既存
      `tests/sensor/` 全 green)。`drift_fields` 指定時はその集合で
      `_provenance_drift_reason` の比較対象を差し替える。
- [ ] suite 側の drift_fields 導出規則を test で固定: `adapter_version` と
      `identity_algorithm_version` は **常時 drift** (require_same_* で緩和不可)、
      `ruleset_hash` / `sensor_version` / `advisory_db_hash` は対応する
      `require_same_*` が `True` のときのみ drift。default policy の effective set が
      現行 G-1 default (`{adapter_version, identity_algorithm_version, ruleset_hash,
      advisory_db_hash}`) と一致することを test で確認。
      例: `require_same_sensor_version: True` で sensor_version 差 → 当該 sensor unknown。

### F. isolation / dual-case

- [ ] `tests/architecture/` に suite isolation test を追加 (`test_sensor_isolation.py`
      / `test_ssp_isolation.py` の idiom 踏襲): `suite/` は `sensor` / `framework` /
      `evaluator` / `domain` を import 可だが **`cli` を import してはならない**。
      新 module 追加で auto-discovery される形 (個別列挙でなく package walk) にする。
- [ ] **dual-case dogfood**: `evaluate_security` を **fail を返すケースと pass を返す
      ケースの両方**で test する (planning §2.3 の例を素材に。例: high-severity
      added → not_in:[high,critical] で fail / 同じ finding を suppress すると pass)。
      pass 1 件のみの no-op gate を作らない (`AGENTS.md §5.5`)。

## Scope

- IN:
  - `src/semantic_ci_code/suite/` 新設 (`__init__.py` / `evaluator.py` / `security.py`)
  - `src/semantic_ci_code/framework/security_policy.py` 新設
  - `src/semantic_ci_code/framework/target_svp.py` (`security` field 追加のみ)
  - `src/semantic_ci_code/sensor/delta.py` (`drift_fields` optional keyword 追加のみ、
    後方互換)
  - `tests/suite/` 新設、`tests/architecture/` に suite isolation test 追加、
    必要に応じ `tests/sensor/` に drift_fields 回帰 test 追加
- OUT:
  - **CLI 配線は一切しない** (`cli/`、`--sensor` フラグ、subcommand) = G-4 (CSCI-48)
  - **JSON / human / SARIF 出力 / exit code** = G-4 (本 brief は新 subcommand を
    足さないので `docs/exit_codes.md` の変更不要)
  - **SSP v0.1 migration / `migrate-suppressions` CLI / cross-version suppression** = G-4
  - **security templates** (`auth_guard_preserved` 等) = G-5 (CSCI-49)
  - `sensor/models.py` の `SensorState` / `SecurityFinding` / `PerSensorDelta` /
    `SecurityDelta` schema 変更 (G-1 確定形を不変で使う)
  - `evaluator/` (core code evaluator) / `domain/state_schema.py` (CodeState) /
    `delta/` (code delta) は変更しない (planning §5 Scope Guard)
  - security 側の `repair` severity routing (soft/hard 振り分け) は本 brief では
    扱わない。security verdict は `{pass, fail, unknown}` の 3 値に限定 (将来拡張は別 brief)

## Allowed Dependencies

なし (新規依存は禁止)。`datetime` / `hashlib` / `json` は stdlib。

## Implementation Hints

- **layering**: `framework/` (declared-intent schema、dumb models) → `suite/`
  (integration evaluator、sensor/evaluator 参照) の一方向。`suite` → `sensor` /
  `framework` / `evaluator` は downward で OK。`framework` → `suite` は禁止 (inversion)。
  Suppression の hash 整合性検証を suite 側に置くことで `framework` の sensor-free を
  保つ設計 (AC A 末尾 / C 参照)。
- **再利用**: `sensor.models.canonical_id_for_identity` (suppression 整合性検証) /
  `sensor.models.aggregate_status` (sensor 集約) / `sensor.delta.compute_security_delta`
  (drift_fields 経由) / `evaluator.evaluator.VerdictResult` (code verdict 型)。
  ゼロから再実装しない。
- **drift_fields 導出**は `suite/security.py` 内の小さな純関数 (`_drift_fields_for_scanner
  (policy.scanner) -> frozenset[str]`) に切り出すと AC E の test が書きやすい。
- planning §2.3 の severity 行列 (default / 例1 not_in / 例2 max_count) を
  parametrize test の素材にすると AC C / F の dual-case が同時に満たせる。
- `combine_verdict` は precedence rank dict (`{pass:0, repair:1, fail:2, unknown:3}`)
  で max を採る実装が最小。

## Required Outputs

- Branch name: `codex/csci-47-suite-evaluator`
- PR title: `feat(suite): add suite evaluator + target.yaml security namespace (CSCI-47)`
- Expected files changed:
  - `src/semantic_ci_code/suite/__init__.py` (new)
  - `src/semantic_ci_code/suite/evaluator.py` (new)
  - `src/semantic_ci_code/suite/security.py` (new)
  - `src/semantic_ci_code/framework/security_policy.py` (new)
  - `src/semantic_ci_code/framework/target_svp.py` (security field)
  - `src/semantic_ci_code/sensor/delta.py` (drift_fields keyword)
  - `tests/suite/...` (new) + `tests/architecture/test_suite_isolation.py` (new)
- Required tests:
  - `combine_verdict` 9-cell 集約表 parametrize
  - `evaluate_security` dual-case (fail + pass)、suppression active/expired、
    not_in / max_count / deny_added 各 gate、drift override (require_same_sensor_version)
  - suppression hash 不整合で ValueError
  - 決定論性 (clock 不読 grep / 同一入力同一出力)
  - `compute_security_delta` drift_fields 後方互換回帰
  - suite isolation architecture test

## Done When

- All acceptance criteria are checked
- `ruff check .` passes
- `pytest -q` passes
- PR body starts with a Completion Summary (`AGENTS.md §2`)

## Required Reading (Codex 実装前)

1. `docs/phase_g_planning.md` §1.4 / §1.5 / §1.6 / §2.1.1 / §2.3 / §3 (G-3)
2. `src/semantic_ci_code/sensor/models.py` + `sensor/delta.py` (G-1 確定形)
3. `src/semantic_ci_code/framework/target_svp.py` (TargetSVP 既存形)
4. `src/semantic_ci_code/evaluator/evaluator.py` の `VerdictResult` / `_aggregate`
5. `tests/architecture/test_sensor_isolation.py` (isolation test idiom)
6. `docs/code_semantic_ci_design.md §23` (engine contract / §23.1 input neutrality)
