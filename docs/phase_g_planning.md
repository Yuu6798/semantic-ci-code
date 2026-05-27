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
2. **ロジック脆弱性の不検知**: 認可バイパス等はパターンマッチでは検知不能だが、
   core の effects constraint (`equals_baseline`) なら検知可能。SSP はその力に
   接続していない
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

**決定: SAST finding は adapter 層で FQN 空間に翻訳する。**

SSP v0.1 の fingerprint (5 要素 hash) は近似一致であり、core delta 計算の
「自然キーによる完全一致」ポリシーと緊張する。Gemini 提案の FQN 翻訳により:

- adapter が semgrep の (file, line) を AST 解析で FQN に逆引き
- SAST finding の自然キー = `(rule_id, fqn)` の複合キー
- core は FQN ベースの集合演算 (既存の effects / api_surface と同構造)
- fingerprint の設計判断が core に入らない

```python
# SAST: FQN が自然キー
canonical_id = f"v1:sast:{rule_id}:{fqn}"

# SCA: package + advisory が自然キー (元から一意)
canonical_id = f"v1:sca:{package_name}:{advisory_id}"
```

### 1.3 D3: canonical_id のバージョン埋め込み

**決定: canonical_id に identity algorithm version を prefix する。**

```
canonical_id = "v1:sast:sql-injection:app.db.get_user"
               ^^^
               identity algorithm version
```

algorithm が変わったら canonical_id 全体が変わる。core は文字列の完全一致
しかしないので、暗黙の finding 入れ替えを防ぐ。

### 1.4 D4: scanner drift の検出

**決定: SensorState に provenance を持たせ、delta 計算で drift を検出する。**

```python
class SensorProvenance(FrozenModel):
    sensor_name: str
    sensor_version: str
    ruleset_hash: str | None
    adapter_version: str
    identity_algorithm_version: str

class SensorDelta(FrozenModel):
    added: tuple[SecurityFinding, ...]
    removed: tuple[SecurityFinding, ...]
    unchanged_count: int
    provenance_changed: bool  # True なら verdict を unknown に寄せる
```

scanner / ruleset / adapter が変わっている場合、added finding をコード変更
起因と断定するのは危険。verdict は unknown に寄せる。

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

```yaml
# target.yaml
constraints:
  # Layer 2: ロジック脆弱性を既存 constraint で検知
  code:
    effects:
      do_transfer:
        callers: equals_baseline

  # Layer 1: scanner finding を security constraint で制御
  security:
    findings:
      added:
        severity:
          not_in: [high, critical]
    scanner:
      require_same_ruleset: true
```

Layer 2 は新設計不要 (既存の target.yaml で書ける)。
Layer 1 が本 Phase の新設部分。

## 2. 新設 schema

### 2.1 SensorState model

```python
class SecurityFinding(FrozenModel):
    canonical_id: str        # "v1:sast:rule_id:fqn" or "v1:sca:pkg:advisory"
    category: str            # "sast" | "sca"
    severity: str            # "critical" | "high" | "medium" | "low" | "info"
    sensor_id: str           # "semgrep" | "pip-audit" | ...
    rule_id: str | None      # SAST 用
    advisory_id: str | None  # SCA 用
    fqn: str | None          # SAST: adapter が FQN 翻訳。SCA: None
    package_name: str | None # SCA 用
    message: str
    provenance: FindingProvenance

class FindingProvenance(FrozenModel):
    sensor_name: str
    sensor_version: str
    ruleset_hash: str | None
    adapter_version: str
    identity_algorithm_version: str
    identity_components: dict  # canonical_id の生成根拠 (audit log 用)

class SensorState(FrozenModel):
    findings: tuple[SecurityFinding, ...]
    provenance: SensorProvenance
```

### 2.2 SAST FQN 翻訳 (adapter 層)

SSP v0.1 の `SemgrepAdapter` は既に `qualified_name_for_line()` で
file:line → FQN の逆引きを実装している (`ssp/adapters/qualified_name.py`)。
本 Phase ではこれを `SecurityFinding.fqn` に正式化する。

### 2.3 target.yaml security namespace

```yaml
security:
  # finding delta への constraint (糖衣構文)
  findings:
    added:
      severity:
        not_in: [high, critical]
      max_count: 0              # severity 不問で added 0 件 (厳格モード)

  # 特定ルールの存在禁止
  rules:
    deny_added:
      - sql-injection
      - eval-use

  # scanner 環境一致要求
  scanner:
    require_same_ruleset: true
    require_same_sensor_version: false  # minor version 差は許容

  # false positive 抑制 (理由 + 期限必須)
  suppressions:
    - canonical_id: "v1:sast:xss:app.legacy.render"
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
  - `auth_guard_preserved.yaml`
  - `validation_preserved.yaml`
  - `dangerous_imports_denied.yaml`
  - `privileged_api_gated.yaml`
- 既存 core constraint (effects / imports / api_surface) の組み合わせで記述
- 新 operator 不要 (既存 operator で表現可能)
- **AC**: `semantic-ci init --recipe security:auth-guard` で
  認可ロジック保護の target.yaml が生成される

## 4. 移行戦略

### SSP v0.1 との関係

- SSP v0.1 は Phase G-4 完了まで現行のまま維持
- Phase G-4 で `ssp scan` / `ssp from-json` に deprecation notice 追加
- Phase G-4 以降、SSP の独自 delta エンジンは sensor/delta.py に吸収
- SSP の envelope format (`ssp-1`) は suite envelope の一部として維持可能

### 既存テストへの影響

- CodeState schema 変更なし → 既存テスト全互換
- 新設モジュールは全て optional (sensor/ suite/) → 既存 CLI 動作不変
- Phase G-5 のテンプレートは target.yaml の content であり engine 変更なし

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
