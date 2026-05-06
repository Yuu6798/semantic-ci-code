# Brief 3 Planning — Pipeline 統合 (判定層) の分割計画

> **STATUS: Archived (Brief 3 complete).**
> 本文書は履歴保存目的で残されている。Brief 3 は CSCI-10 (PR #15) / CSCI-11 (#16) /
> CSCI-12 (#17) / CSCI-13 (#18) / CSCI-14 (#19) として全 PR が merge 済みで完結した。
> 後続の Brief 4 (CLI / operational entrypoint) の planning は
> [`docs/brief_4_planning.md`](./brief_4_planning.md) を参照。
>
> 本文書内に記された operator 5 個案などの **CSCI-12 周りの記述は CSCI-12 brief 段階で
> 上書き** されている (Operator enum 20 個 / `tolerance` 等の field 受理の方針が正)。
> 当時の判断履歴として残す。

本文書は `docs/code_semantic_ci_design.md` §24 の Brief 3 を 5 つの narrow PR (CSCI-10 〜 CSCI-14) に分割する計画。Brief 3 完了後は archive 候補。

## 位置付け

Brief 2 (Python P1 抽出器 6 次元) が完了し、`CodeState` の全観測点が deterministic に取得可能になった。Brief 3 は **observed delta vs declared intent** を機械的に照合する判定層を構築する。

```
Brief 1: schema 定義              ✅
Brief 2: Python 抽出器 6 次元      ✅ (CSCI-2/3/4/5/6/7/8/9)
Brief 3: pipeline 統合             ← 本文書の対象
Brief 4: CLI + JSON report
Brief 5+: attribution / quality / suite / vibe-coding adapter
```

## 設計方針 (Q&A で確定)

planning セッションで 4 つの方向性を確定。詳細は本節の各項目を参照。

### Q1: 判定の厳しさ — **B (バランス)**

- unknown_policy default = `repair`
- hard 制約のみ P1 で実装 (soft / info は P1 で受け付けない)
- operator 5 個セット (Q3 と整合): `equals_baseline` / `subset_of` / `superset_of` / `disjoint_from` / `count_less_than_or_equal`

採用理由:
- §14.2 の「ground truth = 人間」原則と整合 (機械は曖昧なケースを断定しない)
- §17 の attribution-only 哲学とも整合 (ブロックは外部層に委ねる)
- 厳格 (A) は誤検出で開発者の信頼を失う、寛容 (C) は CI として弱い

### Q2: 分割粒度 — **5 PR に細分割 (CSCI-10〜14)**

- 各 PR 200-400 LOC 想定
- Brief 2 で 5 PR を 1 セッションで回した実績を踏襲
- 動くものは CSCI-13 で見える (4 PR 後)

採用理由:
- Brief 2 が deviation 0 で merge できた要因は narrow Brief
- CSCI-12 (compiler) と CSCI-13 (evaluator) は思想が異なる (YAML 解釈 vs 照合ロジック)
- 太い PR は Codex の解釈ブレを誘発しやすい

### Q3: target.yaml の形 — **B (標準)**

`.semantic-ci/intent.yaml` (PR ごとに添えるファイル) で受け付けるフィールド:

| フィールド | 扱い |
|---|---|
| `intent` | **必須** (string) |
| `change.primary_kind` | **必須** (`feature` / `bugfix` / `refactor` / `test_update`) |
| `change.allowed_secondary_kinds` | optional (list of primary_kind) |
| `constraints[]` | optional |
| `constraints[].id` | constraints 内必須 (string) |
| `constraints[].kind` | constraints 内必須 (`state` / `delta`) |
| `constraints[].target` | constraints 内必須 (RPE field path string) |
| `constraints[].operator` | constraints 内必須 (5 個セット) |
| `constraints[].expected` | constraints 内必須 (literal or `"baseline"`) |
| `constraints[].severity` | constraints 内必須 (`hard` のみ受け付け) |

P1 で **拒否する** (compile error として弾く) フィールド:

- `severity: soft` / `severity: info` — hard 強制
- `unknown_policy` override — default `repair` 固定
- `tolerance` — 緩衝なし
- `constraints[].scope: file|module|function` — 全コードベース対象
- `evidence_required` — 常に true 扱い
- `change.scope.files` / `change.scope.modules` — P1 で実装しない
- `authorship` (§17) / `performance` (§18) — 後続 Brief

採用理由 ("緩める呪文を書ける機能自体を P1 で実装しない"):
- semantic CI は構造上「書き手が判定基準を決める」CI である
- 表現力が高すぎると書き手 (AI でも人間でも) が自分の検査を緩める呪文を書ける
- フルスペック (C) は AI が `severity: soft` / `tolerance: 5` 等で意図せず検査をすり抜ける
- 厳しくする方向 (`constraints[]` 追記) のみ P1 で許可、緩める方向は P1 で拒否
- §19 の meta-verdict と組み合わせて P2.5 で「緩める呪文と検出機構をペアで」解禁する

### Q4: Repair SVP の詳しさ — **B' (B + stable error code)**

各 violation に:
- `code`: 安定した error code (例: `API_SURFACE_ADDED_IN_REFACTOR`) — ruff スタイル
- `constraint_id`: どの constraint が違反したか
- `target`: RPE field path
- `actual`: 違反の中身 (delta の該当部分)
- `evidence`: extractor 名 / file / line

P1 で **生成しない**:
- `suggestion.candidates` (修正候補) — §9.3 Repair Compiler (P2.5) の責務

採用理由:
- §9.3 Repair Compiler / §21.4 generator-specific prompt との責務分離
- evidence chain は §10 hash trail 整合のため P1 で必須
- §21 vibe coding adapter は evidence の file/line がないと AI prompt を生成できない
- 修正候補は generator (Claude / Cursor / Codex) ごとに最適フォーマットが違う、CSCI-14 で固定すると後で困る
- error code は ruff/ESLint の成功パターン (stable ID で参照可能、grep / suppression / 集計が将来効く)

## 5 PR への分割

### CSCI-10: CodeState Orchestrator

**Goal**: 6 抽出器 (effects / api_surface / imports / module_graph / complexity / test_surface) を呼び出し 1 つの `CodeState` を組む薄い層。

**Public API**:
```python
def extract_code_state(
    package_root: Path,
    *,
    paths: Iterable[Path] | None = None,
) -> CodeState: ...
```

**Scope**:
- IN: `src/semantic_ci_code/orchestrator/` (新設)、`src/semantic_ci_code/common/` (新設、共有 helper) 、テスト + フィクスチャ
- OUT: schema、各抽出器、CLI、git 操作

**含める refactor**:
- `_iter_module_scope_*` パターンの共有 helper 化 (`semantic_ci_code.common.ast_walk`)
- `_module_fqn_from_path` の `semantic_ci_code.common.module_fqn` への昇格
- ast.walk ベース forbidden-import 検査の他 4 抽出器 (CSCI-5/6/7/8) への back-port

**設計判断**:
- git 操作なし (CLI 層 = Brief 4 の責任)
- SyntaxError は伝播 (partial extraction tolerance は §6.2、後続 Brief)
- 並列抽出は P1 で実装しない (§18.5、後続 Brief)
- パフォーマンスキャッシュなし (§18.2、後続 Brief)

**Required tests** (最小):
- 6 次元すべてが populate される
- 共有 helper 化後も既存抽出器テスト全件が green
- subprocess 跨ぎ determinism
- `paths=None` で whole package_root 対象、`paths=...` で個別ファイル指定
- forbidden import 検査が 6 抽出器すべてで動く

**Branch / PR**: `codex/csci-10-codestate-orchestrator` / `feat(orchestrator): add CodeState orchestrator (CSCI-10)`

### CSCI-11: CodeStateDelta Computer

**Goal**: 2 つの `CodeState` から `CodeStateDelta` を計算する純粋関数。

**Public API**:
```python
def compute_code_state_delta(
    baseline: CodeState,
    candidate: CodeState,
) -> CodeStateDelta: ...
```

**Scope**:
- IN: `src/semantic_ci_code/delta/` (新設)、テスト + フィクスチャ
- OUT: schema、抽出器、CLI、git 操作

**設計判断**:
- リネーム検出なし (set 差分のみ、`pkg.foo` → `pkg.bar` は「foo 削除 + bar 追加」)
- 各次元の差分ルールを docstring に逐語固定 (CSCI-5〜9 と同じ docstring contract pattern)
- `loc_delta` / `files_touched` は外部入力 (Brief 4 で git diff 経由で渡す)、CSCI-11 では未実装または optional 引数扱い
- complexity_delta は cyclomatic / cognitive それぞれの「追加された関数の合計」マイナス「削除された関数の合計」(maybe-decrease 判定の基礎)

**各次元の差分ルール** (docstring に逐語固定):

| Dimension | 差分計算 |
|---|---|
| api_surface | `(fqn, kind)` で同定、`signature` 変更を `changed`、欠損を `removed`、新規を `added` |
| type_relations | `(fqn, type_expr)` セット差 |
| effects | `(fqn, effect_class)` セット差 |
| imports | `(module, from_, symbols)` セット差 |
| module_graph | `(module → imports)` の edge セット差 |
| complexity | `fqn` で同定、`cyclomatic` / `cognitive` の差を delta に |
| test_surface | `(test_file, test_function)` で同定、`asserts` / `parametrize_count` の差を delta に |

**Required tests** (最小):
- 各次元の add / remove / change を最低 1 ケースずつ
- 同一 state 同士で空 delta
- 全 6 次元の差分が 1 つの delta オブジェクトに統合される
- subprocess 跨ぎ determinism
- `model_dump_json()` byte-identical

**Branch / PR**: `codex/csci-11-codestate-delta` / `feat(delta): add CodeStateDelta computer (CSCI-11)`

### CSCI-12: Constraint Compiler

**Goal**: `target.yaml` を解釈し、内部表現の `Constraint` リストにコンパイル。

**Public API**:
```python
def compile_target_svp(
    yaml_source: str,
    *,
    filename: str = "<string>",
) -> CompiledTarget: ...

@dataclass(frozen=True)
class CompiledTarget:
    intent: str
    primary_kind: ChangeKind
    allowed_secondary_kinds: tuple[ChangeKind, ...]
    constraints: tuple[CompiledConstraint, ...]
```

**Scope**:
- IN: `src/semantic_ci_code/compiler/` (新設)、テスト + フィクスチャ
- OUT: schema、抽出器、CLI、評価器、Repair emitter

**設計判断**:
- `target.yaml` の受け付けフィールドは Q3 で確定したセットに厳密に制限
- 拒否フィールドは **黙って無視せず compile error** として明示的に弾く (`unknown_policy` 等を AI が書いてもエラーになる)
- operator 5 個セット (Q1 で確定):
  - `equals_baseline`
  - `subset_of`
  - `superset_of`
  - `disjoint_from`
  - `count_less_than_or_equal`
- `change_kind` テンプレート展開:

| primary_kind | 自動展開される hard 制約 |
|---|---|
| `feature` | 既存公開 API 削除禁止、未宣言 effect 追加禁止 |
| `bugfix` | 公開 API 不変、未宣言 effect 追加禁止 |
| `refactor` | 公開 API 不変、type_relations 不変、effects 不変、test_surface 不変 |
| `test_update` | production code (api_surface / effects / imports) 不変 |

- ユーザー定義 `constraints[]` はテンプレート展開後に **追加** される (override は P1 で許可しない、緩める呪文と同じ理由)

**Required tests** (最小):
- 必須フィールド欠落で compile error
- 拒否フィールド (`tolerance` / `severity: soft` 等) が書かれていたら compile error
- 各 primary_kind でテンプレートが期待通り展開
- `constraints[]` がテンプレートに追加される
- 5 個の operator がすべて正しくパース
- subprocess 跨ぎ determinism

**Branch / PR**: `codex/csci-12-constraint-compiler` / `feat(compiler): add Target SVP constraint compiler (CSCI-12)`

### CSCI-13: Constraint Evaluator

**Goal**: コンパイル済み constraints と `CodeStateDelta` から `Verdict` を生成。

**Public API**:
```python
def evaluate_constraints(
    compiled: CompiledTarget,
    delta: CodeStateDelta,
    *,
    baseline: CodeState,
    candidate: CodeState,
) -> Verdict: ...

@dataclass(frozen=True)
class Verdict:
    result: VerdictResult  # pass | repair | fail
    violations: tuple[Violation, ...]

@dataclass(frozen=True)
class Violation:
    code: str  # error code (Q4)
    constraint_id: str
    kind: ConstraintKind
    target: str
    operator: str
    expected: object
    actual: object
    evidence: Evidence
```

**Scope**:
- IN: `src/semantic_ci_code/evaluator/` (新設)、テスト + フィクスチャ
- OUT: schema、抽出器、CLI、Compiler、Repair emitter

**設計判断**:
- 評価順: lock 違反 → hard 違反 → unknown (§8.2)
- unknown は default `repair` (Q1)
- exit code: pass=0 / repair=2 / fail=1 (§8.3) — exit code 自体は CLI 層で扱う、Verdict には result enum のみ
- error code 体系 (Q4) — P1 minimum 8 コードセット:

| Code | 意味 |
|---|---|
| `API_SURFACE_ADDED_IN_REFACTOR` | refactor 宣言で公開 API 追加 |
| `API_SURFACE_REMOVED_IN_FEATURE` | feature 宣言で公開 API 削除 |
| `API_SURFACE_REMOVED_IN_BUGFIX` | bugfix 宣言で公開 API 削除 |
| `API_SURFACE_CHANGED_IN_REFACTOR` | refactor 宣言でシグネチャ変更 |
| `NEW_EFFECT_IN_REFACTOR` | refactor 宣言で副作用追加 |
| `NEW_EFFECT_IN_BUGFIX` | bugfix 宣言で副作用追加 |
| `PRODUCTION_CODE_TOUCHED_IN_TEST_UPDATE` | test_update 宣言で production code 変更 |
| `CONSTRAINT_VIOLATION` | ユーザー定義 constraint 違反 (汎用、id を suffix に付与) |

- 命名規則: `<DIMENSION>_<ACTION>_IN_<CONTEXT>` を docstring に逐語固定。後続 Brief で拡張可能。
- evidence chain: extractor 名 / file / line を delta から転記 (§10 hash trail)

**Required tests** (最小):
- 各 error code を最低 1 ケースずつ生成
- 違反なしで `pass`
- hard 違反 + soft 違反混在で `fail` (P1 では soft 制約はそもそもないので実質 hard のみ)
- unknown フィールド (delta が None) で `repair`
- 各 violation に code が必ず付与される
- 各 violation に evidence (extractor / file / line) が付与される
- subprocess 跨ぎ determinism
- 5 個の operator がすべて正しく評価される

**Branch / PR**: `codex/csci-13-constraint-evaluator` / `feat(evaluator): add constraint evaluator (CSCI-13)`

### CSCI-14: Repair SVP Emitter

**Goal**: `Verdict` から構造化された `RepairSVP` を生成。

**Public API**:
```python
def emit_repair_svp(verdict: Verdict) -> RepairSVP: ...

@dataclass(frozen=True)
class RepairSVP:
    verdict: VerdictResult
    violations: tuple[RepairViolation, ...]

@dataclass(frozen=True)
class RepairViolation:
    code: str
    constraint_id: str
    target: str
    actual: object
    evidence: Evidence
```

**Scope**:
- IN: `src/semantic_ci_code/repair/` (新設)、テスト + フィクスチャ
- OUT: schema、抽出器、CLI、Compiler、Evaluator

**設計判断**:
- 修正候補は **生成しない** (§9.3 Repair Compiler の責務、P2.5)
- code + evidence + actual の構造化記録のみ
- `verdict.result == pass` の時は空の violations を返す
- コードを直接変更しない (§9.2)
- YAML / JSON dump 対応 (Pydantic `model_dump_json()`)

**Required tests** (最小):
- pass verdict で空 violations
- fail verdict で violations が完全に転記される
- repair verdict で violations が転記される
- 各 violation の code / evidence が保持される
- subprocess 跨ぎ determinism
- `model_dump_json()` byte-identical
- YAML serialization も含めた round-trip

**Branch / PR**: `codex/csci-14-repair-emitter` / `feat(repair): add Repair SVP emitter (CSCI-14)`

## 工程サマリー

| PR | LOC 想定 | 動作確認可能なもの |
|---|---|---|
| CSCI-10 | 200-400 | `CodeState` が package_root から取れる |
| CSCI-11 | 150-300 | 2 つの State から `CodeStateDelta` が出る |
| CSCI-12 | 200-400 | `target.yaml` が `Constraint` リストに変換される |
| CSCI-13 | 250-450 | delta + constraints から `Verdict` が出る (E2E 動作の最小) |
| CSCI-14 | 150-300 | `Verdict` から `RepairSVP` が出る (Brief 3 完成) |

合計 LOC 想定: 950-1850。Brief 2 の +3,440 LOC より少ない (各 PR が薄いため)。

## Engine API 契約 (重要、CSCI-10〜14 全体で守る)

§23 (Comparator Architecture) の通り、engine 本体は **「実コードがそこに在ること」を前提にしない汎用 2-state 比較器** として実装する。

### 入力 contract

```python
def evaluate(
    baseline: CodeState,      # frozen Pydantic, 抽出 / 仮想 / mock 何でも可
    candidate: CodeState,     # 同上
    intent: CompiledTarget,   # CSCI-12 が compile した内部表現
) -> Verdict: ...
```

CSCI-10 (orchestrator) は実コードから CodeState を抽出する **1 つの経路**を提供するが、engine 本体 (CSCI-13 evaluator) は CodeState を直接受け取る形で実装する。これにより:

- pre-generation validation (§21.2): AI が予測した CodeState を直接 evaluate に渡せる
- what-if simulation: 仮想 CodeState を作って evaluate に渡せる
- contract testing: expected CodeState と actual CodeState を比較できる
- mock テスト: CSCI-13 自体のテストで仮想 CodeState を使える

### CSCI-10〜14 への具体的な影響

- **CSCI-10**: orchestrator は「実コードから CodeState を作る」関数。evaluator から見ると **CodeState の供給元の 1 つ**でしかない。orchestrator なしでも evaluator は動かせる構造を保つ。
- **CSCI-11**: delta computer は CodeState 2 個を受けて delta を返す純粋関数。CodeState の出所を問わない。
- **CSCI-13**: evaluator は (baseline, candidate, compiled_target) を受け取る。CodeState の出所への依存をテストで防ぐ — fixture で仮想 CodeState を組んだテストを最低 1 件含めること。
- **CSCI-14**: repair emitter は Verdict を構造化するだけ。CodeState には触らない。

### 実装上のガードレール

CSCI-13 のテストに以下を含める:

```python
def test_evaluator_works_with_virtual_code_state():
    """Engine は実コード抽出経由でなくても動く（仮想 state でも valid な verdict を返す）"""
    baseline = CodeState(...)   # 手で組んだ仮想 state
    candidate = CodeState(...)  # 手で組んだ仮想 state
    compiled = compile_target_svp("intent: ...\nchange:\n  primary_kind: refactor\n")
    verdict = evaluate_constraints(compiled, ..., baseline=baseline, candidate=candidate)
    assert verdict.result in {VerdictResult.PASS, VerdictResult.REPAIR, VerdictResult.FAIL}
```

これにより engine が「extractor 経由の CodeState 」にだけ動く状態に退化することを防ぐ。

## Brief 4 (CLI) への申し送り

§23.4 で確定した CLI 設計方針:

**Brief 4 は「PR 専用 CLI」ではなく「2 リビジョン汎用比較器」として設計する。**

### 受け付ける呼び出しパターン (Brief 4 で実装)

```bash
# A. 暗黙の PR モード（最頻ユースケース）
semantic-ci-code check
# → main と現ブランチを自動検出して比較

# B. 任意 2 リビジョン
semantic-ci-code check --baseline=v1.0.0 --candidate=v1.1.0

# C. 単発観測（intent なし、observation only mode）
semantic-ci-code observe --target=HEAD
# → CodeState を JSON dump、判定なし

# D. 任意 snapshot ディレクトリ
semantic-ci-code check --baseline-dir=./snap_a --candidate-dir=./snap_b

# E. pre-commit モード
semantic-ci-code check --baseline=HEAD --candidate=staged
```

### Brief 4 の責務分離

- **git 操作の一切は Brief 4 の責任** — Brief 3 の engine は git を知らない
- **`.semantic-ci/intent.yaml` の発見ロジックも Brief 4** — engine は file path or string を受け取るだけ
- **JSON / YAML 出力の整形も Brief 4** — engine は Pydantic model を返すだけ
- **exit code への変換も Brief 4** — engine は VerdictResult enum を返すだけ

Brief 3 で engine を作る時、CLI への結合を作りこまない。これが Brief 4 で「2 リビジョン汎用比較器」を綺麗に実装する前提。

## 残課題 (Brief 3 範囲外、後続 Brief で扱う)

- **Partial extraction tolerance** (§6.2) — 一部 extractor が落ちても他の verdict を維持する仕組み
- **soft / info constraint** — Q1 で hard のみとしたが、§19 meta-verdict と一緒に解禁検討
- **`tolerance` / `scope` / `unknown_policy` override** — Q3 で拒否したが、§19 と一緒に解禁検討
- **Repair Compiler** (§9.3, §21.4, P2.5) — Repair SVP を generator-specific prompt に変換
- **Performance budget** (§18) — baseline RPE cache、incremental extraction、per-extractor timeout、並列抽出
- **Spec quality metrics** (§19) — spec_coverage、meta-verdict
- **Spec authorship anchoring** (§17) — `target.yaml` の `authorship` フィールド受け付け
- **Lock violation の即 fail** (§8.2) — 「変更してはいけない」と明示宣言された箇所への変更検出
- **Hash trail** (§10) — extractor_versions、config_hash、schema_version の組み込み
- **Round-trip log** (§10.3) — 評価過程の audit trail
- **Brief 4 (CLI + JSON report)** — git 操作、`.semantic-ci/intent.yaml` の発見、verdict の post

## 次のアクション

1. CSCI-10 の Task Brief を AGENTS.md フォーマットで発行
2. Codex 実装 → PR
3. Claude レビュー → merge
4. CSCI-11 へ進む

---

**この planning 文書は Brief 3 完了 (CSCI-14 merge) で役割を終える。完了後は archive 候補。**
