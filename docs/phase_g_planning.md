# Phase G Planning — SSP Core Integration (Security Observation Layer)

> SSP v0.1 (Brief 7、2026-05-27 完走) を semantic-ci core と**縦接続**する
> 設計 planning。SSP v0.1 は core の「横」に並列配置され、独自の delta
> エンジン・envelope・verdict を持つ。本 Phase は SSP を core の「上」に
> 接続し、target.yaml の constraint 体系でセキュリティ判定を宣言可能にする。

## 0. 経緯と問題認識

### 0.1 SSP v0.1 の成果と限界

SSP v0.1 (PR #109〜#112) は diff-based security gate として動作する:
- semgrep (SAST) + pip-audit (SCA) の 2 sensor adapter
- fingerprint 突き合わせによる added / removed / unchanged 分類
- JSON / human / SARIF 3 format
- 14 実リポジトリケース + 5 仮想ケース + 7 マルチエージェントケースで検証済み

しかし以下の構造的限界が 2026-05-27 の実地テストで顕在化した:

1. **射程の退化**: core が持つ intent 宣言 + 構造比較の力を使えない。
   SSP の intent は「finding を増やすな」固定で、target.yaml の自由度がない
2. **ロジック脆弱性の不検知**: 認可バイパス等はパターンマッチでは検知不能。
   core の CodeState 次元 (api_surface / imports / module_graph 等) への
   constraint で部分的に検知可能だが、SSP はその力に接続していない。
   ただし effects では純粋な auth guard 関数 (require_admin() 等) は
   effect signature DB に登録されていない限り検出できないため、
   auth guard 保護には call graph / data_flow / api_surface ベースの
   constraint 設計が必要 (Phase G-5 で検討)
3. **概念的孤立**: 独自 delta エンジンが core の delta と接続しておらず、
   code verdict と security verdict が統合されない

### 0.2 並列設計の原因と再評価

並列にした理由は core ポリシー防御:
- core の決定論性を守る (semgrep / pip-audit への依存を core に入れない)
- core の vendor 非依存を守る
- core の入力中立性 (§23.1) を守る

再評価: **3 つとも守りながら縦接続は可能**。core に入れるのは
Pydantic schema (SecurityFinding 型) だけで、scanner 実行は adapter に留める。
ただし CodeState に直接入れるのではなく、SensorState として分離する (§1.1)。

### 0.3 設計の合成

3 つの独立分析 (GPT / Gemini / Grok) を統合した設計:

| 出典 | 貢献 | 本 planning での位置 |
|------|------|---------------------|
| GPT | SensorState 分離 + suite evaluator + scanner drift + unknown handling | 骨格 (§1〜§4) |
| Gemini | SAST finding の FQN 翻訳 (fingerprint 問題の消滅) | SAST adapter 戦略 (§2.2) |
| Grok | canonical_id versioning + target.yaml 糖衣構文 | 横断品質 (§2.3, §3.2) |

## 1. Core 設計判断

### 1.1 D1: CodeState vs SensorState の分離

**決定: SensorState を CodeState と並列の別 state として新設する。**

CodeState は「コードそのものから AST で決定的に抽出できる構造状態」。
SecurityFinding は「外部センサーによる観測結果」で、ルールセット・ツール
バージョン・正規化処理に依存する。これはコード状態ではなく観測状態であり、
CodeState に混ぜると CodeState の概念定義が曖昧になる。

```
baseline:
  code_state: CodeState        # 既存 (AST 由来)
  sensor_state: SensorState    # 新設 (scanner 由来)

candidate:
  code_state: CodeState
  sensor_state: SensorState

evaluation:
  code_delta = diff(CodeState_baseline, CodeState_candidate)
  security_delta = diff(SensorState_baseline, SensorState_candidate)
  verdict = suite_evaluate(code_delta, security_delta, policy)
```

### 1.2 D2: SAST finding の自然キー

**決定: SAST finding は adapter 層で FQN 空間に翻訳する。FQN 単独では
同一関数内の複数 finding を区別できないため、normalized_text_hash と
ordinal の両方を discriminator に加える。**

SSP v0.1 の fingerprint (5 要素 hash) は近似一致であり、core delta 計算の
「自然キーによる完全一致」ポリシーと緊張する。Gemini 提案の FQN 翻訳により:

- adapter が semgrep の (file, line) を AST 解析で FQN に逆引き
- SAST finding の自然キー = `(rule_id, fqn, normalized_text_hash, ordinal)`
  の 4 要素複合キー
- normalized_text_hash は matched source の正規化テキストの short hash。
  ordinal は同一 `(rule_id, fqn, normalized_text_hash)` グループ内での
  出現順序 (0-indexed)。SSP v0.1 `docs/ssp_protocol.md §5.1` の ordinal
  割り当てルールを継承
- なぜ両方必要か:
  - normalized_text_hash だけだと、同一関数内で同一テキストの finding が
    複数ある場合 (例: `eval(config)` が 2 回) に衝突する → ordinal で区別
  - ordinal だけだと、同一位置でコード片が変わった場合
    (例: `eval(config)` → `exec(config)`) に unchanged 誤判定する
    → normalized_text_hash で区別
- core は複合キーベースの集合演算 (既存の effects / api_surface と同構造)
- fingerprint の設計判断が core に入らない

```python
# SAST: sensor_id + FQN + text_hash + ordinal が自然キー
# sensor_id を含めることで、複数 SAST sensor が同じ rule_id を emit しても衝突しない
#
# 重要: canonical_id はコンポーネント tuple の injective encoding + hash で生成する。
# delimiter join (`:` / `\0` 等) はコンポーネントに delimiter が含まれる場合に
# alias collision を起こす (例: ("a\0b","c") と ("a","b\0c") が同一 byte stream)。
# SSP v0.1 docs/ssp_protocol.md §5.1 は canonical JSON array encoding で
# この class の collision を回避しており、本設計もそれを継承する。
#
# 実装: adapter が以下の tuple を canonical JSON array に serialize し、
# その byte 列の sha256 short hash を canonical_id とする。
# JSON array は各要素が quoted string で length-prefixed されるため injective。
# identity_components (audit log 用) に tuple の全要素を保存する。
import json
_identity_tuple = ["v1", "sast", sensor_id, rule_id, fqn, normalized_text_hash, str(ordinal)]
canonical_id = "v1:" + hashlib.sha256(json.dumps(_identity_tuple, separators=(",", ":"), sort_keys=False).encode()).hexdigest()[:16]

# SCA も同様
_identity_tuple = ["v1", "sca", sensor_id, package_name, installed_version, advisory_id]
canonical_id = "v1:" + hashlib.sha256(json.dumps(_identity_tuple, separators=(",", ":"), sort_keys=False).encode()).hexdigest()[:16]
```

canonical_id は不透明な hash 文字列であり、人間が読み解く必要はない。
人間向けの説明は `_SecurityFindingBase.identity_components` に全要素を保存して
audit log / CI 出力で表示する。`v1:` prefix は identity algorithm version を
示し、algorithm 変更時に全 hash が変わることを保証する。

### 1.3 D3: canonical_id のバージョン埋め込み

**決定: canonical_id に identity algorithm version を prefix する。**

```
canonical_id = "v1:3a7f8b2e1c9d04a5"
               ^^^  ^^^^^^^^^^^^^^^^
               |    sha256 short hash of json.dumps(identity_tuple)
               identity algorithm version

# identity_tuple (_SecurityFindingBase.identity_components に保存):
# ["v1", "sast", "semgrep", "sql-injection", "app.db.get_user", "a3f8", "0"]
# encoding: json.dumps(list, separators=(",",":"), sort_keys=False)
```

algorithm が変わったら canonical_id 全体が変わる。core は文字列の完全一致
しかしないので、暗黙の finding 入れ替えを防ぐ。

**Suppression migration**: identity algorithm 変更時は全 canonical_id が変わり、
既存の `security.suppressions` エントリが silent fail する (マッチしなくなる)。
対策:
- evaluator は identity_algorithm_version の不一致を検出し warning を emit する
- Phase G-4 の CLI に `semantic-ci migrate-suppressions --from v1 --to v2`
  コマンドを scope に含め、旧 canonical_id → 新 canonical_id の一括更新手段を提供
- 過渡期に v1/v2 両方の canonical_id をマッチさせるべきかは G-3 brief で判断

### 1.4 D4: scanner drift の検出

**決定: SensorState に provenance を持たせ、delta 計算で drift を検出する。**

```python
class SensorProvenance(FrozenModel):
    sensor_name: str
    sensor_version: str
    status: str                    # "complete" | "error" | "timeout" | "skipped"
    error_message: str | None      # status != "complete" の場合の詳細
    ruleset_hash: str | None       # SAST: semgrep ruleset file の hash
    advisory_db_hash: str | None   # SCA: advisory database snapshot の hash
    adapter_version: str
    identity_algorithm_version: str

class PerSensorDelta(FrozenModel):
    sensor_id: str
    status: str                    # "pass" | "fail" | "unknown"
    added: tuple[SecurityFinding, ...]
    removed: tuple[SecurityFinding, ...]
    unchanged_count: int
    provenance_changed: bool
    # この sensor の provenance が baseline と異なるかどうか。
    # True の場合、status は "unknown" に強制される。
    error_message: str | None      # status == "unknown" 時の原因説明

class SecurityDelta(FrozenModel):
    deltas_by_sensor: dict[str, PerSensorDelta]
    # key = sensor_id。SSP v0.1 の deltas_by_sensor 構造を継承。
    # per-sensor verdict が自然に計算できる。
    aggregate_status: str          # "pass" | "fail" | "unknown"
    # model_validator (整合性検証、SSP v0.1 SSPEnvelope._validate_delta_consistency 継承):
    #   1. deltas_by_sensor の各 key == value.sensor_id を検証
    #   2. aggregate_status == aggregate(d.status for d in deltas_by_sensor.values())
    #      を検証 (precedence: unknown > fail > pass)
    #   hand-built JSON や buggy adapter が不整合な aggregate_status を設定した場合、
    #   構築時に ValidationError で reject する。
```

delta は SSP v0.1 同様 **per-sensor** で保持する。SSP v0.1 の
`deltas_by_sensor: dict[str, SSPDelta]` 構造を継承し、per-sensor verdict を
自然に計算可能にする。aggregate は suite evaluator 層で合成する。

scanner / ruleset / adapter が変わっている場合、**当該 sensor の verdict 全体**
を unknown にする (`provenance_changed: true` → `status: "unknown"`)。
added finding だけでなく removed finding もコード変更起因と断定できない
(finding が消えたのがコード修正なのか ruleset 変更なのか区別不能)。
provenance が一致している sensor の finding のみ pass / fail 判定を受ける。

### 1.5 D5: verdict 体系

**決定: suite evaluator で code_verdict と security_verdict を統合する。**

```
suite_verdict:
  code:     pass | repair | fail
  security: pass | repair | fail | unknown
  final:    pass | repair | fail | unknown

aggregation: unknown > fail > repair > pass
```

unknown は fail ではないが pass でもない。既存 core の verdict 体系は変更しない。
suite 層で unknown を保持する。

### 1.6 D6: security constraint の二層化

**決定: security は observation 層と semantic constraint 層に分ける。**

Layer 1 — 外部 scanner 由来 (SensorState):
  semgrep / pip-audit / secret scan の finding delta

Layer 2 — core constraints 由来 (既存 CodeState):
  effects / api_surface / imports への constraint として記述

Layer 2 の target.yaml 例 (既存の constraint list 形式):

```yaml
# target.yaml — Layer 2 は既存の constraints list 形式で記述可能
constraints:
  # 危険な import の追加を禁止
  # (effects で auth guard を検知する案は不適: extract_python_effects は
  #  effect signature DB 登録済みの副作用のみ抽出し、require_admin() 等の
  #  純粋な auth guard 関数は effects に現れない。auth guard 保護は
  #  call graph / data_flow / api_surface の制約で扱うべきであり、
  #  Phase G-5 の security template 設計で正式に検討する)
  - id: deny-dangerous-imports
    kind: delta
    target: imports_delta.added
    operator: excludes_all
    expected:
      - module: pickle
      - module: subprocess
    severity: hard
```

Layer 1 の security constraint は**別の namespace / 別ファイル**で宣言する。
既存の `constraints` list (`framework/target_svp.py` の `tuple[Constraint, ...]`)
は変更しない。security constraint の宣言形式は Phase G-3 で設計する。
候補は以下の 2 案:

- 案 A: target.yaml に `security:` top-level key を新設
  - `TargetSVP` は `ConfigDict(extra="forbid")` のため、未知キーは
    Pydantic ValidationError で reject される。案 A を選ぶ場合は
    `framework/target_svp.py` に `security: SecurityPolicy | None = None`
    フィールドを追加する変更が**必須**。`extra="forbid"` 自体は既知キーの
    追加で違反しないが、framework 層の変更であり §5 Scope Guard
    「core evaluator は変更しない」との関係を G-3 brief で明示すること
- 案 B: `security.yaml` として別ファイルに分離 (target.yaml / TargetSVP 不変)
  - `extra="forbid"` 制約を回避できるが、2 ファイル管理の運用コストが増加

いずれも既存の `constraints` list schema とは独立。具体的な DSL 設計は
G-3 brief の AC として扱う。

Layer 2 は新設計不要 (既存の target.yaml で書ける)。
Layer 1 が本 Phase の新設部分。

## 2. 新設 schema

### 2.1 SensorState model

```python
# SSP v0.1 同様、SAST / SCA を discriminated union で分離する。
# 全フィールドを Optional で flatten すると category と必須フィールドの
# 整合性が型レベルで保証できなくなる (SSP v0.1 からの型安全性退行)。

class _SecurityFindingBase(FrozenModel):
    canonical_id: str        # opaque "v1:<sha256[:16]>"; see §1.2
    severity: str            # "critical" | "high" | "medium" | "low" | "info"
    sensor_id: str           # "semgrep" | "pip-audit" | ...
    message: str
    identity_components: dict  # canonical_id の生成根拠 (audit log 用)

class SASTSecurityFinding(_SecurityFindingBase):
    category: Literal["sast"] = "sast"
    rule_id: str                      # min_length=1
    fqn: str                          # adapter が FQN 翻訳。min_length=1
    normalized_text_hash: str         # matched source の正規化 hash
    module_path: str                  # "src/app/db.py" 等のファイルパス
    source_span: SourceSpan | None    # 行・列の範囲 (SSP v0.1 SourceSpan 継承)

class SCASecurityFinding(_SecurityFindingBase):
    category: Literal["sca"] = "sca"
    package_name: str                 # min_length=1
    installed_version: str            # min_length=1
    advisory_id: str                  # min_length=1

SecurityFinding = Annotated[
    SASTSecurityFinding | SCASecurityFinding,
    Field(discriminator="category"),
]

class SensorState(FrozenModel):
    findings: tuple[SecurityFinding, ...]
    provenance_by_sensor: dict[str, SensorProvenance]
    # provenance の source of truth は provenance_by_sensor (state-level) に一元化。
    # finding-level の provenance 重複フィールド (sensor_name, sensor_version,
    # ruleset_hash, adapter_version, identity_algorithm_version) は V3 review で
    # 削除し、finding は sensor_id 参照のみ保持する (_SecurityFindingBase.sensor_id)。
    # identity_components (canonical_id 生成根拠) は finding-level に残す (audit 用)。
    # drift 検出は provenance_by_sensor のみを参照する。
    #
    # model_validator (参照整合性):
    #   全 finding.sensor_id ∈ provenance_by_sensor.keys() を enforce する。
    #   hand-built JSON や buggy adapter が provenance なしの sensor_id を
    #   持つ finding を emit した場合、drift/error 判定が不能になるため、
    #   構築時に ValidationError で reject する。
    # key = sensor_id ("semgrep", "pip-audit", ...)
    # 複数 sensor を同時に使う場合、各 sensor の provenance を独立に記録する。
    # drift 検出は per-sensor で行う: sensor A の ruleset が変わっても
    # sensor B の finding は unknown に寄せない。
    # zero-finding sensor も provenance は記録する (status="complete" で
    # finding 0 件 = clean scan、status="error" = scanner 失敗、
    # provenance_by_sensor に key がない = sensor 未実行、の 3 状態を区別)。
    # status != "complete" の sensor は verdict を unknown に寄せる。
```

### 2.2 SAST FQN 翻訳 (adapter 層)

SSP v0.1 の `SemgrepAdapter` は既に `qualified_name_for_line()` で
file:line → FQN の逆引きを実装している (`ssp/adapters/qualified_name.py`)。
本 Phase ではこれを `SecurityFinding.fqn` に正式化する。

### 2.3 target.yaml security namespace

```yaml
security:
  # finding delta への constraint (糖衣構文)
  # SSP v0.1 の default: info severity の追加は verdict に影響しない
  # (_FAIL_SEVERITIES = {critical, high, medium, low}、info 除外)。
  # Phase G もこの default を継承する。明示的な severity filter で上書き可能:
  #
  # | 設定 | info | low | medium | high | critical |
  # |------|------|-----|--------|------|----------|
  # | default (設定なし) | 許容 | fail | fail | fail | fail |
  # | 例 1 (not_in) | 許容 | 許容 | 許容 | fail | fail |
  # | 例 2 (max_count: 0) | fail | fail | fail | fail | fail |
  findings:
    added:
      # 例 1: high / critical の追加を禁止 (medium 以下は許容)
      severity:
        not_in: [high, critical]

      # 例 2: severity 不問で added 0 件 (厳格モード、例 1 と排他)
      # info を含む全 severity の追加を禁止 (SSP v0.1 default と異なる)
      # max_count: 0

  # 特定ルールの存在禁止
  rules:
    deny_added:
      - sql-injection
      - eval-use

  # scanner 環境一致要求 (drift 検出との合成ルール)
  # drift 検出は provenance_by_sensor の全フィールドを比較する。
  # require_same_*: false のフィールドは比較対象から除外する。
  # 例: require_same_sensor_version: false の場合、sensor_version の差は
  # drift として扱わず unknown に寄せない。ruleset_hash の差のみ drift 判定。
  scanner:
    require_same_ruleset: true          # false なら ruleset_hash 差は drift 除外
    require_same_sensor_version: false  # minor version 差は許容 (drift 除外)
    require_same_advisory_db: true      # SCA: advisory DB hash 差の drift 判定

  # false positive 抑制 (理由 + 期限必須)
  suppressions:
    - canonical_id: "v1:e4b2a7c9f1d30856"
      # opaque hash; identity_components on finding for audit
      reason: "Validated upstream by WAF"
      expires: "2026-09-01"
      owner: "security-team"
```

## 3. PR 分割案

### Phase G-1: SensorState model + canonical_id (CSCI-45)
- `src/semantic_ci_code/sensor/` 新設
  - `models.py`: SecurityFinding, SensorState, SensorProvenance
  - `delta.py`: canonical_id ベースの集合差分
- `tests/sensor/`: model validation + delta 計算
- 既存コード変更なし (新設のみ)
- **AC**: SensorState が hand-built JSON で構築・比較可能 (§23.1 鏡像)

### Phase G-2: FQN 翻訳 adapter (CSCI-46)
- `src/semantic_ci_code/sensor/adapters/` 新設
  - `semgrep_adapter.py`: SSP v0.1 SemgrepAdapter → SensorState 変換
  - `pip_audit_adapter.py`: SSP v0.1 PipAuditAdapter → SensorState 変換
  - `fqn_resolver.py`: file:line → FQN 逆引き (SSP の `qualified_name.py` を移植)
- canonical_id 生成 (v1 prefix + identity_algorithm_version)
- provenance 生成
- **AC**: semgrep / pip-audit の出力が SensorState に正規化される

### Phase G-3: Suite evaluator + security constraint (CSCI-47)
- `src/semantic_ci_code/suite/` 新設
  - `evaluator.py`: code_delta + security_delta → suite_verdict
  - `security_constraints.py`: target.yaml `security:` namespace 解釈
- target.yaml parser 拡張 (security namespace)
- scanner drift 検出 (provenance_changed → unknown)
- **AC**: target.yaml に security constraint を書いて verdict が出る

### Phase G-4: CLI 統合 + SSP v0.1 migration path (CSCI-48)
- `semantic-ci check` に `--sensor` オプション追加
  (SensorState を CodeState と同時に評価)
- SSP v0.1 の `ssp scan` / `ssp from-json` は互換維持 (deprecated 予告)
- suite verdict の JSON / human / SARIF 出力
- **AC**: `semantic-ci check --sensor semgrep --config rules.yaml` で
  code + security の統合 verdict が出る

### Phase G-5: Semantic security templates (CSCI-49)
- `src/semantic_ci_code/templates/security/` 新設
- テンプレートは 2 カテゴリに分かれる:

**カテゴリ A — 既存 extractor で表現可能 (engine 変更なし)**:
  - `dangerous_imports_denied.yaml`: imports_delta.added + excludes_all
  - `validation_preserved.yaml`: api_surface + equals_baseline
    (public API の signature 変更を検知)

**カテゴリ B — extractor 拡張が必要 (G-5 brief で extractor scope を定義)**:
  - `auth_guard_preserved.yaml`: 現行 effects extractor は effect signature
    DB 登録済みの呼び出しのみ抽出するため、`require_admin()` 等の純粋な
    auth guard 関数は検出不能。G-5 brief で api_surface の auth decorator
    検出 (e.g. `@login_required` の有無追跡) または data_flow 実装
    (call graph 上の guard → handler 経路追跡) のいずれかを選択する
  - `privileged_api_gated.yaml`: 同上。privileged endpoint の guard 有無を
    追跡するには auth decorator または call graph が必要

- カテゴリ A は新 operator 不要 (既存 operator で表現可能)
- カテゴリ B は extractor 拡張の scope を G-5 brief AC として定義する
- **AC (カテゴリ A)**: `semantic-ci init --recipe security:deny-dangerous-imports`
  で target.yaml が生成される
- **AC (カテゴリ B)**: G-5 brief が extractor 拡張の scope + AC を定義し、
  template は extractor 完了後に有効化される

## 4. 移行戦略

### SSP v0.1 との関係

- SSP v0.1 は Phase G-4 完了まで現行のまま維持
- Phase G-4 で `ssp scan` / `ssp from-json` に deprecation notice 追加
- Phase G-4 以降、SSP の独自 delta エンジンは sensor/delta.py に吸収
- SSP の envelope format (`ssp-1`) は suite envelope の一部として維持可能

### 既存テストへの影響

- CodeState schema 変更なし → 既存テスト全互換
- 新設モジュールは全て optional (sensor/ suite/) → 既存 CLI 動作不変
- Phase G-5 カテゴリ A テンプレートは target.yaml の content であり engine 変更なし
- Phase G-5 カテゴリ B テンプレートは extractor 拡張を伴う (G-5 brief で scope 定義)

## 5. Scope Guard

- core evaluator (`evaluator/`) は変更しない。security constraint は
  suite evaluator が解釈する
- core の CodeState schema は変更しない。SensorState は並列の別 state
- core の delta 計算 (`delta/`) は変更しない。sensor delta は別モジュール
- core の 3 原則 (決定論性 / 外部ツール非依存 / 入力中立性) は維持
- SensorState も手書き / 仮想入力で構築可能 (§23.1 鏡像)
- scanner 実行は adapter 層の責務。core / suite は SensorState schema のみ知る

## 6. Open Questions

- **Q1**: suite evaluator は既存の evaluator と同じモジュールに置くか、
  完全に別パッケージか
- **Q2**: security constraint の DSL を target.yaml に統合するか、
  `security.yaml` として分離するか
- **Q3**: Phase G-5 のテンプレートは `target-catalog` に統合するか、
  別コマンドにするか
- **Q4**: SSP v0.1 の SARIF 出力は suite 層に移行するか、
  独立出力として維持するか
- **Q5**: SensorState の JSON schema は SSP v0.1 の `ssp-1` を拡張するか、
  新 schema version (`suite-1`) を起こすか

## 7. Required Reading (Phase G brief 起草時)

1. 本 planning doc 全体
2. `docs/ssp_protocol.md` — SSP v0.1 normative spec (移行元の仕様)
3. `docs/ssp_protocol_design_note.md` — Brief 7 設計申し送り
4. `docs/code_semantic_ci_design.md §23` — engine contract / boundary
5. `docs/brief_7_planning.md §3` — SSP v0.1 の設計判断 6 項目
6. `src/semantic_ci_code/ssp/` — 現行実装 (移植元)
7. 本 session の議論ログ (`.claude/memory/2026-05-27.md`)
