# Code Semantic CI — Design Specification (v0.1 draft)

## 0. Statement of Scope (most important)

> **This is not a linter. This is not a type checker. This is not a test runner.**
>
> Code Semantic CI is a deterministic semantic CI layer that compares
> **declared change intent**, **expected code state**, **baseline code state**,
> and **observed code state**, and emits a **semantic diff** plus
> **repair instructions** for the next generator pass.

既存 CI ツール（lint / type / test）が見逃す **「宣言された修正意図」と「観測された差分」の意味的整合性** を、決定論的に検証することが本製品の唯一の存在理由。生成 AI（Codex / Claude Code / Cursor 等）が出した PR を gate するレイヤとして機能する。

## 1. 位置付けと差別化

| 既存ツール | 見るもの | 限界 |
|---|---|---|
| linter | 規約違反 | 意図に対する逸脱は見ない |
| type checker | 型整合性 | 「変えてはいけない型を変えた」は見ない |
| test runner | 振る舞い | テストが通っても意図ずれは検出不能 |
| **Code Semantic CI** | **declared intent vs observed delta** | — |

LLM-as-judge 系（Coderabbit / Greptile 等）との差別化:

- 決定論的（同入力 → 同出力、CI gate に使える）
- 監査可能（evidence chain を必ず出す）
- 第三者性（生成ベンダ非依存）

## 2. 中核モデル: 3-state RPE

音楽版の `Target SVP → Expected RPE → Observed RPE → Diff` モデルを **コード版では 3 状態** に拡張する:

```
Target SVP            Baseline Code         Candidate Code
    │                       │                       │
    ▼                       ▼                       ▼
Expected RPE         Baseline RPE           Observed RPE
    │                       │                       │
    └───────────┬───────────┴──────────┬───────────┘
                ▼                       ▼
        ConstraintEvaluator     CodeStateDelta
                │                       │
                └───────────┬───────────┘
                            ▼
                      Semantic Diff
                            ▼
                         Verdict (pass | repair | fail)
                            ▼
                       Repair SVP
                            ▼
              Repair Prompt / Patch Instruction
```

### なぜ Baseline RPE が必須か

リファクタリング・バグ修正の本質は「**外部契約は変えずに内部構造を変える**」こと。これを検証するには baseline との差分が必要で、Observed と Expected だけでは表現できない。

例: spec が `preserve api_surface_of: ["src.api.users.*"]` と言った時、これを評価するには baseline の API surface を知る必要がある。

### この拡張は音楽版にも遡及的に効く

将来 `preserve section_structure from baseline` のような制約を音楽版に入れる時、同じ 3-state モデルが必要になる。本設計はフレームワーク core の改善でもある。

## 3. State Schema

**共通スキーマ + 言語固有 extension** に分割する。

### 3.1 CodeState（共通スキーマ）

```yaml
CodeState:
  api_surface:           # 公開シンボル集合
    - { fqn, kind, signature, visibility }
  type_relations:        # 型関係
    - { fqn, type_expr, nullable, generic_params }
  effects:               # 効果分類
    - { fqn, effect_class: [pure|io|net|fs|process|env|time_random|stdout|dynamic_code|unsafe_deserialize|global_mutation], confidence, evidence }
  control_flow:          # CFG メトリクス（P2 以降の充実）
    - { fqn, branches, loops, exception_paths, cyclomatic }
  data_flow:             # 簡易タイント（P2 以降）
    - { source, sink, path }
  imports:               # モジュール依存
    - { module, from, symbols }
  complexity:
    - { fqn, cyclomatic, cognitive }
  test_surface:
    - { test_file, test_function, asserts, parametrize_count }
  coverage:              # P3 以降、dynamic 拡張
    - { file, line_coverage, branch_coverage }
  module_graph:
    - { module, imports, imported_by }
```

### 3.2 CodeStateDelta（first-class エンティティ）

`CodeStateDelta` は単なるレポートフィールドではなく、**制約が target にできる first-class エンティティ**。

```yaml
CodeStateDelta:
  api_surface_delta: { added: [...], removed: [...], changed: [...] }
  type_changes: [...]
  effect_changes: { added: [...], removed: [...] }
  cfg_delta: { new_branches, removed_branches }
  imports_delta: { added: [...], removed: [...] }
  complexity_delta: { cyclomatic: ±N, cognitive: ±N }
  test_surface_delta: { new_files, new_cases, removed_cases }
  coverage_delta: { line: ±%, branch: ±% }       # optional
  files_touched: int
  loc_delta: { added: int, removed: int }
```

### 3.3 言語固有 extension

Python / TypeScript で共通スキーマを満たしつつ、言語固有フィールドを追加可能:

```yaml
# Python extension
python_specific:
  decorators: [...]
  metaclasses: [...]
  type_var_bounds: [...]

# TypeScript extension
typescript_specific:
  generic_constraints: [...]
  conditional_types: [...]
  declaration_merging: [...]
```

## 4. Target SVP DSL

### 4.1 基本構造

```yaml
intent: "<人間可読の意図 1 行>"
change:
  primary_kind: refactor | feature | bugfix | test_update
  allowed_secondary_kinds: [...]
  scope:
    files: [...]
    modules: [...]

# StateConstraints / DeltaConstraints / RepairConstraints
constraints:
  - id: <unique id>
    kind: state | delta | repair
    target: <RPE field path>
    operator: <typed operator>
    expected: <value or "baseline">
    severity: hard | soft | info
    unknown_policy: fail | repair | warn | ignore
    tolerance: <numeric or null>
    evidence_required: true | false
    scope: file | module | function | package
```

### 4.2 change_kind は制約テンプレート展開器

`change_kind` は単なるラベルではなく、**default 制約セットを展開するキー**として扱う。

```yaml
# Target SVP に
change:
  primary_kind: refactor

# が宣言されると、ConstraintTemplate(refactor) が以下を自動展開:
#   - api_surface.public_symbols equals_baseline (hard, fail on unknown)
#   - type_signatures equals_baseline (hard)
#   - effects equals_baseline (hard)
#   - test_expectations unchanged (hard)
#   - complexity may_decrease (soft)
#   - internal_symbols may_change (soft)
```

ユーザは追加制約を `constraints:` で override / 補強できる。

### 4.3 change_kind の規範ルール（P1 範囲）

| change_kind | 必須（required） | 許可（allowed） | 禁止（forbidden） |
|---|---|---|---|
| **feature** | declared API 追加, テスト追加 | 新型, 新 config, allowed import 追加 | 既存 API 削除, 未宣言 effect |
| **bugfix** | 公開 API 不変, 回帰テスト追加 | 局所変更, 局所複雑度変化 | 新公開 API, 大規模構造変更, 未宣言 effect |
| **refactor** | 公開 API 不変, 型契約不変, effect 不変 | 内部構造変更, 複雑度低下, 命名整理 | 公開 API 変更, 型契約変更, 新 effect, テスト期待値変更 |
| **test_update** | テスト追加/修正 | fixture 更新 | production code の意味変更 |

### 4.4 複合 PR の扱い

実務では `feature + refactor`、`bugfix + dependency_update` のような混在が起きる。P1 では:

- `primary_kind` は **必須**
- `allowed_secondary_kinds` で明示宣言された範囲のみ許可
- 未宣言の secondary delta が出たら **repair**
- hard violation が出たら **fail**

### 4.5 サンプル: 機能追加

```yaml
intent: "fetch_user_profile を追加"
change:
  primary_kind: feature
  scope:
    files: ["src/api/users.py", "tests/test_users.py"]

constraints:
  - id: feature_added
    kind: delta
    target: api_surface_delta.added
    operator: includes_all
    expected: ["src.api.users.fetch_user_profile"]
    severity: hard
    unknown_policy: fail
    evidence_required: true

  - id: no_other_api_changes
    kind: delta
    target: api_surface.public_symbols
    operator: superset_of_baseline
    severity: hard
    unknown_policy: fail

  - id: no_new_io_in_models
    kind: delta
    target: effects
    operator: no_new_items
    scope: src.models.*
    severity: hard
    unknown_policy: repair

  - id: complexity_budget
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than_or_equal
    expected: 5
    severity: soft
    unknown_policy: warn

  - id: test_added
    kind: delta
    target: test_surface_delta.new_test_cases
    operator: greater_than_or_equal
    expected: 1
    severity: hard
    unknown_policy: fail
```

### 4.6 サンプル: リファクタリング

```yaml
intent: "auth を middleware 化"
change:
  primary_kind: refactor

# change_kind=refactor のテンプレート展開で
# api_surface / type / effects の equals_baseline 制約が自動付与される。
# 追加で:

constraints:
  - id: complexity_should_decrease
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than
    expected: 0
    severity: soft
    unknown_policy: warn
```

## 5. Constraint Type System

### 5.1 3 種類の制約

| kind | 何を評価するか | 例 |
|---|---|---|
| **state** | Observed RPE 単独で満たすべき性質 | `complexity ≤ 10` |
| **delta** | Baseline と Observed の関係性 | `api_surface unchanged` |
| **repair** | 次サイクルへの指示 | `restore X, reduce Y` |

これらを混同せず、評価器を分離する。

### 5.2 P1 で実装する operator 集合

```
equals
not_equals
equals_baseline           # delta: baseline と一致
not_equals_baseline       # delta: baseline と不一致
includes_all              # set: 部分集合関係
includes_any
excludes_all
subset_of
superset_of
superset_of_baseline      # delta: baseline の superset
no_new_items              # delta: 追加なし
no_removed_items          # delta: 削除なし
less_than
less_than_or_equal
greater_than
greater_than_or_equal
within_range
unchanged                 # delta: 変更なし
changed                   # delta: 何らかの変更あり
changed_only_in           # delta: 変更が指定 scope 内のみ
```

P1 ではこれ以上 operator を増やさない。**任意 Python 式や独自構文 DSL は採用しない**（決定論・安全性・再現性が壊れる）。

### 5.3 制約評価結果の構造

評価結果は単なる boolean ではなく、必ず evidence chain を持つ:

```yaml
result:
  constraint_id: public_api_preserved
  status: violated | satisfied | unknown
  severity: hard | soft | info
  target: api_surface.public_symbols
  expected: baseline
  observed_added: []
  observed_removed:
    - src.api.users.create_user
  evidence:
    extractor: griffe
    extractor_version: "0.42.0"
    field: api_surface.public_symbols
    source_location:
      file: src/api/users.py
      line: 12
  repair_hint: restore_removed_public_symbol
```

### 5.4 unknown_policy: 計測層と判定層の分離

extractor が抽出に失敗した場合（型情報不足、解析対象外パターン等）の挙動を **constraint ごと**に指定:

| policy | 挙動 |
|---|---|
| **fail** | 即時 fail。critical な制約に使う |
| **repair** | repair 経路へ。回復可能なら再生成 |
| **warn** | 警告のみ、verdict には影響しない |
| **ignore** | 完全に無視 |

これは UGH Audit Engine の「検出層・電卓層・判定層を分離する」原理と同じ。**計測器は数値や状態を出すだけで、最終判定は別層**で行う。

## 6. Extractor Architecture

### 6.1 既存ツール wrapping を基本とする

自前で型検査器・AST 解析器を作らない。**既存ツールの出力を共通スキーマに正規化する** だけが Semantic CI の責務。

| 次元 | Python | TypeScript |
|---|---|---|
| API surface | `griffe` | `ts-morph` + `@microsoft/api-extractor` |
| 型 | `mypy` / `pyright` | `tsc --emitDeclarationOnly` |
| AST / CFG | `ast` + `networkx` | `ts-morph` + `@typescript-eslint/parser` |
| 効果 | known-effect リスト + AST 走査 | 同上 |
| 複雑度 | `radon` / `lizard` | `eslintcc` / `ts-complex` |
| import 解析 | `ast` | `ts-morph` |
| test surface | `pytest --collect-only` AST | `jest --listTests` |
| coverage（P3+） | `coverage.py` | `c8` / `nyc` |

### 6.2 partial extraction tolerance

一部 extractor が落ちても、他の verdict は維持する。失敗した次元は対応する制約の `unknown_policy` に従う。

## 7. effect_db の設計

### 7.1 保守的な副作用シグネチャ辞書

完全な副作用解析は P1 範囲外。**known-effect の API シグネチャ辞書** として始める。

```yaml
effects:
  - id: builtin_open
    language: python
    match:
      call: open
    effect: fs
    access: unknown
    severity: medium

  - id: os_remove
    language: python
    match:
      call: os.remove
    effect: fs
    access: write
    severity: high

  - id: urllib_urlopen
    language: python
    match:
      call: urllib.request.urlopen
    effect: net
    access: read
    severity: high
```

### 7.2 検出結果には confidence と resolution_level を必ず持たせる

```yaml
detected_effect:
  effect: fs
  access: write
  confidence: 0.7
  evidence:
    call: write_text
    file: src/config.py
    line: 44
  resolution_level: method_name_only  # direct_call | imported_alias | method_name_only
```

これにより誤検出と確定検出を区別できる。

### 7.3 解決レベルの段階的実装

| Level | 例 | P1 範囲 |
|---|---|---|
| 1: direct call | `open()`, `os.remove()` | ✓ |
| 2: imported alias | `from os import remove as rm; rm()` | 一部 |
| 3: object method | `Path("x").write_text()` | ✗（P2 以降） |

完全な型・名前解決は P1 では狙わない。

### 7.4 P1 seed: Python 標準ライブラリ

| effect | entries（抜粋） |
|---|---|
| **fs** | `open`, `pathlib.Path.open`, `Path.read_text`, `Path.write_text`, `os.remove`, `os.unlink`, `os.rename`, `os.replace`, `os.mkdir`, `os.makedirs`, `shutil.copy`, `shutil.copyfile`, `shutil.copytree`, `shutil.rmtree`, `shutil.move` |
| **net** | `socket.socket`, `urllib.request.urlopen`, `http.client.HTTPConnection`, `http.client.HTTPSConnection`, `ftplib.FTP`, `smtplib.SMTP`, `imaplib.IMAP4`, `poplib.POP3`, `xmlrpc.client.ServerProxy` |
| **process** | `subprocess.run`, `subprocess.Popen`, `subprocess.call`, `os.system`, `os.exec*`, `os.spawn*` |
| **env** | `os.environ`, `os.getenv`, `os.putenv`, `os.unsetenv` |
| **time_random** | `time.time`, `datetime.datetime.now`, `datetime.date.today`, `random.*`, `secrets.*`, `uuid.uuid4` |
| **stdout** | `print`, `sys.stdout.write`, `sys.stderr.write`, `logging.*` |
| **dynamic_code** | `eval`, `exec`, `compile`, `__import__`, `importlib.import_module` |
| **unsafe_deserialize** | `pickle.load`, `pickle.loads`, `marshal.load`, `marshal.loads` |
| **global_mutation** | `global` 文, module-level 再代入, module global の変更 |

## 8. Verdict 設計

### 8.1 3-tier semantics

| verdict | 条件 |
|---|---|
| **pass** | hard 制約全て満たす + soft 違反は tolerance 内 + unknown は non-critical |
| **repair** | hard 違反があるが回復可能 / soft 違反が tolerance 超過 / 宣言意図と observed delta が不整合だが回復可能 |
| **fail** | spec 矛盾 / critical 制約での extractor 失敗 / 禁止 effect 検出 / refactor で公開 API 破壊 / セキュリティ関連 dynamic_code 導入 |

### 8.2 階層的判定（lock 違反は即 fail）

```
1. lock 違反が 1 つでも → fail（即時、loss 計算不要）
2. preserve 違反 → repair（修復可能、loss に加算）
3. over_changed → repair（change_budget 超過分を縮減）
4. metric tolerance 内逸脱 → loss 加算
5. 全て tolerance 内 → pass
```

### 8.3 exit code policy

```
pass   → exit 0
repair → exit 1（CI を block）
fail   → exit 2（CI を block、より重篤）
```

## 9. Repair SVP

### 9.1 構造

```yaml
repair:
  preserve:                     # 維持を引き継ぎ
    - api_of: src.auth.login
  restore:                      # 削除されたものを復旧
    - public_function: src.api.users.delete_user
  reduce:                       # 過剰変更を縮減
    - imports_added: ["aiohttp"]
    - files_touched: ["src/utils/helpers.py"]
  defer:                        # 今回は保留
    - "complexity_reduction_in: src/core/engine.py"
  lock:
    - public_api_of: src.models.*
  repair_order:                 # 修復の優先順
    - restore_api
    - reduce_imports
    - retry_feature_addition
```

### 9.2 Repair SVP は **コードを直接変更しない**

Repair SVP は決定論的な修復指示を出すのみ。実際のコード patch は外部 generator（Codex / Claude Code 等）が次サイクルで適用する。これにより:

- Semantic CI は決定論を維持
- 生成は generator の責務
- 両者の責任分界が明確

### 9.3 Repair Compiler（P5 範囲）

将来、Repair SVP を generator-specific な prompt patch に変換する layer を追加する:

```
Repair SVP → Repair Compiler → {
  Codex prompt patch,
  Claude Code instruction,
  Cursor edit hint,
  ...
}
```

P1 では Repair SVP を JSON / YAML として emit するのみ。

## 10. Hash Trail（reproducibility）

### 10.1 hash に含めるべき要素

```python
input_hash = hash(
    target_svp_hash,
    baseline_code_hash,
    candidate_code_hash,
    schema_version,
    extractor_versions = {
        "griffe": "0.42.0",
        "mypy": "1.8.0",
        "radon": "6.0.1",
        ...
    },
    effect_db_version,
    constraint_operator_version,
    python_version,            # interpreter version も影響する
    config_hash,               # 設定 yaml の hash
    threshold,                 # 既出: 閾値も状態の一部
)
```

### 10.2 なぜ extractor version が必須か

`mypy` / `pyright` / `radon` / `griffe` などはバージョンアップで出力が変わる可能性がある。Semantic CI が再現性を名乗るなら、これらすべての version を hash trail に含める必要がある。

### 10.3 Round-trip Log

各段階の中間生成物の hash を chain として記録:

```yaml
round_trip:
  - stage: extract_baseline
    input_hash: <baseline_code_hash>
    output_hash: <baseline_rpe_hash>
    extractor_versions: {...}
  - stage: extract_observed
    input_hash: <candidate_code_hash>
    output_hash: <observed_rpe_hash>
  - stage: compile_expected
    input_hash: <target_svp_hash>
    output_hash: <expected_rpe_hash>
  - stage: evaluate_constraints
    input_hash: <expected_rpe_hash + baseline_rpe_hash + observed_rpe_hash>
    output_hash: <constraint_results_hash>
  - stage: semantic_diff
    output_hash: <diff_hash>
  - stage: verdict
    output_hash: <verdict_hash>
  - stage: repair_svp
    output_hash: <repair_svp_hash>
```

## 11. アーキテクチャ

### 11.1 Framework / Domain 分離

```
svp-rpe-code/
├── framework/              # ← モダリティ非依存（音楽版と将来共通化）
│   ├── target_svp.py       # 仕様モデル
│   ├── constraint_types.py # state / delta / repair の型定義
│   ├── operators.py        # typed operator 実装
│   ├── expected_compiler.py
│   ├── constraint_evaluator.py
│   ├── diff.py             # CodeStateDelta + Semantic Diff
│   ├── repair_compiler.py
│   ├── verdict.py
│   └── hash_trail.py
├── domain_code/            # ← コードドメイン固有
│   ├── state_schema.py     # CodeState + CodeStateDelta
│   ├── change_kind_templates.py
│   ├── languages/
│   │   ├── python/
│   │   │   ├── api_surface.py    # griffe wrapper
│   │   │   ├── type_diff.py      # mypy/pyright wrapper
│   │   │   ├── effect.py         # AST + effect_db
│   │   │   ├── complexity.py     # radon wrapper
│   │   │   ├── imports.py        # ast wrapper
│   │   │   └── test_surface.py   # pytest collect wrapper
│   │   └── typescript/           # P3 以降
│   │       └── ...
│   ├── effect_db/
│   │   ├── python_io_apis.yaml
│   │   ├── python_net_apis.yaml
│   │   └── typescript_*.yaml     # P3 以降
│   └── rules/
│       ├── change_kind.yaml      # refactor/feature/fix 分類規則
│       └── repair_priority.yaml
├── adapters/                # ← 外部統合（P3+）
│   ├── github_action.py
│   ├── claude_code.py
│   └── cursor.py
└── tests/
    └── fixtures/
        ├── feature_clean/
        ├── feature_with_breaking_change/
        ├── refactor_clean/
        ├── refactor_violates_lock/
        ├── bugfix_minimal/
        └── bugfix_over_changed/
```

### 11.2 framework/ は将来音楽版と共通化する

`Baseline RPE` 概念・`StateConstraint / DeltaConstraint / RepairConstraint` 型システム・`unknown_policy`・`evidence chain` などは modality 非依存。Code Edition で確立後、音楽版に逆輸入する。

## 12. フェーズ計画

> **現在地(2026-05 時点)**: P1 完走間近(Brief 1〜4 merged、Exit criteria 達成済み)。Brief 5 planning に向けて P2 / P2.5 の入口段階。Brief 進捗の詳細は §25 参照。
>
> **§21 / §22 による前倒し反映**: Generator Adapter(元 P5)と Repair Compiler は **P2.5** に、TypeScript extractor(元 P3b)は **P2.5 並列** に移動済み。本節の元計画と §21/§22 で記述が分かれている箇所は §21/§22 が優先。

### P1: Python Static Semantic CI MVP（3–4 週） ✓ 完走間近

- Python のみ
- 静的特徴のみ（coverage は除外）
- 抽出: `api_surface`, `type_surface`, `imports`, `complexity`, `test_surface`, `effects_light`
- `effects_light` は AST + import/call pattern による保守的検出（Level 1 + 一部 Level 2）
- `Baseline RPE` + `Observed RPE` 両方向抽出
- `Target SVP` YAML パーサ
- `Expected RPE` compiler（change_kind テンプレート展開込み）
- typed `Constraint Evaluator`
- `CodeStateDelta`
- `Semantic Diff`
- `Repair SVP`
- CLI + JSON レポート
- `hash_trail`（extractor version 含む）
- fixtures 6 件で round-trip テスト pass

**Exit criteria**: fixtures 全件で verdict 安定 + 決定論テスト pass + hash trail が再現可能

**Status**: Brief 1(schema)/ Brief 2(extractor 6 次元)/ Brief 3(pipeline)/ Brief 4(CLI 5 subcommand)が CSCI-1〜19 として merged。`semantic-ci` CLI release 可能状態。

**P1 内 hot-fix(優先、Brief 4c で対応)**:
- **effects slice extractor の `fqn` semantics 修正**: `python_effect_extractor.py` の `EffectEntry.fqn` が現在 callee 名(例: `print`)を保持しているが、§3.1 schema は enclosing function(例: `audit.audit_state`)を要求している。AST `NodeVisitor` 化 + FunctionDef stack 導入で per-fqn 比較を機能させる。半日〜1 日規模、Brief 4b と並列可。詳細は `.claude/memory/2026-05-05.md` Session 2

§7.3 の Level 2/3(method call 解決、`Path.write_text` 等)は P2 予定どおり、本 hot-fix のスコープ外。

### P2: Python Repair Core Completion（3–4 週） ⏭ 次フェーズ

- effect_db 拡張（resolution Level 2 / 一部 3）
- 部分 CFG / 簡易 data flow
- `repair_order` の優先順制御
- `reduce` / `defer` / `lock` の完全実装
  - **`lock` operator は §8.2 の lock violation 即 fail 仕様に準拠**（Brief 3 残課題 #8 を本フェーズで吸収）
- Markdown レポート
- snapshot tests（fixture diff の自動検出）
- **Performance budget 部分対応（§18）**: per-extractor timeout、incremental extraction の foundation（Brief 3 残課題 #5 から本フェーズに繰り上げ）
- **Hash trail per-extractor version（§10 残部）**: extractor 個別 version を hash に組み込み、P3a empirical alignment の reproducibility 担保（Brief 3 残課題 #9 残部から本フェーズに繰り上げ）

### P2.5: Vibe Coding Adapter + Repair Compiler + TS extractor 並列（§21 / §22 で前倒し）

§12 元計画(P5 / P3b)から **P2.5 へ前倒し**された統合 phase。詳細は §21・§22。

- **Generator Adapter**(§21.3): Claude Code / Cursor / Codex / v0 / Lovable / Bolt 等の AI 生成ツール統合
- **Repair Compiler**(§21.4 / §9.3): Repair SVP → generator-specific prompt の compiler
- **TypeScript extractor 着手**(§22.2): P3b から並列前倒し
- **Pre-generation validation 専用 entry point**(候補): `semantic-ci validate-plan` 等(`docs/pre_generation_validation_case.md` 残された問い #4)

### P3a: GitHub Action 配布（Python only）（2–3 週）

empirical alignment データ収集を急ぐため、TypeScript 対応より先に実 PR で回す。

- GitHub Action として配布
- 実 PR 100 件で人間 reviewer 判定 vs ツール verdict の比較データセット構築
- 一致率 / 不一致パターンを分析しルール調整

### P3b: TypeScript Edition（4–6 週）

- `ts-morph` ベースの extractor 一式
- TypeScript extension schema
- TypeScript fixtures
- 言語横断スキーマの妥当性検証

### P4: CI Integration の本格化

- Codeberg 対応
- manifest runner（複数 PR / 複数 artifact 一括処理）
- artifact upload
- exit code policy の本番運用

### P5: Generator Adapter → §21.1 で **P2.5 に前倒し済み**(本 phase は実質空席)

元計画では最終フェーズだったが、vibe coding ツールの普及加速を受けて中身が P2.5 に移動。履歴として残す。

- `Repair SVP` → generator-specific prompt patch の compiler
- Codex / Claude Code adapter
- 生成 → 観測 → 修復 → 再生成の自動ループ

## 13. 範囲外（P1 で **やらない** こと）

意図的に除外:

- coverage 計算（dynamic 拡張、P3+）
- 完全な CFG 解析（P2）
- 完全な data flow 解析（P2+）
- behavioral correctness 証明（範囲外、Rice 定理）
- 自動コード patch 生成（範囲外、generator の責務）
- 多言語同時対応（P3 以降）
- LLM 補助 critique（別 layer、advisory tier）
- spec 自動推論（P4 以降）

これらに手を出すと、Semantic CI の核（**spec → expected → observe → diff → repair**）が固まる前に普通の静的解析ツール開発に逸れる。

## 14. 検証戦略

### 14.1 8 層の検証

| # | 層 | 検証内容 | 検証手段 |
|---|---|---|---|
| 1 | extractor unit test | 各抽出器が正しく動く | 既知 input → 既知 output |
| 2 | fixture test | エンドツーエンドで verdict が正しい | 人間が作った before/after + 期待 verdict |
| 3 | determinism test | 同入力で同出力 | 自分自身を 2 回走らせて bit-equal 比較 |
| 4 | round-trip test | Observed と Expected が同じ state space | 実コード → Observed → 仕様化 → Expected → 一致 |
| 5 | mutation test | gate が違反を検知する | passing fixture を意図的に破壊 → 落ちるか |
| 6 | anti-mutation test | gate が false positive を出さない | 無害な変更（コメント等）→ pass のままか |
| 7 | human alignment test | 人間判断と一致する | 実 PR 100 件で人手分類と比較 |
| 8 | self-application | 自分自身に当てる | Code Semantic CI のコード自身を gate |

### 14.2 regress の底

「検証器を検証する検証器を…」という無限後退は 3 つで止まる:

1. **fixture（人手で作った ground truth）** — `tests/fixtures/*/expected_verdict.yaml` に人間が宣言
2. **決定論性（数学的性質）** — 外部 ground truth 不要、自分で確認可能
3. **ルールが人間可読** — `change_kind.yaml` 等を人間が直接 audit

### 14.3 LLM-as-judge を ground truth に使わない

便利だが、これをやると:

- LLM の癖がツールに転写される
- 非決定論性が ground truth に混入
- 監査可能性が消える

**人間 reviewer が ground truth、LLM はせいぜい補助**に留める。

## 15. 重要な設計判断（決定済み）

| # | 論点 | 決定 |
|---|---|---|
| 1 | spec 記述形式 | YAML（人手）+ JSON Schema（機械検証） |
| 2 | spec のスコープ | PR 単位 default |
| 3 | 粒度 | function / file / module の混在を許可 |
| 4 | 言語スキーマ | 共通スキーマ + 言語固有 extension |
| 5 | spec 著者 | 人手が default、推論は assist（P4+） |
| 6 | verdict tier | 3-tier (pass / repair / fail) |
| 7 | threshold | per-metric default、aggregate は fallback |
| 8 | extractor 実装 | 既存ツール wrapping のみ |
| 9 | LLM の役割 | 不使用（決定論維持）。critique は将来の別 layer |
| 10 | Constraint DSL | YAML + typed operator のみ。任意 Python 式 / 独自構文 DSL は非採用 |
| 11 | Constraint kind | state / delta / repair の 3 種を明示分離 |
| 12 | Baseline RPE | 必須（refactor / bugfix 検証に不可欠） |
| 13 | change_kind | 宣言制、自動推論は advisory のみ |
| 14 | unknown_policy | per constraint で fail / repair / warn / ignore |
| 15 | Repair SVP | コードを直接変更しない、指示のみ emit |
| 16 | hash trail | extractor version / interpreter version / config hash 全含む |

## 16. 既存プラットフォームとの関係

| 既存 CI | Code Semantic CI |
|---|---|
| 補完関係（置換ではない） | declared intent との整合性 layer |
| lint / type / test を実行 | これらの上に意味的整合性 gate を追加 |
| failure を見せる | failure を意味的に分類 + repair 指示 |

`lint pass + test pass + Code Semantic CI pass` の 3 段ゲートで PR を gate するのが想定運用。

## 17. Spec Authorship Anchoring

### 17.1 役割: 記録 (attribution) のみ、ブロックは外部

semantic CI が担うのは **誰が spec を書いたかの記録**のみ。署名の正当性検証や「N 人の承認が必要」等のブロック判定は外部層に委ねる。

| 層 | 担当 |
|---|---|
| 記録 (attribution) | semantic CI（hash trail に記録） |
| 署名検証 (validation) | git / GPG / sigstore |
| 強制 (enforcement) | CODEOWNERS / branch protection / OPA |

これは §14.2 の「ground truth = 人間」原則と整合し、semantic CI が auth/governance 層に侵食しないための分離。

### 17.2 default behavior

Target SVP に `authorship` セクションを optional フィールドとして定義:

```yaml
authorship:
  authors:
    - identity: alice@example.com
      signature: <sig>
  declared_at: 2026-05-01T12:34:56Z
```

semantic CI はこのフィールドを **evidence chain に転記する**だけで、内容を判定しない。署名が valid かは外部 verifier の責務。

### 17.3 opt-in: 自己宣言型の auth 制約

spec が自己の auth 要件を constraint として宣言した場合のみ、semantic CI は decisive にチェックする:

```yaml
constraints:
  - id: requires_two_authors
    kind: meta
    target: authorship.authors
    operator: count_greater_than_or_equal
    expected: 2
    severity: hard
    unknown_policy: fail
```

- semantic CI: 「authors の数が 2 以上か」を機械的に判定
- 「その author が誰か」「その signature が valid か」は判定しない（外部に委譲）

これにより spec は自己完結した auth 要求を declare でき、semantic CI は declarative model を維持できる。

### 17.4 AI 生成 spec の検出

vibe coding 時代に spec が AI 生成される可能性に対して、heuristic な記録を提供:

- spec 内 `generation_metadata` フィールド（任意）
- 既知の AI tool signature（Claude Code / Cursor / Codex 等の trail）
- これらを evidence chain に記録する（block しない）

判断は組織のポリシーに委ねるが、attribution によって事後的に追跡可能にする。

## 18. Performance Budget

### 18.1 課題

AI 生成 PR が大量発生する環境では baseline 抽出を毎回フル実行すると破綻する。§10 の hash trail と整合しつつ、抽出コストを線形以下に抑える必要がある。

### 18.2 baseline RPE cache

CSCI-26 implements the first operational slice of this budget: `semantic-ci
check` stores ref-backed Python `CodeState` observations in
`.semantic-ci/cache/code_state/`, keyed by the package subtree object id,
package root, execution mode, extracted dimensions, Python minor version,
package version, CodeState schema version, and cache format version. Cache
misses, corrupt entries, and write failures fall back to normal extraction; JSON
verdict output and engine semantics remain unchanged. Worktree caching,
incremental extraction, eviction, and JSON cache statistics remain CSCI-27+
work.

baseline は git ref で content-addressable にキャッシュする:

```
cache key = (
    baseline_code_hash,
    extractor_versions,
    config_hash,
    schema_version,
)
cache value = baseline_rpe (serialized)
```

- main の RPE は最初の 1 回だけ抽出
- PR の baseline が同じ commit を指す限り、抽出スキップ
- extractor version 変更で自動 invalidation（§10.1 の hash trail と一貫）

### 18.3 incremental extraction

candidate 側は変更ファイルのみ再抽出:

- changed files = `git diff --name-only baseline...candidate`
- baseline RPE をベースに、changed files の各次元だけ差し替え
- module graph / imports は依存伝播範囲のみ再計算

### 18.4 per-extractor timeout

各 extractor に timeout を設定し、超過した次元は `unknown_policy` に従う:

```yaml
performance:
  extractor_timeouts:
    api_surface: 30s
    type_surface: 60s
    effects: 30s
    complexity: 15s
  total_budget: 180s
```

- §5.4 の `unknown_policy: fail/repair/warn/ignore` と統合
- timeout で部分結果のまま verdict を出せる（§6.2 partial extraction tolerance）

### 18.5 並列抽出

extractor 間に依存はないため並列実行を default とする。CI matrix での並列化と CLI 内 thread/process pool の二段並列を許容する。

## 19. Spec Quality Metrics

### 19.1 課題

雑な spec は雑な検出しかできない。constraints 0 個の spec は技術的に valid だが意味的に無価値。spec 自身の品質を可視化する meta-verdict を導入する。

### 19.2 spec coverage

spec が言及している RPE 次元の網羅率:

```
spec_coverage = |constrained_dimensions| / |available_dimensions|

available_dimensions = {
    api_surface, type_relations, effects, imports,
    complexity, test_surface, module_graph, ...
}
```

例: `api_surface` と `effects` のみ縛っている spec → coverage = 2/8 = 25%

### 19.3 change_kind デフォルトとの差分

§4.2 の change_kind テンプレート展開で得られる constraints と、ユーザ宣言の constraints の差分を report:

- テンプレートに含まれる制約をユーザが override / 削除 → 警告
- テンプレートが要求する次元をユーザが追加で縛っていない → 情報

### 19.4 meta-verdict

verdict と並行して spec quality verdict を emit:

| level | 条件 |
|---|---|
| good | coverage ≥ 60%、change_kind テンプレートを override 削除していない |
| weak | coverage < 60%、または重要次元（api_surface / effects）の constraint が空 |
| insufficient | constraints が 0 件、または change_kind 未指定 |

これは block しない（§17 と同じ哲学で attribution のみ）。組織が自主的に「weak 以上を要求する」ポリシーを branch protection 側で実装する。

### 19.5 unspecified 次元の自動観測

spec が言及していない次元も extractor は抽出し、evidence chain に記録する。

- ユーザが宣言していない次元の delta も report に含まれる
- block はしないが、後から「あの時 effects が増えていた」を遡れる
- AI 生成 PR の post-incident 分析に有用

## 20. Suite Packaging Strategy

### 20.1 layered distribution

semantic CI を組織が採用しやすい形で配布するため、3 層構成を採る:

```
semantic-ci-code     ← core (本リポジトリ、純粋な intent vs diff)
semantic-ci-suite    ← meta-package (core + ruff + mypy + pytest の opinionated bundle)
semantic-ci-action   ← GitHub Action (suite + workflow yaml + minimal config)
```

### 20.2 core の不変性

`semantic-ci-code` (core) は決定論性・第三者性・LLM 不依存を維持し、特定 lint / type / test ベンダーへの依存を持たない。

### 20.3 suite の opinionated default

`semantic-ci-suite` は core を内包し、§16 の「3 段ゲート」を最小設定で構築する:

- L1+L2: ruff
- L3: mypy（pyright も alternative として選択可能）
- L4: pytest
- L7: semantic-ci-code

これらをまとめた `pyproject.toml` template と CI workflow を提供する。

### 20.4 action の zero-config

`semantic-ci-action` は GitHub Action 化し、最小設定で導入できる:

```yaml
- uses: yuu6798/semantic-ci-action@v1
  with:
    spec: .semantic-ci/intent.yaml
```

§12 P3a の Python only Action 配布をこの戦略に統合する。

### 20.5 ブランド維持

各層の責務を明示する:
- core: decisions about intent
- suite: standard CI stack with intent gate
- action: drop-in PR gate for GitHub

suite / action は便宜であり、core の独立性を希釈しない。

## 21. Vibe Coding Adapter Roadmap

### 21.1 priority shift

§12 元計画では Generator Adapter は P5（最終フェーズ）だが、vibe coding ツール（Cursor / Claude Code / v0 / Lovable / Bolt 等）の普及加速を踏まえ、**P2.5 への前倒し**を採用する。

### 21.2 統合ポイント

vibe coding workflow の各段階で gate を提供:

| 段階 | 統合方式 |
|---|---|
| pre-generation | spec を AI に渡す前に semantic CI が validate |
| post-generation | AI 出力 PR に対して通常の verdict |
| repair loop | Repair SVP を AI への follow-up prompt に変換 |

### 21.3 adapter list (P2.5)

- Claude Code adapter（pre-commit hook / instruction file 連携）
- Cursor adapter（rule file への変換）
- Codex (OpenAI) adapter
- v0 / Lovable / Bolt adapter（HTTP integration、後続）

### 21.4 Repair Compiler の前倒し

§9.3 の Repair Compiler を P5 から P2.5 に移動し、Repair SVP を generator-specific prompt に変換する layer を adapter と同時提供する。

### 21.5 IDE / pre-commit integration

CI 待ちの feedback loop を短縮するため:
- pre-commit hook 統合（軽量モード、partial extraction）
- LSP server 化（IDE 内 real-time gate、P3 以降）

## 22. Multi-language Phasing

### 22.1 課題

§12 元計画では TypeScript は P3b（Python の後）だが、vibe coding 主戦場は TS/JSX が多い（v0 / Lovable / Bolt が React 中心）。市場タイミングに合わせ、TS を P2.5 と並列に前倒しする選択肢を保持する。

### 22.2 段階提案

| Phase | 内容 |
|---|---|
| P1 | Python only（既定通り） |
| P2 | Python repair core + TS schema 検証 |
| P2.5 | vibe coding adapter + TS extractor 着手 |
| P3 | TS GA + 多言語スキーマ妥当性確認 |
| P4+ | Go / Rust / Swift（需要と extractor 成熟度次第） |

### 22.3 schema 共通性の検証

§3.3 の言語固有 extension が複数言語で機能することを早期に確認するため、TS extractor の prototype 段階で共通スキーマの妥当性レビューを実施する。

### 22.4 adapter と language の交差

vibe coding ツールの言語分布を踏まえた優先度:

| ツール | 主言語 | 着手フェーズ |
|---|---|---|
| Claude Code / Codex | Python / TS / 多 | P2.5 |
| Cursor | 多言語 | P2.5 |
| v0 / Lovable / Bolt | TS / React | P2.5（TS 必須） |

これにより §21 の adapter 計画と §22 の TS 前倒しが整合する。

## 23. Comparator Architecture and Application Matrix

### 23.1 中核 contract: Generic 2-state Comparator

semantic CI の core engine は **PR 専用ではなく、汎用的な 2-state 比較器** として設計する。入力 contract:

```
入力:
  - baseline_state: CodeState   (実コード抽出 / 仮想 / mock いずれも可)
  - candidate_state: CodeState  (同上)
  - intent: target.yaml         (declared change intent)

出力:
  - verdict: pass | repair | fail
  - violations: tuple[Violation, ...]
```

`CodeState` は frozen Pydantic schema として抽象化されているため、**どこから観測されたかを engine は問わない**。これは §2 の 3-state RPE モデル（baseline と observed が両方 CodeState 型）の自然な帰結であり、§21.2 pre-generation validation の前提条件でもある。

PR は最初の主要ユースケースだが、唯一のユースケースではない。Engine の入力契約を生成元から分離することで、後続フェーズでの応用範囲を確保する。

### 23.2 Application Matrix

`CodeState` を「実コード抽出」以外から供給することで、以下の用途が成立する:

| 用途 | baseline 取得 | candidate 取得 | intent 由来 | フェーズ |
|---|---|---|---|---|
| **PR review** | git baseline ref | git candidate ref | `.semantic-ci/intent.yaml` | P1 (Brief 4) |
| **pre-commit hook** | HEAD | staged tree | working intent | §21.5, P3+ |
| **任意 2 リビジョン比較** | 任意 commit | 任意 commit | 任意 yaml | P1 (Brief 4) |
| **retrospective audit** | 過去 tag | 過去 tag | 過去 spec を再現 | P3+ |
| **nightly regression scan** | 24h 前 main | 現 main | observation only | §19.5, P3+ |
| **pre-generation validation** | 現コード | AI 提案 state（予測） | AI 依頼 spec | §21.2, P2.5 |
| **what-if simulation** | 現コード | hypothetical state | 設計仮説 | §21, P2.5+ |
| **contract testing** | expected state | actual state | contract spec | 応用領域 |
| **educational simulator** | mock state | mock state | 学習用 spec | 応用領域 |

「実コードがそこに存在する」という前提を engine から切り離すことで、AI 時代の vibe coding workflow（§21）と監査・教育・契約テストといった他用途の両方を同一 engine でカバーできる。

### 23.3 Brief 4 設計方針への波及

§24 Brief 4（CLI）は **「PR 専用 CLI」ではなく「2 リビジョン汎用比較器」として設計する**。具体的には:

```bash
# パターン A: 暗黙の PR モード（最頻ユースケース）
semantic-ci-code check
# → 自動で main と現ブランチを比較

# パターン B: 任意 2 リビジョン
semantic-ci-code check --baseline=v1.0.0 --candidate=v1.1.0

# パターン C: 単発観測（intent なし）
semantic-ci-code observe --target=HEAD

# パターン D: 任意 snapshot ディレクトリ
semantic-ci-code check --baseline-dir=./snap_a --candidate-dir=./snap_b

# パターン E: pre-commit
semantic-ci-code check --baseline=HEAD --candidate=staged
```

Engine 本体は同一で、CLI が baseline/candidate の取得経路を切り替えるだけ。実装コスト差は引数パースの増分のみ。

### 23.4 設計上の含意

generic comparator として設計することの帰結:

- **エンジンは「実コードがそこに在ること」を前提にしない** — lint/type/test との根本的な差別化
- **§21.2 pre-generation validation が core engine 機能として直接成立** — adapter 層の追加実装が薄くなる
- **§10.3 Round-trip Log に仮想 state も hash 化して記録可能** — 「いつ、どんな仮想シナリオで、どんな verdict が出たか」を audit log に残せる
- **§19.5 unspecified 次元の自動観測** が retrospective audit や regression scan として直接使える

この generic comparator 性質は P1 で実装するが、応用ユースケース（pre-generation / what-if / contract test）は P2.5 以降の vibe coding adapter 層で本格化する。**Engine の input contract を最初から仮想 state も受け付ける形に保つ** ことが、後付け応用を可能にする鍵。

## 24. 関連ドキュメント

- [`CLAUDE.md`](../CLAUDE.md) — リポジトリ全体の運用ポリシー
- [`AGENTS.md`](../AGENTS.md) — Claude × Codex 連絡プロトコル（Task Brief / Completion Summary）
- [`brief_3_planning.md`](./brief_3_planning.md) — Brief 3 (pipeline 統合) を CSCI-10〜14 の 5 PR に分割する planning（Brief 3 完了時に archive 候補）

今後 `docs/<topic>.md` を追加した場合は、本節と README の Documentation 節に追記する。

## 25. 次のアクション

本設計を Codex 実装に落とすため、以下の順で Task Brief を発行する。

> **現行運用(2026-05 確定、Brief 3/4 未解決の再分配反映済み)**:
> - **Brief 5 の肥大化を解消**: `semantic-ci init`(Q4)と spec authorship anchoring(§17 / Brief 3 #7)と soft/info constraint kind(Brief 3 #2)は **Brief 4d に独立 thin Brief 化**。Brief 5 本体は Vibe Coding Adapter + Repair Compiler に絞る
> - **Brief 4b に Q11 同梱**: pre-commit framework manifest(`.pre-commit-hooks.yaml`)を SARIF と一括で発行
> - **Brief 5 と Brief 6 を並列発行**: §22 設計通り(直列の "Brief 5 → Brief 6" を改める)
> - **P2 Brief 化時に Brief 3 #5 / #8 / #9 残部を細目として明記**: Lock violation 即 fail / per-extractor timeout / per-extractor version の hash trail 組込
> - 元 §25 計画の Brief 5(spec authorship + performance budget)/ Brief 6(spec quality + suite packaging)は分解済み — §17 / §18 は本表で行先確定、§19 / §20 のみ Brief 7+ に残置

| Brief | 範囲 | 想定 PR | Status |
|---|---|---|---|
| **Brief 1** | schema 定義（`CodeState` / `CodeStateDelta` / `Constraint` 型 / `Target SVP` DSL JSON Schema） | `codex/code-semantic-ci-schema` | merged |
| **Brief 2** | extractor 実装（Python のみ、6 次元） | `codex/code-semantic-ci-py-extractors` | merged (CSCI-5〜9) |
| **Brief 3** | pipeline 統合（compiler / evaluator / diff / repair） | `codex/code-semantic-ci-pipeline` | merged (CSCI-10〜14、`brief_3_planning.md` archived) |
| **Brief 4** | CLI + JSON report + fixture テスト | `codex/code-semantic-ci-cli` | merged (CSCI-15〜19、`brief_4_planning.md` 完結) |
| **Brief 4b** | SARIF 出力（Q9）+ GitHub Actions annotation（Q10）+ **`.pre-commit-hooks.yaml` manifest（Q11）同梱** | `codex/code-semantic-ci-sarif-precommit` | **next**(Brief 4c / 4d と並列発行) |
| **Brief 4c** | effect extractor の `fqn` semantics 修正（callee → enclosing function、§3.1 schema 適合） | `codex/code-semantic-ci-effect-fqn-fix` | **P1 内 hot-fix(優先)**、Brief 4b と並列 |
| **Brief 4d** | `semantic-ci init`（Q4、target.yaml scaffolding）+ **spec authorship anchoring（§17 / Brief 3 #7）** + **soft / info constraint kind（Brief 3 #2）** — thin spec/CLI 拡張 | `codex/code-semantic-ci-thin-spec` | **Brief 4b / 4c と並列発行可、Brief 5 の前** |
| **Brief 5** | **Vibe Coding Adapter（§21.3）+ Repair Compiler 前倒し（§9.3 / §21.4 / Brief 3 #4）** — P2.5 entry に絞る | `codex/code-semantic-ci-adapter-compiler` | planning |
| **Brief 6** | TypeScript extractor 着手（§22.2、P2.5 並列） | `codex/code-semantic-ci-ts-extractor` | **Brief 5 と並列発行**（§22 設計通り） |
| **P2 Brief 群** | Repair Core Completion (§12 参照) — Brief 3 #5 / #8 / #9 残部を細目として明記:<br>・**Lock violation 即 fail（§8.2 / Brief 3 #8）** を `lock` operator 完全実装の一部として<br>・**Performance budget 部分対応（§18 / Brief 3 #5）**: per-extractor timeout、incremental extraction の foundation<br>・**Hash trail per-extractor version（§10 / Brief 3 #9 残部）**: P3a empirical alignment の reproducibility 担保 | TBD（P2 Brief 化時に分割） | pending |
| **Brief 7+ deferred** | spec quality metrics（§19 / Brief 3 #6）+ suite packaging（§20）+ tolerance / scope / unknown_policy override（Brief 3 #3）+ Round-trip log（§10.3 / Brief 3 #10）+ orchestrator 観測応用（`docs/multi_agent_audit_case.md`） | TBD | deferred |

各 Brief 完了ごとに Claude が Completion Summary を review し、次 Brief を発行する。
